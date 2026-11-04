"""Telegram bot command handlers and router."""

from __future__ import annotations

import logging
import time
from aiogram import Router, html
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.types import Message

from home_notifications.config import AppConfig
from home_notifications.features.device_monitor import DeviceMonitorFeature
from home_notifications.features.discovery import NetworkDiscoveryFeature
from home_notifications.features.external_ip import ExternalIPFeature
from home_notifications.features.flag_status import FlagStatusFeature
from home_notifications.features.photolevel import PhotolevelFeature
from home_notifications.notifier import NotificationDispatcher
from home_notifications.state import StateManager

logger = logging.getLogger(__name__)


def create_bot_router(
    config: AppConfig,
    state: StateManager,
    notifier: NotificationDispatcher,
    ip_feature: ExternalIPFeature,
    flag_feature: FlagStatusFeature,
    photo_feature: PhotolevelFeature,
    discovery_feature: NetworkDiscoveryFeature,
    monitor_feature: DeviceMonitorFeature,
) -> Router:
    """Create and configure aiogram Router with all bot commands."""
    router = Router()

    @router.message(CommandStart())
    @router.message(Command("help"))
    async def cmd_help(message: Message) -> None:
        user_name = message.from_user.first_name if message.from_user else "User"
        text = (
            f"👋 Hello, <b>{html.quote(user_name)}</b>!\n\n"
            f"🏠 <b>Home Notification System Commands:</b>\n\n"
            f"• /status - Overall system & feature health summary\n"
            f"• /ip - View current external public IP address\n"
            f"• /flag - Check current flag status (half-staff alert)\n"
            f"• /devices (or /hosts) - Status of all monitored devices\n"
            f"• /services - Status of all monitored ports & services\n"
            f"• /resources - CPU, RAM, & Disk usage for monitored servers\n"
            f"• /scan - Trigger an immediate network discovery scan\n"
            f"• /new_devices - List all discovered network devices\n"
            f"• /photo - Ambient light sensor reading\n"
            f"• /digest - Flush queued batch notifications immediately\n"
            f"• /help - Display this commands list"
        )
        await message.answer(text, parse_mode=ParseMode.HTML)

    @router.message(Command("ip"))
    async def cmd_ip(message: Message) -> None:
        await message.answer("🌐 Checking external IP address...")
        try:
            ip = await ip_feature.fetch_ip()
            await message.answer(f"🌐 <b>Current Public IP:</b> <code>{ip}</code>", parse_mode=ParseMode.HTML)
        except Exception as e:
            await message.answer(f"❌ Failed to get external IP: {e}")

    @router.message(Command("flag"))
    async def cmd_flag(message: Message) -> None:
        await message.answer("🚩 Checking flag status...")
        try:
            status = await flag_feature.fetch_flag_status()
            await message.answer(f"<b>Flag Status Report:</b>\n\n<pre>{status}</pre>", parse_mode=ParseMode.HTML)
        except Exception as e:
            await message.answer(f"❌ Failed to get flag status: {e}")

    @router.message(Command("photo"))
    async def cmd_photo(message: Message) -> None:
        res = await photo_feature.get_photolevel()
        await message.answer(f"💡 {res}")

    @router.message(Command("devices"))
    @router.message(Command("hosts"))
    async def cmd_devices(message: Message) -> None:
        devices = config.devices
        if not devices:
            await message.answer("ℹ️ No devices configured in <code>devices.yaml</code>.", parse_mode=ParseMode.HTML)
            return

        lines = ["🖥️ <b>Monitored Devices:</b>\n"]
        for dev_id, dev in devices.items():
            dev_state = state.get_monitored_device_state(dev_id)
            status = dev_state.get("status", "UNKNOWN")
            icon = "✅" if status == "UP" else ("🚨" if status == "DOWN" else "❓")

            srv_count = len(dev.services)
            srv_info = f" ({srv_count} service{'s' if srv_count != 1 else ''})" if srv_count > 0 else ""
            lines.append(f"{icon} <b>{dev.name}</b> (<code>{dev.ip}</code>) — <b>{status}</b>{srv_info}")

        lines.append("\n<i>Use /services or /resources for detailed metrics.</i>")
        await message.answer("\n".join(lines), parse_mode=ParseMode.HTML)

    @router.message(Command("services"))
    async def cmd_services(message: Message) -> None:
        devices = config.devices
        if not devices:
            await message.answer("ℹ️ No devices configured in <code>devices.yaml</code>.", parse_mode=ParseMode.HTML)
            return

        lines = ["🔌 <b>Monitored Services:</b>\n"]
        any_services = False

        for dev_id, dev in devices.items():
            if not dev.services:
                continue
            any_services = True
            dev_state = state.get_monitored_device_state(dev_id)
            srv_states = dev_state.get("services", {})

            lines.append(f"<b>{dev.name}</b> (<code>{dev.ip}</code>):")
            for srv in dev.services:
                info = srv_states.get(srv.name, {})
                s_status = info.get("status", "UNKNOWN")
                s_icon = "✅" if s_status == "UP" else ("🚨" if s_status == "DOWN" else "❓")
                latency = info.get("latency_ms", 0.0)
                lat_str = f" ({latency:.1f} ms)" if latency > 0 else ""
                lines.append(f"  {s_icon} {srv.name} [{srv.type.upper()} {srv.port}]: <b>{s_status}</b>{lat_str}")
            lines.append("")

        if not any_services:
            await message.answer("ℹ️ No services configured under any device in <code>devices.yaml</code>.", parse_mode=ParseMode.HTML)
            return

        await message.answer("\n".join(lines), parse_mode=ParseMode.HTML)

    @router.message(Command("resources"))
    async def cmd_resources(message: Message) -> None:
        devices = config.devices
        lines = ["📊 <b>Device System Resources:</b>\n"]
        found = False

        for dev_id, dev in devices.items():
            dev_state = state.get_monitored_device_state(dev_id)
            res = dev_state.get("resources", {})
            if not res or not res.get("memory_percent"):
                continue

            found = True
            lines.append(f"🖥️ <b>{dev.name}</b> (<code>{dev.ip}</code>):")
            load_1m = res.get("cpu_load_1m")
            if load_1m is not None:
                lines.append(f"  • <b>CPU Load (1m):</b> {load_1m}")

            mem_pct = res.get("memory_percent")
            used_mb = res.get("memory_used_mb", 0)
            tot_mb = res.get("memory_total_mb", 0)
            if mem_pct is not None:
                lines.append(f"  • <b>RAM:</b> {mem_pct}% ({used_mb}MB / {tot_mb}MB)")

            disks = res.get("disk_usage", {})
            for mount, pct in disks.items():
                lines.append(f"  • <b>Disk ({mount}):</b> {pct}% used")

            lines.append("")

        if not found:
            await message.answer(
                "ℹ️ No active resource telemetry recorded yet. Ensure SSH monitoring is enabled in <code>devices.yaml</code>.",
                parse_mode=ParseMode.HTML,
            )
            return

        await message.answer("\n".join(lines), parse_mode=ParseMode.HTML)

    @router.message(Command("scan"))
    async def cmd_scan(message: Message) -> None:
        await message.answer("🔎 Scanning local network for active devices, please wait...")
        start = time.time()
        try:
            hosts = await discovery_feature.execute()
            elapsed = time.time() - start
            lines = [f"🔎 <b>Network Scan Complete</b> ({elapsed:.1f}s, {len(hosts)} active devices):\n"]
            for h in sorted(hosts, key=lambda x: x.ip)[:20]:
                vendor_str = f" ({h.vendor})" if h.vendor else ""
                name_str = f" <i>[{h.custom_name}]</i>" if h.custom_name else ""
                lines.append(f"• <code>{h.ip:15}</code> | <code>{h.mac}</code>{vendor_str}{name_str}")

            if len(hosts) > 20:
                lines.append(f"\n<i>...and {len(hosts) - 20} more. Use /new_devices for full list.</i>")

            await message.answer("\n".join(lines), parse_mode=ParseMode.HTML)
        except Exception as e:
            await message.answer(f"❌ Scan failed: {e}")

    @router.message(Command("new_devices"))
    async def cmd_new_devices(message: Message) -> None:
        known = state.get_known_devices()
        if not known:
            await message.answer("ℹ️ No devices recorded in state yet. Run /scan first.", parse_mode=ParseMode.HTML)
            return

        lines = [f"🌐 <b>Known Network Devices ({len(known)} total):</b>\n"]
        for mac, d in sorted(known.items(), key=lambda x: x[1].get("ip", "")):
            ip = d.get("ip", "")
            vendor = d.get("vendor") or "Unknown Vendor"
            name = d.get("custom_name") or d.get("hostname") or ""
            name_str = f" <b>{name}</b>" if name else ""
            online_str = "🟢" if d.get("online", True) else "⚪"
            lines.append(f"{online_str} <code>{ip:15}</code> | <code>{mac}</code> | {vendor}{name_str}")

        await message.answer("\n".join(lines[:35]), parse_mode=ParseMode.HTML)

    @router.message(Command("digest"))
    async def cmd_digest(message: Message) -> None:
        count = await notifier.flush_batches()
        if count == 0:
            await message.answer("ℹ️ No queued batch notifications to send.")
        else:
            await message.answer(f"📬 Flushed {count} batch notifications.")

    @router.message(Command("status"))
    async def cmd_status(message: Message) -> None:
        lines = ["⚙️ <b>Home Notifications System Status:</b>\n"]
        lines.append(f"• <b>Monitored Devices:</b> {len(config.devices)}")
        lines.append(f"• <b>Known Network Hosts:</b> {len(state.get_known_devices())}")
        lines.append(f"• <b>Queued Batch Notifications:</b> {len(state.data.get('queued_notifications', []))}\n")
        lines.append("<b>Features Configuration:</b>")
        for f_name, f_cfg in config.features.items():
            status_ico = "🟢" if f_cfg.enabled else "🔴"
            mode = f_cfg.notify_mode
            lines.append(f"{status_ico} <code>{f_name:18}</code>: every {f_cfg.interval_seconds}s (mode: {mode})")

        await message.answer("\n".join(lines), parse_mode=ParseMode.HTML)

    return router
