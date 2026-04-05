from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sts_syn.models import LocalSidePaths, SidePaths


def _expand_local_path(raw: str, base_dir: Path) -> Path:
    path = Path(raw).expanduser()
    if not path.is_absolute():
        path = (base_dir / path).resolve()
    return path


def _join_remote(root: str, child: str) -> str:
    root_clean = root.rstrip('/')
    child_clean = child.strip('/')
    if child.startswith('/'):
        return child
    if not child_clean:
        return root_clean
    return f"{root_clean}/{child_clean}"


@dataclass(frozen=True)
class AppConfig:
    config_path: Path
    adb_path: str
    device_serial: str | None
    pc_root: Path
    pc_paths: LocalSidePaths
    android_root: str
    android_paths: SidePaths
    android_root_candidates: list[str]
    backup_root: Path
    temp_root: Path
    log_root: Path
    backup_keep: int

    @classmethod
    def load(cls, config_path: Path) -> 'AppConfig':
        raw = json.loads(config_path.read_text(encoding='utf-8'))
        base_dir = config_path.parent.resolve()

        pc_root = _expand_local_path(raw['pc_root'], base_dir)
        pc_paths = LocalSidePaths(
            preferences=_expand_local_path(str(raw.get('pc_preferences_dir', 'preferences')), pc_root),
            saves=_expand_local_path(str(raw.get('pc_saves_dir', 'saves')), pc_root),
            runs=_expand_local_path(str(raw.get('pc_runs_dir', 'runs')), pc_root),
        )

        android_root = str(raw['android_root']).rstrip('/')
        android_paths = SidePaths(
            preferences=_join_remote(android_root, str(raw.get('android_preferences_dir', 'preferences'))),
            saves=_join_remote(android_root, str(raw.get('android_saves_dir', 'saves'))),
            runs=_join_remote(android_root, str(raw.get('android_runs_dir', 'runs'))),
        )

        return cls(
            config_path=config_path.resolve(),
            adb_path=str(raw.get('adb_path', 'adb')),
            device_serial=str(raw.get('device_serial', '')).strip() or None,
            pc_root=pc_root,
            pc_paths=pc_paths,
            android_root=android_root,
            android_paths=android_paths,
            android_root_candidates=[
                str(item).rstrip('/')
                for item in raw.get('android_root_candidates', [])
                if str(item).strip()
            ],
            backup_root=_expand_local_path(str(raw.get('backup_root', './backups')), base_dir),
            temp_root=_expand_local_path(str(raw.get('temp_root', './temp')), base_dir),
            log_root=_expand_local_path(str(raw.get('log_root', './logs')), base_dir),
            backup_keep=int(raw.get('backup_keep', 10)),
        )

    def ensure_runtime_dirs(self) -> None:
        self.backup_root.mkdir(parents=True, exist_ok=True)
        self.temp_root.mkdir(parents=True, exist_ok=True)
        self.log_root.mkdir(parents=True, exist_ok=True)

    def to_manifest_dict(self) -> dict[str, Any]:
        return {
            'config_path': str(self.config_path),
            'adb_path': self.adb_path,
            'device_serial': self.device_serial,
            'pc_root': str(self.pc_root),
            'pc_paths': {
                'preferences': str(self.pc_paths.preferences),
                'saves': str(self.pc_paths.saves),
                'runs': str(self.pc_paths.runs),
            },
            'android_root': self.android_root,
            'android_paths': {
                'preferences': self.android_paths.preferences,
                'saves': self.android_paths.saves,
                'runs': self.android_paths.runs,
            },
            'backup_root': str(self.backup_root),
            'temp_root': str(self.temp_root),
            'log_root': str(self.log_root),
            'backup_keep': self.backup_keep,
        }
