"""Unit tests for features execution and discovery."""

import pytest
from unittest.mock import AsyncMock, MagicMock
from pathlib import Path

from home_notifications.config import AppConfig, DeviceConfig, FeatureConfig, SystemConfig, TelegramConfig
from home_notifications.discovery import DiscoveredHost, NetworkScanner
from home_notifications.features.device_monitor import DeviceMonitorFeature
from home_notifications.features.discovery import NetworkDiscoveryFeature
from home_notifications.notifier import NotificationDispatcher
from home_notifications.state import StateManager


def test_mac_oui_lookup():
    vendor = NetworkScanner.lookup_vendor("b8:27:eb:11:22:33")
    assert "Raspberry Pi" in vendor

    vendor_apple = NetworkScanner.lookup_vendor("dc:4f:22:aa:bb:cc")
    assert "Apple" in vendor_apple

    vendor_unknown = NetworkScanner.lookup_vendor("02:00:00:00:00:00")
    assert vendor_unknown == ""


@pytest.mark.asyncio
async def test_network_discovery_alert_trigger(tmp_path: Path):
    telegram_cfg = TelegramConfig(bot_token="test-token", chat_id=123456)
    system_cfg = SystemConfig(state_file=str(tmp_path / "state.json"))
    features = {
        "network_discovery": FeatureConfig(
            name="network_discovery",
            enabled=True,
            interval_seconds=60,
            notify_mode="immediate",
            options={"alert_new_device": True},
        ),
    }
    config = AppConfig(
        base_dir=tmp_path,
        telegram=telegram_cfg,
        system=system_cfg,
        features=features,
        devices={},
    )
    state = StateManager(tmp_path / "state.json")
    mock_bot = MagicMock()
    mock_bot.send_message = AsyncMock(return_value=True)
    notifier = NotificationDispatcher(mock_bot, config, state)

    disc_feat = NetworkDiscoveryFeature(config, state, notifier)

    # Mock scanner.scan to return a discovered host
    disc_feat.scanner.scan = AsyncMock(
        return_value=[
            DiscoveredHost(
                ip="192.168.1.99",
                mac="b8:27:eb:aa:bb:cc",
                hostname="new-pi.local",
                vendor="Raspberry Pi Foundation",
            )
        ]
    )

    hosts = await disc_feat.execute()
    assert len(hosts) == 1
    mock_bot.send_message.assert_called_once()
    assert "b8:27:eb:aa:bb:cc" in state.get_known_devices()

    # Second run with same host should NOT trigger a new alert
    mock_bot.send_message.reset_mock()
    hosts2 = await disc_feat.execute()
    assert len(hosts2) == 1
    mock_bot.send_message.assert_not_called()


@pytest.mark.asyncio
async def test_presence_feature(tmp_path: Path):
    from home_notifications.features.presence import PresenceFeature
    import time

    telegram_cfg = TelegramConfig(bot_token="test-token", chat_id=123456)
    system_cfg = SystemConfig(state_file=str(tmp_path / "state.json"))
    features = {
        "presence": FeatureConfig(
            name="presence",
            enabled=True,
            interval_seconds=60,
            notify_mode="immediate",
            options={
                "alert_arrival": True,
                "alert_departure": True,
                "away_threshold_seconds": 300,
                "members": "Paul:aa:bb:cc:dd:ee:ff",
            },
        ),
    }
    config = AppConfig(
        base_dir=tmp_path,
        telegram=telegram_cfg,
        system=system_cfg,
        features=features,
        devices={},
    )
    state = StateManager(tmp_path / "state.json")
    mock_bot = MagicMock()
    mock_bot.send_message = AsyncMock(return_value=True)
    notifier = NotificationDispatcher(mock_bot, config, state)

    presence = PresenceFeature(config, state, notifier)

    # Initially Paul is AWAY
    state.get_presence_state()["Paul"] = {"name": "Paul", "status": "AWAY", "last_seen": 0}

    # Now Paul's device appears online in ARP table
    state.register_or_update_device(mac="aa:bb:cc:dd:ee:ff", ip="192.168.1.105")

    res = await presence.execute()
    assert res["Paul"]["status"] == "HOME"
    mock_bot.send_message.assert_called_once()
    assert "Paul" in mock_bot.send_message.call_args[1]["text"]


@pytest.mark.asyncio
async def test_webhook_feature(tmp_path: Path):
    from home_notifications.features.webhooks import WebhookFeature

    telegram_cfg = TelegramConfig(bot_token="test-token", chat_id=123456)
    system_cfg = SystemConfig(state_file=str(tmp_path / "state.json"))
    features = {
        "webhooks": FeatureConfig(
            name="webhooks",
            enabled=True,
            options={"api_key": "my-secret-key", "allow_unauthenticated": False},
        ),
    }
    config = AppConfig(
        base_dir=tmp_path,
        telegram=telegram_cfg,
        system=system_cfg,
        features=features,
        devices={},
    )
    state = StateManager(tmp_path / "state.json")
    mock_bot = MagicMock()
    mock_bot.send_message = AsyncMock(return_value=True)
    notifier = NotificationDispatcher(mock_bot, config, state)

    wh = WebhookFeature(config, state, notifier)

    assert wh.validate_token("wrong-key") is False
    assert wh.validate_token("my-secret-key") is True

    # Ingest payload
    res = await wh.ingest_webhook({"title": "Front Door", "message": "Door opened", "level": "WARNING"})
    assert res["success"] is True
    assert len(state.get_webhook_logs()) == 1
    mock_bot.send_message.assert_called_once()
    assert "Front Door" in mock_bot.send_message.call_args[1]["text"]


def test_night_owl_time_check():
    from home_notifications.features.night_owl import NightOwlFeature

    assert NightOwlFeature.is_in_quiet_hours("00:00", "23:59") is True
    # If same time or invalid
    assert isinstance(NightOwlFeature.is_in_quiet_hours("01:00", "05:00"), bool)


@pytest.mark.asyncio
async def test_ssl_cert_feature(tmp_path: Path):
    from home_notifications.features.ssl_cert import SSLCertFeature

    telegram_cfg = TelegramConfig(bot_token="test-token", chat_id=123456)
    system_cfg = SystemConfig(state_file=str(tmp_path / "state.json"))
    features = {
        "ssl_cert": FeatureConfig(
            name="ssl_cert",
            enabled=True,
            options={"warning_days": 14, "alert_expiring_soon": True, "custom_targets": "test.local:443"},
        ),
    }
    config = AppConfig(base_dir=tmp_path, telegram=telegram_cfg, system=system_cfg, features=features, devices={})
    state = StateManager(tmp_path / "state.json")
    mock_bot = MagicMock()
    mock_bot.send_message = AsyncMock(return_value=True)
    notifier = NotificationDispatcher(mock_bot, config, state)

    ssl_feat = SSLCertFeature(config, state, notifier)
    # Mock synchronous cert check
    ssl_feat._check_cert_sync = MagicMock(return_value={
        "success": True,
        "host": "test.local",
        "port": 443,
        "days_left": 5,
        "expiry_date": "2026-11-02",
        "subject": "test.local",
        "issuer": "Let's Encrypt",
        "expired": False,
    })

    results = await ssl_feat.execute()
    assert len(results) == 1
    assert results[0]["days_left"] == 5
    mock_bot.send_message.assert_called_once()
    assert "Expiring Soon" in mock_bot.send_message.call_args[1]["text"]


@pytest.mark.asyncio
async def test_ups_monitor_feature(tmp_path: Path):
    from home_notifications.features.ups_monitor import UPSMonitorFeature

    telegram_cfg = TelegramConfig(bot_token="test-token", chat_id=123456)
    system_cfg = SystemConfig(state_file=str(tmp_path / "state.json"))
    features = {
        "ups_monitor": FeatureConfig(
            name="ups_monitor",
            enabled=True,
            options={"alert_on_battery": True, "ups_type": "probe"},
        ),
    }
    config = AppConfig(base_dir=tmp_path, telegram=telegram_cfg, system=system_cfg, features=features, devices={})
    state = StateManager(tmp_path / "state.json")
    mock_bot = MagicMock()
    mock_bot.send_message = AsyncMock(return_value=True)
    notifier = NotificationDispatcher(mock_bot, config, state)

    ups_feat = UPSMonitorFeature(config, state, notifier)

    # Mock power probe reporting on battery
    ups_feat._query_power_probe = AsyncMock(return_value={
        "online": False,
        "battery_percent": 85,
        "status": "ONBATT",
        "runtime_mins": 30,
    })

    res = await ups_feat.execute()
    assert res["status"] == "ONBATT"
    mock_bot.send_message.assert_called_once()
    assert "Power Outage Detected" in mock_bot.send_message.call_args[1]["text"]


@pytest.mark.asyncio
async def test_speedtest_degradation_alert(tmp_path: Path):
    from home_notifications.features.speedtest import SpeedtestFeature

    telegram_cfg = TelegramConfig(bot_token="test-token", chat_id=123456)
    system_cfg = SystemConfig(state_file=str(tmp_path / "state.json"))
    features = {
        "speedtest": FeatureConfig(
            name="speedtest",
            enabled=True,
            options={"min_download_mbps": 50.0, "max_latency_ms": 100.0, "alert_on_degraded": True},
        ),
    }
    config = AppConfig(base_dir=tmp_path, telegram=telegram_cfg, system=system_cfg, features=features, devices={})
    state = StateManager(tmp_path / "state.json")
    mock_bot = MagicMock()
    mock_bot.send_message = AsyncMock(return_value=True)
    notifier = NotificationDispatcher(mock_bot, config, state)

    st_feat = SpeedtestFeature(config, state, notifier)
    st_feat.run_throughput_test = AsyncMock(return_value={
        "success": True,
        "latency_ms": 160.0,  # Laggy (>100)
        "download_mbps": 12.0,  # Slow (<50)
        "bytes_tested": 1000000,
        "duration_sec": 1.0,
    })

    res = await st_feat.execute()
    assert res["success"] is True
    mock_bot.send_message.assert_called_once()
    assert "Degradation" in mock_bot.send_message.call_args[1]["text"]


def test_flag_date_and_count_parsers():
    from home_notifications.features.flag_status import parse_date_string, parse_int_count
    from datetime import datetime

    dt1 = parse_date_string("October 24, 2026")
    assert dt1 == datetime(2026, 10, 24)

    dt2 = parse_date_string("Oct 24, 2026[3]")
    assert dt2 == datetime(2026, 10, 24)

    dt3 = parse_date_string("2026-10-24")
    assert dt3 == datetime(2026, 10, 24)

    dt4 = parse_date_string("October 24–25, 2026")
    assert dt4 is not None
    assert dt4.year == 2026

    assert parse_int_count("4[note 1]") == 4
    assert parse_int_count("none") == 0
    assert parse_int_count("-") == 0
    assert parse_int_count(12) == 12


def test_flag_wikipedia_table_extraction():
    from bs4 import BeautifulSoup
    from datetime import datetime
    from home_notifications.features.flag_status import extract_incidents_from_soup

    html = """
    <html>
      <body>
        <table class="wikitable">
          <thead>
            <tr>
              <th>Date</th>
              <th>Location</th>
              <th>Deaths</th>
              <th>Injuries</th>
              <th>Total</th>
              <th>Description</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td>October 20, 2026</td>
              <td>Austin, Texas</td>
              <td>2[1]</td>
              <td>3</td>
              <td>5</td>
              <td>Shooting incident at university campus.</td>
            </tr>
            <tr>
              <td>October 10, 2026</td>
              <td>Miami, Florida</td>
              <td>0</td>
              <td>1</td>
              <td>1</td>
              <td>Accidental discharge in parking lot.</td>
            </tr>
          </tbody>
        </table>
      </body>
    </html>
    """
    soup = BeautifulSoup(html, "lxml")
    today = datetime(2026, 10, 22)
    incidents = extract_incidents_from_soup(soup, "Test Source", "https://wiki.example/test", today=today)

    assert len(incidents) == 2
    # Incidents parsed in order
    tx = next(i for i in incidents if "Texas" in i["location"])
    assert tx["dead"] == 2
    assert tx["injured"] == 3
    assert tx["total"] == 5
    assert tx["days_ago"] == 2  # Oct 22 - Oct 20


@pytest.mark.asyncio
async def test_flag_status_feature_execution(tmp_path: Path):
    from home_notifications.features.flag_status import FlagStatusFeature
    from datetime import datetime

    telegram_cfg = TelegramConfig(bot_token="test-token", chat_id=123456)
    system_cfg = SystemConfig(state_file=str(tmp_path / "state.json"))
    features = {
        "flag_status": FeatureConfig(
            name="flag_status",
            enabled=True,
            interval_seconds=3600,
            notify_mode="on_change",
            options={
                "duration_days": 4,
                "min_deaths": 1,
                "min_casualties": 1,
                "state_filter": "",
            },
        ),
    }
    config = AppConfig(base_dir=tmp_path, telegram=telegram_cfg, system=system_cfg, features=features, devices={})
    state = StateManager(tmp_path / "state.json")
    mock_bot = MagicMock()
    mock_bot.send_message = AsyncMock(return_value=True)
    notifier = NotificationDispatcher(mock_bot, config, state)

    flag_feat = FlagStatusFeature(config, state, notifier)

    # Mock fetch_flag_details to simulate lowering flag for an active incident
    mock_details = {
        "status_text": "Flag Status: Lower Flag\nDate: October 20, 2026\nLocation: Austin, Texas\nDead: 2\nInjured: 1\nTotal: 3\nDesc: Campus incident",
        "status_type": "LOWER",
        "active_incident": {
            "source_name": "US Incidents",
            "source_url": "https://wiki.example/shootings",
            "date": "October 20, 2026",
            "days_ago": 2,
            "location": "Austin, Texas",
            "dead": 2,
            "injured": 1,
            "total": 3,
            "desc": "Campus incident",
        },
        "recent_incidents": [],
    }
    flag_feat.fetch_flag_details = AsyncMock(return_value=mock_details)

    # Initial execution: state changes from None to LOWER
    res = await flag_feat.execute()
    assert "Lower Flag" in res
    flag_data = state.get_flag_status_data()
    assert flag_data["status_type"] == "LOWER"
    assert flag_data["active_incident"]["location"] == "Austin, Texas"
    # First run without old status won't alert (old_status was None)

    # Second run with status change to RAISE:
    mock_details_raise = {
        "status_text": "Flag Status: Raise Flag\nDays Since Last Incident: 10",
        "status_type": "RAISE",
        "active_incident": None,
        "recent_incidents": [],
    }
    flag_feat.fetch_flag_details = AsyncMock(return_value=mock_details_raise)
    res2 = await flag_feat.execute()
    assert "Raise Flag" in res2
    mock_bot.send_message.assert_called_once()
    assert "Full-Staff" in mock_bot.send_message.call_args[1]["text"]



