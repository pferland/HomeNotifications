"""Configuration loader for HomeNotifications.

Loads settings from config.ini (Telegram, system, and feature settings)
and devices.yaml (monitored device inventory and their properties).
"""

from __future__ import annotations

import configparser
import json
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional
import yaml

logger = logging.getLogger(__name__)


@dataclass
class OIDCConfig:
    enabled: bool = False
    issuer_url: str = ""
    client_id: str = ""
    client_secret: str = ""
    redirect_uri: str = ""
    scopes: List[str] = field(default_factory=lambda: ["openid", "profile", "email"])
    authorization_endpoint: str = ""
    token_endpoint: str = ""
    jwks_uri: str = ""
    userinfo_endpoint: str = ""
    end_session_endpoint: str = ""
    session_secret: str = ""
    cookie_name: str = "hn_session"
    cookie_secure: bool = False
    cookie_max_age: int = 86400
    api_tokens: List[str] = field(default_factory=list)
    allowed_emails: List[str] = field(default_factory=list)
    allowed_groups: List[str] = field(default_factory=list)
    roles_claim: str = "groups"


@dataclass
class TelegramConfig:
    bot_token: str
    chat_id: int | str
    admin_ids: List[int | str] = field(default_factory=list)
    parse_mode: str = "HTML"
    enabled: bool = True


@dataclass
class SystemConfig:
    devices_file: str = "devices.yaml"
    state_file: str = "data/state.json"
    log_level: str = "INFO"
    web_enabled: bool = True
    web_host: str = "0.0.0.0"
    web_port: int = 8085


@dataclass
class FeatureConfig:
    name: str
    enabled: bool = True
    interval_seconds: int = 300
    notify_mode: str = "on_change"  # immediate, batched, on_change, periodic, never
    batch_interval_seconds: int = 300
    options: Dict[str, Any] = field(default_factory=dict)

    def get(self, key: str, default: Any = None) -> Any:
        return self.options.get(key, default)

    def get_bool(self, key: str, default: bool = False) -> bool:
        val = self.options.get(key, default)
        if isinstance(val, bool):
            return val
        if isinstance(val, str):
            return val.lower() in ("true", "1", "yes", "on")
        return bool(val)

    def get_int(self, key: str, default: int = 0) -> int:
        val = self.options.get(key, default)
        try:
            return int(val)
        except (ValueError, TypeError):
            return default

    def get_float(self, key: str, default: float = 0.0) -> float:
        val = self.options.get(key, default)
        try:
            return float(val)
        except (ValueError, TypeError):
            return default


@dataclass
class ServiceCheckConfig:
    name: str
    type: str = "tcp"  # tcp, http, https, udp, systemd
    port: int = 80
    path: str = "/"
    expected_status: int = 200
    timeout: float = 3.0
    hostname: str = ""
    check_ssl: bool = False
    options: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SSHMonitorConfig:
    enabled: bool = False
    port: int = 22
    username: str = ""
    key_path: Optional[str] = None
    password: Optional[str] = None
    timeout: float = 8.0
    cpu_warning_percent: float = 85.0
    memory_warning_percent: float = 90.0
    disk_warning_percent: float = 85.0
    disk_mounts: List[str] = field(default_factory=lambda: ["/"])
    systemd_services: List[str] = field(default_factory=list)
    auth_log_path: str = "/var/log/auth.log"
    check_failed_logins: bool = True
    failed_login_threshold: int = 3


@dataclass
class SNMPMonitorConfig:
    enabled: bool = False
    port: int = 161
    community: str = "public"
    version: str = "2c"
    timeout: float = 3.0
    oids: Dict[str, str] = field(default_factory=dict)


@dataclass
class PrometheusMonitorConfig:
    enabled: bool = False
    url: str = "http://localhost:9100/metrics"
    timeout: float = 5.0
    alerts: Dict[str, float] = field(default_factory=dict)


@dataclass
class DeviceConfig:
    id: str
    name: str
    ip: str
    mac: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    ping_enabled: bool = True
    ping_timeout: float = 2.0
    services: List[ServiceCheckConfig] = field(default_factory=list)
    ssh: Optional[SSHMonitorConfig] = None
    snmp: Optional[SNMPMonitorConfig] = None
    prometheus: Optional[PrometheusMonitorConfig] = None
    properties: Dict[str, Any] = field(default_factory=dict)


class AppConfig:
    """Master configuration class holding Telegram, system, features, and devices."""

    def __init__(
        self,
        base_dir: Path,
        telegram: TelegramConfig,
        system: SystemConfig,
        features: Dict[str, FeatureConfig],
        devices: Dict[str, DeviceConfig],
        auth: Optional[OIDCConfig] = None,
    ):
        self.base_dir = base_dir
        self.telegram = telegram
        self.system = system
        self.features = features
        self.devices = devices
        self.auth = auth if auth is not None else OIDCConfig()

    def get_feature(self, name: str) -> FeatureConfig:
        return self.features.get(
            name, FeatureConfig(name=name, enabled=False, interval_seconds=300)
        )

    def is_feature_enabled(self, name: str) -> bool:
        feature = self.features.get(name)
        return bool(feature and feature.enabled)

    def get_state_path(self) -> Path:
        state_file = self.system.state_file
        path = Path(state_file)
        if not path.is_absolute():
            path = self.base_dir / path
        path.parent.mkdir(parents=True, exist_ok=True)
        return path


def load_config(base_path: Optional[str | Path] = None) -> AppConfig:
    """Load config.ini and devices.yaml from base_path (or project directory)."""
    if base_path is None:
        base_dir = Path(__file__).resolve().parent.parent
    else:
        base_dir = Path(base_path).resolve()

    ini_path = base_dir / "config.ini"
    if not ini_path.exists():
        ini_sample = base_dir / "config.ini.sample"
        if ini_sample.exists():
            logger.warning(
                "config.ini not found, loading from sample %s", ini_sample
            )
            ini_path = ini_sample

    parser = configparser.ConfigParser(interpolation=None)
    if ini_path.exists():
        parser.read(ini_path, encoding="utf-8")

    # 1. Telegram config (support both [telegram] and legacy [DEFAULT])
    token = ""
    chat_id = 0
    admin_ids: List[int | str] = []
    parse_mode = "HTML"
    telegram_enabled = True

    if parser.has_section("telegram"):
        t_sec = parser["telegram"]
        token = t_sec.get("bot_token", "").strip('"\'')
        chat_id = t_sec.get("chat_id", "0").strip('"\'')
        admin_raw = t_sec.get("admin_ids", "").strip()
        if admin_raw:
            admin_ids = [a.strip() for a in admin_raw.split(",") if a.strip()]
        parse_mode = t_sec.get("parse_mode", "HTML").strip('"\'')
        telegram_enabled = t_sec.getboolean("enabled", fallback=True)

    # Fallback to [DEFAULT] section
    if not token and "DEFAULT" in parser:
        token = parser["DEFAULT"].get("TOKEN", "").strip('"\'')
    if not chat_id and "DEFAULT" in parser:
        chat_id = parser["DEFAULT"].get("CHATID", "0").strip('"\'')
    if "DEFAULT" in parser and "ENABLED" in parser["DEFAULT"]:
        telegram_enabled = parser["DEFAULT"].getboolean("ENABLED", fallback=telegram_enabled)

    try:
        chat_id_int = int(chat_id)
        chat_id_val: int | str = chat_id_int
    except (ValueError, TypeError):
        chat_id_val = str(chat_id)

    telegram_cfg = TelegramConfig(
        bot_token=token,
        chat_id=chat_id_val,
        admin_ids=admin_ids,
        parse_mode=parse_mode,
        enabled=telegram_enabled,
    )

    # 2. System config
    devices_file = "devices.yaml"
    state_file = "data/state.json"
    log_level = "INFO"
    web_enabled = True
    web_host = "0.0.0.0"
    web_port = 8085
    if parser.has_section("system"):
        s_sec = parser["system"]
        devices_file = s_sec.get("devices_file", devices_file).strip('"\'')
        state_file = s_sec.get("state_file", state_file).strip('"\'')
        log_level = s_sec.get("log_level", log_level).strip('"\'').upper()
        web_enabled = s_sec.getboolean("web_enabled", fallback=web_enabled)
        web_host = s_sec.get("web_host", web_host).strip('"\'')
        web_port = s_sec.getint("web_port", fallback=web_port)

    system_cfg = SystemConfig(
        devices_file=devices_file,
        state_file=state_file,
        log_level=log_level,
        web_enabled=web_enabled,
        web_host=web_host,
        web_port=web_port,
    )

    # 3. Features config
    default_features: Dict[str, Dict[str, Any]] = {
        "external_ip": {
            "enabled": True,
            "interval_seconds": 21600,
            "notify_mode": "on_change",
            "batch_interval_seconds": 3600,
        },
        "flag_status": {
            "enabled": True,
            "interval_seconds": 21600,
            "notify_mode": "on_change",
            "batch_interval_seconds": 3600,
            "duration_days": 4,
            "min_deaths": 1,
            "min_casualties": 1,
            "state_filter": "",
            "sources": json.dumps([
                {
                    "id": "school_shootings_2020s",
                    "name": "US School Shootings (2020s)",
                    "url": "https://en.wikipedia.org/wiki/List_of_school_shootings_in_the_United_States_(2020s)",
                    "enabled": True,
                },
                {
                    "id": "school_shootings_2000s",
                    "name": "US School Shootings (2000–present)",
                    "url": "https://en.wikipedia.org/wiki/List_of_school_shootings_in_the_United_States_(2000%E2%80%93present)",
                    "enabled": True,
                },
            ]),
        },
        "photolevel": {
            "enabled": False,
            "interval_seconds": 3600,
            "notify_mode": "periodic",
            "batch_interval_seconds": 3600,
        },
        "network_discovery": {
            "enabled": True,
            "interval_seconds": 300,
            "notify_mode": "immediate",
            "batch_interval_seconds": 300,
            "subnets": "auto",
            "alert_new_device": True,
            "alert_device_offline": False,
            "offline_threshold_seconds": 1800,
        },
        "device_monitor": {
            "enabled": True,
            "interval_seconds": 60,
            "notify_mode": "on_change",
            "batch_interval_seconds": 300,
            "alert_on_down": True,
            "alert_on_recovery": True,
            "cooldown_seconds": 3600,
        },
        "access_logs": {
            "enabled": True,
            "interval_seconds": 120,
            "notify_mode": "immediate",
            "batch_interval_seconds": 300,
            "failed_login_threshold": 3,
        },
        "presence": {
            "enabled": True,
            "interval_seconds": 60,
            "notify_mode": "immediate",
            "batch_interval_seconds": 300,
            "alert_arrival": True,
            "alert_departure": True,
            "away_threshold_seconds": 900,
            "members": "Paul:dc:a6:32:5c:27:2a",
        },
        "ssl_cert": {
            "enabled": True,
            "interval_seconds": 86400,
            "notify_mode": "on_change",
            "batch_interval_seconds": 3600,
            "warning_days": 14,
            "critical_days": 3,
            "alert_expired": True,
            "alert_expiring_soon": True,
            "custom_targets": "",
        },
        "webhooks": {
            "enabled": True,
            "interval_seconds": 300,
            "notify_mode": "immediate",
            "batch_interval_seconds": 300,
            "api_key": "homenotify-secret-key",
            "allow_unauthenticated": False,
        },
        "speedtest": {
            "enabled": False,
            "interval_seconds": 21600,
            "notify_mode": "on_change",
            "batch_interval_seconds": 3600,
            "provider": "ookla",
            "server_id": "",
            "server_location": "",
            "latency_targets": "1.1.1.1, 8.8.8.8, 9.9.9.9",
            "min_download_mbps": 25.0,
            "min_upload_mbps": 5.0,
            "max_latency_ms": 120.0,
            "alert_on_degraded": True,
        },
        "cisco_snmp": {
            "enabled": True,
            "interval_seconds": 120,
            "notify_mode": "on_change",
            "batch_interval_seconds": 300,
            "device_id": "core-switch",
            "alert_link_down": True,
            "alert_port_saturation": True,
            "saturation_threshold_mbps": 100.0,
            "monitored_ports": "all",
        },
        "ups_monitor": {
            "enabled": False,
            "interval_seconds": 60,
            "notify_mode": "immediate",
            "batch_interval_seconds": 300,
            "ups_type": "probe",
            "host": "127.0.0.1",
            "port": 3493,
            "alert_on_battery": True,
            "alert_low_battery": True,
            "alert_power_restored": True,
            "low_battery_percent": 25,
            "probe_host": "192.168.1.1",
        },
        "night_owl": {
            "enabled": False,
            "interval_seconds": 300,
            "notify_mode": "immediate",
            "batch_interval_seconds": 300,
            "quiet_start": "01:00",
            "quiet_end": "05:30",
            "monitored_tags": "kids,console,entertainment",
            "monitored_macs": "",
            "alert_active": True,
            "cooldown_minutes": 60,
        },
    }

    features_cfg: Dict[str, FeatureConfig] = {}
    for feat_name, def_vals in default_features.items():
        sec_name = f"feature:{feat_name}"
        if parser.has_section(sec_name):
            sec = parser[sec_name]
            enabled = sec.getboolean("enabled", fallback=def_vals["enabled"])
            interval = sec.getint("interval_seconds", fallback=sec.getint("interval", fallback=def_vals["interval_seconds"]))
            notify_mode = sec.get("notify_mode", fallback=def_vals["notify_mode"]).strip().lower()
            batch_interval = sec.getint("batch_interval_seconds", fallback=sec.getint("batch_interval", fallback=def_vals["batch_interval_seconds"]))
            
            # collect remaining options (ignoring DEFAULT section items like token and chatid)
            sec_dict = parser._sections.get(sec_name, {}) if hasattr(parser, "_sections") else sec
            options = {
                k: v
                for k, v in sec_dict.items()
                if k not in (
                    "enabled",
                    "interval",
                    "interval_seconds",
                    "notify_mode",
                    "batch_interval",
                    "batch_interval_seconds",
                    "token",
                    "chatid",
                    "chat_id",
                    "bot_token",
                )
            }
            # Merge with default non-standard keys
            for k, v in def_vals.items():
                if k not in ("enabled", "interval_seconds", "notify_mode", "batch_interval_seconds") and k not in options:
                    options[k] = v
                    
            features_cfg[feat_name] = FeatureConfig(
                name=feat_name,
                enabled=enabled,
                interval_seconds=interval,
                notify_mode=notify_mode,
                batch_interval_seconds=batch_interval,
                options=options,
            )
        else:
            feat_opts = {k: v for k, v in def_vals.items() if k not in ("enabled", "interval_seconds", "notify_mode", "batch_interval_seconds")}
            features_cfg[feat_name] = FeatureConfig(
                name=feat_name,
                enabled=def_vals["enabled"],
                interval_seconds=def_vals["interval_seconds"],
                notify_mode=def_vals["notify_mode"],
                batch_interval_seconds=def_vals["batch_interval_seconds"],
                options=feat_opts,
            )

    # 4. Auth (OIDC) config
    auth_enabled = False
    issuer_url = ""
    client_id = ""
    client_secret = ""
    redirect_uri = ""
    scopes = ["openid", "profile", "email"]
    authorization_endpoint = ""
    token_endpoint = ""
    jwks_uri = ""
    userinfo_endpoint = ""
    end_session_endpoint = ""
    session_secret = ""
    cookie_name = "hn_session"
    cookie_secure = False
    cookie_max_age = 86400
    api_tokens: List[str] = []
    allowed_emails: List[str] = []
    allowed_groups: List[str] = []
    roles_claim = "groups"

    if parser.has_section("auth"):
        a_sec = parser["auth"]
        auth_enabled = a_sec.getboolean("enabled", fallback=False)
        issuer_url = a_sec.get("issuer_url", "").strip('"\'')
        client_id = a_sec.get("client_id", "").strip('"\'')
        client_secret = a_sec.get("client_secret", "").strip('"\'')
        redirect_uri = a_sec.get("redirect_uri", "").strip('"\'')
        scopes_raw = a_sec.get("scopes", "openid,profile,email").strip()
        if scopes_raw:
            scopes = [s.strip() for s in scopes_raw.split(",") if s.strip()]
        authorization_endpoint = a_sec.get("authorization_endpoint", "").strip('"\'')
        token_endpoint = a_sec.get("token_endpoint", "").strip('"\'')
        jwks_uri = a_sec.get("jwks_uri", "").strip('"\'')
        userinfo_endpoint = a_sec.get("userinfo_endpoint", "").strip('"\'')
        end_session_endpoint = a_sec.get("end_session_endpoint", "").strip('"\'')
        session_secret = a_sec.get("session_secret", "").strip('"\'')
        cookie_name = a_sec.get("cookie_name", "hn_session").strip('"\'')
        cookie_secure = a_sec.getboolean("cookie_secure", fallback=False)
        cookie_max_age = a_sec.getint("cookie_max_age", fallback=86400)

        api_tokens_raw = a_sec.get("api_tokens", "").strip()
        if api_tokens_raw:
            api_tokens = [t.strip() for t in api_tokens_raw.split(",") if t.strip()]

        allowed_emails_raw = a_sec.get("allowed_emails", "").strip()
        if allowed_emails_raw:
            allowed_emails = [e.strip().lower() for e in allowed_emails_raw.split(",") if e.strip()]

        allowed_groups_raw = a_sec.get("allowed_groups", "").strip()
        if allowed_groups_raw:
            allowed_groups = [g.strip() for g in allowed_groups_raw.split(",") if g.strip()]

        roles_claim = a_sec.get("roles_claim", "groups").strip('"\'')

    auth_cfg = OIDCConfig(
        enabled=auth_enabled,
        issuer_url=issuer_url,
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri=redirect_uri,
        scopes=scopes,
        authorization_endpoint=authorization_endpoint,
        token_endpoint=token_endpoint,
        jwks_uri=jwks_uri,
        userinfo_endpoint=userinfo_endpoint,
        end_session_endpoint=end_session_endpoint,
        session_secret=session_secret,
        cookie_name=cookie_name,
        cookie_secure=cookie_secure,
        cookie_max_age=cookie_max_age,
        api_tokens=api_tokens,
        allowed_emails=allowed_emails,
        allowed_groups=allowed_groups,
        roles_claim=roles_claim,
    )

    # 5. Devices config (from YAML)
    dev_path = base_dir / devices_file
    if not dev_path.exists():
        sample_dev = base_dir / f"{devices_file}.sample"
        if sample_dev.exists():
            dev_path = sample_dev

    devices_cfg = load_devices_yaml(dev_path)

    return AppConfig(
        base_dir=base_dir,
        telegram=telegram_cfg,
        system=system_cfg,
        features=features_cfg,
        devices=devices_cfg,
        auth=auth_cfg,
    )


def load_devices_yaml(yaml_path: Path) -> Dict[str, DeviceConfig]:
    """Parse devices.yaml into a dictionary of DeviceConfig objects keyed by device ID."""
    devices: Dict[str, DeviceConfig] = {}
    if not yaml_path.exists():
        logger.debug("Devices file not found at %s", yaml_path)
        return devices

    try:
        with open(yaml_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except Exception as e:
        logger.error("Failed to parse devices yaml file %s: %s", yaml_path, e)
        return devices

    if not isinstance(data, dict) or "devices" not in data:
        logger.warning("devices.yaml root must be a dict with a 'devices' list")
        return devices

    raw_devices = data.get("devices", [])
    if not isinstance(raw_devices, list):
        return devices

    for raw in raw_devices:
        if not isinstance(raw, dict):
            continue
        dev_id = str(raw.get("id", "")).strip()
        if not dev_id:
            continue

        name = raw.get("name", dev_id)
        ip = raw.get("ip", "")
        mac = raw.get("mac")
        if mac:
            mac = str(mac).strip().lower()
        tags = raw.get("tags", [])
        if not isinstance(tags, list):
            tags = [str(tags)]

        monitors = raw.get("monitors", {})
        if not isinstance(monitors, dict):
            monitors = {}

        # Ping monitor
        ping_cfg = monitors.get("ping", {})
        ping_enabled = ping_cfg.get("enabled", True) if isinstance(ping_cfg, dict) else bool(ping_cfg)
        ping_timeout = float(ping_cfg.get("timeout", 2.0)) if isinstance(ping_cfg, dict) else 2.0

        # Services
        services_list: List[ServiceCheckConfig] = []
        raw_services = monitors.get("services", [])
        if isinstance(raw_services, list):
            for s in raw_services:
                if isinstance(s, dict) and "name" in s:
                    stype = str(s.get("type", "tcp")).lower()
                    port_val = int(s.get("port", 80))
                    default_check_ssl = (stype == "https" or port_val == 443)
                    services_list.append(
                        ServiceCheckConfig(
                            name=str(s.get("name")),
                            type=stype,
                            port=port_val,
                            path=str(s.get("path", "/")),
                            expected_status=int(s.get("expected_status", 200)),
                            timeout=float(s.get("timeout", 3.0)),
                            hostname=str(s.get("hostname", "")).strip(),
                            check_ssl=bool(s.get("check_ssl", default_check_ssl)),
                            options={k: v for k, v in s.items() if k not in ("name", "type", "port", "path", "expected_status", "timeout", "hostname", "check_ssl")},
                        )
                    )

        # SSH monitor
        ssh_cfg: Optional[SSHMonitorConfig] = None
        raw_ssh = monitors.get("ssh")
        if isinstance(raw_ssh, dict) and raw_ssh.get("enabled", False):
            res = raw_ssh.get("resources", {})
            acc = raw_ssh.get("access_logs", {})
            ssh_cfg = SSHMonitorConfig(
                enabled=True,
                port=int(raw_ssh.get("port", 22)),
                username=str(raw_ssh.get("username", "")),
                key_path=raw_ssh.get("key_path"),
                password=raw_ssh.get("password"),
                timeout=float(raw_ssh.get("timeout", 8.0)),
                cpu_warning_percent=float(res.get("cpu_warning_percent", 85.0)),
                memory_warning_percent=float(res.get("memory_warning_percent", 90.0)),
                disk_warning_percent=float(res.get("disk_warning_percent", 85.0)),
                disk_mounts=res.get("disk_mounts", ["/"]),
                systemd_services=raw_ssh.get("systemd_services", []),
                auth_log_path=str(acc.get("auth_log_path", "/var/log/auth.log")),
                check_failed_logins=bool(acc.get("check_failed_logins", True)),
                failed_login_threshold=int(acc.get("failed_login_threshold", 3)),
            )

        # SNMP monitor
        snmp_cfg: Optional[SNMPMonitorConfig] = None
        raw_snmp = monitors.get("snmp")
        if isinstance(raw_snmp, dict) and raw_snmp.get("enabled", False):
            snmp_cfg = SNMPMonitorConfig(
                enabled=True,
                port=int(raw_snmp.get("port", 161)),
                community=str(raw_snmp.get("community", "public")),
                version=str(raw_snmp.get("version", "2c")),
                timeout=float(raw_snmp.get("timeout", 3.0)),
                oids=raw_snmp.get("oids", {}),
            )

        # Prometheus monitor
        prom_cfg: Optional[PrometheusMonitorConfig] = None
        raw_prom = monitors.get("prometheus")
        if isinstance(raw_prom, dict) and raw_prom.get("enabled", False):
            prom_cfg = PrometheusMonitorConfig(
                enabled=True,
                url=str(raw_prom.get("url", f"http://{ip}:9100/metrics")),
                timeout=float(raw_prom.get("timeout", 5.0)),
                alerts=raw_prom.get("alerts", {}),
            )

        # Custom user-defined properties
        properties = {
            k: v
            for k, v in raw.items()
            if k not in ("id", "name", "ip", "mac", "tags", "monitors")
        }

        devices[dev_id] = DeviceConfig(
            id=dev_id,
            name=name,
            ip=ip,
            mac=mac,
            tags=tags,
            ping_enabled=ping_enabled,
            ping_timeout=ping_timeout,
            services=services_list,
            ssh=ssh_cfg,
            snmp=snmp_cfg,
            prometheus=prom_cfg,
            properties=properties,
        )

    return devices
