"""Ping (ICMP) monitor for device availability and latency."""

from __future__ import annotations

import asyncio
import re
import time
from typing import Optional

from home_notifications.monitors.base import CheckResult


class PingMonitor:
    """Checks device reachability and round-trip latency via ICMP ping."""

    @staticmethod
    async def check(ip_or_host: str, timeout: float = 2.0, count: int = 2) -> CheckResult:
        start_time = time.time()
        try:
            proc = await asyncio.create_subprocess_exec(
                "ping",
                "-c",
                str(count),
                "-W",
                str(int(timeout)),
                ip_or_host,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=timeout + 2.0
            )
            stdout_str = stdout.decode("utf-8", errors="replace")
            elapsed_ms = (time.time() - start_time) * 1000

            if proc.returncode == 0:
                # Try to extract avg RTT: rtt min/avg/max/mdev = 0.245/0.312/...
                rtt_match = re.search(r"=\s*[\d\.]+/([\d\.]+)/", stdout_str)
                avg_rtt = float(rtt_match.group(1)) if rtt_match else elapsed_ms / count
                return CheckResult(
                    name="ping",
                    success=True,
                    status="UP",
                    latency_ms=avg_rtt,
                    message=f"Reachable ({avg_rtt:.1f} ms)",
                    details={"avg_rtt_ms": avg_rtt},
                )
            else:
                return CheckResult(
                    name="ping",
                    success=False,
                    status="DOWN",
                    latency_ms=0.0,
                    message="Host unreachable (ping timeout)",
                    details={"error": "ping failed", "stdout": stdout_str},
                )
        except asyncio.TimeoutError:
            return CheckResult(
                name="ping",
                success=False,
                status="DOWN",
                latency_ms=0.0,
                message="Ping timed out",
            )
        except Exception as e:
            return CheckResult(
                name="ping",
                success=False,
                status="ERROR",
                latency_ms=0.0,
                message=str(e),
            )
