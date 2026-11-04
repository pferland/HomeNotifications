"""Unified HomeNotifications Service.

Runs the interactive Telegram bot alongside background schedulers for:
- Network discovery of new and existing devices
- Health, service, and resource monitoring of devices
- External IP change monitoring
- Flag status (half-staff) tracking
- Batched notification digest delivery
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Auto-activate .venv if running via system python without required dependencies
_venv_py = Path(__file__).resolve().parent / ".venv" / "bin" / "python"
if sys.prefix == sys.base_prefix and _venv_py.exists() and os.environ.get("_HOMENOTIFY_REEXEC") != "1":
    try:
        import apscheduler
        import aiogram
    except ImportError:
        os.environ["_HOMENOTIFY_REEXEC"] = "1"
        os.execv(str(_venv_py), [str(_venv_py)] + sys.argv)

import asyncio
import logging
import signal
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from home_notifications.bot.handlers import create_bot_router
from home_notifications.config import AppConfig, load_config
from home_notifications.features.device_monitor import DeviceMonitorFeature
from home_notifications.features.discovery import NetworkDiscoveryFeature
from home_notifications.features.external_ip import ExternalIPFeature
from home_notifications.features.flag_status import FlagStatusFeature
from home_notifications.features.photolevel import PhotolevelFeature
from home_notifications.features.cisco_snmp import CiscoSNMPFeature
from home_notifications.features.night_owl import NightOwlFeature
from home_notifications.features.presence import PresenceFeature
from home_notifications.features.speedtest import SpeedtestFeature
from home_notifications.features.ssl_cert import SSLCertFeature
from home_notifications.features.ups_monitor import UPSMonitorFeature
from home_notifications.features.webhooks import WebhookFeature
from home_notifications.notifier import NotificationDispatcher
from home_notifications.state import StateManager

logger = logging.getLogger("HomeNotifications")


class HomeNotificationApp:
    """Master application orchestrating the Telegram bot, scheduler, and features."""

    def __init__(self, base_dir: Path | None = None):
        self.config: AppConfig = load_config(base_dir)
        self.state: StateManager = StateManager(self.config.get_state_path())
        self.scheduler = AsyncIOScheduler()
        self.dp = Dispatcher()

        # Bot setup
        bot_token = self.config.telegram.bot_token
        if not bot_token:
            logger.warning("No bot token configured in config.ini! Running in offline/dry-run mode.")
            self.bot = None
        else:
            self.bot = Bot(
                token=bot_token,
                default=DefaultBotProperties(parse_mode=ParseMode.HTML),
            )

        self.notifier = NotificationDispatcher(self.bot, self.config, self.state)

        # Features
        self.ip_feature = ExternalIPFeature(self.config, self.state, self.notifier)
        self.flag_feature = FlagStatusFeature(self.config, self.state, self.notifier)
        self.photo_feature = PhotolevelFeature(self.config, self.state, self.notifier)
        self.discovery_feature = NetworkDiscoveryFeature(self.config, self.state, self.notifier)
        self.device_feature = DeviceMonitorFeature(self.config, self.state, self.notifier)
        self.presence_feature = PresenceFeature(self.config, self.state, self.notifier)
        self.ssl_feature = SSLCertFeature(self.config, self.state, self.notifier)
        self.webhook_feature = WebhookFeature(self.config, self.state, self.notifier)
        self.speedtest_feature = SpeedtestFeature(self.config, self.state, self.notifier)
        self.cisco_feature = CiscoSNMPFeature(self.config, self.state, self.notifier)
        self.ups_feature = UPSMonitorFeature(self.config, self.state, self.notifier)
        self.night_owl_feature = NightOwlFeature(self.config, self.state, self.notifier)

        # Web Management UI
        if self.config.system.web_enabled:
            from home_notifications.web.server import WebServer
            self.web_server: WebServer | None = WebServer(
                config=self.config,
                state=self.state,
                notifier=self.notifier,
                discovery_feature=self.discovery_feature,
                device_feature=self.device_feature,
                ip_feature=self.ip_feature,
                flag_feature=self.flag_feature,
                presence_feature=self.presence_feature,
                ssl_feature=self.ssl_feature,
                webhook_feature=self.webhook_feature,
                speedtest_feature=self.speedtest_feature,
                cisco_feature=self.cisco_feature,
                ups_feature=self.ups_feature,
                night_owl_feature=self.night_owl_feature,
            )
        else:
            self.web_server = None

        # Register bot router
        router = create_bot_router(
            config=self.config,
            state=self.state,
            notifier=self.notifier,
            ip_feature=self.ip_feature,
            flag_feature=self.flag_feature,
            photo_feature=self.photo_feature,
            discovery_feature=self.discovery_feature,
            monitor_feature=self.device_feature,
        )
        self.dp.include_router(router)

    def schedule_jobs(self) -> None:
        """Schedule background feature jobs according to configuration intervals."""
        # 1. External IP feature
        if self.ip_feature.is_enabled:
            interval = self.ip_feature.feature_config.interval_seconds
            self.scheduler.add_job(
                self.ip_feature.execute,
                "interval",
                seconds=interval,
                id="external_ip",
                name="External IP Monitor",
            )
            logger.info("Scheduled External IP Monitor every %ds", interval)

        # 2. Flag status feature
        if self.flag_feature.is_enabled:
            interval = self.flag_feature.feature_config.interval_seconds
            self.scheduler.add_job(
                self.flag_feature.execute,
                "interval",
                seconds=interval,
                id="flag_status",
                name="Flag Status Monitor",
            )
            logger.info("Scheduled Flag Status Monitor every %ds", interval)

        # 3. Photolevel feature
        if self.photo_feature.is_enabled:
            interval = self.photo_feature.feature_config.interval_seconds
            self.scheduler.add_job(
                self.photo_feature.execute,
                "interval",
                seconds=interval,
                id="photolevel",
                name="Photolevel Monitor",
            )
            logger.info("Scheduled Photolevel Monitor every %ds", interval)

        # 4. Network discovery feature
        if self.discovery_feature.is_enabled:
            interval = self.discovery_feature.feature_config.interval_seconds
            self.scheduler.add_job(
                self.discovery_feature.execute,
                "interval",
                seconds=interval,
                id="network_discovery",
                name="Network Discovery",
            )
            logger.info("Scheduled Network Discovery every %ds", interval)

        # 5. Device monitor feature
        if self.device_feature.is_enabled:
            interval = self.device_feature.feature_config.interval_seconds
            self.scheduler.add_job(
                self.device_feature.execute,
                "interval",
                seconds=interval,
                id="device_monitor",
                name="Device Health Monitor",
            )
            logger.info("Scheduled Device Health Monitor every %ds", interval)

        # 6. Presence feature
        if self.presence_feature.is_enabled:
            interval = self.presence_feature.feature_config.interval_seconds
            self.scheduler.add_job(
                self.presence_feature.execute,
                "interval",
                seconds=interval,
                id="presence",
                name="Resident Presence Monitor",
            )
            logger.info("Scheduled Presence Monitor every %ds", interval)

        # 7. SSL Certificate Expiry feature
        if self.ssl_feature.is_enabled:
            interval = self.ssl_feature.feature_config.interval_seconds
            self.scheduler.add_job(
                self.ssl_feature.execute,
                "interval",
                seconds=interval,
                id="ssl_cert",
                name="SSL Certificate Monitor",
            )
            logger.info("Scheduled SSL Certificate Monitor every %ds", interval)

        # 8. Speedtest feature
        if self.speedtest_feature.is_enabled:
            interval = self.speedtest_feature.feature_config.interval_seconds
            self.scheduler.add_job(
                self.speedtest_feature.execute,
                "interval",
                seconds=interval,
                id="speedtest",
                name="Speedtest Monitor",
            )
            logger.info("Scheduled Speedtest Monitor every %ds", interval)

        # 9. Cisco SNMP Switch feature
        if self.cisco_feature.is_enabled:
            interval = self.cisco_feature.feature_config.interval_seconds
            self.scheduler.add_job(
                self.cisco_feature.execute,
                "interval",
                seconds=interval,
                id="cisco_snmp",
                name="Cisco Switch Monitor",
            )
            logger.info("Scheduled Cisco Switch Monitor every %ds", interval)

        # 10. UPS Power feature
        if self.ups_feature.is_enabled:
            interval = self.ups_feature.feature_config.interval_seconds
            self.scheduler.add_job(
                self.ups_feature.execute,
                "interval",
                seconds=interval,
                id="ups_monitor",
                name="UPS Power Monitor",
            )
            logger.info("Scheduled UPS Power Monitor every %ds", interval)

        # 11. Night Owl feature
        if self.night_owl_feature.is_enabled:
            interval = self.night_owl_feature.feature_config.interval_seconds
            self.scheduler.add_job(
                self.night_owl_feature.execute,
                "interval",
                seconds=interval,
                id="night_owl",
                name="Night Owl Activity Monitor",
            )
            logger.info("Scheduled Night Owl Monitor every %ds", interval)

        # 12. Periodic batch flush
        self.scheduler.add_job(
            self.notifier.flush_batches,
            "interval",
            seconds=60,
            id="batch_flush",
            name="Notification Batch Flusher",
        )
        logger.info("Scheduled Notification Batch Flusher every 60s")

    async def start(self) -> None:
        """Start the application: scheduler, initial scans, and bot polling."""
        logger.info("Starting HomeNotifications System...")

        # Schedule background tasks
        self.schedule_jobs()
        self.scheduler.start()

        # Start Web Management UI
        if self.web_server:
            await self.web_server.start()

        # Send Telegram startup notification
        if self.bot and self.config.telegram.chat_id:
            dev_count = len(self.config.devices)
            web_url = f"http://{self.config.system.web_host}:{self.config.system.web_port}" if self.web_server else ""
            web_info = f"\n• Web UI: <b>{web_url}</b>" if web_url else ""
            startup_msg = (
                f"🚀 <b>Home Notifications System Started</b>\n\n"
                f"• Monitored Devices: <b>{dev_count}</b>\n"
                f"• Active Features: <b>{len([f for f in self.config.features.values() if f.enabled])}</b>"
                f"{web_info}\n\n"
                f"<i>Type /help to view available commands.</i>"
            )
            await self.notifier.send_immediate(
                category="system",
                title="Service Started",
                message=startup_msg,
                level="INFO",
            )

        # Trigger quick initial warmup tasks in background
        asyncio.create_task(self._initial_warmup())

        # Start bot polling
        if self.bot:
            logger.info("Starting Telegram bot polling...")
            await self.dp.start_polling(self.bot)
        else:
            logger.info("Bot polling skipped (no token). Running scheduler in loop...")
            while True:
                await asyncio.sleep(3600)

    async def _initial_warmup(self) -> None:
        """Perform initial feature runs after brief delay to avoid blocking startup."""
        await asyncio.sleep(1.0)
        logger.info("Running initial startup scans...")
        if self.device_feature.is_enabled:
            try:
                await self.device_feature.execute()
            except Exception as e:
                logger.error("Initial device check failed: %s", e)

        if self.discovery_feature.is_enabled:
            try:
                await self.discovery_feature.execute()
            except Exception as e:
                logger.error("Initial network discovery failed: %s", e)

        if self.ip_feature.is_enabled:
            try:
                await self.ip_feature.execute()
            except Exception as e:
                logger.error("Initial external IP check failed: %s", e)

        if self.flag_feature.is_enabled:
            try:
                await self.flag_feature.execute()
            except Exception as e:
                logger.error("Initial flag status check failed: %s", e)

        if self.presence_feature.is_enabled:
            try:
                await self.presence_feature.execute()
            except Exception as e:
                logger.error("Initial presence check failed: %s", e)

        if self.ssl_feature.is_enabled:
            try:
                await self.ssl_feature.execute()
            except Exception as e:
                logger.error("Initial SSL check failed: %s", e)

        if self.cisco_feature.is_enabled:
            try:
                await self.cisco_feature.execute()
            except Exception as e:
                logger.error("Initial Cisco check failed: %s", e)

    async def stop(self) -> None:
        """Gracefully shutdown scheduler, web server, and bot."""
        logger.info("Shutting down HomeNotifications...")
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)
        if self.web_server:
            await self.web_server.stop()
        await self.state.save()
        if self.bot:
            await self.bot.session.close()
        logger.info("Shutdown complete.")


async def main() -> None:
    app = HomeNotificationApp()
    
    # Configure logging
    log_level = getattr(logging, app.config.system.log_level, logging.INFO)
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        stream=sys.stdout,
    )

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, lambda: asyncio.create_task(app.stop()))
        except (NotImplementedError, RuntimeError):
            pass

    try:
        await app.start()
    except (asyncio.CancelledError, KeyboardInterrupt):
        await app.stop()


if __name__ == "__main__":
    asyncio.run(main())
