from __future__ import annotations

import logging
import shutil
from datetime import datetime
from pathlib import Path

from sts_syn.models import DirStatus


class FileOpsError(RuntimeError):
    """Raised when local file operations fail."""


def ensure_clean_dir(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


def copy_dir_if_exists(source: Path, target: Path) -> bool:
    if not source.exists():
        return False
    if target.exists():
        shutil.rmtree(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, target)
    return True


def safe_replace_directory(source_dir: Path, target_dir: Path, logger: logging.Logger) -> None:
    if not source_dir.exists():
        raise FileOpsError(f'replacement source does not exist: {source_dir}')

    target_parent = target_dir.parent
    target_parent.mkdir(parents=True, exist_ok=True)
    tmp_target = target_parent / f'{target_dir.name}.tmp_replace'
    rollback_target = None

    if tmp_target.exists():
        shutil.rmtree(tmp_target)
    shutil.copytree(source_dir, tmp_target)

    try:
        if target_dir.exists():
            rollback_target = target_parent / f'{target_dir.name}.rollback_{datetime.now():%Y%m%d%H%M%S}'
            logger.debug('Preparing rollback directory: %s', rollback_target)
            target_dir.replace(rollback_target)
        tmp_target.replace(target_dir)
        if rollback_target and rollback_target.exists():
            shutil.rmtree(rollback_target)
    except Exception as exc:  # noqa: BLE001
        logger.exception('Failed during directory replacement, attempting rollback')
        if target_dir.exists():
            shutil.rmtree(target_dir, ignore_errors=True)
        if rollback_target and rollback_target.exists():
            rollback_target.replace(target_dir)
        if tmp_target.exists():
            shutil.rmtree(tmp_target, ignore_errors=True)
        raise FileOpsError(f'failed to replace directory {target_dir}: {exc}') from exc


def local_dir_status(path: Path) -> DirStatus:
    if not path.exists() or not path.is_dir():
        return DirStatus(path=str(path), exists=False, file_count=None, latest_mtime=None)

    files = [item for item in path.rglob('*') if item.is_file()]
    latest = max((item.stat().st_mtime for item in files), default=path.stat().st_mtime)
    return DirStatus(
        path=str(path),
        exists=True,
        file_count=len(files),
        latest_mtime=datetime.fromtimestamp(latest),
    )
