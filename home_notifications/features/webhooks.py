"""Smart Home Webhook Notification Ingestor Feature.

Provides an authenticated HTTP endpoint (/api/webhook/notify) allowing external
smart home systems (Home Assistant, 3D printers, Frigate NVR, Zigbee sensors)
to trigger high-priority or batched Telegram alerts.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict

from home_notifications.features.base import BaseFeature

logger = logging.getLogger(__name__)


class WebhookFeature(BaseFeature):
    """Processes incoming third-party smart home webhooks and forwards them to Telegram."""

    def __init__(self, config, state, notifier):
        super().__init__("webhooks", config, state, notifier)

    def validate_token(self, provided_token: str) -> bool:
        """Check if incoming request authorization matches configured api_key."""
        if self.feature_config.get_bool("allow_unauthenticated", False):
            return True
        expected = str(self.feature_config.get("api_key", "homenotify-secret-key")).strip()
        if not expected:
            return True
        return provided_token.strip() == expected

    async def ingest_webhook(self, payload: Dict[str, Any], source_ip: str = "") -> Dict[str, Any]:
        """Process, validate, log, and dispatch an incoming webhook."""
        if not self.is_enabled:
            return {"success": False, "error": "Webhook feature is disabled in configuration"}

        title = str(payload.get("title") or payload.get("event") or "Smart Home Event").strip()
        message = str(payload.get("message") or payload.get("text") or payload.get("description") or "").strip()
        level = str(payload.get("level") or payload.get("severity") or "INFO").strip().upper()
        category = str(payload.get("category") or "smart_home").strip()
        force_immediate = bool(payload.get("immediate", payload.get("force_immediate", True)))

        if not message:
            message = f"Event triggered from source: {source_ip or 'webhook'}"

        # Record event in state
        entry = {
            "timestamp": time.time(),
            "source_ip": source_ip,
            "title": title,
            "message": message,
            "level": level,
            "category": category,
        }
        self.state.add_webhook_log(entry)
        await self.state.save()

        # Dispatch alert
        sent = await self.notifier.notify(
            category=self.name,
            title=title,
            message=message,
            level=level,
            force_immediate=force_immediate,
        )

        return {"success": True, "dispatched": sent, "entry": entry}

    async def execute(self) -> None:
        """Periodic housekeeping / pruning if needed."""
        pass
