"""Network discovery and new device detection feature."""

from __future__ import annotations

import logging
from typing import List

from home_notifications.discovery import DiscoveredHost, NetworkScanner
from home_notifications.features.base import BaseFeature

logger = logging.getLogger(__name__)


class NetworkDiscoveryFeature(BaseFeature):
    """Scans local subnets, tracks ARP tables, and alerts when new devices connect."""

    def __init__(self, config, state, notifier):
        super().__init__("network_discovery", config, state, notifier)
        self.scanner = NetworkScanner(concurrency=40, ping_timeout=1.0)

    async def execute(self) -> List[DiscoveredHost]:
        if not self.is_enabled:
            return []

        # 1. Determine subnets
        subnets_raw = self.feature_config.get("subnets", "auto")
        if isinstance(subnets_raw, str) and subnets_raw.strip().lower() == "auto":
            subnets = self.scanner.auto_detect_subnets()
        elif isinstance(subnets_raw, list):
            subnets = [str(s).strip() for s in subnets_raw if str(s).strip()]
        else:
            subnets = [s.strip() for s in str(subnets_raw).split(",") if s.strip()]

        if not subnets:
            subnets = ["192.168.1.0/24"]

        logger.debug("Running network discovery scan on %s", subnets)
        discovered = await self.scanner.scan(subnets)

        # 2. Map configured devices by MAC and IP for correlation
        configured_by_mac = {}
        configured_by_ip = {}
        for dev in self.config.devices.values():
            if dev.mac:
                configured_by_mac[dev.mac.lower()] = dev
            if dev.ip:
                configured_by_ip[dev.ip] = dev

        alert_new = self.feature_config.get_bool("alert_new_device", True)
        new_count = 0

        # 3. Process each discovered host
        for host in discovered:
            mac_clean = host.mac.lower()
            matching_dev = configured_by_mac.get(mac_clean) or configured_by_ip.get(host.ip)

            is_configured = matching_dev is not None
            custom_name = matching_dev.name if matching_dev else ""

            _, is_new = self.state.register_or_update_device(
                mac=mac_clean,
                ip=host.ip,
                hostname=host.hostname,
                vendor=host.vendor,
                is_configured=is_configured,
                custom_name=custom_name,
            )

            if is_new:
                new_count += 1
                if alert_new:
                    vendor_display = host.vendor or "Unknown Manufacturer"
                    name_display = f" ({custom_name})" if custom_name else ""
                    host_display = f"\n<b>Hostname:</b> <code>{host.hostname}</code>" if host.hostname else ""
                    msg = (
                        f"A new device was detected on your network{name_display}:\n\n"
                        f"<b>IP:</b> <code>{host.ip}</code>\n"
                        f"<b>MAC:</b> <code>{mac_clean}</code>\n"
                        f"<b>Vendor:</b> {vendor_display}"
                        f"{host_display}"
                    )
                    await self.notifier.notify(
                        category=self.name,
                        title="New Network Device Discovered",
                        message=msg,
                        level="WARNING",
                    )

        # 4. Check for devices going offline
        alert_offline = self.feature_config.get_bool("alert_device_offline", False)
        threshold = float(self.feature_config.get_int("offline_threshold_seconds", 1800))
        newly_offline = self.state.mark_offline_devices(threshold)

        if alert_offline and newly_offline:
            for dev in newly_offline:
                dev_name = dev.get("custom_name") or dev.get("hostname") or dev.get("ip")
                msg = (
                    f"Device <b>{dev_name}</b> has gone offline.\n"
                    f"<b>IP:</b> <code>{dev.get('ip')}</code>\n"
                    f"<b>MAC:</b> <code>{dev.get('mac')}</code>"
                )
                await self.notifier.notify(
                    category=self.name,
                    title="Device Went Offline",
                    message=msg,
                    level="INFO",
                )

        await self.state.save()
        logger.info(
            "Discovery complete: %d active hosts, %d newly added",
            len(discovered),
            new_count,
        )
        return discovered
