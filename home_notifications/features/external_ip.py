"""External IP monitor feature."""

from __future__ import annotations

import logging
import aiohttp

from home_notifications.features.base import BaseFeature

logger = logging.getLogger(__name__)

IP_ENDPOINTS = [
    "https://api.ipify.org",
    "https://icanhazip.com",
    "https://ifconfig.me/ip",
]


class ExternalIPFeature(BaseFeature):
    """Monitors external public IP address and notifies on change or periodically."""

    def __init__(self, config, state, notifier):
        super().__init__("external_ip", config, state, notifier)

    @staticmethod
    async def fetch_ip() -> str:
        """Fetch current public IPv4 address with fallback providers."""
        async with aiohttp.ClientSession() as session:
            for url in IP_ENDPOINTS:
                try:
                    async with session.get(url, timeout=aiohttp.ClientTimeout(total=5.0)) as resp:
                        if resp.status == 200:
                            ip = (await resp.text()).strip()
                            if ip and len(ip.split(".")) == 4:
                                return ip
                except Exception as e:
                    logger.debug("Failed to get IP from %s: %s", url, e)
        raise RuntimeError("Unable to retrieve public IP from any provider")

    async def execute(self) -> str:
        if not self.is_enabled:
            return "External IP check disabled"

        try:
            curr_ip = await self.fetch_ip()
            old_ip = self.state.get_last_ip()
            changed = self.state.update_ip(curr_ip)
            await self.state.save()

            notify_mode = self.feature_config.notify_mode

            if changed and old_ip is not None:
                msg = f"<b>Previous IP:</b> <code>{old_ip}</code>\n<b>New IP:</b> <code>{curr_ip}</code>"
                await self.notifier.notify(
                    category=self.name,
                    title="External IP Address Changed",
                    message=msg,
                    level="WARNING",
                )
            elif notify_mode == "periodic":
                msg = f"<b>Current Public IP:</b> <code>{curr_ip}</code>"
                await self.notifier.notify(
                    category=self.name,
                    title="External IP Status",
                    message=msg,
                    level="INFO",
                )
            elif old_ip is None:
                # First run recording
                logger.info("Initialized external IP tracking: %s", curr_ip)

            return f"IP Address: {curr_ip}"
        except Exception as e:
            logger.error("Error executing ExternalIPFeature: %s", e)
            return f"Error retrieving external IP: {e}"
