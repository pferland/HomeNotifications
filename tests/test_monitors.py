"""Unit tests for ping, service, and metrics monitors."""

import pytest
from home_notifications.config import PrometheusMonitorConfig, ServiceCheckConfig
from home_notifications.monitors.ping import PingMonitor
from home_notifications.monitors.prometheus import PrometheusMonitor
from home_notifications.monitors.service import ServiceMonitor


@pytest.mark.asyncio
async def test_ping_monitor_localhost():
    res = await PingMonitor.check("127.0.0.1", timeout=1.0, count=1)
    assert res.success is True
    assert res.status == "UP"
    assert res.latency_ms >= 0


@pytest.mark.asyncio
async def test_service_monitor_tcp_refusal():
    # Attempt connecting to unused high port
    res = await ServiceMonitor.check_tcp("127.0.0.1", port=59999, timeout=0.5)
    assert res.success is False
    assert res.status == "DOWN"


def test_prometheus_metrics_parser():
    raw_text = """
# HELP node_cpu_seconds_total Seconds the CPUs spent in each mode.
# TYPE node_cpu_seconds_total counter
node_cpu_seconds_total{cpu="0",mode="idle"} 104523.45
node_memory_MemAvailable_bytes 8452145152
node_load1 0.42
"""
    parsed = PrometheusMonitor.parse_prometheus_metrics(raw_text)
    assert parsed.get("node_memory_MemAvailable_bytes") == 8452145152.0
    assert parsed.get("node_load1") == 0.42


def test_ssh_monitor_parse_processes():
    from home_notifications.monitors.ssh import SSHMonitor

    raw_ps = """    PID USER     %CPU %MEM COMMAND         COMMAND
1026115 pferland  3.2  5.4 python          /opt/HomeNotifications/.venv/bin/python main.py
  49442 omada     1.5 44.0 jsvc            omada -cwd /opt/tplink/EAPController/lib
2116479 pferland 200.0 0.0 ps              ps -eo pid,user,%cpu,%mem,comm,args
 998902 pferland  0.3  2.3 uvicorn         /opt/tongue/.venv/bin/uvicorn app.main:app
"""
    procs = SSHMonitor.parse_processes(raw_ps, limit=10)
    # The ps inspector process itself should be filtered out
    assert len(procs) == 3

    p0 = procs[0]
    assert p0["pid"] == 1026115
    assert p0["user"] == "pferland"
    assert p0["cpu_percent"] == 3.2
    assert p0["mem_percent"] == 5.4
    assert p0["command"] == "python"
    assert "/opt/HomeNotifications/.venv/bin/python main.py" in p0["args"]

    p1 = procs[1]
    assert p1["pid"] == 49442
    assert p1["user"] == "omada"
    assert p1["cpu_percent"] == 1.5
    assert p1["mem_percent"] == 44.0
    assert p1["command"] == "jsvc"
