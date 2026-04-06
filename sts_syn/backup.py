from __future__ import annotations

import logging
import shutil
import zipfile
from pathlib import Path
from typing import Iterable

from sts_syn.adb_client import ADBClient
from sts_syn.config import AppConfig
from sts_syn.file_ops import copy_dir_if_exists
from sts_syn.models import COMPONENTS
from sts_syn.utils.time_utils import timestamp_for_path


class BackupManager:
    def __init__(self, config: AppConfig, adb: ADBClient, logger: logging.Logger) -> None:
        self.config = config
        self.adb = adb
        self.logger = logger

    def create_session_dir(self, label: str) -> Path:
        session_dir = self.config.backup_root / f'{timestamp_for_path()}_{label}'
        session_dir.mkdir(parents=True, exist_ok=False)
        return session_dir

    def _write_directory_to_zip(self, source_dir: Path, archive_path: Path) -> None:
        with zipfile.ZipFile(archive_path, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
            if not source_dir.exists():
                return
            for path in sorted(source_dir.rglob('*')):
                relative_path = path.relative_to(source_dir)
                archive_name = relative_path.as_posix()
                if path.is_dir():
                    archive.writestr(f'{archive_name}/', '')
                else:
                    archive.write(path, arcname=archive_name)

    def _compress_stage_dir(self, session_dir: Path, stage: str) -> Path:
        stage_dir = session_dir / stage
        archive_path = session_dir / f'{stage}.zip'
        if archive_path.exists():
            archive_path.unlink()
        self._write_directory_to_zip(stage_dir, archive_path)
        shutil.rmtree(stage_dir, ignore_errors=True)
        self.logger.info('Compressed backup stage: %s', archive_path)
        return archive_path

    def backup_components(
        self, session_dir: Path, components: Iterable[str], stage: str, dry_run: bool = False
    ) -> dict[str, list[str]]:
        copied: dict[str, list[str]] = {'pc': [], 'android': []}
        if dry_run:
            self.logger.info('[dry-run] Would back up components=%s stage=%s', list(components), stage)
            return copied

        stage_dir = session_dir / stage
        for side in ('pc', 'android'):
            (stage_dir / side).mkdir(parents=True, exist_ok=True)

        for component in components:
            pc_source = self.config.pc_paths.get(component)
            pc_target = stage_dir / 'pc' / component
            if copy_dir_if_exists(pc_source, pc_target):
                copied['pc'].append(component)

            android_source = self.config.android_paths.get(component)
            android_target = stage_dir / 'android' / component
            if self.adb.directory_exists(android_source):
                self.adb.pull(android_source, android_target, check=True)
                copied['android'].append(component)

        self._compress_stage_dir(session_dir, stage)
        return copied

    def full_backup(self, session_dir: Path, dry_run: bool = False) -> dict[str, list[str]]:
        return self.backup_components(session_dir, COMPONENTS, stage='snapshot', dry_run=dry_run)

    def prune_old_backups(self) -> None:
        keep = self.config.backup_keep
        if keep <= 0:
            return
        dirs = sorted(
            [item for item in self.config.backup_root.iterdir() if item.is_dir()],
            key=lambda item: item.stat().st_mtime,
            reverse=True,
        )
        for stale in dirs[keep:]:
            self.logger.info('Pruning old backup: %s', stale)
            shutil.rmtree(stale, ignore_errors=True)
