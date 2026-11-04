"""Prometheus / Node Exporter metrics scraper and threshold monitor."""

from __future__ import annotations

import asyncio
import logging
import re
import time
from typing import Dict, Optional
import aiohttp

from home_notifications.config import PrometheusMonitorConfig
from home_notifications.monitors.base import CheckResult

logger = logging.getLogger(__name__)


class PrometheusMonitor:
    """Scrapes Prometheus / Node Exporter metrics and evaluates threshold alerts."""

    @staticmethod
    def parse_prometheus_metrics(raw_text: str) -> Dict[str, float]:
        """Parse Prometheus text-format metrics into name -> float value."""
        metrics: Dict[str, float] = {}
        for line in raw_text.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            # format: metric_name{labels} 123.45  OR  metric_name 123.45
            match = re.match(r"^([a-zA-Z_:][a-zA-Z0-9_:]*)(?:\{[^}]*\})?\s+([+-]?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?|NaN|\+Inf|-Inf)", line)
            if match:
                mname = match.group(1)
                val_str = match.group(2)
                try:
                    metrics[mname] = float(val_str)
                except ValueError:
                    pass
        return metrics

    @classmethod
    async def check(cls, config: PrometheusMonitorConfig) -> CheckResult:
        if not config.enabled:
            return CheckResult(
                name="prometheus", success=False, status="DISABLED", message="Prometheus monitor disabled"
            )

        start_time = time.time()
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    config.url,
                    timeout=aiohttp.ClientTimeout(total=config.timeout),
                ) as resp:
                    elapsed_ms = (time.time() - start_time) * 1000
                    if resp.status != 200:
                        return CheckResult(
                            name="prometheus",
                            success=False,
                            status="DOWN",
                            latency_ms=elapsed_ms,
                            message=f"HTTP status {resp.status}",
                        )
                    text = await resp.text()
                    metrics = cls.parse_prometheus_metrics(text)

                    warnings = []
                    for metric_name, threshold in config.alerts.items():
                        val = metrics.get(metric_name)
                        if val is not None and val >= threshold:
                            warnings.append(
                                f"{metric_name} exceeded threshold: {val} >= {threshold}"
                            )

                    if warnings:
                        return CheckResult(
                            name="prometheus",
                            success=True,
                            status="WARNING",
                            latency_ms=elapsed_ms,
                            message="; ".join(warnings),
                            details={"metrics": metrics, "warnings": warnings},
                        )

                    return CheckResult(
                        name="prometheus",
                        success=True,
                        status="UP",
                        latency_ms=elapsed_ms,
                        message=f"Metrics OK ({len(metrics)} parsed, {elapsed_ms:.1f} ms)",
                        details={"metrics_count": len(metrics)},
                    )
        except Exception as e:
            return CheckResult(
                name="prometheus",
                success=False,
                status="DOWN",
                latency_ms=0.0,
                message=str(e),
            )
