from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional


COMPONENTS = ("preferences", "saves", "runs")


@dataclass(frozen=True)
class CommandResult:
    command: list[str]
    returncode: int
    stdout: str
    stderr: str

    @property
    def ok(self) -> bool:
        return self.returncode == 0


@dataclass(frozen=True)
class DeviceInfo:
    serial: str
    state: str


@dataclass(frozen=True)
class SidePaths:
    preferences: str
    saves: str
    runs: str

    def get(self, component: str) -> str:
        return {
            "preferences": self.preferences,
            "saves": self.saves,
            "runs": self.runs,
        }[component]


@dataclass(frozen=True)
class LocalSidePaths:
    preferences: Path
    saves: Path
    runs: Path

    def get(self, component: str) -> Path:
        return {
            "preferences": self.preferences,
            "saves": self.saves,
            "runs": self.runs,
        }[component]


@dataclass(frozen=True)
class DirStatus:
    path: str
    exists: bool
    file_count: Optional[int]
    latest_mtime: Optional[datetime]
    detail: str = ""
