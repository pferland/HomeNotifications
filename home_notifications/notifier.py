"""Notification Dispatcher for HomeNotifications.

Handles immediate Telegram alerts, batched digest delivery, rate limiting,
and message formatting with HTML tags.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import List, Optional
from aiogram import Bot
from aiogram.enums import ParseMode

from home_notifications.config import AppConfig, FeatureConfig
from home_notifications.state import QueuedNotification, StateManager

logger = logging.getLogger(__name__)

EMOJIS = {
    "INFO": "ℹ️",
    "SUCCESS": "✅",
    "WARNING": "⚠️",
    "ERROR": "🚨",
    "DISCOVERY": "🔎",
    "NETWORK": "🌐",
    "SECURITY": "🛡️",
    "SERVER": "🖥️",
    "PRESENCE": "👋",
    "SSL": "🔒",
    "WEBHOOK": "🔌",
    "SPEEDTEST": "⚡",
    "SWITCH": "🔀",
    "UPS": "🔋",
    "NIGHT_OWL": "🌙",
}


class NotificationDispatcher:
    """Dispatches notifications immediately or batches them according to feature config."""

    def __init__(self, bot: Bot, config: AppConfig, state: StateManager):
        self.bot = bot
        self.config = config
        self.state = state
        self._lock = asyncio.Lock()

    def is_enabled(self) -> bool:
        """Check if Telegram notifications are globally enabled in configuration."""
        return bool(self.config.telegram.enabled)

    def is_paused(self) -> bool:
        """Check if Telegram notifications are temporarily snoozed/paused."""
        return self.state.is_telegram_paused()

    def get_pause_remaining(self) -> int:
        """Seconds remaining in active pause window, or 0 if not paused."""
        return self.state.get_telegram_pause_remaining()

    def pause(self, seconds: int) -> float:
        """Pause all Telegram notifications for a set duration in seconds."""
        until = time.time() + max(1, seconds)
        self.state.set_telegram_pause(until)
        logger.info("Paused Telegram notifications for %ds (until %s)", seconds, time.ctime(until))
        return until

    def resume(self) -> None:
        """Immediately resume Telegram notifications."""
        self.state.clear_telegram_pause()
        logger.info("Resumed Telegram notifications")

    async def notify(
        self,
        category: str,
        title: str,
        message: str,
        level: str = "INFO",
        force_immediate: bool = False,
    ) -> bool:
        """Route notification to either immediate send or batched queue based on feature settings."""
        feat: FeatureConfig = self.config.get_feature(category)
        notify_mode = feat.notify_mode.lower() if feat else "immediate"

        if notify_mode == "never":
            logger.debug("Notification for %s suppressed (mode=never)", category)
            return False

        if force_immediate or notify_mode in ("immediate", "on_change"):
            return await self.send_immediate(category, title, message, level)
        elif notify_mode == "batched":
            qn = QueuedNotification(
                category=category,
                title=title,
                message=message,
                timestamp=time.time(),
                level=level,
            )
            self.state.queue_notification(qn)
            await self.state.save()
            logger.debug("Queued notification for batch flush: %s", title)
            return True
        else:
            # Default to immediate
            return await self.send_immediate(category, title, message, level)

    async def send_immediate(
        self, category: str, title: str, message: str, level: str = "INFO"
    ) -> bool:
        """Immediately format and transmit a notification to the configured Telegram chat."""
        icon = EMOJIS.get(level.upper(), "🔔")
        header = f"{icon} <b>{title}</b>"
        full_text = f"{header}\n\n{message}"
        return await self._send_telegram_chunks(full_text)

    async def flush_batches(self, category: Optional[str] = None) -> int:
        """Flush queued batched notifications into combined digest message(s). Returns count sent."""
        async with self._lock:
            items = self.state.pop_queued_notifications(category)
            if not items:
                return 0

            await self.state.save()

            # Group items by category or format sequentially
            lines: List[str] = []
            lines.append("📬 <b>[Home Notifications Digest]</b>")
            lines.append(f"<i>{len(items)} update{'s' if len(items) > 1 else ''} collected:</i>\n")

            for item in items:
                icon = EMOJIS.get(item.level.upper(), "•")
                lines.append(f"{icon} <b>{item.title}</b>")
                lines.append(f"{item.message}\n")

            full_text = "\n".join(lines).strip()
            success = await self._send_telegram_chunks(full_text)
            if success:
                logger.info("Successfully dispatched batch digest with %d items", len(items))
                return len(items)
            else:
                logger.error("Failed to send batch digest, re-queuing %d items", len(items))
                for item in items:
                    self.state.queue_notification(item)
                await self.state.save()
                return 0

    async def _send_telegram_chunks(self, text: str) -> bool:
        """Send message safely handling Telegram's 4096 character limit."""
        if not self.is_enabled():
            logger.info("Telegram notifications are globally disabled. Message suppressed.")
            return False

        if self.is_paused():
            rem = self.get_pause_remaining()
            logger.info("Telegram notifications are paused (%ds remaining). Message suppressed.", rem)
            return False

        if not self.bot:
            logger.debug("No active bot session; dry-run notification suppressed.")
            return False

        chat_id = self.config.telegram.chat_id
        if not chat_id:
            logger.warning("Telegram CHATID not set, cannot send message")
            return False

        max_len = 4000
        chunks: List[str] = []
        if len(text) <= max_len:
            chunks = [text]
        else:
            # Split by line breaks safely
            curr_chunk = ""
            for line in text.split("\n"):
                if len(curr_chunk) + len(line) + 1 > max_len:
                    chunks.append(curr_chunk)
                    curr_chunk = line
                else:
                    curr_chunk = f"{curr_chunk}\n{line}" if curr_chunk else line
            if curr_chunk:
                chunks.append(curr_chunk)

        try:
            for chunk in chunks:
                await self.bot.send_message(
                    chat_id=chat_id,
                    text=chunk,
                    parse_mode=ParseMode.HTML,
                    disable_web_page_preview=True,
                )
                await asyncio.sleep(0.1)
            return True
        except Exception as e:
            logger.error("Error sending Telegram message to %s: %s", chat_id, e)
            return False
