"""Unit tests for StateManager."""

import pytest
from pathlib import Path
from home_notifications.state import QueuedNotification, StateManager


@pytest.mark.asyncio
async def test_state_manager_persistence(tmp_path: Path):
    state_file = tmp_path / "state.json"
    mgr = StateManager(state_file)

    # 1. Register device
    dev, is_new = mgr.register_or_update_device(
        mac="AA:BB:CC:11:22:33",
        ip="192.168.1.50",
        hostname="my-pi",
        vendor="Raspberry Pi Foundation",
    )
    assert is_new is True
    assert dev["mac"] == "aa:bb:cc:11:22:33"
    assert dev["online"] is True

    # 2. Update existing device
    dev2, is_new2 = mgr.register_or_update_device(
        mac="aa:bb:cc:11:22:33",
        ip="192.168.1.51",
    )
    assert is_new2 is False
    assert dev2["ip"] == "192.168.1.51"
    assert dev2["hostname"] == "my-pi"

    # 3. Notification queue
    mgr.queue_notification(
        QueuedNotification(
            category="network_discovery",
            title="New Device",
            message="Device joined",
            level="INFO",
        )
    )

    await mgr.save()

    # Reload from disk
    mgr2 = StateManager(state_file)
    assert "aa:bb:cc:11:22:33" in mgr2.get_known_devices()
    queued = mgr2.pop_queued_notifications()
    assert len(queued) == 1
    assert queued[0].title == "New Device"
    assert len(mgr2.pop_queued_notifications()) == 0


def test_cooldown_checks(tmp_path: Path):
    mgr = StateManager(tmp_path / "state.json")
    key = "device_down:server1"

    # First check should succeed
    assert mgr.should_alert(key, cooldown_seconds=60) is True
    # Immediate second check should be throttled
    assert mgr.should_alert(key, cooldown_seconds=60) is False

    mgr.clear_alert_cooldown(key)
    assert mgr.should_alert(key, cooldown_seconds=60) is True


def test_speedtest_state_comparison(tmp_path: Path):
    mgr = StateManager(tmp_path / "state.json")

    # Empty initially
    cmp0 = mgr.get_speedtest_comparison()
    assert cmp0["current"] is None
    assert cmp0["previous"] is None
    assert cmp0["comparison"] is None

    # First test run
    res1 = {
        "timestamp": 1000.0,
        "provider": "ookla",
        "download_mbps": 200.0,
        "upload_mbps": 50.0,
        "latency_ms": 30.0,
        "target_latencies": {
            "1.1.1.1": {"latency_ms": 12.0, "status": "UP"},
            "8.8.8.8": {"latency_ms": 18.0, "status": "UP"},
        },
    }
    mgr.add_speedtest_result(res1)
    cmp1 = mgr.get_speedtest_comparison()
    assert cmp1["current"]["download_mbps"] == 200.0
    assert cmp1["previous"] is None
    assert cmp1["comparison"] is None

    # Second test run
    res2 = {
        "timestamp": 1300.0,
        "provider": "ookla",
        "download_mbps": 225.0,
        "upload_mbps": 60.0,
        "latency_ms": 25.0,
        "target_latencies": {
            "1.1.1.1": {"latency_ms": 10.0, "status": "UP"},
            "8.8.8.8": {"latency_ms": 20.0, "status": "UP"},
        },
    }
    mgr.add_speedtest_result(res2)
    cmp2 = mgr.get_speedtest_comparison()
    assert cmp2["current"]["download_mbps"] == 225.0
    assert cmp2["previous"]["download_mbps"] == 200.0
    comp = cmp2["comparison"]
    assert comp is not None
    assert comp["download_delta_mbps"] == 25.0
    assert comp["download_delta_pct"] == 12.5
    assert comp["upload_delta_mbps"] == 10.0
    assert comp["latency_delta_ms"] == -5.0
    assert comp["time_delta_seconds"] == 300
    assert comp["targets"]["1.1.1.1"]["delta_ms"] == -2.0
    assert comp["targets"]["8.8.8.8"]["delta_ms"] == 2.0
