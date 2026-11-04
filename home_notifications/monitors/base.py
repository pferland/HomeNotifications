"""Base monitor interfaces and data classes."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict


@dataclass
class CheckResult:
    name: str
    success: bool
    status: str  # UP, DOWN, WARNING, ERROR
    latency_ms: float = 0.0
    message: str = ""
    details: Dict[str, Any] = field(default_factory=dict)
