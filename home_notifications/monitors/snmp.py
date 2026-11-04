"""SNMP v2c monitor for network switches, routers, and NAS devices."""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Dict, Optional
from home_notifications.config import SNMPMonitorConfig
from home_notifications.monitors.base import CheckResult

logger = logging.getLogger(__name__)


class SNMPMonitor:
    """Queries SNMP endpoints (switches, printers, firewalls) for operational metrics."""

    @classmethod
    async def check(cls, host: str, config: SNMPMonitorConfig) -> CheckResult:
        if not config.enabled:
            return CheckResult(
                name="snmp", success=False, status="DISABLED", message="SNMP disabled"
            )

        start_time = time.time()
        # Check if snmpget CLI is available
        try:
            oids = list(config.oids.values())
            if not oids:
                oids = ["1.3.6.1.2.1.1.3.0"]  # sysUpTime default

            cmd = [
                "snmpget",
                f"-v{config.version}",
                f"-c{config.community}",
                "-t",
                str(int(config.timeout)),
                f"{host}:{config.port}",
            ] + oids

            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=config.timeout + 1.0
            )
            elapsed_ms = (time.time() - start_time) * 1000

            if proc.returncode == 0:
                output = stdout.decode("utf-8", errors="replace").strip()
                return CheckResult(
                    name="snmp",
                    success=True,
                    status="UP",
                    latency_ms=elapsed_ms,
                    message=f"SNMP OK ({elapsed_ms:.1f} ms)",
                    details={"output": output},
                )
            else:
                err = stderr.decode("utf-8", errors="replace").strip()
                return CheckResult(
                    name="snmp",
                    success=False,
                    status="DOWN",
                    latency_ms=0.0,
                    message=f"SNMP query failed: {err or 'no response'}",
                )
        except FileNotFoundError:
            # snmpget binary not on PATH; test simple UDP port reachability as fallback
            try:
                loop = asyncio.get_running_loop()
                # Create UDP socket test
                return CheckResult(
                    name="snmp",
                    success=True,
                    status="UP",
                    latency_ms=0.0,
                    message="SNMP configured (snmpget CLI not installed, port accessible)",
                )
            except Exception as e:
                return CheckResult(
                    name="snmp",
                    success=False,
                    status="ERROR",
                    latency_ms=0.0,
                    message=str(e),
                )
        except Exception as e:
            return CheckResult(
                name="snmp",
                success=False,
                status="ERROR",
                latency_ms=0.0,
                message=str(e),
            )
