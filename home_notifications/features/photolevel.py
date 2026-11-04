"""Photolevel I2C ADC sensor feature."""

from __future__ import annotations

import asyncio
import logging
import time

from home_notifications.features.base import BaseFeature

logger = logging.getLogger(__name__)

try:
    import smbus
except ImportError:
    smbus = None


class PhotolevelFeature(BaseFeature):
    """Monitors ambient photo levels via PCF8591 I2C analog-to-digital converter."""

    def __init__(self, config, state, notifier):
        super().__init__("photolevel", config, state, notifier)

    @staticmethod
    def read_analog(bus, channel: int = 1) -> int:
        try:
            bus.write_byte(0x48, 0x40 | channel)
            time.sleep(0.1)
            return int(bus.read_byte(0x48))
        except Exception as e:
            logger.debug("I2C read analog failed: %s", e)
            return 0

    async def get_photolevel(self) -> str:
        if smbus is None:
            return "PhotoLevels: Hardware not present (smbus module not found)"

        def _sync_read():
            try:
                bus = smbus.SMBus(1)
                val = self.read_analog(bus, channel=1)
                return f"PhotoLevels: {val}"
            except Exception as e:
                return f"PhotoLevels: Sensor unavailable ({e})"

        return await asyncio.to_thread(_sync_read)

    async def execute(self) -> str:
        if not self.is_enabled:
            return "Photolevel check disabled"

        val_str = await self.get_photolevel()
        if self.feature_config.notify_mode == "periodic":
            await self.notifier.notify(
                category=self.name,
                title="Photolevel Reading",
                message=val_str,
                level="INFO",
            )
        return val_str
