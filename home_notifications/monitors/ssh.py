"""SSH-based remote device monitor for resources, systemd services, and access logs."""

from __future__ import annotations

import asyncio
import logging
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional
import asyncssh

from home_notifications.config import SSHMonitorConfig
from home_notifications.monitors.base import CheckResult

logger = logging.getLogger(__name__)


@dataclass
class SSHCheckResults:
    success: bool
    error: Optional[str] = None
    cpu_percent: Optional[float] = None
    cpu_load_1m: Optional[float] = None
    memory_percent: Optional[float] = None
    memory_total_mb: Optional[int] = None
    memory_used_mb: Optional[int] = None
    disk_usage: Dict[str, float] = field(default_factory=dict)  # mount -> percent
    systemd_status: Dict[str, str] = field(default_factory=dict)  # service -> active/inactive/failed
    failed_logins: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    top_cpu_processes: List[Dict[str, Any]] = field(default_factory=list)
    top_mem_processes: List[Dict[str, Any]] = field(default_factory=list)


class SSHMonitor:
    """Monitors remote Linux systems over SSH without external agents."""

    @staticmethod
    def _build_conn_params(config: SSHMonitorConfig):
        client_keys = []
        if config.key_path:
            key_expanded = os.path.expanduser(config.key_path)
            if os.path.exists(key_expanded):
                client_keys.append(key_expanded)

        username = config.username or os.getenv("USER", "root")

        conn_options = {
            "known_hosts": None,  # Disable strict host key checking for home lab IP reassignments
            "login_timeout": config.timeout,
        }
        if client_keys:
            conn_options["client_keys"] = client_keys
        if config.password:
            conn_options["password"] = config.password

        return username, conn_options

    @staticmethod
    def parse_processes(stdout: str, limit: int = 15) -> List[Dict[str, Any]]:
        """Parses output from `ps -eo pid,user,%cpu,%mem,comm,args` into structured list."""
        processes: List[Dict[str, Any]] = []
        lines = stdout.strip().splitlines()
        if not lines:
            return processes

        # Skip header line if present
        start_idx = 1 if "PID" in lines[0] or "USER" in lines[0] else 0

        for line in lines[start_idx:]:
            line = line.strip()
            if not line:
                continue
            parts = line.split(None, 5)
            if len(parts) >= 5:
                try:
                    pid = int(parts[0])
                except ValueError:
                    continue
                user = parts[1]
                try:
                    cpu = float(parts[2])
                except ValueError:
                    cpu = 0.0
                try:
                    mem = float(parts[3])
                except ValueError:
                    mem = 0.0
                comm = parts[4]
                args = parts[5] if len(parts) > 5 else comm

                # Skip ps / head inspector itself
                if comm == "ps" and ("ps -eo" in args or "ps " in args):
                    continue

                processes.append({
                    "pid": pid,
                    "user": user,
                    "cpu_percent": cpu,
                    "mem_percent": mem,
                    "command": comm,
                    "args": args,
                })
                if len(processes) >= limit:
                    break
        return processes

    @classmethod
    async def get_processes(cls, host: str, config: SSHMonitorConfig, limit: int = 25) -> Dict[str, Any]:
        """Fetch live top CPU and Memory processes on demand over SSH."""
        if not config.enabled:
            return {"success": False, "error": "SSH monitor disabled"}

        username, conn_options = cls._build_conn_params(config)

        try:
            async with asyncssh.connect(
                host,
                port=config.port,
                username=username,
                **conn_options,
            ) as conn:
                cmd = (
                    f"cat /proc/loadavg 2>/dev/null; echo '---SEC_SPLIT---'; "
                    f"free -m 2>/dev/null; echo '---SEC_SPLIT---'; "
                    f"ps -eo pid,user,%cpu,%mem,comm,args --sort=-%cpu 2>/dev/null | head -n {limit + 2}; echo '---SEC_SPLIT---'; "
                    f"ps -eo pid,user,%cpu,%mem,comm,args --sort=-%mem 2>/dev/null | head -n {limit + 2}"
                )
                res = await conn.run(cmd, timeout=config.timeout)
                if res.exit_status != 0:
                    return {"success": False, "error": f"Command returned exit code {res.exit_status}"}

                sections = res.stdout.split("---SEC_SPLIT---")
                load_str = sections[0].strip() if len(sections) > 0 else ""
                mem_str = sections[1].strip() if len(sections) > 1 else ""
                cpu_procs_str = sections[2].strip() if len(sections) > 2 else ""
                mem_procs_str = sections[3].strip() if len(sections) > 3 else ""

                cpu_load_1m = None
                if load_str:
                    parts = load_str.split()
                    if parts:
                        try:
                            cpu_load_1m = float(parts[0])
                        except ValueError:
                            pass

                mem_total = None
                mem_used = None
                mem_pct = None
                for line in mem_str.splitlines():
                    if line.startswith("Mem:"):
                        parts = line.split()
                        if len(parts) >= 7:
                            tot = int(parts[1])
                            avail = int(parts[6])
                            usd = tot - avail
                            pct = round((usd / tot) * 100, 1) if tot > 0 else 0
                            mem_total = tot
                            mem_used = usd
                            mem_pct = pct
                        break

                top_cpu = cls.parse_processes(cpu_procs_str, limit=limit)
                top_mem = cls.parse_processes(mem_procs_str, limit=limit)

                return {
                    "success": True,
                    "cpu_load_1m": cpu_load_1m,
                    "memory_percent": mem_pct,
                    "memory_used_mb": mem_used,
                    "memory_total_mb": mem_total,
                    "top_cpu_processes": top_cpu,
                    "top_mem_processes": top_mem,
                }
        except Exception as e:
            logger.debug("Failed to get live processes for %s: %s", host, e)
            return {"success": False, "error": str(e)}

    @classmethod
    async def check(cls, host: str, config: SSHMonitorConfig) -> SSHCheckResults:
        if not config.enabled:
            return SSHCheckResults(success=False, error="SSH monitor disabled")

        username, conn_options = cls._build_conn_params(config)

        try:
            async with asyncssh.connect(
                host,
                port=config.port,
                username=username,
                **conn_options,
            ) as conn:
                results = SSHCheckResults(success=True)

                # 1. CPU Load Average: /proc/loadavg
                load_res = await conn.run("cat /proc/loadavg 2>/dev/null", timeout=config.timeout)
                if load_res.exit_status == 0:
                    parts = load_res.stdout.split()
                    if parts:
                        try:
                            results.cpu_load_1m = float(parts[0])
                        except ValueError:
                            pass

                # 2. Memory: free -m
                mem_res = await conn.run("free -m 2>/dev/null", timeout=config.timeout)
                if mem_res.exit_status == 0:
                    # Mem: total used free shared buff/cache available
                    for line in mem_res.stdout.splitlines():
                        if line.startswith("Mem:"):
                            parts = line.split()
                            if len(parts) >= 7:
                                total = int(parts[1])
                                avail = int(parts[6])
                                used = total - avail
                                pct = (used / total) * 100 if total > 0 else 0
                                results.memory_total_mb = total
                                results.memory_used_mb = used
                                results.memory_percent = round(pct, 1)
                                if pct >= config.memory_warning_percent:
                                    results.warnings.append(
                                        f"Memory usage critical: {pct:.1f}% >= {config.memory_warning_percent}%"
                                    )
                            break

                # 3. Disk Usage: df -kP <mounts>
                mounts_str = " ".join(config.disk_mounts)
                df_res = await conn.run(f"df -kP {mounts_str} 2>/dev/null", timeout=config.timeout)
                if df_res.exit_status == 0:
                    for line in df_res.stdout.splitlines()[1:]:
                        parts = line.split()
                        if len(parts) >= 6:
                            mount = parts[5]
                            cap_str = parts[4].rstrip("%")
                            try:
                                cap_pct = float(cap_str)
                                results.disk_usage[mount] = cap_pct
                                if cap_pct >= config.disk_warning_percent:
                                    results.warnings.append(
                                        f"Disk {mount} usage critical: {cap_pct:.1f}% >= {config.disk_warning_percent}%"
                                    )
                            except ValueError:
                                pass

                # 4. Systemd Services
                for srv in config.systemd_services:
                    srv_clean = srv.strip()
                    if not srv_clean:
                        continue
                    srv_res = await conn.run(
                        f"systemctl is-active {srv_clean} 2>/dev/null", timeout=config.timeout
                    )
                    status_str = srv_res.stdout.strip().lower() or "unknown"
                    results.systemd_status[srv_clean] = status_str
                    if status_str != "active":
                        results.warnings.append(
                            f"Systemd service '{srv_clean}' is not active ({status_str})"
                        )

                # 5. Access Logs (Failed logins)
                if config.check_failed_logins:
                    log_path = config.auth_log_path
                    log_cmd = (
                        f"if [ -f {log_path} ]; then tail -n 100 {log_path}; "
                        f"elif [ -f /var/log/secure ]; then tail -n 100 /var/log/secure; "
                        f"else journalctl -u ssh -u sshd -n 50 --no-pager 2>/dev/null; fi"
                    )
                    log_res = await conn.run(log_cmd, timeout=config.timeout)
                    if log_res.exit_status == 0:
                        failed_patterns = re.compile(
                            r"(Failed password|Invalid user|authentication failure|Failed publickey)",
                            re.IGNORECASE,
                        )
                        for line in log_res.stdout.splitlines():
                            if failed_patterns.search(line):
                                results.failed_logins.append(line.strip())

                        if len(results.failed_logins) >= config.failed_login_threshold:
                            results.warnings.append(
                                f"Detected {len(results.failed_logins)} failed SSH login attempts!"
                            )

                # 6. Process Breakdown (Top CPU and Top Memory processes)
                proc_cmd = (
                    "ps -eo pid,user,%cpu,%mem,comm,args --sort=-%cpu 2>/dev/null | head -n 16; "
                    "echo '---MEM_SPLIT---'; "
                    "ps -eo pid,user,%cpu,%mem,comm,args --sort=-%mem 2>/dev/null | head -n 16"
                )
                proc_res = await conn.run(proc_cmd, timeout=config.timeout)
                if proc_res.exit_status == 0 and proc_res.stdout:
                    if "---MEM_SPLIT---" in proc_res.stdout:
                        cpu_part, mem_part = proc_res.stdout.split("---MEM_SPLIT---", 1)
                        results.top_cpu_processes = cls.parse_processes(cpu_part, limit=15)
                        results.top_mem_processes = cls.parse_processes(mem_part, limit=15)
                    else:
                        results.top_cpu_processes = cls.parse_processes(proc_res.stdout, limit=15)

                return results

        except Exception as e:
            logger.debug("SSH check failed for %s: %s", host, e)
            return SSHCheckResults(success=False, error=str(e))
