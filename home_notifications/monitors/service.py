"""Service monitors for TCP and HTTP/HTTPS endpoints."""

from __future__ import annotations

import asyncio
import time
import aiohttp

from home_notifications.config import ServiceCheckConfig
from home_notifications.monitors.base import CheckResult


class ServiceMonitor:
    """Monitors network services on devices (TCP ports, HTTP/HTTPS web endpoints)."""

    @staticmethod
    async def check_tcp(
        host: str, port: int, timeout: float = 3.0, name: str = "tcp"
    ) -> CheckResult:
        start_time = time.time()
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(host, port), timeout=timeout
            )
            elapsed_ms = (time.time() - start_time) * 1000
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass

            return CheckResult(
                name=name,
                success=True,
                status="UP",
                latency_ms=elapsed_ms,
                message=f"Port {port} open ({elapsed_ms:.1f} ms)",
                details={"port": port},
            )
        except asyncio.TimeoutError:
            return CheckResult(
                name=name,
                success=False,
                status="DOWN",
                latency_ms=0.0,
                message=f"Port {port} connection timed out",
                details={"port": port},
            )
        except Exception as e:
            return CheckResult(
                name=name,
                success=False,
                status="DOWN",
                latency_ms=0.0,
                message=f"Port {port} connection refused/failed: {e}",
                details={"port": port, "error": str(e)},
            )

    @staticmethod
    async def check_http(
        host: str,
        port: int = 80,
        path: str = "/",
        expected_status: int = 200,
        timeout: float = 5.0,
        use_https: bool = False,
        name: str = "http",
        hostname: str = "",
        check_ssl: bool = False,
    ) -> CheckResult:
        scheme = "https" if use_https or port == 443 else "http"
        url = f"{scheme}://{host}:{port}{path}"
        vhost = str(hostname or "").strip()
        headers = {"User-Agent": "HomeNotifications-Monitor/1.0"}
        if vhost:
            headers["Host"] = vhost if port in (80, 443) else f"{vhost}:{port}"

        start_time = time.time()
        display_target = f"{scheme}://{vhost or host}:{port}{path}"

        # 1. Try with async aiohttp
        try:
            connector = aiohttp.TCPConnector(ssl=False)
            async with aiohttp.ClientSession(connector=connector) as session:
                req_kwargs: Dict[str, Any] = {
                    "timeout": aiohttp.ClientTimeout(total=timeout),
                    "headers": headers,
                    "allow_redirects": True,
                }
                if (use_https or port == 443) and vhost:
                    req_kwargs["server_hostname"] = vhost

                async with session.get(url, **req_kwargs) as resp:
                    elapsed_ms = (time.time() - start_time) * 1000
                    status_code = resp.status
                    success = status_code == expected_status

                    # Quick certificate validity inspection if requested
                    ssl_str = ""
                    ssl_details = None
                    if (use_https or port == 443) and check_ssl:
                        try:
                            from home_notifications.features.ssl_cert import SSLCertFeature
                            cert_res = await asyncio.to_thread(
                                SSLCertFeature._check_cert_sync, host, port, vhost, min(timeout, 2.5)
                            )
                            if cert_res.get("success"):
                                ssl_details = cert_res
                                days = cert_res.get("days_left", 999)
                                if days < 0:
                                    ssl_str = f" • ⚠️ TLS Expired {abs(days)}d ago"
                                else:
                                    ssl_str = f" • TLS Valid ({days}d left)"
                        except Exception:
                            pass

                    if success:
                        status_str = "UP"
                        msg = f"HTTP {status_code} OK ({elapsed_ms:.1f} ms){ssl_str}"
                    else:
                        status_str = "DOWN" if status_code >= 500 else "WARNING"
                        msg = f"HTTP {status_code} (expected {expected_status}){ssl_str}"

                    return CheckResult(
                        name=name,
                        success=success,
                        status=status_str,
                        latency_ms=elapsed_ms,
                        message=msg,
                        details={
                            "url": url,
                            "display_target": display_target,
                            "hostname": vhost,
                            "status_code": status_code,
                            "expected_status": expected_status,
                            "tls": ssl_details,
                        },
                    )
        except Exception as e:
            # 2. Fallback to urllib / requests in thread for lenient parsing of embedded routers
            def _fallback_check():
                import urllib.request
                import ssl
                ctx = ssl.create_default_context()
                ctx.check_hostname = False
                ctx.verify_mode = ssl.CERT_NONE
                req = urllib.request.Request(url, headers=headers)
                try:
                    with urllib.request.urlopen(req, timeout=timeout, context=ctx) as r:
                        return r.getcode(), None
                except urllib.error.HTTPError as he:
                    return he.code, None
                except Exception as ex:
                    return None, str(ex)

            status_code, err = await asyncio.to_thread(_fallback_check)
            elapsed_ms = (time.time() - start_time) * 1000
            if status_code is not None:
                success = status_code == expected_status
                status_str = "UP" if success else ("DOWN" if status_code >= 500 else "WARNING")
                msg = f"HTTP {status_code} OK ({elapsed_ms:.1f} ms)" if success else f"HTTP {status_code} (expected {expected_status})"
                return CheckResult(
                    name=name,
                    success=success,
                    status=status_str,
                    latency_ms=elapsed_ms,
                    message=msg,
                    details={"url": url, "display_target": display_target, "hostname": vhost, "status_code": status_code},
                )

            return CheckResult(
                name=name,
                success=False,
                status="DOWN",
                latency_ms=0.0,
                message=f"HTTP request to {display_target} failed: {e}",
                details={"url": url, "display_target": display_target, "hostname": vhost, "error": str(e)},
            )

    @classmethod
    async def check_service(
        cls, host: str, config: ServiceCheckConfig
    ) -> CheckResult:
        stype = config.type.lower()
        if stype in ("http", "https"):
            use_https = stype == "https" or config.port == 443
            return await cls.check_http(
                host=host,
                port=config.port,
                path=config.path,
                expected_status=config.expected_status,
                timeout=config.timeout,
                use_https=use_https,
                name=config.name,
                hostname=config.hostname,
                check_ssl=config.check_ssl,
            )
        else:
            return await cls.check_tcp(
                host=host,
                port=config.port,
                timeout=config.timeout,
                name=config.name,
            )
