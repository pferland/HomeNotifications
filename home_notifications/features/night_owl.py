"""Night Owl / Late-Night Network Activity Monitor Feature.

Detects active streaming, gaming, or mobile network usage during scheduled
sleep hours (e.g. 1:00 AM - 5:30 AM) on selected devices.
"""

from __future__ import annotations

from datetime import datetime
import logging
import time
from typing import Any, Dict, List

from home_notifications.features.base import BaseFeature

logger = logging.getLogger(__name__)


class NightOwlFeature(BaseFeature):
    """Monitors entertainment and kids devices during quiet hours."""

    def __init__(self, config, state, notifier):
        super().__init__("night_owl", config, state, notifier)

    @staticmethod
    def is_in_quiet_hours(start_str: str, end_str: str) -> bool:
        """Check if current local time falls between HH:MM start and end."""
        now = datetime.now()
        curr_time = now.strftime("%H:%M")

        try:
            if start_str <= end_str:
                return start_str <= curr_time <= end_str
            else:
                # Overnight window (e.g., 01:00 to 05:30 or 23:00 to 06:00)
                return curr_time >= start_str or curr_time <= end_str
        except Exception:
            return False

    def get_target_devices(self) -> List[Dict[str, Any]]:
        """Identify devices tagged with monitored tags or matching monitored_macs."""
        raw_tags = str(self.feature_config.get("monitored_tags", "kids,console,entertainment")).lower()
        tags = [t.strip() for t in raw_tags.split(",") if t.strip()]

        raw_macs = str(self.feature_config.get("monitored_macs", "")).lower()
        macs = [m.strip() for m in raw_macs.split(",") if m.strip()]

        targets: List[Dict[str, Any]] = []

        # 1. From devices inventory
        for dev in self.config.devices.values():
            has_tag = any(t in dev.tags for t in tags)
            has_mac = dev.mac and dev.mac.lower() in macs
            if has_tag or has_mac:
                targets.append({
                    "id": dev.id,
                    "name": dev.name,
                    "ip": dev.ip,
                    "mac": (dev.mac or "").lower(),
                })

        # 2. From ARP discovery cache matching MACs
        known = self.state.get_known_devices()
        for mac, h in known.items():
            if mac in macs and not any(t["mac"] == mac for t in targets):
                targets.append({
                    "id": mac,
                    "name": h.get("custom_name") or h.get("hostname") or h.get("vendor") or mac,
                    "ip": h.get("ip", ""),
                    "mac": mac,
                })

        return targets

    async def execute(self) -> Dict[str, Any]:
        if not self.is_enabled:
            return {"enabled": False}

        quiet_start = str(self.feature_config.get("quiet_start", "01:00"))
        quiet_end = str(self.feature_config.get("quiet_end", "05:30"))
        alert_active = self.feature_config.get_bool("alert_active", True)
        cooldown = float(self.feature_config.get_int("cooldown_minutes", 60) * 60)

        in_quiet = self.is_in_quiet_hours(quiet_start, quiet_end)
        targets = self.get_target_devices()

        known = self.state.get_known_devices()
        now = time.time()
        active_devices: List[str] = []

        if in_quiet and targets:
            for tgt in targets:
                mac = tgt.get("mac")
                ip = tgt.get("ip")
                host_info = None

                if mac and mac in known:
                    host_info = known[mac]
                else:
                    for h in known.values():
                        if h.get("ip") == ip:
                            host_info = h
                            break

                if host_info and host_info.get("online", False):
                    # Check if seen within the last 10 minutes
                    if now - host_info.get("last_seen", 0) <= 600:
                        active_devices.append(f"{tgt['name']} ({tgt['ip']})")

            if active_devices and alert_active:
                if self.state.should_alert("night_owl_activity", cooldown):
                    curr_time_str = datetime.now().strftime("%I:%M %p")
                    dev_list_str = "\n• ".join(active_devices)
                    await self.notifier.notify(
                        category=self.name,
                        title="Late-Night Activity Detected",
                        message=f"🌙 <b>Late-Night Network Usage Alert</b>\n\nActive during quiet hours ({quiet_start} - {quiet_end}) at <b>{curr_time_str}</b>:\n• {dev_list_str}",
                        level="WARNING",
                        force_immediate=True,
                    )

        owl_state = self.state.get_night_owl_state()
        owl_state["in_quiet_hours"] = in_quiet
        owl_state["active_devices"] = active_devices
        owl_state["last_check"] = now
        await self.state.save()

        return {
            "in_quiet_hours": in_quiet,
            "active_count": len(active_devices),
            "active_devices": active_devices,
        }
