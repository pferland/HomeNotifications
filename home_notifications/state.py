"""Persistent State Manager for HomeNotifications.

Maintains known devices, previous check results, notification cooldowns,
and queued batch notifications across bot restarts.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import tempfile
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class QueuedNotification:
    category: str  # e.g., "network_discovery", "device_monitor", "ip", "flag"
    title: str
    message: str
    timestamp: float = field(default_factory=time.time)
    level: str = "INFO"  # INFO, WARNING, ERROR, SUCCESS

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> QueuedNotification:
        return cls(
            category=data.get("category", "general"),
            title=data.get("title", ""),
            message=data.get("message", ""),
            timestamp=float(data.get("timestamp", time.time())),
            level=data.get("level", "INFO"),
        )


class StateManager:
    """Manages persistent JSON state safely with atomic writes."""

    def __init__(self, state_path: Path):
        self.state_path = state_path
        self._lock = asyncio.Lock()
        self.data: Dict[str, Any] = {
            "known_devices": {},  # mac -> {mac, ip, hostname, vendor, first_seen, last_seen, online}
            "monitored_devices": {},  # device_id -> {status, last_check, last_change, last_alert, ...}
            "external_ip": {"last_ip": None, "last_check": 0, "last_change": 0},
            "flag_status": {"last_status": None, "last_check": 0, "last_change": 0},
            "queued_notifications": [],
            "last_batch_flush": {},  # category -> timestamp
            "access_log_cursors": {},  # device_id -> cursor/offset
            "telegram_paused_until": 0.0,
            "presence": {},  # resident_id -> {name, mac, status, last_seen, last_transition}
            "ssl_certs": {},  # target -> {issuer, subject, not_after, days_left, status}
            "webhook_logs": [],  # recent incoming webhooks
            "speedtest_history": [],  # recent latency & speed results
            "cisco_ports": {},  # port -> {status, speed_mbps, in_octets, out_octets, ...}
            "ups_status": {"status": "ONLINE", "battery_percent": 100, "runtime_mins": 60, "last_check": 0},
            "night_owl": {"last_alert": 0, "active_devices": []},
        }
        self.load()

    def load(self) -> None:
        """Load state from disk if exists."""
        if not self.state_path.exists():
            logger.info("No state file at %s, starting fresh", self.state_path)
            return

        try:
            with open(self.state_path, "r", encoding="utf-8") as f:
                saved = json.load(f)
                if isinstance(saved, dict):
                    self.data.update(saved)
                    logger.debug("Loaded state with %d known devices", len(self.data.get("known_devices", {})))
        except Exception as e:
            logger.error("Failed to load state file %s: %s", self.state_path, e)

    async def save(self) -> None:
        """Persist current state atomically to disk."""
        async with self._lock:
            await asyncio.to_thread(self._sync_save)

    def _sync_save(self) -> None:
        try:
            self.state_path.parent.mkdir(parents=True, exist_ok=True)
            temp_file = tempfile.NamedTemporaryFile(
                "w", dir=self.state_path.parent, delete=False, encoding="utf-8"
            )
            json.dump(self.data, temp_file, indent=2)
            temp_file.flush()
            os.fsync(temp_file.fileno())
            temp_file.close()
            os.replace(temp_file.name, self.state_path)
        except Exception as e:
            logger.error("Failed to save state to %s: %s", self.state_path, e)

    # --- Known Devices Tracking ---

    def get_known_devices(self) -> Dict[str, Dict[str, Any]]:
        return self.data.setdefault("known_devices", {})

    def register_or_update_device(
        self,
        mac: str,
        ip: str,
        hostname: Optional[str] = None,
        vendor: Optional[str] = None,
        is_configured: bool = False,
        custom_name: Optional[str] = None,
    ) -> tuple[Dict[str, Any], bool]:
        """Update or register device. Returns (device_dict, is_new)."""
        mac = mac.lower().strip()
        devices = self.get_known_devices()
        now = time.time()
        is_new = mac not in devices

        if is_new:
            devices[mac] = {
                "mac": mac,
                "ip": ip,
                "hostname": hostname or "",
                "vendor": vendor or "",
                "first_seen": now,
                "last_seen": now,
                "online": True,
                "is_configured": is_configured,
                "custom_name": custom_name or "",
            }
        else:
            dev = devices[mac]
            dev["ip"] = ip
            dev["last_seen"] = now
            dev["online"] = True
            if hostname:
                dev["hostname"] = hostname
            if vendor and not dev.get("vendor"):
                dev["vendor"] = vendor
            if is_configured:
                dev["is_configured"] = True
            if custom_name:
                dev["custom_name"] = custom_name

        return devices[mac], is_new

    def mark_offline_devices(self, threshold_seconds: float) -> List[Dict[str, Any]]:
        """Find devices whose last_seen exceeds threshold and mark them offline. Returns newly offline devices."""
        now = time.time()
        newly_offline = []
        for mac, dev in self.get_known_devices().items():
            if dev.get("online", True):
                if now - dev.get("last_seen", 0) > threshold_seconds:
                    dev["online"] = False
                    newly_offline.append(dev)
        return newly_offline

    # --- Monitored Devices Runtime State ---

    def get_monitored_device_state(self, dev_id: str) -> Dict[str, Any]:
        monitored = self.data.setdefault("monitored_devices", {})
        return monitored.setdefault(
            dev_id,
            {
                "status": "UNKNOWN",  # UP, DOWN, UNKNOWN
                "last_check": 0,
                "last_change": 0,
                "last_down_alert": 0,
                "failure_count": 0,
                "services": {},  # name -> {status: UP/DOWN, latency_ms: float, error: str}
                "resources": {},
                "systemd": {},
                "last_error": None,
            },
        )

    # --- External IP State ---

    def get_last_ip(self) -> Optional[str]:
        return self.data.setdefault("external_ip", {}).get("last_ip")

    def update_ip(self, ip: str) -> bool:
        """Returns True if IP changed."""
        rec = self.data.setdefault("external_ip", {})
        old_ip = rec.get("last_ip")
        now = time.time()
        rec["last_check"] = now
        if old_ip != ip:
            rec["last_ip"] = ip
            rec["last_change"] = now
            return True
        return False

    # --- Flag Status State ---

    def get_last_flag_status(self) -> Optional[str]:
        return self.data.setdefault("flag_status", {}).get("last_status")

    def get_flag_status_data(self) -> dict:
        """Get full flag status details including incidents and active trigger."""
        return self.data.setdefault(
            "flag_status",
            {
                "last_status": "Normal (Not Checked)",
                "status_type": "RAISE",
                "last_check": 0,
                "last_change": 0,
                "active_incident": None,
                "recent_incidents": [],
            },
        )

    def update_flag_status(
        self,
        status: str,
        status_type: str = "RAISE",
        active_incident: Optional[dict] = None,
        recent_incidents: Optional[List[dict]] = None,
    ) -> bool:
        """Returns True if flag status changed."""
        rec = self.data.setdefault("flag_status", {})
        old_status = rec.get("last_status")
        now = time.time()
        rec["last_check"] = now
        rec["status_type"] = status_type
        if active_incident is not None:
            rec["active_incident"] = active_incident
        elif status_type == "RAISE":
            rec["active_incident"] = None

        if recent_incidents is not None:
            rec["recent_incidents"] = recent_incidents

        if old_status != status:
            rec["last_status"] = status
            rec["last_change"] = now
            return True
        return False

    # --- Notification Queue (Batched) ---

    def queue_notification(self, notification: QueuedNotification) -> None:
        queue = self.data.setdefault("queued_notifications", [])
        queue.append(notification.to_dict())

    def pop_queued_notifications(
        self, category: Optional[str] = None
    ) -> List[QueuedNotification]:
        queue = self.data.setdefault("queued_notifications", [])
        if category is None:
            items = [QueuedNotification.from_dict(x) for x in queue]
            self.data["queued_notifications"] = []
            return items

        matching = []
        remaining = []
        for x in queue:
            if x.get("category") == category:
                matching.append(QueuedNotification.from_dict(x))
            else:
                remaining.append(x)
        self.data["queued_notifications"] = remaining
        return matching

    def should_alert(
        self, alert_key: str, cooldown_seconds: float
    ) -> bool:
        """Checks if enough time has passed since the last alert for this key."""
        alerts = self.data.setdefault("last_alerts", {})
        last_time = alerts.get(alert_key, 0)
        now = time.time()
        if now - last_time >= cooldown_seconds:
            alerts[alert_key] = now
            return True
        return False

    def clear_alert_cooldown(self, alert_key: str) -> None:
        alerts = self.data.setdefault("last_alerts", {})
        alerts.pop(alert_key, None)

    # --- Telegram Pause / Snooze State ---

    def get_telegram_paused_until(self) -> float:
        return float(self.data.get("telegram_paused_until", 0.0))

    def set_telegram_pause(self, until_timestamp: float) -> None:
        self.data["telegram_paused_until"] = float(until_timestamp)

    def clear_telegram_pause(self) -> None:
        self.data["telegram_paused_until"] = 0.0

    def is_telegram_paused(self) -> bool:
        return time.time() < self.get_telegram_paused_until()

    def get_telegram_pause_remaining(self) -> int:
        rem = self.get_telegram_paused_until() - time.time()
        return max(0, int(rem))

    # --- New Feature State Accessors ---

    def get_presence_state(self) -> Dict[str, Any]:
        return self.data.setdefault("presence", {})

    def get_ssl_certs_state(self) -> Dict[str, Any]:
        return self.data.setdefault("ssl_certs", {})

    def get_webhook_logs(self, limit: int = 50) -> List[Dict[str, Any]]:
        logs = self.data.setdefault("webhook_logs", [])
        return logs[-limit:]

    def add_webhook_log(self, entry: Dict[str, Any]) -> None:
        logs = self.data.setdefault("webhook_logs", [])
        logs.append(entry)
        if len(logs) > 100:
            self.data["webhook_logs"] = logs[-100:]

    def get_speedtest_history(self, limit: int = 20) -> List[Dict[str, Any]]:
        hist = self.data.setdefault("speedtest_history", [])
        return hist[-limit:]

    def add_speedtest_result(self, entry: Dict[str, Any]) -> None:
        hist = self.data.setdefault("speedtest_history", [])
        hist.append(entry)
        if len(hist) > 50:
            self.data["speedtest_history"] = hist[-50:]

    def get_speedtest_comparison(self) -> Dict[str, Any]:
        """Return the most recent speedtest result, previous result, and comparison deltas."""
        hist = self.data.get("speedtest_history", [])
        current = hist[-1] if len(hist) >= 1 else None
        previous = hist[-2] if len(hist) >= 2 else None

        comparison = None
        if current and previous:
            c_dl = float(current.get("download_mbps", 0.0))
            p_dl = float(previous.get("download_mbps", 0.0))
            c_ul = float(current.get("upload_mbps", 0.0))
            p_ul = float(previous.get("upload_mbps", 0.0))
            c_lat = float(current.get("latency_ms", 0.0))
            p_lat = float(previous.get("latency_ms", 0.0))

            dl_delta = round(c_dl - p_dl, 2)
            dl_pct = round(((c_dl - p_dl) / p_dl * 100.0), 1) if p_dl > 0 else 0.0
            ul_delta = round(c_ul - p_ul, 2)
            ul_pct = round(((c_ul - p_ul) / p_ul * 100.0), 1) if p_ul > 0 else 0.0
            lat_delta = round(c_lat - p_lat, 1)

            # Targets comparison
            target_diffs = {}
            c_targets = current.get("target_latencies", {})
            p_targets = previous.get("target_latencies", {})
            all_target_keys = set(c_targets.keys()).union(set(p_targets.keys()))
            for tk in all_target_keys:
                c_item = c_targets.get(tk, {})
                p_item = p_targets.get(tk, {})
                c_t_lat = c_item.get("latency_ms")
                p_t_lat = p_item.get("latency_ms")
                t_delta = round(c_t_lat - p_t_lat, 1) if (c_t_lat is not None and p_t_lat is not None) else None
                target_diffs[tk] = {
                    "current_ms": c_t_lat,
                    "previous_ms": p_t_lat,
                    "delta_ms": t_delta,
                    "current_status": c_item.get("status", "UNKNOWN"),
                    "previous_status": p_item.get("status", "UNKNOWN"),
                    "current_message": c_item.get("message", ""),
                    "previous_message": p_item.get("message", ""),
                }

            c_ts = current.get("timestamp", 0)
            p_ts = previous.get("timestamp", 0)
            comparison = {
                "download_delta_mbps": dl_delta,
                "download_delta_pct": dl_pct,
                "upload_delta_mbps": ul_delta,
                "upload_delta_pct": ul_pct,
                "latency_delta_ms": lat_delta,
                "time_delta_seconds": round(c_ts - p_ts) if c_ts and p_ts else 0,
                "targets": target_diffs,
            }

        return {
            "current": current,
            "previous": previous,
            "comparison": comparison,
            "history_count": len(hist),
        }

    def get_cisco_ports(self) -> Dict[str, Any]:
        return self.data.setdefault("cisco_ports", {})

    def get_ups_status(self) -> Dict[str, Any]:
        return self.data.setdefault("ups_status", {"status": "ONLINE", "battery_percent": 100, "runtime_mins": 60, "last_check": 0})

    def get_night_owl_state(self) -> Dict[str, Any]:
        return self.data.setdefault("night_owl", {"last_alert": 0, "active_devices": []})
