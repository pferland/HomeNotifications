"""Wi-Fi and Network Presence Monitoring Feature.

Tracks household members and residents based on their smartphones, watches,
or personal laptops connecting to or disconnecting from the home network.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Tuple

from home_notifications.features.base import BaseFeature

logger = logging.getLogger(__name__)


class PresenceFeature(BaseFeature):
    """Monitors Wi-Fi presence of residents and alerts on arrival or departure."""

    def __init__(self, config, state, notifier):
        super().__init__("presence", config, state, notifier)

    def parse_members(self) -> List[Tuple[str, str]]:
        """Parse members string (format: 'Name:MAC,Name2:IP') or fallback to configured tagged devices."""
        raw = self.feature_config.get("members", "")
        members: List[Tuple[str, str]] = []

        if isinstance(raw, str) and raw.strip():
            for part in raw.split(","):
                part = part.strip()
                if not part:
                    continue
                if ":" in part:
                    # Support Name:MAC or Name:IP
                    tokens = part.split(":", 1)
                    name = tokens[0].strip()
                    ident = tokens[1].strip().lower()
                    members.append((name, ident))

        # If no explicit members string, check for devices tagged 'resident' or 'phone' in devices.yaml
        if not members and self.config.devices:
            for dev in self.config.devices.values():
                if any(t in ("resident", "phone", "person") for t in dev.tags):
                    ident = (dev.mac or dev.ip).lower().strip()
                    members.append((dev.name, ident))

        return members

    async def execute(self) -> Dict[str, Any]:
        if not self.is_enabled:
            return {"enabled": False, "residents": {}}

        alert_arrival = self.feature_config.get_bool("alert_arrival", True)
        alert_departure = self.feature_config.get_bool("alert_departure", True)
        away_threshold = self.feature_config.get_int("away_threshold_seconds", 900)

        members = self.parse_members()
        known = self.state.get_known_devices()
        presence_state = self.state.get_presence_state()
        now = time.time()

        summary: Dict[str, Any] = {}

        for name, ident in members:
            # Match by MAC or by IP
            matched_dev = None
            for mac, dev in known.items():
                if mac.lower() == ident.lower() or dev.get("ip") == ident:
                    matched_dev = dev
                    break

            is_online = False
            last_seen = 0.0

            if matched_dev:
                last_seen = float(matched_dev.get("last_seen", 0.0))
                time_since_seen = now - last_seen
                is_online = bool(matched_dev.get("online", True)) and (time_since_seen <= away_threshold)
            else:
                last_seen = 0.0

            curr_status = "HOME" if is_online else "AWAY"
            prev_record = presence_state.get(name, {})
            prev_status = prev_record.get("status", "UNKNOWN")

            # Check Transitions
            if prev_status == "AWAY" and curr_status == "HOME":
                if alert_arrival:
                    await self.notifier.notify(
                        category=self.name,
                        title=f"Welcome Home: {name}",
                        message=f"👋 <b>{name}</b> arrived home (device reconnected to LAN).",
                        level="PRESENCE",
                        force_immediate=True,
                    )
                prev_record["last_transition"] = now
            elif prev_status == "HOME" and curr_status == "AWAY":
                if alert_departure:
                    mins = int(away_threshold / 60)
                    await self.notifier.notify(
                        category=self.name,
                        title=f"Left Home: {name}",
                        message=f"🚗 <b>{name}</b> left home (unseen on Wi-Fi for >{mins}m).",
                        level="INFO",
                        force_immediate=True,
                    )
                prev_record["last_transition"] = now
            elif prev_status == "UNKNOWN":
                prev_record["last_transition"] = now

            prev_record["name"] = name
            prev_record["identifier"] = ident
            prev_record["status"] = curr_status
            prev_record["last_seen"] = last_seen
            presence_state[name] = prev_record

            summary[name] = {
                "status": curr_status,
                "last_seen": last_seen,
                "last_transition": prev_record.get("last_transition", now),
            }

        await self.state.save()
        return summary
