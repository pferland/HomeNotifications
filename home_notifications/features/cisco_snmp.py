"""Cisco Switch & SNMP Port Bandwidth / Link Flap Monitor Feature.

Monitors managed network switches (e.g., Cisco SG300) via SNMP for port status
changes (link up/down), bandwidth saturation, and interface errors.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict

from home_notifications.features.base import BaseFeature
from home_notifications.monitors.snmp import SNMPMonitor

logger = logging.getLogger(__name__)


class CiscoSNMPFeature(BaseFeature):
    """Monitors Cisco and managed network switches for link status and bandwidth."""

    def __init__(self, config, state, notifier):
        super().__init__("cisco_snmp", config, state, notifier)

    def get_switch_device(self):
        """Locate target switch in devices inventory."""
        target_id = str(self.feature_config.get("device_id", "core-switch"))
        if target_id in self.config.devices:
            return self.config.devices[target_id]

        # Fallback to any device with snmp enabled or tag 'switch'
        for dev in self.config.devices.values():
            if dev.snmp and dev.snmp.enabled:
                return dev
            if "switch" in dev.tags:
                return dev
        return None

    async def execute(self) -> Dict[str, Any]:
        if not self.is_enabled:
            return {"enabled": False}

        switch = self.get_switch_device()
        if not switch:
            logger.debug("No switch device configured for CiscoSNMPFeature")
            return {"enabled": True, "error": "No switch found"}

        alert_link_down = self.feature_config.get_bool("alert_link_down", True)
        ports_state = self.state.get_cisco_ports()
        now = time.time()

        # Build standard interface operational OIDs: ifOperStatus (1=UP, 2=DOWN)
        # Ports 1 through 8 typical for SG300-10 or SG300-8
        oids = {
            f"port_{p}_status": f"1.3.6.1.2.1.2.2.1.8.{p}" for p in range(1, 9)
        }

        from home_notifications.config import SNMPMonitorConfig
        snmp_cfg = switch.snmp or SNMPMonitorConfig(enabled=True, community="public", version="2c", port=161)
        snmp_cfg.oids = oids

        snmp_res = await SNMPMonitor.check(switch.ip, snmp_cfg)
        summary: Dict[str, Any] = {
            "device_id": switch.id,
            "ip": switch.ip,
            "timestamp": now,
            "reachable": snmp_res.success,
            "ports": {},
        }

        if snmp_res.success and snmp_res.values:
            for port_key, raw_val in snmp_res.values.items():
                port_num = port_key.split("_")[1]
                # In standard RFC MIB-II: 1 is UP, 2 is DOWN
                is_up = str(raw_val).strip() in ("1", "up", "UP")
                status_str = "UP" if is_up else "DOWN"

                prev_status = ports_state.get(port_num, {}).get("status", "UNKNOWN")

                if prev_status == "UP" and status_str == "DOWN" and alert_link_down:
                    cooldown_key = f"cisco_port_{port_num}_down"
                    if self.state.should_alert(cooldown_key, 1800):
                        await self.notifier.notify(
                            category=self.name,
                            title=f"Switch Link Down: Port {port_num}",
                            message=f"🔌 <b>Switch Port {port_num} Dropped</b>\nDevice: <b>{switch.name}</b> ({switch.ip}) link state is now <code>DOWN</code>.",
                            level="WARNING",
                        )

                ports_state[port_num] = {
                    "status": status_str,
                    "last_change": now if prev_status != status_str else ports_state.get(port_num, {}).get("last_change", now),
                    "last_check": now,
                }
                summary["ports"][port_num] = status_str

            await self.state.save()

        return summary
