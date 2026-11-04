"""Network Discovery and ARP Monitoring for HomeNotifications.

Performs asynchronous subnet sweeps without requiring root privileges,
reads the OS ARP cache, resolves hostnames and MAC vendors, and detects
newly connected devices on the home network.
"""

from __future__ import annotations

import asyncio
import ipaddress
import logging
import re
import socket
import subprocess
import time
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Common MAC OUI prefixes mapped to manufacturer names
OUI_DATABASE: Dict[str, str] = {
    "b8:27:eb": "Raspberry Pi Foundation",
    "dc:a6:32": "Raspberry Pi Foundation",
    "e4:5f:01": "Raspberry Pi Foundation",
    "28:cd:c1": "Raspberry Pi Foundation",
    "d8:3a:dd": "Raspberry Pi Foundation",
    "24:0a:c4": "Espressif Systems (ESP32/8266)",
    "24:6f:28": "Espressif Systems (ESP32/8266)",
    "30:ae:a4": "Espressif Systems (ESP32/8266)",
    "84:0d:8e": "Espressif Systems (ESP32/8266)",
    "b4:e6:2d": "Espressif Systems (ESP32/8266)",
    "3c:71:bf": "Espressif Systems (ESP32/8266)",
    "dc:4f:22": "Apple, Inc.",
    "3c:78:95": "Apple, Inc.",
    "b0:7f:b9": "Apple, Inc.",
    "bc:df:58": "Apple, Inc.",
    "f0:18:98": "Apple, Inc.",
    "a4:83:e7": "Apple, Inc.",
    "7c:04:d0": "Apple, Inc.",
    "00:03:93": "Apple, Inc.",
    "38:86:f7": "Intel Corporate",
    "6c:15:db": "Intel Corporate",
    "00:87:31": "Intel Corporate",
    "00:1b:21": "Intel Corporate",
    "68:05:ca": "Intel Corporate",
    "cc:ba:bd": "Netgear",
    "20:e5:2a": "Netgear",
    "00:1f:33": "Netgear",
    "50:c7:bf": "TP-Link",
    "14:cc:20": "TP-Link",
    "54:af:97": "TP-Link",
    "70:4f:57": "TP-Link",
    "00:27:22": "Ubiquiti Networks",
    "24:a4:3c": "Ubiquiti Networks",
    "78:45:58": "Ubiquiti Networks",
    "b4:fb:e4": "Ubiquiti Networks",
    "d8:b3:70": "Ubiquiti Networks",
    "00:14:22": "Dell Inc.",
    "18:66:da": "Dell Inc.",
    "00:07:ab": "Samsung Electronics",
    "00:12:47": "Samsung Electronics",
    "f4:f5:d8": "Google LLC",
    "00:1a:11": "Google LLC",
    "74:75:48": "Amazon Technologies",
    "fc:65:de": "Amazon Technologies",
    "00:0e:58": "Sonos, Inc.",
    "5c:aa:fd": "Sonos, Inc.",
    "94:9f:3e": "Sonos, Inc.",
}


@dataclass
class DiscoveredHost:
    ip: str
    mac: str
    hostname: str = ""
    vendor: str = ""
    interface: str = ""
    is_known: bool = False
    custom_name: str = ""


class NetworkScanner:
    """Non-root asynchronous network discovery scanner."""

    def __init__(self, concurrency: int = 50, ping_timeout: float = 1.0):
        self.concurrency = concurrency
        self.ping_timeout = ping_timeout

    @staticmethod
    def lookup_vendor(mac: str) -> str:
        """Find vendor for a given MAC address using OUI database."""
        mac_clean = mac.lower().replace("-", ":")
        prefix = ":".join(mac_clean.split(":")[:3])
        return OUI_DATABASE.get(prefix, "")

    @staticmethod
    def auto_detect_subnets() -> List[str]:
        """Automatically detect active non-loopback local subnets from routing table."""
        subnets: List[str] = []
        try:
            proc = subprocess.run(
                ["ip", "route", "show"],
                capture_output=True,
                text=True,
                timeout=3.0,
            )
            for line in proc.stdout.splitlines():
                parts = line.strip().split()
                if len(parts) >= 3 and parts[0] != "default" and "/" in parts[0]:
                    try:
                        net = ipaddress.ip_network(parts[0], strict=False)
                        if not net.is_loopback and not net.is_link_local:
                            subnets.append(str(net))
                    except ValueError:
                        pass
        except Exception as e:
            logger.debug("Failed to detect subnets via ip route: %s", e)

        # Fallback to 192.168.1.0/24 if nothing detected
        if not subnets:
            subnets = ["192.168.1.0/24"]
        return subnets

    async def _ping_host(self, ip_str: str, sem: asyncio.Semaphore) -> bool:
        """Ping a single IP to warm up ARP table."""
        async with sem:
            try:
                proc = await asyncio.create_subprocess_exec(
                    "ping",
                    "-c",
                    "1",
                    "-W",
                    str(int(self.ping_timeout)),
                    ip_str,
                    stdout=asyncio.subprocess.DEVNULL,
                    stderr=asyncio.subprocess.DEVNULL,
                )
                rc = await proc.wait()
                return rc == 0
            except Exception:
                return False

    async def ping_sweep(self, subnets: List[str]) -> None:
        """Run parallel ping sweeps across subnets to populate ARP table."""
        sem = asyncio.Semaphore(self.concurrency)
        tasks = []

        for subnet_str in subnets:
            try:
                net = ipaddress.ip_network(subnet_str, strict=False)
                # Cap /24 or smaller to avoid scanning huge ranges
                if net.num_addresses > 512:
                    logger.warning("Subnet %s is too large (%d hosts), skipping", subnet_str, net.num_addresses)
                    continue
                for host in net.hosts():
                    tasks.append(self._ping_host(str(host), sem))
            except Exception as e:
                logger.error("Invalid subnet string %s: %s", subnet_str, e)

        if tasks:
            logger.debug("Pinging %d addresses to warm up ARP table...", len(tasks))
            await asyncio.gather(*tasks, return_exceptions=True)

    def read_arp_table(self) -> Dict[str, Dict[str, str]]:
        """Read /proc/net/arp and ip neigh to get IP -> MAC map."""
        hosts: Dict[str, Dict[str, str]] = {}

        # 1. Read /proc/net/arp
        try:
            with open("/proc/net/arp", "r", encoding="utf-8") as f:
                lines = f.readlines()[1:]  # skip header
                for line in lines:
                    parts = line.split()
                    if len(parts) >= 6:
                        ip, hw_type, flags, mac, mask, dev = parts[:6]
                        mac = mac.lower().strip()
                        if mac and mac != "00:00:00:00:00:00" and flags != "0x0":
                            hosts[ip] = {"ip": ip, "mac": mac, "interface": dev}
        except Exception as e:
            logger.debug("Failed to read /proc/net/arp: %s", e)

        # 2. Augment with `ip neigh show`
        try:
            proc = subprocess.run(
                ["ip", "neigh", "show"],
                capture_output=True,
                text=True,
                timeout=3.0,
            )
            for line in proc.stdout.splitlines():
                parts = line.strip().split()
                # format: <ip> dev <dev> lladdr <mac> <STATE>
                if "lladdr" in parts:
                    idx = parts.index("lladdr")
                    if idx + 1 < len(parts):
                        ip = parts[0]
                        mac = parts[idx + 1].lower().strip()
                        state = parts[-1] if len(parts) > idx + 2 else "UNKNOWN"
                        if mac and mac != "00:00:00:00:00:00" and state != "FAILED":
                            dev = parts[2] if len(parts) > 2 else ""
                            hosts[ip] = {"ip": ip, "mac": mac, "interface": dev}
        except Exception as e:
            logger.debug("Failed to run ip neigh: %s", e)

        return hosts

    async def _resolve_hostname(self, ip: str) -> str:
        """Resolve PTR hostname in executor without blocking."""
        loop = asyncio.get_running_loop()
        try:
            host_info = await loop.run_in_executor(None, socket.gethostbyaddr, ip)
            return host_info[0]
        except Exception:
            return ""

    async def scan(
        self, subnets: Optional[List[str]] = None
    ) -> List[DiscoveredHost]:
        """Perform a complete discovery scan: ping sweep, ARP parse, and hostname/vendor resolution."""
        if not subnets:
            subnets = self.auto_detect_subnets()

        # Sweep subnets
        await self.ping_sweep(subnets)

        # Allow slight delay for kernel to record ARP responses
        await asyncio.sleep(0.5)

        arp_entries = self.read_arp_table()
        discovered: List[DiscoveredHost] = []

        # Resolve hostnames concurrently
        resolve_tasks = []
        ip_list = list(arp_entries.keys())
        for ip in ip_list:
            resolve_tasks.append(self._resolve_hostname(ip))

        hostnames = await asyncio.gather(*resolve_tasks, return_exceptions=True)

        for ip, hostname_res in zip(ip_list, hostnames):
            entry = arp_entries[ip]
            mac = entry["mac"]
            hostname = hostname_res if isinstance(hostname_res, str) else ""
            vendor = self.lookup_vendor(mac)
            discovered.append(
                DiscoveredHost(
                    ip=ip,
                    mac=mac,
                    hostname=hostname,
                    vendor=vendor,
                    interface=entry.get("interface", ""),
                )
            )

        return discovered
