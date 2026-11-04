"""Web Management UI Server for HomeNotifications.

Provides a REST API and static web dashboard served via aiohttp.web.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import time
import urllib.parse
from pathlib import Path
from typing import Any, Dict, List, Optional
import yaml
from aiohttp import web

from home_notifications.auth import AuthManager

from home_notifications.config import AppConfig, DeviceConfig, ServiceCheckConfig, SSHMonitorConfig, load_config
from home_notifications.features.device_monitor import DeviceMonitorFeature
from home_notifications.features.discovery import NetworkDiscoveryFeature
from home_notifications.features.external_ip import ExternalIPFeature
from home_notifications.features.flag_status import FlagStatusFeature
from home_notifications.features.cisco_snmp import CiscoSNMPFeature
from home_notifications.features.night_owl import NightOwlFeature
from home_notifications.features.presence import PresenceFeature
from home_notifications.features.speedtest import SpeedtestFeature
from home_notifications.features.ssl_cert import SSLCertFeature
from home_notifications.features.ups_monitor import UPSMonitorFeature
from home_notifications.features.webhooks import WebhookFeature
from home_notifications.notifier import NotificationDispatcher
from home_notifications.monitors.ssh import SSHMonitor
from home_notifications.state import StateManager

logger = logging.getLogger(__name__)

AUTH_USER_KEY = getattr(web, "RequestKey", web.AppKey)("user")


class WebServer:
    """Embedded aiohttp web server hosting the Management UI and REST API."""

    def __init__(
        self,
        config: AppConfig,
        state: StateManager,
        notifier: NotificationDispatcher,
        discovery_feature: NetworkDiscoveryFeature,
        device_feature: DeviceMonitorFeature,
        ip_feature: ExternalIPFeature,
        flag_feature: FlagStatusFeature,
        presence_feature: Optional[PresenceFeature] = None,
        ssl_feature: Optional[SSLCertFeature] = None,
        webhook_feature: Optional[WebhookFeature] = None,
        speedtest_feature: Optional[SpeedtestFeature] = None,
        cisco_feature: Optional[CiscoSNMPFeature] = None,
        ups_feature: Optional[UPSMonitorFeature] = None,
        night_owl_feature: Optional[NightOwlFeature] = None,
    ):
        self.config = config
        self.state = state
        self.notifier = notifier
        self.discovery_feature = discovery_feature
        self.device_feature = device_feature
        self.ip_feature = ip_feature
        self.flag_feature = flag_feature
        self.presence_feature = presence_feature
        self.ssl_feature = ssl_feature
        self.webhook_feature = webhook_feature
        self.speedtest_feature = speedtest_feature
        self.cisco_feature = cisco_feature
        self.ups_feature = ups_feature
        self.night_owl_feature = night_owl_feature

        self.auth_manager = AuthManager(self.config.auth)
        self.app = web.Application(middlewares=[self._auth_middleware])
        self.runner: web.AppRunner | None = None
        self.site: web.TCPSite | None = None
        self.start_time = time.time()

        self._setup_routes()

    @web.middleware
    async def _auth_middleware(self, request: web.Request, handler) -> web.Response:
        """Enforces OIDC session or Bearer token authentication for WebUI and REST APIs."""
        if not self.config.auth.enabled:
            request[AUTH_USER_KEY] = None
            return await handler(request)

        path = request.path

        # Public routes exempt from auth checks
        if (
            path.startswith("/static/")
            or path in ("/auth/login", "/auth/callback", "/auth/logout")
            or path == "/favicon.ico"
        ):
            return await handler(request)

        # Webhook token authentication bypass for /api/webhook/notify
        if path == "/api/webhook/notify":
            token = request.headers.get("X-Webhook-Token") or request.query.get("token")
            if token and self.webhook_feature and self.webhook_feature.validate_token(token):
                request[AUTH_USER_KEY] = {"sub": "webhook", "type": "webhook"}
                return await handler(request)

        # 1. Check Session Cookie (for WebUI and browser requests)
        cookie_name = self.config.auth.cookie_name
        session_cookie = request.cookies.get(cookie_name)
        user = None
        if session_cookie:
            user = self.auth_manager.verify_session_token(session_cookie)

        # 2. Check Bearer / API token header (for REST API and service requests)
        if not user:
            auth_header = request.headers.get("Authorization") or request.headers.get("X-API-Key")
            if auth_header:
                user = await self.auth_manager.verify_bearer_token(auth_header)

        if user:
            request[AUTH_USER_KEY] = user
            return await handler(request)

        # Handle unauthenticated requests:
        if path.startswith("/api/"):
            return web.json_response(
                {
                    "error": "Unauthorized",
                    "message": "Valid authentication required. Provide an active session cookie or Bearer token.",
                },
                status=401,
            )

        # WebUI browser request: redirect to OIDC login
        redirect_target = request.path_qs
        login_url = f"/auth/login?redirect_to={urllib.parse.quote(redirect_target)}"
        raise web.HTTPFound(login_url)

    def _setup_routes(self) -> None:
        web_dir = Path(__file__).resolve().parent
        static_dir = web_dir / "static"
        templates_dir = web_dir / "templates"

        # Static assets
        self.app.router.add_static("/static/", path=str(static_dir), name="static")

        # HTML Page
        async def index_handler(request: web.Request) -> web.Response:
            index_path = templates_dir / "index.html"
            if index_path.exists():
                return web.FileResponse(index_path)
            return web.Response(text="Management UI template missing", status=404)

        self.app.router.add_get("/", index_handler)

        # Authentication Routes
        self.app.router.add_get("/auth/login", self.auth_login)
        self.app.router.add_get("/auth/callback", self.auth_callback)
        self.app.router.add_get("/auth/logout", self.auth_logout)
        self.app.router.add_post("/auth/logout", self.auth_logout)
        self.app.router.add_get("/auth/user", self.auth_get_user)

        # REST APIs
        self.app.router.add_get("/api/status", self.api_status)
        self.app.router.add_get("/api/devices", self.api_get_devices)
        self.app.router.add_post("/api/devices", self.api_add_or_update_device)
        self.app.router.add_delete("/api/devices/{id}", self.api_delete_device)
        self.app.router.add_get("/api/devices/{id}/available-services", self.api_get_available_services)
        self.app.router.add_get("/api/discovery", self.api_get_discovery)
        self.app.router.add_post("/api/discovery/scan", self.api_trigger_scan)
        self.app.router.add_get("/api/services", self.api_get_services)
        self.app.router.add_post("/api/services", self.api_save_service)
        self.app.router.add_delete("/api/services", self.api_delete_service)
        self.app.router.add_post("/api/services/test", self.api_test_service)
        self.app.router.add_get("/api/resources", self.api_get_resources)
        self.app.router.add_get("/api/resources/{id}/processes", self.api_get_device_processes)
        self.app.router.add_post("/api/resources/{id}/processes", self.api_get_device_processes)
        self.app.router.add_get("/api/features", self.api_get_features)
        self.app.router.add_post("/api/features", self.api_update_features)
        self.app.router.add_post("/api/notifications/flush", self.api_flush_notifications)
        self.app.router.add_post("/api/notifications/test", self.api_test_notification)
        self.app.router.add_post("/api/devices/check", self.api_check_all_devices)
        self.app.router.add_post("/api/ip/refresh", self.api_refresh_ip)

        # Telegram Configuration and Snooze / Pause APIs
        self.app.router.add_get("/api/telegram", self.api_get_telegram)
        self.app.router.add_post("/api/telegram", self.api_update_telegram)
        self.app.router.add_post("/api/telegram/pause", self.api_pause_telegram)

        # Webhook Ingestion API
        self.app.router.add_post("/api/webhook/notify", self.api_webhook_notify)

        # On-Demand Feature Checks
        self.app.router.add_get("/api/flag/status", self.api_get_flag_status)
        self.app.router.add_post("/api/flag/check", self.api_check_flag)
        self.app.router.add_post("/api/flag/test", self.api_test_flag_url)
        self.app.router.add_post("/api/presence/check", self.api_check_presence)
        self.app.router.add_post("/api/ssl/check", self.api_check_ssl)
        self.app.router.add_get("/api/speedtest/results", self.api_get_speedtest_results)
        self.app.router.add_get("/api/speedtest/servers", self.api_get_speedtest_servers)
        self.app.router.add_post("/api/speedtest/run", self.api_run_speedtest)
        self.app.router.add_post("/api/cisco/check", self.api_check_cisco)
        self.app.router.add_post("/api/ups/check", self.api_check_ups)
        self.app.router.add_post("/api/night_owl/check", self.api_check_night_owl)

    # --- Authentication Handlers ---

    async def auth_login(self, request: web.Request) -> web.Response:
        """Initiate OIDC authentication flow by redirecting to the IdP."""
        if not self.config.auth.enabled:
            return web.HTTPFound("/")

        session_cookie = request.cookies.get(self.config.auth.cookie_name)
        if session_cookie and self.auth_manager.verify_session_token(session_cookie):
            dest = request.query.get("redirect_to", "/")
            return web.HTTPFound(dest)

        redirect_to = request.query.get("redirect_to", "/")
        try:
            auth_url = await self.auth_manager.get_authorization_url(return_to=redirect_to)
            raise web.HTTPFound(auth_url)
        except web.HTTPException:
            raise
        except Exception as e:
            logger.error("Failed to generate OIDC authorization URL: %s", e)
            return web.Response(
                text=f"Authentication Configuration Error: {e}",
                status=500,
                content_type="text/plain",
            )

    async def auth_callback(self, request: web.Request) -> web.Response:
        """Handle OIDC authorization code callback from the Identity Provider."""
        if not self.config.auth.enabled:
            return web.HTTPFound("/")

        error = request.query.get("error")
        error_desc = request.query.get("error_description", error)
        if error:
            logger.warning("OIDC authentication returned error: %s (%s)", error, error_desc)
            return web.Response(
                text=f"Authentication Failed: {error_desc}",
                status=400,
                content_type="text/plain",
            )

        code = request.query.get("code")
        state = request.query.get("state")
        if not code or not state:
            return web.Response(
                text="Missing code or state parameter in callback",
                status=400,
                content_type="text/plain",
            )

        try:
            result = await self.auth_manager.exchange_code(code, state)
        except PermissionError as pe:
            logger.warning("OIDC authorization access denied: %s", pe)
            return web.Response(
                text=f"Access Denied: {pe}",
                status=403,
                content_type="text/plain",
            )
        except Exception as e:
            logger.error("OIDC code exchange failed: %s", e, exc_info=True)
            return web.Response(
                text=f"Authentication Error: {e}",
                status=500,
                content_type="text/plain",
            )

        user = result["user"]
        return_to = result.get("return_to") or "/"
        # Prevent open redirect vulnerabilities
        if not return_to.startswith("/") or return_to.startswith("//"):
            return_to = "/"

        session_token = self.auth_manager.create_session_token(user)
        response = web.HTTPFound(return_to)
        response.set_cookie(
            name=self.config.auth.cookie_name,
            value=session_token,
            max_age=self.config.auth.cookie_max_age,
            httponly=True,
            secure=self.config.auth.cookie_secure,
            samesite="Lax",
            path="/",
        )
        raise response

    async def auth_logout(self, request: web.Request) -> web.Response:
        """Log out the current user by deleting the session cookie and redirecting to IdP or login."""
        end_session_url = await self.auth_manager.get_logout_url()
        target_url = end_session_url if end_session_url else "/auth/login"

        response = web.HTTPFound(target_url)
        response.del_cookie(self.config.auth.cookie_name, path="/")
        response.headers["Clear-Site-Data"] = '"cookies", "storage"'
        raise response

    async def auth_get_user(self, request: web.Request) -> web.Response:
        """Return the profile of the currently authenticated user."""
        user = request.get(AUTH_USER_KEY, request.get("user"))
        if user:
            return web.json_response({
                "authenticated": True,
                "auth_enabled": self.config.auth.enabled,
                "user": {
                    "sub": user.get("sub", ""),
                    "name": user.get("name", ""),
                    "email": user.get("email", ""),
                    "username": user.get("username", ""),
                    "groups": user.get("groups", []),
                },
            })
        return web.json_response({
            "authenticated": False,
            "auth_enabled": self.config.auth.enabled,
            "user": None,
        })

    # --- API Handlers ---

    async def api_status(self, request: web.Request) -> web.Response:
        """System health and summary statistics."""
        devices = self.config.devices
        up_count = 0
        down_count = 0
        unknown_count = 0

        for dev_id in devices:
            st = self.state.get_monitored_device_state(dev_id).get("status", "UNKNOWN")
            if st == "UP":
                up_count += 1
            elif st == "DOWN":
                down_count += 1
            else:
                unknown_count += 1

        known_devices = self.state.get_known_devices()
        queued_count = len(self.state.data.get("queued_notifications", []))

        # Auto-resolve external IP if not yet loaded
        ext_ip = self.state.get_last_ip()
        if not ext_ip and self.ip_feature and self.ip_feature.is_enabled:
            try:
                await self.ip_feature.execute()
                ext_ip = self.state.get_last_ip()
            except Exception as e:
                logger.debug("Failed auto-resolving IP in api_status: %s", e)

        # Count total services across all devices
        total_services = 0
        up_services = 0
        down_services = 0
        for dev_id in devices:
            st = self.state.get_monitored_device_state(dev_id)
            srv_dict = st.get("services", {})
            total_services += len(srv_dict)
            for s in srv_dict.values():
                if isinstance(s, dict):
                    if s.get("status") == "UP":
                        up_services += 1
                    elif s.get("status") == "DOWN":
                        down_services += 1
            sys_dict = st.get("systemd", {})
            total_services += len(sys_dict)
            for state_val in sys_dict.values():
                if state_val == "active":
                    up_services += 1
                elif state_val in ("inactive", "failed"):
                    down_services += 1

        features_summary = {}
        flag_data = self.state.get_flag_status_data()
        pres_state = self.state.get_presence_state()
        ssl_certs = self.state.data.get("ssl_certs", {})
        speed_hist = self.state.data.get("speedtest_history", [])
        cisco_ports = self.state.data.get("cisco_ports", {})
        ups_data = self.state.data.get("ups_status", {})
        night_owl = self.state.data.get("night_owl", {})
        webhook_logs = self.state.data.get("webhook_logs", [])

        for fname, fcfg in self.config.features.items():
            info = {
                "name": fname,
                "enabled": fcfg.enabled,
                "interval_seconds": fcfg.interval_seconds,
                "notify_mode": fcfg.notify_mode,
                "batch_interval_seconds": fcfg.batch_interval_seconds,
            }
            if fname == "device_monitor":
                info["headline"] = f"{up_count}/{len(devices)} Hosts UP"
                info["detail"] = f"{total_services} services ({up_services} UP, {down_services} DOWN)"
                info["status_badge"] = "UP" if down_count == 0 else "DEGRADED"
            elif fname == "network_discovery":
                online_c = sum(1 for d in known_devices.values() if d.get("online", True))
                info["headline"] = f"{online_c} Online"
                info["detail"] = f"{len(known_devices)} known ARP hosts"
                info["status_badge"] = "ACTIVE"
            elif fname == "external_ip":
                info["headline"] = ext_ip or "Checking..."
                info["detail"] = "WAN IP change alert"
                info["status_badge"] = "ACTIVE" if ext_ip else "UNKNOWN"
            elif fname == "flag_status":
                st_type = flag_data.get("status_type", "UNKNOWN")
                days_ago = None
                recents = flag_data.get("recent_incidents", [])
                if recents and isinstance(recents, list) and len(recents) > 0:
                    days_ago = recents[0].get("days_ago")
                if st_type == "HALF-STAFF":
                    info["headline"] = "HALF-STAFF"
                    info["status_badge"] = "HALF-STAFF"
                else:
                    info["headline"] = "RAISE FLAG"
                    info["status_badge"] = "RAISE"
                info["detail"] = f"{days_ago}d since incident • {len(fcfg.options.get('sources', []))} source(s)" if days_ago is not None else "Sources monitored"
            elif fname == "presence":
                home_c = sum(1 for r in pres_state.values() if r.get("status") == "HOME")
                info["headline"] = f"{home_c}/{len(pres_state)} Home"
                info["detail"] = f"{len(pres_state)} residents tracked"
                info["status_badge"] = "HOME" if home_c > 0 else "AWAY"
            elif fname == "ssl_cert":
                exp_c = sum(1 for c in ssl_certs.values() if isinstance(c, dict) and c.get("days_left", 999) <= 14)
                if exp_c > 0:
                    info["headline"] = f"{exp_c} Expiring Soon"
                    info["status_badge"] = "WARNING"
                else:
                    info["headline"] = f"{len(ssl_certs)} Valid" if ssl_certs else "All Valid"
                    info["status_badge"] = "VALID"
                info["detail"] = "TLS/HTTPS cert audit"
            elif fname == "speedtest":
                cmp_data = self.state.get_speedtest_comparison()
                curr_s = cmp_data.get("current")
                prev_s = cmp_data.get("previous")
                comp = cmp_data.get("comparison")
                if curr_s:
                    dl = curr_s.get("download_mbps", 0.0)
                    ul = curr_s.get("upload_mbps", 0.0)
                    lat = curr_s.get("latency_ms", 0.0)
                    info["headline"] = f"↓ {dl:.1f} Mbps • ↑ {ul:.1f} Mbps"
                    loc = curr_s.get("server", {}).get("location") or curr_s.get("provider", "WAN")
                    info["detail"] = f"Ping: {lat:.0f}ms • {loc}"
                    min_dl = fcfg.options.get("min_download_mbps", 25.0)
                    info["status_badge"] = "GOOD" if dl >= min_dl else "DEGRADED"
                    info["current"] = curr_s
                    info["previous"] = prev_s
                    info["comparison"] = comp
                else:
                    info["headline"] = "Scheduled" if fcfg.enabled else "Disabled"
                    info["detail"] = "WAN bandwidth & latency"
                    info["status_badge"] = "READY" if fcfg.enabled else "MUTED"
            elif fname == "cisco_snmp":
                sw_id = fcfg.options.get("device_id", "core-switch")
                down_ports = sum(1 for p in cisco_ports.values() if isinstance(p, dict) and p.get("status") == "DOWN")
                info["headline"] = sw_id
                info["detail"] = f"{len(cisco_ports)} ports ({down_ports} down)" if cisco_ports else "Switch port & link monitor"
                info["status_badge"] = "NORMAL" if down_ports == 0 else "ALERT"
            elif fname == "ups_monitor":
                ups_st = ups_data.get("status", "Online" if fcfg.enabled else "Disabled")
                bat = ups_data.get("battery_percent", 100)
                info["headline"] = ups_st
                info["detail"] = f"Battery: {bat}%"
                info["status_badge"] = "ONLINE" if "on battery" not in str(ups_st).lower() else "ON BATTERY"
            elif fname == "access_logs":
                info["headline"] = "Auditing" if fcfg.enabled else "Disabled"
                info["detail"] = f"Threshold: {fcfg.options.get('failed_login_threshold', 3)} failures"
                info["status_badge"] = "AUDITING" if fcfg.enabled else "MUTED"
            elif fname == "webhooks":
                wh_cnt = len(webhook_logs) if isinstance(webhook_logs, list) else 0
                info["headline"] = "Endpoint Active" if fcfg.enabled else "Disabled"
                info["detail"] = f"{wh_cnt} webhooks received"
                info["status_badge"] = "ACTIVE" if fcfg.enabled else "MUTED"
            elif fname == "night_owl":
                q_s = fcfg.options.get("quiet_start", "01:00")
                q_e = fcfg.options.get("quiet_end", "05:30")
                info["headline"] = f"{q_s} – {q_e}"
                info["detail"] = "Quiet hours screen time"
                info["status_badge"] = "SCHEDULED" if fcfg.enabled else "MUTED"
            elif fname == "photolevel":
                info["headline"] = "Hardware Sensor"
                info["detail"] = "I2C ambient light level"
                info["status_badge"] = "ACTIVE" if fcfg.enabled else "DISABLED"

            features_summary[fname] = info

        return web.json_response(
            {
                "success": True,
                "uptime_seconds": int(time.time() - self.start_time),
                "external_ip": ext_ip or "Unknown",
                "flag_status": self.state.get_last_flag_status() or "Not Checked",
                "flag_status_details": self.state.get_flag_status_data(),
                "devices": {
                    "total": len(devices),
                    "up": up_count,
                    "down": down_count,
                    "unknown": unknown_count,
                },
                "network_discovery": {
                    "total_known": len(known_devices),
                    "online_count": sum(1 for d in known_devices.values() if d.get("online", True)),
                },
                "telegram": {
                    "configured": bool(self.config.telegram.bot_token),
                    "chat_id": self.config.telegram.chat_id,
                    "enabled": self.notifier.is_enabled(),
                    "is_paused": self.notifier.is_paused(),
                    "pause_remaining_seconds": self.notifier.get_pause_remaining(),
                },
                "presence": {
                    "residents_total": len(self.state.get_presence_state()),
                    "residents_home": sum(1 for r in self.state.get_presence_state().values() if r.get("status") == "HOME"),
                },
                "services": {
                    "total": total_services,
                    "up": up_services,
                    "down": down_services,
                },
                "queued_notifications": queued_count,
                "features_summary": features_summary,
            }
        )

    async def api_get_devices(self, request: web.Request) -> web.Response:
        """List all devices in inventory with live monitor states."""
        out = []
        for dev_id, dev in self.config.devices.items():
            st = self.state.get_monitored_device_state(dev_id)
            ssh_info = None
            if dev.ssh:
                ssh_info = {
                    "enabled": dev.ssh.enabled,
                    "username": dev.ssh.username,
                    "port": dev.ssh.port,
                    "key_path": dev.ssh.key_path or "",
                    "systemd_services": dev.ssh.systemd_services or [],
                }
            out.append(
                {
                    "id": dev.id,
                    "name": dev.name,
                    "ip": dev.ip,
                    "mac": dev.mac or "",
                    "tags": dev.tags,
                    "ping_enabled": dev.ping_enabled,
                    "ping_timeout": dev.ping_timeout,
                    "status": st.get("status", "UNKNOWN"),
                    "last_check": st.get("last_check", 0),
                    "services": st.get("services", {}),
                    "resources": st.get("resources", {}),
                    "systemd": st.get("systemd", {}),
                    "ssh": ssh_info,
                    "ssh_enabled": bool(dev.ssh and dev.ssh.enabled),
                    "snmp_enabled": bool(dev.snmp and dev.snmp.enabled),
                    "prometheus_enabled": bool(dev.prometheus and dev.prometheus.enabled),
                }
            )
        return web.json_response({"success": True, "devices": out})

    async def api_add_or_update_device(self, request: web.Request) -> web.Response:
        """Add or update a device in devices.yaml while preserving existing services."""
        try:
            body = await request.json()
        except Exception:
            return web.json_response({"success": False, "error": "Invalid JSON"}, status=400)

        dev_id = str(body.get("id", "")).strip()
        original_id = str(body.get("original_id", "")).strip() or dev_id
        name = str(body.get("name", "")).strip()
        ip = str(body.get("ip", "")).strip()
        mac = str(body.get("mac", "")).strip()
        tags_raw = body.get("tags", [])

        if not dev_id or not ip:
            return web.json_response(
                {"success": False, "error": "id and ip are required"}, status=400
            )

        if isinstance(tags_raw, str):
            tags = [t.strip() for t in tags_raw.split(",") if t.strip()]
        elif isinstance(tags_raw, list):
            tags = [str(t).strip() for t in tags_raw]
        else:
            tags = []

        yaml_path = self.config.base_dir / self.config.system.devices_file

        # Load existing YAML
        data: Dict[str, Any] = {"devices": []}
        if yaml_path.exists():
            try:
                with open(yaml_path, "r", encoding="utf-8") as f:
                    loaded = yaml.safe_load(f)
                    if isinstance(loaded, dict) and "devices" in loaded:
                        data = loaded
            except Exception as e:
                logger.error("Failed to read devices.yaml: %s", e)

        devices_list: List[Dict[str, Any]] = data.get("devices", [])

        # Find if device exists (matching original_id or dev_id)
        existing_idx = None
        for idx, item in enumerate(devices_list):
            if isinstance(item, dict) and item.get("id") in (original_id, dev_id):
                existing_idx = idx
                break

        ping_enabled = bool(body.get("ping_enabled", True))
        try:
            ping_timeout = float(body.get("ping_timeout", 2.0))
        except (ValueError, TypeError):
            ping_timeout = 2.0

        if existing_idx is not None:
            # Edit existing device while preserving configured monitors (services, etc.)
            old_record = devices_list[existing_idx]
            monitors = old_record.get("monitors", {})
            if not isinstance(monitors, dict):
                monitors = {}

            # Update ping monitor
            ping_cfg = monitors.setdefault("ping", {})
            if isinstance(ping_cfg, dict):
                ping_cfg["enabled"] = ping_enabled
                ping_cfg["timeout"] = ping_timeout
            else:
                monitors["ping"] = {"enabled": ping_enabled, "timeout": ping_timeout}

            # Update SSH monitor if provided
            if "ssh" in body:
                ssh_body = body["ssh"]
                if isinstance(ssh_body, dict):
                    ssh_mon = monitors.setdefault("ssh", {})
                    if isinstance(ssh_mon, dict):
                        ssh_mon["enabled"] = bool(ssh_body.get("enabled", False))
                        if "username" in ssh_body and ssh_body["username"]:
                            ssh_mon["username"] = str(ssh_body["username"])
                        if "port" in ssh_body:
                            try:
                                ssh_mon["port"] = int(ssh_body["port"])
                            except (ValueError, TypeError):
                                pass
                        if "key_path" in ssh_body:
                            ssh_mon["key_path"] = str(ssh_body["key_path"])
                        if "systemd_services" in ssh_body:
                            raw_sys = ssh_body["systemd_services"]
                            if isinstance(raw_sys, str):
                                ssh_mon["systemd_services"] = [s.strip() for s in raw_sys.split(",") if s.strip()]
                            elif isinstance(raw_sys, list):
                                ssh_mon["systemd_services"] = [str(s).strip() for s in raw_sys if str(s).strip()]

            new_record = {
                "id": dev_id,
                "name": name or dev_id,
                "ip": ip,
                "mac": mac,
                "tags": tags,
                "monitors": monitors,
            }
            # Preserve any extra top-level fields
            for k, v in old_record.items():
                if k not in new_record:
                    new_record[k] = v

            devices_list[existing_idx] = new_record

            # If device ID changed, update state mapping
            if original_id != dev_id:
                st_map = self.state.data.get("monitored_devices", {})
                if original_id in st_map:
                    st_map[dev_id] = st_map.pop(original_id)
                    await self.state.save()
        else:
            # New device creation
            monitors = {
                "ping": {"enabled": ping_enabled, "timeout": ping_timeout},
                "services": body.get("services", []),
            }
            if body.get("ssh") and isinstance(body["ssh"], dict) and body["ssh"].get("enabled"):
                monitors["ssh"] = body["ssh"]

            new_record = {
                "id": dev_id,
                "name": name or dev_id,
                "ip": ip,
                "mac": mac,
                "tags": tags,
                "monitors": monitors,
            }
            devices_list.append(new_record)

        data["devices"] = devices_list

        # Save to YAML
        try:
            with open(yaml_path, "w", encoding="utf-8") as f:
                yaml.dump(data, f, sort_keys=False, indent=2)
        except Exception as e:
            return web.json_response({"success": False, "error": f"Failed to save: {e}"}, status=500)

        # Reload devices in config
        self.config.devices = load_config(self.config.base_dir).devices

        # Trigger check for this device
        asyncio.create_task(self.device_feature.execute())

        return web.json_response({"success": True, "message": "Device saved successfully"})

    async def api_delete_device(self, request: web.Request) -> web.Response:
        """Remove a device from devices.yaml."""
        dev_id = request.match_info.get("id", "")
        yaml_path = self.config.base_dir / self.config.system.devices_file
        if not yaml_path.exists():
            return web.json_response({"success": False, "error": "devices.yaml not found"}, status=404)

        try:
            with open(yaml_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
        except Exception as e:
            return web.json_response({"success": False, "error": str(e)}, status=500)

        devs = data.get("devices", [])
        new_devs = [d for d in devs if isinstance(d, dict) and d.get("id") != dev_id]

        if len(devs) == len(new_devs):
            return web.json_response({"success": False, "error": "Device not found"}, status=404)

        data["devices"] = new_devs
        with open(yaml_path, "w", encoding="utf-8") as f:
            yaml.dump(data, f, sort_keys=False, indent=2)

        self.config.devices = load_config(self.config.base_dir).devices
        return web.json_response({"success": True, "message": f"Device {dev_id} deleted"})

    async def api_get_available_services(self, request: web.Request) -> web.Response:
        """Discover running systemd services and open listening ports on a target device."""
        device_id = request.match_info.get("id", "").strip()
        req_type = request.query.get("type", "").strip().lower()

        dev_cfg = self.config.devices.get(device_id)
        if not dev_cfg:
            self.config.devices = load_config(self.config.base_dir).devices
            dev_cfg = self.config.devices.get(device_id)

        if not dev_cfg:
            return web.json_response(
                {"success": False, "error": f"Device '{device_id}' not found"}, status=404
            )

        ip = dev_cfg.ip
        ssh_cfg = dev_cfg.ssh
        ssh_enabled = bool(ssh_cfg and ssh_cfg.enabled)

        monitored_sys_services = set(ssh_cfg.systemd_services if ssh_cfg else [])
        monitored_net_ports = {s.port for s in dev_cfg.services}

        discovered_services: List[Dict[str, Any]] = []

        # Common ports map: port -> (Default Name, Default Protocol, Default Path)
        COMMON_PORTS: Dict[int, tuple[str, str, str]] = {
            21: ("FTP Server", "tcp", ""),
            22: ("SSH Remote Access", "tcp", ""),
            23: ("Telnet Server", "tcp", ""),
            25: ("SMTP Mail Server", "tcp", ""),
            53: ("DNS Server", "tcp", ""),
            80: ("HTTP Web Server", "http", "/"),
            110: ("POP3 Mail", "tcp", ""),
            143: ("IMAP Mail", "tcp", ""),
            443: ("HTTPS Web Server", "https", "/"),
            465: ("SMTPS Secure Mail", "tcp", ""),
            587: ("Mail Submission", "tcp", ""),
            993: ("IMAPS Secure Mail", "tcp", ""),
            995: ("POP3S Secure Mail", "tcp", ""),
            1883: ("MQTT Broker", "tcp", ""),
            2947: ("GPSD Daemon", "tcp", ""),
            3000: ("Grafana / Node.js Web", "http", "/"),
            3001: ("Uptime Kuma / Node.js", "http", "/"),
            3306: ("MySQL / MariaDB Database", "tcp", ""),
            5000: ("Docker Registry / Flask Web", "http", "/"),
            5432: ("PostgreSQL Database", "tcp", ""),
            6379: ("Redis Server", "tcp", ""),
            8000: ("HTTP Web Alt", "http", "/"),
            8043: ("UniFi Portal", "https", "/"),
            8080: ("HTTP Web Proxy / Alt", "http", "/"),
            8086: ("InfluxDB Metrics API", "http", "/ping"),
            8088: ("HTTP Management", "http", "/"),
            8096: ("HomeNotifications / Jellyfin", "http", "/"),
            8123: ("Home Assistant Web", "http", "/"),
            8443: ("HTTPS Web Alt", "https", "/"),
            8843: ("UniFi Controller Web", "https", "/"),
            9000: ("Portainer Web", "http", "/"),
            9090: ("Prometheus / Cockpit", "http", "/"),
            9443: ("Portainer HTTPS", "https", "/"),
            27017: ("MongoDB Database", "tcp", ""),
            32400: ("Plex Media Server", "http", "/web"),
        }

        # 1. systemd service discovery (via SSH)
        if req_type == "systemd" or req_type in ("", "all"):
            if ssh_enabled and ssh_cfg:
                try:
                    import asyncssh
                    client_keys = []
                    if ssh_cfg.key_path:
                        key_exp = os.path.expanduser(ssh_cfg.key_path)
                        if os.path.exists(key_exp):
                            client_keys.append(key_exp)
                    conn_kwargs: Dict[str, Any] = {
                        "known_hosts": None,
                        "login_timeout": min(ssh_cfg.timeout, 4.0),
                    }
                    if client_keys:
                        conn_kwargs["client_keys"] = client_keys
                    if ssh_cfg.password:
                        conn_kwargs["password"] = ssh_cfg.password
                    username = ssh_cfg.username or os.getenv("USER", "root")

                    _ssh_conn = await asyncio.wait_for(
                        asyncssh.connect(
                            ip,
                            port=ssh_cfg.port,
                            username=username,
                            **conn_kwargs
                        ),
                        timeout=min(ssh_cfg.timeout, 3.0)
                    )
                    async with _ssh_conn as conn:
                        cmd = "systemctl list-units --type=service --state=running,active --no-pager --no-legend 2>/dev/null"
                        res = await conn.run(cmd, timeout=4.0)
                        if res.exit_status == 0:
                            sys_pattern = re.compile(r"^\s*([^\s]+)\.service\s+loaded\s+(\w+)\s+(\w+)\s+(.*)$")
                            for line in res.stdout.splitlines():
                                m = sys_pattern.match(line)
                                if m:
                                    unit, active_st, substate, desc = m.groups()
                                    desc_clean = desc.strip()
                                    is_monitored = unit in monitored_sys_services
                                    mon_tag = " [Monitored]" if is_monitored else ""
                                    discovered_services.append({
                                        "name": unit,
                                        "label": f"{unit} - {desc_clean} ({substate}){mon_tag}",
                                        "type": "systemd",
                                        "port": 0,
                                        "path": "",
                                        "description": desc_clean,
                                        "status": substate,
                                        "monitored": is_monitored,
                                    })
                except Exception as e:
                    logger.debug("Failed querying systemd services on %s (%s): %s", device_id, ip, e)

        # 2. Network port & service discovery (ss via SSH + fast concurrent TCP socket probe)
        if req_type in ("tcp", "http", "https", "", "all"):
            ssh_ports: Dict[int, str] = {}  # port -> process name
            if ssh_enabled and ssh_cfg:
                try:
                    import asyncssh
                    client_keys = []
                    if ssh_cfg.key_path:
                        key_exp = os.path.expanduser(ssh_cfg.key_path)
                        if os.path.exists(key_exp):
                            client_keys.append(key_exp)
                    conn_kwargs = {
                        "known_hosts": None,
                        "login_timeout": min(ssh_cfg.timeout, 4.0),
                    }
                    if client_keys:
                        conn_kwargs["client_keys"] = client_keys
                    if ssh_cfg.password:
                        conn_kwargs["password"] = ssh_cfg.password
                    username = ssh_cfg.username or os.getenv("USER", "root")

                    _ssh_conn = await asyncio.wait_for(
                        asyncssh.connect(
                            ip,
                            port=ssh_cfg.port,
                            username=username,
                            **conn_kwargs
                        ),
                        timeout=min(ssh_cfg.timeout, 3.0)
                    )
                    async with _ssh_conn as conn:
                        ss_res = await conn.run("ss -tlpn 2>/dev/null || ss -tln 2>/dev/null", timeout=4.0)
                        if ss_res.exit_status == 0:
                            port_re = re.compile(r"(?:\s|^)(?:(?:\*|0\.0\.0\.0|\[::\]|:::|127\.0\.0\.1|\[::1\]|(?:\d{1,3}\.){3}\d{1,3})):(\d+)\s")
                            proc_re = re.compile(r"users:\(\(\"([^\"]+)\"")
                            for line in ss_res.stdout.splitlines():
                                m_p = port_re.search(line)
                                if m_p:
                                    try:
                                        p_num = int(m_p.group(1))
                                    except ValueError:
                                        continue
                                    m_pr = proc_re.search(line)
                                    proc_name = m_pr.group(1) if m_pr else ""
                                    if p_num not in ssh_ports or (not ssh_ports[p_num] and proc_name):
                                        ssh_ports[p_num] = proc_name
                except Exception as e:
                    logger.debug("Failed querying ss listening ports on %s (%s): %s", device_id, ip, e)

            # Concurrent socket probe against known candidate ports and any ssh discovered ports
            candidate_ports = set(COMMON_PORTS.keys()).union(ssh_ports.keys())
            candidate_ports = {p for p in candidate_ports if 1 <= p <= 65535}

            async def probe_one(p: int) -> Optional[int]:
                try:
                    _, writer = await asyncio.wait_for(asyncio.open_connection(ip, p), timeout=0.4)
                    writer.close()
                    await writer.wait_closed()
                    return p
                except Exception:
                    return None

            probe_results = await asyncio.gather(*[probe_one(p) for p in candidate_ports])
            open_ports = sorted([p for p in probe_results if p is not None])

            for p in open_ports:
                proc = ssh_ports.get(p, "")
                info = COMMON_PORTS.get(p)
                default_name = info[0] if info else f"Port {p} Service"
                default_type = info[1] if info else ("https" if p in (443, 8043, 8443, 8843, 9443) else ("http" if p in (80, 8080, 8000, 3000, 5000, 8086, 8096, 8123) else "tcp"))
                default_path = info[2] if info else "/"

                suggested_name = default_name
                if proc and proc not in ("systemd", "docker-proxy"):
                    suggested_name = f"{default_name} ({proc})"
                elif proc == "docker-proxy" and info:
                    suggested_name = f"{info[0]} (Docker)"

                # Filtering by requested type
                if req_type == "http":
                    if default_type != "http" and p != 80 and "http" not in suggested_name.lower():
                        continue
                elif req_type == "https":
                    if default_type != "https" and p != 443 and "https" not in suggested_name.lower():
                        continue
                elif req_type == "tcp":
                    # All reachable ports are TCP
                    pass

                is_monitored = p in monitored_net_ports
                mon_tag = " [Monitored]" if is_monitored else ""
                label = f"Port {p} ({default_type.upper()}) - {suggested_name}{mon_tag}"

                discovered_services.append({
                    "name": suggested_name,
                    "label": label,
                    "type": default_type,
                    "port": p,
                    "path": default_path,
                    "description": f"Listening on port {p}" + (f" ({proc})" if proc else ""),
                    "status": "open",
                    "monitored": is_monitored,
                })

        return web.json_response({
            "success": True,
            "device_id": device_id,
            "device_name": dev_cfg.name,
            "ip": ip,
            "ssh_enabled": ssh_enabled,
            "requested_type": req_type,
            "count": len(discovered_services),
            "services": discovered_services,
        })

    async def api_get_discovery(self, request: web.Request) -> web.Response:
        """List all discovered ARP network devices."""
        known = self.state.get_known_devices()
        out = list(known.values())
        return web.json_response({"success": True, "hosts": out})

    async def api_trigger_scan(self, request: web.Request) -> web.Response:
        """Trigger an on-demand network discovery scan."""
        try:
            hosts = await self.discovery_feature.execute()
            return web.json_response(
                {
                    "success": True,
                    "count": len(hosts),
                    "hosts": [
                        {
                            "ip": h.ip,
                            "mac": h.mac,
                            "hostname": h.hostname,
                            "vendor": h.vendor,
                            "custom_name": h.custom_name,
                        }
                        for h in hosts
                    ],
                }
            )
        except Exception as e:
            return web.json_response({"success": False, "error": str(e)}, status=500)

    async def api_check_all_devices(self, request: web.Request) -> web.Response:
        """Trigger immediate check on all devices in inventory."""
        try:
            results = await self.device_feature.execute()
            return web.json_response({"success": True, "count": len(results)})
        except Exception as e:
            return web.json_response({"success": False, "error": str(e)}, status=500)

    async def api_refresh_ip(self, request: web.Request) -> web.Response:
        """Trigger an on-demand check of external public IP."""
        try:
            msg = await self.ip_feature.execute()
            curr_ip = self.state.get_last_ip()
            return web.json_response({"success": True, "ip": curr_ip, "message": msg})
        except Exception as e:
            return web.json_response({"success": False, "error": str(e)}, status=500)

    async def api_get_services(self, request: web.Request) -> web.Response:
        """List all monitored services with status, latency, and full configuration."""
        services = []
        for dev_id, dev in self.config.devices.items():
            st = self.state.get_monitored_device_state(dev_id)
            srv_states = st.get("services", {})
            for srv in dev.services:
                s_info = srv_states.get(srv.name, {})
                services.append(
                    {
                        "device_id": dev.id,
                        "device_name": dev.name,
                        "device_ip": dev.ip,
                        "service_name": srv.name,
                        "type": srv.type,
                        "port": srv.port,
                        "hostname": srv.hostname or "",
                        "check_ssl": srv.check_ssl,
                        "path": srv.path,
                        "expected_status": srv.expected_status,
                        "timeout": srv.timeout,
                        "status": s_info.get("status", "UNKNOWN"),
                        "latency_ms": s_info.get("latency_ms", 0.0),
                        "message": s_info.get("message", ""),
                        "is_systemd": False,
                    }
                )
            if dev.ssh and dev.ssh.enabled and dev.ssh.systemd_services:
                systemd_st = st.get("systemd", {})
                for srv_name in dev.ssh.systemd_services:
                    srv_clean = srv_name.strip()
                    if not srv_clean:
                        continue
                    curr_state = systemd_st.get(srv_clean, "unknown")
                    is_active = (curr_state == "active")
                    services.append(
                        {
                            "device_id": dev.id,
                            "device_name": dev.name,
                            "device_ip": dev.ip,
                            "service_name": f"{srv_clean} (systemd)",
                            "type": "systemd",
                            "port": "—",
                            "path": "",
                            "expected_status": "active",
                            "timeout": dev.ssh.timeout or 8.0,
                            "status": "UP" if is_active else ("DOWN" if curr_state in ("inactive", "failed") else "UNKNOWN"),
                            "latency_ms": 0.0,
                            "message": f"systemctl is-active: {curr_state}",
                            "is_systemd": True,
                            "systemd_unit": srv_clean,
                        }
                    )
        return web.json_response({"success": True, "services": services})

    async def api_save_service(self, request: web.Request) -> web.Response:
        """Add or update a monitored service on a device in devices.yaml."""
        try:
            body = await request.json()
        except Exception:
            return web.json_response({"success": False, "error": "Invalid JSON"}, status=400)

        device_id = str(body.get("device_id", "")).strip()
        name = str(body.get("name", "")).strip()
        original_name = str(body.get("original_name", "")).strip()
        stype = str(body.get("type", "tcp")).strip().lower()
        try:
            port = int(body.get("port", 80))
        except (ValueError, TypeError):
            port = 80
        hostname = str(body.get("hostname", "")).strip()
        check_ssl_raw = body.get("check_ssl")
        if check_ssl_raw is None:
            check_ssl = (stype == "https" or port == 443)
        else:
            check_ssl = bool(check_ssl_raw)
        path = str(body.get("path", "/")).strip() or "/"
        try:
            expected_status = int(body.get("expected_status", 200))
        except (ValueError, TypeError):
            expected_status = 200
        try:
            timeout = float(body.get("timeout", 3.0))
        except (ValueError, TypeError):
            timeout = 3.0

        if not device_id or not name:
            return web.json_response(
                {"success": False, "error": "device_id and name are required"}, status=400
            )

        yaml_path = self.config.base_dir / self.config.system.devices_file
        if not yaml_path.exists():
            return web.json_response(
                {"success": False, "error": "devices.yaml not found"}, status=404
            )

        try:
            with open(yaml_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
        except Exception as e:
            return web.json_response(
                {"success": False, "error": f"Failed to read devices.yaml: {e}"}, status=500
            )

        devices_list = data.get("devices", [])
        target_device = None
        for dev in devices_list:
            if isinstance(dev, dict) and dev.get("id") == device_id:
                target_device = dev
                break

        if not target_device:
            return web.json_response(
                {"success": False, "error": f"Device '{device_id}' not found"}, status=404
            )

        monitors = target_device.setdefault("monitors", {})
        if not isinstance(monitors, dict):
            monitors = {}
            target_device["monitors"] = monitors

        if stype == "systemd":
            unit_clean = name.replace(" (systemd)", "").strip()
            ssh_mon = monitors.setdefault("ssh", {})
            if not isinstance(ssh_mon, dict):
                ssh_mon = {}
                monitors["ssh"] = ssh_mon
            ssh_mon.setdefault("enabled", True)
            sys_services = ssh_mon.setdefault("systemd_services", [])
            if not isinstance(sys_services, list):
                sys_services = []
                ssh_mon["systemd_services"] = sys_services
            if original_name:
                orig_clean = original_name.replace(" (systemd)", "").strip()
                if orig_clean in sys_services:
                    sys_services.remove(orig_clean)
                if "services" in monitors and isinstance(monitors["services"], list):
                    monitors["services"] = [
                        s for s in monitors["services"]
                        if isinstance(s, dict) and s.get("name") not in (original_name, orig_clean)
                    ]
            if unit_clean not in sys_services:
                sys_services.append(unit_clean)

            try:
                with open(yaml_path, "w", encoding="utf-8") as f:
                    yaml.dump(data, f, sort_keys=False, indent=2)
            except Exception as e:
                return web.json_response(
                    {"success": False, "error": f"Failed to save devices.yaml: {e}"}, status=500
                )

            self.config.devices = load_config(self.config.base_dir).devices
            dev_cfg = self.config.devices.get(device_id)
            st = self.state.get_monitored_device_state(device_id)
            if original_name:
                orig_clean = original_name.replace(" (systemd)", "").strip()
                if "services" in st and original_name in st["services"]:
                    del st["services"][original_name]
                if orig_clean != unit_clean and "systemd" in st and orig_clean in st["systemd"]:
                    del st["systemd"][orig_clean]
            if dev_cfg and dev_cfg.ssh and dev_cfg.ssh.enabled:
                try:
                    import asyncssh
                    conn_kwargs = {"known_hosts": None}
                    if dev_cfg.ssh.key_path:
                        conn_kwargs["client_keys"] = [dev_cfg.ssh.key_path]
                    _ssh_conn = await asyncio.wait_for(
                        asyncssh.connect(dev_cfg.ip, port=dev_cfg.ssh.port, username=dev_cfg.ssh.username, **conn_kwargs),
                        timeout=min(dev_cfg.ssh.timeout, 3.0)
                    )
                    async with _ssh_conn as conn:
                        res = await conn.run(f"systemctl is-active {unit_clean} 2>/dev/null", timeout=dev_cfg.ssh.timeout)
                        state_str = res.stdout.strip().lower() or "unknown"
                        st.setdefault("systemd", {})[unit_clean] = state_str
                        await self.state.save()
                except Exception:
                    pass

            return web.json_response({"success": True, "message": f"Systemd service '{unit_clean}' saved successfully"})

        # Clean up any systemd service with original_name if switching types
        if original_name and "ssh" in monitors and isinstance(monitors["ssh"], dict):
            orig_clean = original_name.replace(" (systemd)", "").strip()
            sys_svcs = monitors["ssh"].get("systemd_services", [])
            if isinstance(sys_svcs, list) and orig_clean in sys_svcs:
                sys_svcs.remove(orig_clean)

        services = monitors.setdefault("services", [])
        if not isinstance(services, list):
            services = []
            monitors["services"] = services

        new_srv: Dict[str, Any] = {
            "name": name,
            "type": stype,
            "port": port,
        }
        if hostname:
            new_srv["hostname"] = hostname
        if stype in ("http", "https"):
            new_srv["path"] = path
            new_srv["expected_status"] = expected_status
            new_srv["check_ssl"] = check_ssl
        elif check_ssl:
            new_srv["check_ssl"] = True
        if timeout != 3.0:
            new_srv["timeout"] = timeout

        # Replace existing or append
        replaced = False
        search_name = original_name or name
        for idx, s in enumerate(services):
            if isinstance(s, dict) and s.get("name") == search_name:
                services[idx] = new_srv
                replaced = True
                break

        if not replaced:
            services.append(new_srv)

        try:
            with open(yaml_path, "w", encoding="utf-8") as f:
                yaml.dump(data, f, sort_keys=False, indent=2)
        except Exception as e:
            return web.json_response(
                {"success": False, "error": f"Failed to save devices.yaml: {e}"}, status=500
            )

        # Reload devices in config
        self.config.devices = load_config(self.config.base_dir).devices

        # Immediately probe service
        dev_cfg = self.config.devices.get(device_id)
        if dev_cfg:
            from home_notifications.monitors.service import ServiceMonitor
            srv_cfg = ServiceCheckConfig(
                name=name,
                type=stype,
                port=port,
                path=path,
                expected_status=expected_status,
                timeout=timeout,
                hostname=hostname,
                check_ssl=check_ssl,
            )
            check_res = await ServiceMonitor.check_service(dev_cfg.ip, srv_cfg)
            st = self.state.get_monitored_device_state(device_id)
            if original_name and original_name != name and original_name in st.get("services", {}):
                del st["services"][original_name]
            if original_name:
                orig_clean = original_name.replace(" (systemd)", "").strip()
                if "systemd" in st and orig_clean in st["systemd"]:
                    del st["systemd"][orig_clean]
            st.setdefault("services", {})[name] = {
                "status": check_res.status,
                "latency_ms": check_res.latency_ms,
                "message": check_res.message,
            }
            await self.state.save()

        return web.json_response({"success": True, "message": f"Service '{name}' saved successfully"})

    async def api_delete_service(self, request: web.Request) -> web.Response:
        """Remove a service from a device in devices.yaml."""
        try:
            body = await request.json()
        except Exception:
            body = {}
        device_id = str(body.get("device_id") or request.query.get("device_id", "")).strip()
        service_name = str(body.get("service_name") or request.query.get("service_name", "")).strip()

        if not device_id or not service_name:
            return web.json_response(
                {"success": False, "error": "device_id and service_name are required"}, status=400
            )

        yaml_path = self.config.base_dir / self.config.system.devices_file
        if not yaml_path.exists():
            return web.json_response(
                {"success": False, "error": "devices.yaml not found"}, status=404
            )

        try:
            with open(yaml_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
        except Exception as e:
            return web.json_response(
                {"success": False, "error": f"Failed to read: {e}"}, status=500
            )

        devices_list = data.get("devices", [])
        found = False
        for dev in devices_list:
            if isinstance(dev, dict) and dev.get("id") == device_id:
                monitors = dev.get("monitors", {})
                if isinstance(monitors, dict):
                    services = monitors.get("services", [])
                    new_services = [
                        s for s in services if isinstance(s, dict) and s.get("name") != service_name
                    ]
                    if len(new_services) != len(services):
                        monitors["services"] = new_services
                        found = True

                    ssh_mon = monitors.get("ssh", {})
                    if isinstance(ssh_mon, dict):
                        sys_services = ssh_mon.get("systemd_services", [])
                        unit_clean = service_name.replace(" (systemd)", "").strip()
                        if unit_clean in sys_services or service_name in sys_services:
                            ssh_mon["systemd_services"] = [
                                s for s in sys_services if s not in (unit_clean, service_name)
                            ]
                            found = True
                break

        if not found:
            return web.json_response(
                {"success": False, "error": f"Service '{service_name}' not found on device '{device_id}'"},
                status=404,
            )

        try:
            with open(yaml_path, "w", encoding="utf-8") as f:
                yaml.dump(data, f, sort_keys=False, indent=2)
        except Exception as e:
            return web.json_response(
                {"success": False, "error": f"Failed to write: {e}"}, status=500
            )

        self.config.devices = load_config(self.config.base_dir).devices

        st = self.state.get_monitored_device_state(device_id)
        if "services" in st and service_name in st["services"]:
            del st["services"][service_name]
        unit_clean = service_name.replace(" (systemd)", "").strip()
        if "systemd" in st and unit_clean in st["systemd"]:
            del st["systemd"][unit_clean]
        await self.state.save()

        return web.json_response({"success": True, "message": f"Service '{service_name}' deleted"})

    async def api_test_service(self, request: web.Request) -> web.Response:
        """Probe a service on-demand without altering configuration."""
        try:
            body = await request.json()
        except Exception:
            return web.json_response({"success": False, "error": "Invalid JSON"}, status=400)

        device_id = body.get("device_id")
        ip = body.get("ip")
        if not ip and device_id and device_id in self.config.devices:
            ip = self.config.devices[device_id].ip

        if not ip:
            return web.json_response(
                {"success": False, "error": "Target IP or valid device_id required"}, status=400
            )

        service_name = str(body.get("service_name") or body.get("name") or "").strip()
        stype = str(body.get("type", "tcp")).lower()

        if stype == "systemd":
            dev_cfg = self.config.devices.get(device_id) if device_id else None
            ssh_cfg = dev_cfg.ssh if dev_cfg else None
            unit_name = service_name.replace(" (systemd)", "").strip()
            if not ssh_cfg or not ssh_cfg.enabled:
                return web.json_response({
                    "success": True,
                    "result": {
                        "status": "UNKNOWN",
                        "latency_ms": 0.0,
                        "message": "SSH is not configured/enabled for this device"
                    }
                })
            import asyncssh
            import time
            t0 = time.perf_counter()
            try:
                conn_kwargs = {"known_hosts": None}
                if ssh_cfg.key_path:
                    conn_kwargs["client_keys"] = [ssh_cfg.key_path]
                _ssh_conn = await asyncio.wait_for(
                    asyncssh.connect(ip, port=ssh_cfg.port, username=ssh_cfg.username, **conn_kwargs),
                    timeout=min(ssh_cfg.timeout, 3.0)
                )
                async with _ssh_conn as conn:
                    res = await conn.run(f"systemctl is-active {unit_name} 2>/dev/null", timeout=ssh_cfg.timeout)
                    lat = (time.perf_counter() - t0) * 1000.0
                    state_str = res.stdout.strip().lower() or "unknown"
                    is_active = (state_str == "active")
                    r_status = "UP" if is_active else "DOWN"
                    r_msg = f"systemctl is-active: {state_str}"
                    if device_id:
                        st = self.state.get_monitored_device_state(device_id)
                        st.setdefault("systemd", {})[unit_name] = state_str
                        await self.state.save()
                    return web.json_response({
                        "success": True,
                        "result": {
                            "status": r_status,
                            "latency_ms": lat,
                            "message": r_msg
                        }
                    })
            except Exception as e:
                return web.json_response({
                    "success": True,
                    "result": {
                        "status": "DOWN",
                        "latency_ms": 0.0,
                        "message": f"SSH connection failed: {e}"
                    }
                })
        try:
            port = int(body.get("port", 80))
        except (ValueError, TypeError):
            port = 80
        hostname = str(body.get("hostname", "")).strip()
        check_ssl_raw = body.get("check_ssl")
        if check_ssl_raw is None:
            check_ssl = (stype == "https" or port == 443)
        else:
            check_ssl = bool(check_ssl_raw)
        path = str(body.get("path", "/"))
        try:
            expected_status = int(body.get("expected_status", 200))
        except (ValueError, TypeError):
            expected_status = 200
        try:
            timeout = float(body.get("timeout", 3.0))
        except (ValueError, TypeError):
            timeout = 3.0

        # Try to infer service_name if not provided and device is configured
        if not service_name and device_id and device_id in self.config.devices:
            for s in self.config.devices[device_id].services:
                if s.port == port and s.type.lower() == stype:
                    service_name = s.name
                    break

        from home_notifications.monitors.service import ServiceMonitor
        srv_cfg = ServiceCheckConfig(
            name=service_name or "test-probe",
            type=stype,
            port=port,
            path=path,
            expected_status=expected_status,
            timeout=timeout,
            hostname=hostname,
            check_ssl=check_ssl,
        )
        res = await ServiceMonitor.check_service(ip, srv_cfg)

        # Save probe result to state so the table immediately reflects it
        if device_id and service_name:
            st = self.state.get_monitored_device_state(device_id)
            services_dict = st.setdefault("services", {})
            services_dict[service_name] = {
                "status": res.status,
                "latency_ms": res.latency_ms,
                "message": res.message,
            }
            await self.state.save()

        return web.json_response(
            {
                "success": True,
                "result": {
                    "status": res.status,
                    "latency_ms": res.latency_ms,
                    "message": res.message,
                    "success": res.success,
                    "service_name": service_name,
                },
            }
        )

    async def api_get_resources(self, request: web.Request) -> web.Response:
        """List telemetry for all servers with recorded resources."""
        res_list = []
        for dev_id, dev in self.config.devices.items():
            st = self.state.get_monitored_device_state(dev_id)
            res = st.get("resources", {})
            if res and res.get("memory_percent") is not None:
                res_list.append(
                    {
                        "device_id": dev.id,
                        "device_name": dev.name,
                        "device_ip": dev.ip,
                        "cpu_load_1m": res.get("cpu_load_1m"),
                        "memory_percent": res.get("memory_percent"),
                        "memory_used_mb": res.get("memory_used_mb"),
                        "memory_total_mb": res.get("memory_total_mb"),
                        "disk_usage": res.get("disk_usage", {}),
                        "systemd": st.get("systemd", {}),
                        "top_cpu_processes": res.get("top_cpu_processes", []),
                        "top_mem_processes": res.get("top_mem_processes", []),
                    }
                )
        return web.json_response({"success": True, "resources": res_list})

    async def api_get_device_processes(self, request: web.Request) -> web.Response:
        """Fetch live top CPU & Memory process breakdown for a specific device."""
        dev_id = request.match_info["id"]
        dev = self.config.devices.get(dev_id)
        if not dev:
            return web.json_response({"success": False, "error": f"Device '{dev_id}' not found"}, status=404)

        if not dev.ssh or not dev.ssh.enabled:
            return web.json_response(
                {
                    "success": False,
                    "error": f"SSH monitoring is not enabled for device '{dev.name}'. Please enable SSH in devices.yaml.",
                },
                status=400,
            )

        limit = 25
        try:
            if "limit" in request.query:
                limit = int(request.query["limit"])
        except ValueError:
            pass

        result = await SSHMonitor.get_processes(dev.ip, dev.ssh, limit=limit)
        if result.get("success"):
            # Update cached device resources state
            st = self.state.get_monitored_device_state(dev.id)
            if "resources" not in st or not isinstance(st["resources"], dict):
                st["resources"] = {}
            if result.get("cpu_load_1m") is not None:
                st["resources"]["cpu_load_1m"] = result["cpu_load_1m"]
            if result.get("memory_percent") is not None:
                st["resources"]["memory_percent"] = result["memory_percent"]
                st["resources"]["memory_used_mb"] = result.get("memory_used_mb")
                st["resources"]["memory_total_mb"] = result.get("memory_total_mb")
            st["resources"]["top_cpu_processes"] = result.get("top_cpu_processes", [])
            st["resources"]["top_mem_processes"] = result.get("top_mem_processes", [])
            await self.state.save()

        result["device_id"] = dev.id
        result["device_name"] = dev.name
        result["device_ip"] = dev.ip
        return web.json_response(result)

    async def api_get_features(self, request: web.Request) -> web.Response:
        """List features with their configurations."""
        out = {}
        for f_name, f_cfg in self.config.features.items():
            opts = {}
            for k, v in f_cfg.options.items():
                if k.lower() in ("token", "chatid", "bot_token", "chat_id"):
                    continue
                if isinstance(v, str) and (v.startswith("[") or v.startswith("{")):
                    try:
                        opts[k] = json.loads(v)
                        continue
                    except Exception:
                        pass
                opts[k] = v
            out[f_name] = {
                "name": f_cfg.name,
                "enabled": f_cfg.enabled,
                "interval_seconds": f_cfg.interval_seconds,
                "notify_mode": f_cfg.notify_mode,
                "batch_interval_seconds": f_cfg.batch_interval_seconds,
                "options": opts,
            }
        return web.json_response({"success": True, "features": out})

    async def api_update_features(self, request: web.Request) -> web.Response:
        """Update feature settings in config.ini."""
        try:
            body = await request.json()
        except Exception:
            return web.json_response({"success": False, "error": "Invalid JSON"}, status=400)

        # In a real environment, update config.ini
        ini_path = self.config.base_dir / "config.ini"
        import configparser

        parser = configparser.ConfigParser(interpolation=None)
        if ini_path.exists():
            parser.read(ini_path, encoding="utf-8")

        for feat_name, settings in body.items():
            if feat_name.lower() in ("telegram", "default"):
                continue
            sec_name = f"feature:{feat_name}"
            if not parser.has_section(sec_name):
                parser.add_section(sec_name)
            if "enabled" in settings:
                parser.set(sec_name, "enabled", str(settings["enabled"]).lower())
            if "interval_seconds" in settings:
                parser.set(sec_name, "interval_seconds", str(settings["interval_seconds"]))
            if "notify_mode" in settings:
                parser.set(sec_name, "notify_mode", str(settings["notify_mode"]))
            if "batch_interval_seconds" in settings:
                parser.set(sec_name, "batch_interval_seconds", str(settings["batch_interval_seconds"]))

            # Save sub-options if present
            options = settings.get("options", {})
            for opt_k, opt_v in options.items():
                if opt_k.lower() in ("token", "chatid", "bot_token", "chat_id"):
                    continue
                if isinstance(opt_v, bool):
                    parser.set(sec_name, opt_k, str(opt_v).lower())
                elif isinstance(opt_v, (list, dict)):
                    parser.set(sec_name, opt_k, json.dumps(opt_v))
                else:
                    parser.set(sec_name, opt_k, str(opt_v))

            for k, v in settings.items():
                if k.lower() in (
                    "token",
                    "chatid",
                    "bot_token",
                    "chat_id",
                    "enabled",
                    "interval_seconds",
                    "notify_mode",
                    "batch_interval_seconds",
                    "options",
                    "name",
                ):
                    continue
                if isinstance(v, bool):
                    parser.set(sec_name, k, str(v).lower())
                elif isinstance(v, (list, dict)):
                    parser.set(sec_name, k, json.dumps(v))
                else:
                    parser.set(sec_name, k, str(v))

        try:
            with open(ini_path, "w", encoding="utf-8") as f:
                parser.write(f)
            # Reload
            self.config.features = load_config(self.config.base_dir).features
            return web.json_response({"success": True, "message": "Features updated"})
        except Exception as e:
            return web.json_response({"success": False, "error": str(e)}, status=500)

    # --- Telegram Configuration & Pause APIs ---

    async def api_get_telegram(self, request: web.Request) -> web.Response:
        """Get current Telegram bot configuration and snooze/pause status."""
        tg = self.config.telegram
        raw_token = tg.bot_token or ""
        masked_token = f"{raw_token[:6]}...{raw_token[-6:]}" if len(raw_token) > 12 else raw_token
        return web.json_response(
            {
                "success": True,
                "configured": bool(raw_token),
                "bot_token": raw_token,
                "bot_token_masked": masked_token,
                "chat_id": tg.chat_id,
                "parse_mode": tg.parse_mode,
                "enabled": self.notifier.is_enabled(),
                "is_paused": self.notifier.is_paused(),
                "pause_remaining_seconds": self.notifier.get_pause_remaining(),
            }
        )

    async def api_update_telegram(self, request: web.Request) -> web.Response:
        """Update Telegram bot settings in config.ini."""
        try:
            body = await request.json()
        except Exception:
            return web.json_response({"success": False, "error": "Invalid JSON"}, status=400)

        ini_path = self.config.base_dir / "config.ini"
        import configparser
        from aiogram import Bot
        from aiogram.client.default import DefaultBotProperties
        from aiogram.enums import ParseMode

        parser = configparser.ConfigParser(interpolation=None)
        if ini_path.exists():
            parser.read(ini_path, encoding="utf-8")

        if not parser.has_section("telegram"):
            parser.add_section("telegram")

        if "bot_token" in body:
            parser.set("telegram", "bot_token", f'"{str(body["bot_token"]).strip()}"')
        if "chat_id" in body:
            parser.set("telegram", "chat_id", str(body["chat_id"]).strip())
        if "parse_mode" in body:
            parser.set("telegram", "parse_mode", str(body["parse_mode"]).strip().upper())
        if "enabled" in body:
            parser.set("telegram", "enabled", str(body["enabled"]).lower())

        try:
            with open(ini_path, "w", encoding="utf-8") as f:
                parser.write(f)

            # Reload config
            reloaded = load_config(self.config.base_dir)
            self.config.telegram = reloaded.telegram

            # Re-initialize bot instance if token changed
            if self.config.telegram.bot_token:
                try:
                    self.notifier.bot = Bot(
                        token=self.config.telegram.bot_token,
                        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
                    )
                except Exception as e:
                    logger.warning("Could not instantiate Bot with new token: %s", e)

            return web.json_response({"success": True, "message": "Telegram configuration saved to config.ini"})
        except Exception as e:
            return web.json_response({"success": False, "error": str(e)}, status=500)

    async def api_pause_telegram(self, request: web.Request) -> web.Response:
        """Pause or resume Telegram alert notifications."""
        try:
            body = await request.json()
        except Exception:
            body = {}

        action = str(body.get("action", "pause")).lower()
        if action == "resume":
            self.notifier.resume()
            return web.json_response({"success": True, "message": "Telegram notifications resumed", "is_paused": False})

        try:
            duration = int(body.get("duration_seconds", 3600))
        except (ValueError, TypeError):
            duration = 3600

        until = self.notifier.pause(duration)
        mins = int(duration / 60)
        return web.json_response({
            "success": True,
            "message": f"Telegram notifications paused for {mins} minutes",
            "is_paused": True,
            "pause_remaining_seconds": duration,
            "until": until,
        })

    # --- Webhook & On-Demand Feature APIs ---

    async def api_webhook_notify(self, request: web.Request) -> web.Response:
        """Receive incoming third-party smart home webhook alerts."""
        token = request.headers.get("X-Webhook-Token") or request.query.get("token") or ""
        if self.webhook_feature and not self.webhook_feature.validate_token(token):
            return web.json_response({"success": False, "error": "Unauthorized: Invalid or missing token"}, status=401)

        try:
            body = await request.json()
        except Exception:
            return web.json_response({"success": False, "error": "Invalid JSON body"}, status=400)

        source_ip = request.remote or ""
        if self.webhook_feature:
            res = await self.webhook_feature.ingest_webhook(body, source_ip=source_ip)
            return web.json_response(res)
        return web.json_response({"success": False, "error": "Webhook feature not enabled"}, status=500)

    # --- Flag Half-Staff Monitor APIs ---

    async def api_get_flag_status(self, request: web.Request) -> web.Response:
        """Get full flag status details, active incident, recent incidents, and config."""
        st = self.state.get_flag_status_data()
        fcfg = self.config.get_feature("flag_status")
        
        from home_notifications.features.flag_status import DEFAULT_FLAG_SOURCES
        sources = fcfg.get("sources", DEFAULT_FLAG_SOURCES)
        if isinstance(sources, str):
            try:
                sources = json.loads(sources)
            except Exception:
                sources = DEFAULT_FLAG_SOURCES

        try:
            duration_days = int(fcfg.get("duration_days", 4))
        except (ValueError, TypeError):
            duration_days = 4

        try:
            min_deaths = int(fcfg.get("min_deaths", 1))
        except (ValueError, TypeError):
            min_deaths = 1

        try:
            min_casualties = int(fcfg.get("min_casualties", 1))
        except (ValueError, TypeError):
            min_casualties = 1

        return web.json_response({
            "success": True,
            "state": st,
            "config": {
                "enabled": fcfg.enabled,
                "interval_seconds": fcfg.interval_seconds,
                "notify_mode": fcfg.notify_mode,
                "batch_interval_seconds": fcfg.batch_interval_seconds,
                "duration_days": duration_days,
                "min_deaths": min_deaths,
                "min_casualties": min_casualties,
                "state_filter": str(fcfg.get("state_filter", "")),
                "sources": sources,
            }
        })

    async def api_check_flag(self, request: web.Request) -> web.Response:
        """Trigger an immediate check of Wikipedia flag sources."""
        if not self.flag_feature:
            return web.json_response({"success": False, "error": "Flag feature not initialized"}, status=500)
        try:
            status_text = await self.flag_feature.execute(force=True)
            st = self.state.get_flag_status_data()
            return web.json_response({"success": True, "status": status_text, "state": st})
        except Exception as e:
            logger.error("Error running flag check: %s", e)
            return web.json_response({"success": False, "error": str(e)}, status=500)

    async def api_test_flag_url(self, request: web.Request) -> web.Response:
        """Probe an arbitrary Wikipedia article URL and extract sample incidents."""
        try:
            body = await request.json()
        except Exception:
            body = {}
        url = str(body.get("url", "")).strip()
        if not url:
            return web.json_response({"success": False, "error": "URL parameter is required"}, status=400)

        from home_notifications.features.flag_status import FlagStatusFeature
        res = await FlagStatusFeature.test_url(url)
        return web.json_response(res)

    async def api_check_presence(self, request: web.Request) -> web.Response:
        """Trigger immediate Wi-Fi presence check on household members."""
        if not self.presence_feature:
            return web.json_response({"success": False, "error": "Presence feature not initialized"}, status=500)
        try:
            res = await self.presence_feature.execute()
            return web.json_response({"success": True, "result": res})
        except Exception as e:
            return web.json_response({"success": False, "error": str(e)}, status=500)

    async def api_check_ssl(self, request: web.Request) -> web.Response:
        """Trigger on-demand SSL certificate expiration scan."""
        if not self.ssl_feature:
            return web.json_response({"success": False, "error": "SSL feature not initialized"}, status=500)
        try:
            res = await self.ssl_feature.execute()
            return web.json_response({"success": True, "certificates": res})
        except Exception as e:
            return web.json_response({"success": False, "error": str(e)}, status=500)

    async def api_run_speedtest(self, request: web.Request) -> web.Response:
        """Trigger on-demand internet speed and WAN quality check with optional overrides."""
        if not self.speedtest_feature:
            return web.json_response({"success": False, "error": "Speedtest feature not initialized"}, status=500)
        try:
            body = await request.json()
        except Exception:
            body = {}

        try:
            res = await self.speedtest_feature.execute(override_options=body if body else None)
            if res and res.get("success"):
                hist = self.state.get_speedtest_history()
                if not hist or hist[-1] is not res:
                    self.state.add_speedtest_result(res)
            cmp_data = self.state.get_speedtest_comparison()
            return web.json_response({
                "success": True,
                "result": res,
                "current": cmp_data.get("current"),
                "previous": cmp_data.get("previous"),
                "comparison": cmp_data.get("comparison"),
            })
        except Exception as e:
            logger.error("Failed running speedtest: %s", e, exc_info=True)
            return web.json_response({"success": False, "error": str(e)}, status=500)

    async def api_get_speedtest_results(self, request: web.Request) -> web.Response:
        """Fetch current and previous speedtest results, comparison deltas, and configuration."""
        data = self.state.get_speedtest_comparison()
        fcfg = self.config.get_feature("speedtest")
        return web.json_response({
            "success": True,
            "current": data["current"],
            "previous": data["previous"],
            "comparison": data["comparison"],
            "history": self.state.get_speedtest_history(limit=10),
            "config": {
                "enabled": fcfg.enabled if fcfg else False,
                "provider": fcfg.get("provider", "ookla") if fcfg else "ookla",
                "server_id": fcfg.get("server_id", "") if fcfg else "",
                "server_location": fcfg.get("server_location", "") if fcfg else "",
                "latency_targets": fcfg.get("latency_targets", "1.1.1.1, 8.8.8.8, 9.9.9.9") if fcfg else "1.1.1.1, 8.8.8.8, 9.9.9.9",
                "min_download_mbps": fcfg.get_float("min_download_mbps", 25.0) if fcfg else 25.0,
                "min_upload_mbps": fcfg.get_float("min_upload_mbps", 5.0) if fcfg else 5.0,
                "max_latency_ms": fcfg.get_float("max_latency_ms", 120.0) if fcfg else 120.0,
                "alert_on_degraded": fcfg.get_bool("alert_on_degraded", True) if fcfg else True,
            },
        })

    async def api_get_speedtest_servers(self, request: web.Request) -> web.Response:
        """Discover nearby Ookla speedtest servers."""
        try:
            from home_notifications.features.speedtest import SpeedtestFeature
            servers = await SpeedtestFeature.get_nearby_servers(limit=15)
            return web.json_response({"success": True, "servers": servers})
        except Exception as e:
            logger.warning("Failed discovering speedtest servers: %s", e)
            return web.json_response({"success": False, "error": str(e), "servers": []})

    async def api_check_cisco(self, request: web.Request) -> web.Response:
        """Trigger on-demand Cisco switch SNMP port check."""
        if not self.cisco_feature:
            return web.json_response({"success": False, "error": "Cisco SNMP feature not initialized"}, status=500)
        try:
            res = await self.cisco_feature.execute()
            return web.json_response({"success": True, "result": res})
        except Exception as e:
            return web.json_response({"success": False, "error": str(e)}, status=500)

    async def api_check_ups(self, request: web.Request) -> web.Response:
        """Trigger on-demand UPS power status check."""
        if not self.ups_feature:
            return web.json_response({"success": False, "error": "UPS feature not initialized"}, status=500)
        try:
            res = await self.ups_feature.execute()
            return web.json_response({"success": True, "result": res})
        except Exception as e:
            return web.json_response({"success": False, "error": str(e)}, status=500)

    async def api_check_night_owl(self, request: web.Request) -> web.Response:
        """Trigger on-demand Night Owl quiet hours activity check."""
        if not self.night_owl_feature:
            return web.json_response({"success": False, "error": "Night owl feature not initialized"}, status=500)
        try:
            res = await self.night_owl_feature.execute()
            return web.json_response({"success": True, "result": res})
        except Exception as e:
            return web.json_response({"success": False, "error": str(e)}, status=500)

    async def api_flush_notifications(self, request: web.Request) -> web.Response:
        """Flush batched Telegram notifications."""
        count = await self.notifier.flush_batches()
        return web.json_response({"success": True, "count": count})

    async def api_test_notification(self, request: web.Request) -> web.Response:
        """Send a test message to Telegram chat."""
        try:
            body = await request.json()
        except Exception:
            body = {}
        msg = body.get("message", "This is a test notification from the HomeNotifications Management UI!")
        success = await self.notifier.send_immediate(
            category="system",
            title="Test Notification",
            message=msg,
            level="INFO",
        )
        return web.json_response({"success": success})

    async def start(self) -> None:
        """Start listening on web_host and web_port."""
        host = self.config.system.web_host
        port = self.config.system.web_port
        self.runner = web.AppRunner(self.app)
        await self.runner.setup()
        self.site = web.TCPSite(self.runner, host, port)
        await self.site.start()
        logger.info("Management UI listening on http://%s:%d", host, port)

    async def stop(self) -> None:
        """Stop the web server."""
        if hasattr(self, "auth_manager"):
            await self.auth_manager.close()
        if self.runner:
            await self.runner.cleanup()
            logger.info("Management UI server stopped.")
