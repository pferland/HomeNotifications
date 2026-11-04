"""Unit tests for configuration loader."""

from pathlib import Path
import tempfile
from home_notifications.config import load_config, load_devices_yaml


def test_load_config_defaults(tmp_path: Path):
    ini_file = tmp_path / "config.ini"
    ini_file.write_text(
        """[telegram]
bot_token = test-token-123
chat_id = 999888
[feature:network_discovery]
enabled = true
interval_seconds = 180
notify_mode = batched
batch_interval_seconds = 60
alert_new_device = true
""",
        encoding="utf-8",
    )

    devices_file = tmp_path / "devices.yaml"
    devices_file.write_text(
        """devices:
  - id: server1
    name: "Server 1"
    ip: 192.168.1.10
    mac: "aa:bb:cc:dd:ee:ff"
    monitors:
      ping:
        enabled: true
      services:
        - name: HTTP
          type: http
          port: 8080
          hostname: myapp.local
          check_ssl: true
""",
        encoding="utf-8",
    )

    cfg = load_config(tmp_path)
    assert cfg.telegram.bot_token == "test-token-123"
    assert cfg.telegram.chat_id == 999888

    feat = cfg.get_feature("network_discovery")
    assert feat.enabled is True
    assert feat.interval_seconds == 180
    assert feat.notify_mode == "batched"
    assert feat.batch_interval_seconds == 60
    assert feat.get_bool("alert_new_device") is True

    assert "server1" in cfg.devices
    dev = cfg.devices["server1"]
    assert dev.name == "Server 1"
    assert dev.ip == "192.168.1.10"
    assert dev.mac == "aa:bb:cc:dd:ee:ff"
    assert len(dev.services) == 1
    assert dev.services[0].port == 8080
    assert dev.services[0].hostname == "myapp.local"
    assert dev.services[0].check_ssl is True


def test_legacy_default_section_fallback(tmp_path: Path):
    ini_file = tmp_path / "config.ini"
    ini_file.write_text(
        """[DEFAULT]
TOKEN = "legacy-bot-token"
CHATID = 12345678
""",
        encoding="utf-8",
    )

    cfg = load_config(tmp_path)
    assert cfg.telegram.bot_token == "legacy-bot-token"
    assert cfg.telegram.chat_id == 12345678
    assert cfg.is_feature_enabled("external_ip") is True

    # Telegram credentials from [DEFAULT] must NOT bleed into feature options
    feat = cfg.get_feature("network_discovery")
    assert "token" not in feat.options
    assert "chatid" not in feat.options
    assert "bot_token" not in feat.options
    assert "chat_id" not in feat.options
