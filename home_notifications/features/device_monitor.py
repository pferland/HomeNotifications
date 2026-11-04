"""Device and Services Monitoring Feature.

Monitors configured inventory devices for ping reachability, TCP/HTTP services,
SSH resources (CPU, RAM, Disks), systemd services, SNMP, and access logs.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Dict, List

from home_notifications.config import DeviceConfig
from home_notifications.features.base import BaseFeature
from home_notifications.monitors.ping import PingMonitor
from home_notifications.monitors.prometheus import PrometheusMonitor
from home_notifications.monitors.service import ServiceMonitor
from home_notifications.monitors.snmp import SNMPMonitor
from home_notifications.monitors.ssh import SSHMonitor

logger = logging.getLogger(__name__)


class DeviceMonitorFeature(BaseFeature):
    """Monitors configured devices, services, system resources, and access logs."""

    def __init__(self, config, state, notifier):
        super().__init__("device_monitor", config, state, notifier)

    async def check_single_device(self, dev: DeviceConfig) -> Dict[str, Any]:
        """Perform all configured checks on a single device concurrently."""
        summary: Dict[str, Any] = {
            "id": dev.id,
            "name": dev.name,
            "ip": dev.ip,
            "ping": None,
            "services": {},
            "ssh": None,
            "snmp": None,
            "prometheus": None,
            "is_up": True,
            "warnings": [],
            "errors": [],
        }

        # 1. Ping check
        if dev.ping_enabled:
            ping_res = await PingMonitor.check(dev.ip, timeout=dev.ping_timeout)
            summary["ping"] = ping_res
            if not ping_res.success:
                summary["is_up"] = False
                summary["errors"].append(f"Ping failed: {ping_res.message}")

        # 2. Services checks
        if dev.services:
            srv_tasks = [
                ServiceMonitor.check_service(dev.ip, srv) for srv in dev.services
            ]
            srv_results = await asyncio.gather(*srv_tasks, return_exceptions=True)
            for srv_cfg, res in zip(dev.services, srv_results):
                if isinstance(res, Exception):
                    summary["services"][srv_cfg.name] = {
                        "status": "ERROR",
                        "latency_ms": 0.0,
                        "message": str(res),
                    }
                    summary["errors"].append(f"Service {srv_cfg.name} check failed: {res}")
                else:
                    summary["services"][srv_cfg.name] = {
                        "status": res.status,
                        "latency_ms": res.latency_ms,
                        "message": res.message,
                    }
                    if not res.success:
                        summary["errors"].append(
                            f"Service '{srv_cfg.name}' is {res.status} ({res.message})"
                        )

        # 3. SSH Remote check (resources, systemd, access logs)
        if dev.ssh and dev.ssh.enabled:
            ssh_res = await SSHMonitor.check(dev.ip, dev.ssh)
            summary["ssh"] = ssh_res
            if ssh_res.success:
                summary["warnings"].extend(ssh_res.warnings)
            else:
                summary["warnings"].append(f"SSH check failed: {ssh_res.error}")

        # 4. SNMP check
        if dev.snmp and dev.snmp.enabled:
            snmp_res = await SNMPMonitor.check(dev.ip, dev.snmp)
            summary["snmp"] = snmp_res
            if not snmp_res.success:
                summary["warnings"].append(f"SNMP check failed: {snmp_res.message}")

        # 5. Prometheus check
        if dev.prometheus and dev.prometheus.enabled:
            prom_res = await PrometheusMonitor.check(dev.prometheus)
            summary["prometheus"] = prom_res
            if prom_res.status == "WARNING":
                summary["warnings"].append(f"Prometheus alert: {prom_res.message}")
            elif not prom_res.success:
                summary["warnings"].append(f"Prometheus failed: {prom_res.message}")

        return summary

    async def execute(self) -> List[Dict[str, Any]]:
        if not self.is_enabled:
            return []

        devices = list(self.config.devices.values())
        if not devices:
            logger.debug("No devices configured in devices.yaml")
            return []

        alert_on_down = self.feature_config.get_bool("alert_on_down", True)
        alert_on_recovery = self.feature_config.get_bool("alert_on_recovery", True)
        cooldown = float(self.feature_config.get_int("cooldown_seconds", 3600))

        # Check all devices concurrently
        tasks = [self.check_single_device(dev) for dev in devices]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        now = time.time()

        for dev, res in zip(devices, results):
            if isinstance(res, Exception):
                logger.error("Error monitoring device %s: %s", dev.id, res)
                continue

            state = self.state.get_monitored_device_state(dev.id)
            prev_status = state.get("status", "UNKNOWN")
            curr_status = "UP" if res["is_up"] else "DOWN"

            state["last_check"] = now
            state["services"] = res["services"]

            if res.get("ssh") and res["ssh"].success:
                ssh = res["ssh"]
                state["resources"] = {
                    "cpu_load_1m": ssh.cpu_load_1m,
                    "memory_percent": ssh.memory_percent,
                    "memory_used_mb": ssh.memory_used_mb,
                    "memory_total_mb": ssh.memory_total_mb,
                    "disk_usage": ssh.disk_usage,
                    "top_cpu_processes": ssh.top_cpu_processes,
                    "top_mem_processes": ssh.top_mem_processes,
                }
                state["systemd"] = ssh.systemd_status

            # Handle State Transitions
            if curr_status == "DOWN" and prev_status != "DOWN":
                # Newly down
                state["status"] = "DOWN"
                state["last_change"] = now
                if alert_on_down and self.state.should_alert(f"device_down:{dev.id}", cooldown):
                    err_msg = "\n".join(f"• {e}" for e in res["errors"]) or "Device stopped responding."
                    msg = (
                        f"<b>Device:</b> {dev.name} (<code>{dev.ip}</code>)\n"
                        f"<b>Status:</b> 🚨 DOWN\n\n"
                        f"{err_msg}"
                    )
                    await self.notifier.notify(
                        category=self.name,
                        title=f"Device Down: {dev.name}",
                        message=msg,
                        level="ERROR",
                    )
            elif curr_status == "UP" and prev_status == "DOWN":
                # Recovered
                state["status"] = "UP"
                state["last_change"] = now
                self.state.clear_alert_cooldown(f"device_down:{dev.id}")
                if alert_on_recovery:
                    ping_info = f" ({res['ping'].latency_ms:.1f} ms)" if res.get("ping") else ""
                    msg = (
                        f"<b>Device:</b> {dev.name} (<code>{dev.ip}</code>)\n"
                        f"<b>Status:</b> ✅ RECOVERED{ping_info}\n"
                        f"All checks passing."
                    )
                    await self.notifier.notify(
                        category=self.name,
                        title=f"Device Recovered: {dev.name}",
                        message=msg,
                        level="SUCCESS",
                    )
            else:
                state["status"] = curr_status

            # Handle Resource & Service Warnings if device is UP
            if curr_status == "UP" and res["warnings"]:
                if self.state.should_alert(f"warnings:{dev.id}", cooldown):
                    warn_body = "\n".join(f"• {w}" for w in res["warnings"])
                    msg = (
                        f"<b>Device:</b> {dev.name} (<code>{dev.ip}</code>)\n\n"
                        f"{warn_body}"
                    )
                    await self.notifier.notify(
                        category=self.name,
                        title=f"Resource Alert: {dev.name}",
                        message=msg,
                        level="WARNING",
                    )

            # Handle Access Log Security Alerts
            if res.get("ssh") and res["ssh"].success:
                failed_logins = res["ssh"].failed_logins
                if failed_logins and self.state.should_alert(f"access_logs:{dev.id}", cooldown):
                    log_sample = "\n".join(failed_logins[-5:])
                    msg = (
                        f"<b>Device:</b> {dev.name} (<code>{dev.ip}</code>)\n"
                        f"<b>Total Failed Logins:</b> {len(failed_logins)}\n\n"
                        f"<pre>{log_sample}</pre>"
                    )
                    await self.notifier.notify(
                        category="access_logs",
                        title=f"Security Alert: Failed Logins on {dev.name}",
                        message=msg,
                        level="WARNING",
                    )

        await self.state.save()
        return [r for r in results if isinstance(r, dict)]
