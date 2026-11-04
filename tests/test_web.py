"""Unit tests for Web Management UI server and REST APIs."""

import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock
from aiohttp.test_utils import AioHTTPTestCase, unittest_run_loop
from aiohttp import web

from home_notifications.config import AppConfig, DeviceConfig, FeatureConfig, SystemConfig, TelegramConfig
from home_notifications.features.device_monitor import DeviceMonitorFeature
from home_notifications.features.discovery import NetworkDiscoveryFeature
from home_notifications.features.external_ip import ExternalIPFeature
from home_notifications.features.flag_status import FlagStatusFeature
from home_notifications.features.speedtest import SpeedtestFeature
from home_notifications.notifier import NotificationDispatcher
from home_notifications.state import StateManager
from home_notifications.web.server import WebServer


@pytest.fixture
def web_test_app(tmp_path: Path):
    telegram_cfg = TelegramConfig(bot_token="test-token", chat_id=123456)
    system_cfg = SystemConfig(
        devices_file="devices.yaml",
        state_file=str(tmp_path / "state.json"),
        web_enabled=True,
        web_host="127.0.0.1",
        web_port=8085,
    )
    features = {
        "external_ip": FeatureConfig("external_ip", enabled=True, interval_seconds=3600),
        "network_discovery": FeatureConfig("network_discovery", enabled=True, interval_seconds=300),
        "device_monitor": FeatureConfig("device_monitor", enabled=True, interval_seconds=60),
        "webhooks": FeatureConfig("webhooks", enabled=True, options={"api_key": "homenotify-secret-key"}),
    }
    dev1 = DeviceConfig(id="dev1", name="Test Device", ip="192.168.1.100")
    config = AppConfig(
        base_dir=tmp_path,
        telegram=telegram_cfg,
        system=system_cfg,
        features=features,
        devices={"dev1": dev1},
    )
    # Write initial devices.yaml
    devs_yaml = tmp_path / "devices.yaml"
    devs_yaml.write_text("devices:\n  - id: dev1\n    name: Test Device\n    ip: 192.168.1.100\n", encoding="utf-8")

    state = StateManager(tmp_path / "state.json")
    state.register_or_update_device(mac="aa:bb:cc:dd:ee:01", ip="192.168.1.100", vendor="Intel")

    mock_bot = MagicMock()
    mock_bot.send_message = AsyncMock(return_value=True)
    notifier = NotificationDispatcher(mock_bot, config, state)

    disc_feat = NetworkDiscoveryFeature(config, state, notifier)
    dev_feat = DeviceMonitorFeature(config, state, notifier)
    ip_feat = ExternalIPFeature(config, state, notifier)
    flag_feat = FlagStatusFeature(config, state, notifier)

    from home_notifications.features.presence import PresenceFeature
    from home_notifications.features.webhooks import WebhookFeature
    from home_notifications.features.speedtest import SpeedtestFeature
    presence_feat = PresenceFeature(config, state, notifier)
    webhook_feat = WebhookFeature(config, state, notifier)
    speedtest_feat = SpeedtestFeature(config, state, notifier)

    server = WebServer(
        config=config,
        state=state,
        notifier=notifier,
        discovery_feature=disc_feat,
        device_feature=dev_feat,
        ip_feature=ip_feat,
        flag_feature=flag_feat,
        presence_feature=presence_feat,
        webhook_feature=webhook_feat,
        speedtest_feature=speedtest_feat,
    )
    return server


@pytest.mark.asyncio
async def test_web_routes(web_test_app, aiohttp_client):
    client = await aiohttp_client(web_test_app.app)

    # 1. Index HTML & Static Assets
    resp = await client.get("/")
    assert resp.status == 200
    text = await resp.text()
    assert "HomeNotify" in text
    assert "Dashboard Overview" in text
    assert 'id="view-breadcrumb"' in text
    assert 'class="breadcrumb"' in text
    assert "feature-modal" in text
    assert "Monitoring Features & Sub-Feature Controls" in text

    # Static CSS & JS
    resp_css = await client.get("/static/css/style.css")
    assert resp_css.status == 200
    css_text = await resp_css.text()
    assert ".breadcrumb" in css_text

    resp_js = await client.get("/static/js/app.js")
    assert resp_js.status == 200
    js_text = await resp_js.text()
    assert "updateBreadcrumbs" in js_text
    assert "homenotify_last_route" in js_text

    # 2. Status API
    resp = await client.get("/api/status")
    assert resp.status == 200
    data = await resp.json()
    assert data["success"] is True
    assert data["devices"]["total"] == 1
    assert data["network_discovery"]["total_known"] == 1

    # 3. Devices API
    resp = await client.get("/api/devices")
    assert resp.status == 200
    data = await resp.json()
    assert len(data["devices"]) == 1
    assert data["devices"][0]["id"] == "dev1"

    # 4. Discovery API
    resp = await client.get("/api/discovery")
    assert resp.status == 200
    data = await resp.json()
    assert len(data["hosts"]) == 1
    assert data["hosts"][0]["ip"] == "192.168.1.100"

    # 5. Features API
    resp = await client.get("/api/features")
    assert resp.status == 200
    data = await resp.json()
    assert "network_discovery" in data["features"]

    # Update feature settings & sub-options via API (as submitted by feature modal)
    feat_update = await client.post(
        "/api/features",
        json={
            "device_monitor": {
                "enabled": True,
                "interval_seconds": 45,
                "notify_mode": "immediate",
                "options": {
                    "alert_on_down": True,
                    "alert_on_recovery": False,
                    "cooldown_seconds": 1800,
                },
            }
        },
    )
    assert feat_update.status == 200
    feat_update_data = await feat_update.json()
    assert feat_update_data["success"] is True

    # Verify updated settings in GET /api/features
    resp2 = await client.get("/api/features")
    data2 = await resp2.json()
    dm = data2["features"]["device_monitor"]
    assert dm["interval_seconds"] == 45
    assert dm["notify_mode"] == "immediate"
    assert dm["options"]["alert_on_recovery"] in (False, "false")
    assert str(dm["options"]["cooldown_seconds"]) == "1800"

    # 6. Add Device API
    add_resp = await client.post(
        "/api/devices",
        json={"id": "dev2", "name": "New Server", "ip": "192.168.1.200", "tags": "backup,lan"},
    )
    assert add_resp.status == 200
    add_data = await add_resp.json()
    assert add_data["success"] is True

    # Verify device was added
    resp = await client.get("/api/devices")
    data = await resp.json()
    assert len(data["devices"]) == 2

    # 7. Delete Device API
    del_resp = await client.delete("/api/devices/dev2")
    assert del_resp.status == 200
    del_data = await del_resp.json()
    assert del_data["success"] is True

    # 8. Add Service API
    srv_add = await client.post(
        "/api/services",
        json={
            "device_id": "dev1",
            "name": "HTTP Web GUI",
            "type": "http",
            "port": 8080,
            "hostname": "test.example.com",
            "check_ssl": True,
            "path": "/admin",
            "expected_status": 200,
        },
    )
    assert srv_add.status == 200
    srv_add_data = await srv_add.json()
    assert srv_add_data["success"] is True

    # Verify service is in GET /api/services
    srv_list = await client.get("/api/services")
    assert srv_list.status == 200
    srv_list_data = await srv_list.json()
    assert len(srv_list_data["services"]) == 1
    assert srv_list_data["services"][0]["service_name"] == "HTTP Web GUI"
    assert srv_list_data["services"][0]["port"] == 8080
    assert srv_list_data["services"][0]["hostname"] == "test.example.com"
    assert srv_list_data["services"][0]["check_ssl"] is True
    assert srv_list_data["services"][0]["path"] == "/admin"

    # 9. Edit Device API (updating dev1's properties and ensuring its service is preserved!)
    edit_resp = await client.post(
        "/api/devices",
        json={
            "original_id": "dev1",
            "id": "dev1",
            "name": "Edited Dev1 Hostname",
            "ip": "192.168.1.105",
            "mac": "11:22:33:44:55:66",
            "tags": "core,edited",
            "ping_enabled": True,
            "ping_timeout": 3.5,
        },
    )
    assert edit_resp.status == 200

    # Verify device was updated
    resp = await client.get("/api/devices")
    data = await resp.json()
    dev1_updated = [d for d in data["devices"] if d["id"] == "dev1"][0]
    assert dev1_updated["name"] == "Edited Dev1 Hostname"
    assert dev1_updated["ip"] == "192.168.1.105"
    assert dev1_updated["mac"] == "11:22:33:44:55:66"
    assert dev1_updated["ping_timeout"] == 3.5

    # Verify existing service was preserved!
    srv_check = await client.get("/api/services")
    srv_data = await srv_check.json()
    assert len(srv_data["services"]) == 1
    assert srv_data["services"][0]["service_name"] == "HTTP Web GUI"

    # 10. Edit Service API (rename / update port)
    srv_edit = await client.post(
        "/api/services",
        json={
            "device_id": "dev1",
            "original_name": "HTTP Web GUI",
            "name": "Updated Web GUI",
            "type": "tcp",
            "port": 8443,
        },
    )
    assert srv_edit.status == 200
    srv_list2 = await client.get("/api/services")
    srv_list_data2 = await srv_list2.json()
    assert len(srv_list_data2["services"]) == 1
    assert srv_list_data2["services"][0]["service_name"] == "Updated Web GUI"
    assert srv_list_data2["services"][0]["port"] == 8443

    # 10. Test Service Probe API
    probe_resp = await client.post(
        "/api/services/test",
        json={"device_id": "dev1", "service_name": "Updated Web GUI", "type": "tcp", "port": 59999, "timeout": 0.5},
    )
    assert probe_resp.status == 200
    probe_data = await probe_resp.json()
    assert probe_data["success"] is True
    assert "status" in probe_data["result"]
    assert probe_data["result"]["service_name"] == "Updated Web GUI"

    # Verify probe result is saved to state and returned in GET /api/services
    srv_list_after_probe = await client.get("/api/services")
    srv_after_data = await srv_list_after_probe.json()
    matched = [s for s in srv_after_data["services"] if s["service_name"] == "Updated Web GUI"][0]
    assert matched["status"] == probe_data["result"]["status"]
    assert matched["message"] == probe_data["result"]["message"]

    # 11. Delete Service API
    srv_del = await client.delete(
        "/api/services",
        json={"device_id": "dev1", "service_name": "Updated Web GUI"},
    )
    assert srv_del.status == 200
    srv_del_data = await srv_del.json()
    assert srv_del_data["success"] is True

    srv_list3 = await client.get("/api/services")
    srv_list_data3 = await client_json(srv_list3) if False else await srv_list3.json()
    assert len(srv_list_data3["services"]) == 0

    # 11b. Systemd Service Save, Query, and Delete
    sys_add = await client.post(
        "/api/services",
        json={"device_id": "dev1", "name": "nginx", "type": "systemd"},
    )
    assert sys_add.status == 200
    sys_list = await client.get("/api/services")
    sys_list_data = await sys_list.json()
    assert any(s["type"] == "systemd" and "nginx" in s["service_name"] for s in sys_list_data["services"])

    sys_del = await client.delete(
        "/api/services",
        json={"device_id": "dev1", "service_name": "nginx (systemd)"},
    )
    assert sys_del.status == 200
    sys_list_after = await client.get("/api/services")
    sys_list_after_data = await sys_list_after.json()
    assert not any("nginx" in s["service_name"] for s in sys_list_after_data["services"])

    # 12. Notification test API
    notif_resp = await client.post("/api/notifications/test", json={"message": "hello"})
    assert notif_resp.status == 200
    notif_data = await notif_resp.json()
    assert notif_data["success"] is True

    # 13. IP refresh API
    ip_resp = await client.post("/api/ip/refresh")
    assert ip_resp.status == 200
    ip_data = await ip_resp.json()
    assert ip_data["success"] is True
    assert "ip" in ip_data

    # 14. Telegram Config & Pause APIs
    tg_get = await client.get("/api/telegram")
    assert tg_get.status == 200
    tg_data = await tg_get.json()
    assert tg_data["success"] is True
    assert tg_data["enabled"] is True
    assert tg_data["is_paused"] is False

    # Pause telegram for 1800s
    pause_resp = await client.post("/api/telegram/pause", json={"duration_seconds": 1800})
    assert pause_resp.status == 200
    pause_data = await pause_resp.json()
    assert pause_data["is_paused"] is True
    assert pause_data["pause_remaining_seconds"] == 1800

    # Resume telegram
    resume_resp = await client.post("/api/telegram/pause", json={"action": "resume"})
    assert resume_resp.status == 200
    resume_data = await resume_resp.json()
    assert resume_data["is_paused"] is False

    # Update telegram config
    update_tg = await client.post(
        "/api/telegram",
        json={"bot_token": "updated-token-123", "chat_id": 999888, "parse_mode": "HTML", "enabled": True},
    )
    assert update_tg.status == 200
    update_tg_data = await update_tg.json()
    assert update_tg_data["success"] is True

    # 15. Webhook Ingestion API
    wh_resp = await client.post(
        "/api/webhook/notify",
        headers={"X-Webhook-Token": "homenotify-secret-key"},
        json={"title": "NVR Camera", "message": "Motion detected on driveway", "level": "WARNING"},
    )
    assert wh_resp.status == 200
    wh_data = await wh_resp.json()
    assert wh_data["success"] is True
    assert wh_data["entry"]["title"] == "NVR Camera"

    # 16. Flag Half-Staff Monitor APIs
    flag_st_resp = await client.get("/api/flag/status")
    assert flag_st_resp.status == 200
    flag_st_data = await flag_st_resp.json()
    assert flag_st_data["success"] is True
    assert "state" in flag_st_data
    assert "config" in flag_st_data
    assert flag_st_data["config"]["duration_days"] == 4

    # Trigger flag check
    web_test_app.flag_feature.execute = AsyncMock(return_value="Flag Status: Raise Flag\nDays Since Last Incident: 15")
    flag_chk_resp = await client.post("/api/flag/check")
    assert flag_chk_resp.status == 200
    flag_chk_data = await flag_chk_resp.json()
    assert flag_chk_data["success"] is True
    assert "Raise Flag" in flag_chk_data["status"]

    # Test probe flag URL
    FlagStatusFeature.test_url = AsyncMock(return_value={
        "success": True,
        "url": "https://en.wikipedia.org/wiki/Test",
        "tables_found": 1,
        "total_incidents_parsed": 5,
        "sample_incidents": [],
    })
    flag_test_resp = await client.post("/api/flag/test", json={"url": "https://en.wikipedia.org/wiki/Test"})
    assert flag_test_resp.status == 200
    flag_test_data = await flag_test_resp.json()
    assert flag_test_data["success"] is True
    assert flag_test_data["tables_found"] == 1

    # 17. Discovered Available Services on Host API
    # 404 for unknown device
    avail_404 = await client.get("/api/devices/unknown_dev_123/available-services")
    assert avail_404.status == 404

    # Available services for dev1
    avail_resp = await client.get("/api/devices/dev1/available-services?type=systemd")
    assert avail_resp.status == 200
    avail_data = await avail_resp.json()
    assert avail_data["success"] is True
    assert avail_data["device_id"] == "dev1"
    assert isinstance(avail_data["ssh_enabled"], bool)
    assert isinstance(avail_data["services"], list)

    # Available network services for dev1 (socket probe)
    avail_tcp = await client.get("/api/devices/dev1/available-services?type=tcp")
    assert avail_tcp.status == 200
    avail_tcp_data = await avail_tcp.json()
    assert avail_tcp_data["success"] is True
    assert isinstance(avail_tcp_data["services"], list)

    # 18. Speedtest & Latency Test APIs
    # Get initial speedtest results
    st_res_resp = await client.get("/api/speedtest/results")
    assert st_res_resp.status == 200
    st_res_data = await st_res_resp.json()
    assert st_res_data["success"] is True
    assert "config" in st_res_data
    assert "current" in st_res_data
    assert "previous" in st_res_data

    # Trigger on-demand speedtest
    web_test_app.speedtest_feature.execute = AsyncMock(return_value={
        "success": True,
        "timestamp": 12345678.0,
        "provider": "ookla",
        "download_mbps": 280.5,
        "upload_mbps": 35.2,
        "latency_ms": 28.0,
        "server": {"name": "Test Server", "sponsor": "Test ISP", "location": "Test Loc"},
        "client": {"ip": "1.2.3.4", "isp": "My ISP"},
        "target_latencies": {
            "1.1.1.1": {"status": "UP", "latency_ms": 9.5},
            "8.8.8.8": {"status": "UP", "latency_ms": 11.2},
        },
    })
    # Run first test
    st_run_resp = await client.post("/api/speedtest/run", json={"provider": "ookla", "latency_targets": "1.1.1.1, 8.8.8.8"})
    assert st_run_resp.status == 200
    st_run_data = await st_run_resp.json()
    assert st_run_data["success"] is True
    assert st_run_data["result"]["download_mbps"] == 280.5

    # Run second test to verify comparison
    web_test_app.speedtest_feature.execute = AsyncMock(return_value={
        "success": True,
        "timestamp": 12346000.0,
        "provider": "ookla",
        "download_mbps": 300.0,
        "upload_mbps": 40.0,
        "latency_ms": 25.0,
        "server": {"name": "Test Server", "sponsor": "Test ISP", "location": "Test Loc"},
        "client": {"ip": "1.2.3.4", "isp": "My ISP"},
        "target_latencies": {
            "1.1.1.1": {"status": "UP", "latency_ms": 8.5},
            "8.8.8.8": {"status": "UP", "latency_ms": 10.0},
        },
    })
    st_run_resp2 = await client.post("/api/speedtest/run")
    assert st_run_resp2.status == 200
    st_run_data2 = await st_run_resp2.json()
    assert st_run_data2["success"] is True
    assert st_run_data2["current"]["download_mbps"] == 300.0
    assert st_run_data2["previous"]["download_mbps"] == 280.5
    assert st_run_data2["comparison"]["download_delta_mbps"] == 19.5

    # Discover speedtest servers
    SpeedtestFeature.get_nearby_servers = AsyncMock(return_value=[
        {"id": "45705", "name": "Grinnell, IA", "sponsor": "Uniti", "country": "US", "distance_km": 100.0}
    ])
    st_srvs_resp = await client.get("/api/speedtest/servers")
    assert st_srvs_resp.status == 200
    st_srvs_data = await st_srvs_resp.json()
    assert st_srvs_data["success"] is True
    assert len(st_srvs_data["servers"]) == 1
    assert st_srvs_data["servers"][0]["id"] == "45705"

    # 19. Resources and Process Breakdown APIs
    # Seed state with resources
    st_dev1 = web_test_app.state.get_monitored_device_state("dev1")
    st_dev1["resources"] = {
        "cpu_load_1m": 0.45,
        "memory_percent": 34.5,
        "memory_used_mb": 1200,
        "memory_total_mb": 3800,
        "disk_usage": {"/": 45.0},
        "top_cpu_processes": [
            {"pid": 1234, "user": "pferland", "cpu_percent": 15.0, "mem_percent": 2.0, "command": "python", "args": "python app.py"}
        ],
        "top_mem_processes": [
            {"pid": 1234, "user": "pferland", "cpu_percent": 1.0, "mem_percent": 22.0, "command": "omada", "args": "omada srv"}
        ],
    }

    res_resp = await client.get("/api/resources")
    assert res_resp.status == 200
    res_data = await res_resp.json()
    assert res_data["success"] is True
    assert len(res_data["resources"]) >= 1
    dev1_res = next(r for r in res_data["resources"] if r["device_id"] == "dev1")
    assert dev1_res["cpu_load_1m"] == 0.45
    assert len(dev1_res["top_cpu_processes"]) == 1
    assert dev1_res["top_cpu_processes"][0]["command"] == "python"

    # Live processes for unknown device
    procs_404 = await client.get("/api/resources/unknown_dev_xyz/processes")
    assert procs_404.status == 404

    # Live processes for dev without SSH
    web_test_app.config.devices["dev1"].ssh = None
    procs_no_ssh = await client.get("/api/resources/dev1/processes")
    assert procs_no_ssh.status == 400

    # Configure SSH on dev1 and mock SSHMonitor.get_processes
    from home_notifications.config import SSHMonitorConfig
    from home_notifications.monitors.ssh import SSHMonitor
    web_test_app.config.devices["dev1"].ssh = SSHMonitorConfig(enabled=True, port=22, username="pferland")

    SSHMonitor.get_processes = AsyncMock(return_value={
        "success": True,
        "cpu_load_1m": 0.55,
        "memory_percent": 40.0,
        "memory_used_mb": 1500,
        "memory_total_mb": 3800,
        "top_cpu_processes": [
            {"pid": 5555, "user": "pferland", "cpu_percent": 25.0, "mem_percent": 3.0, "command": "python", "args": "python main.py"}
        ],
        "top_mem_processes": [
            {"pid": 6666, "user": "omada", "cpu_percent": 2.0, "mem_percent": 45.0, "command": "jsvc", "args": "jsvc omada"}
        ],
    })

    procs_resp = await client.get("/api/resources/dev1/processes")
    assert procs_resp.status == 200
    procs_data = await procs_resp.json()
    assert procs_data["success"] is True
    assert procs_data["device_id"] == "dev1"
    assert procs_data["cpu_load_1m"] == 0.55
    assert len(procs_data["top_cpu_processes"]) == 1
    assert procs_data["top_cpu_processes"][0]["pid"] == 5555

