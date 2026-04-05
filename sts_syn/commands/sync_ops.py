from __future__ import annotations

import logging
from pathlib import Path

from sts_syn.adb_client import ADBClient, AdbError
from sts_syn.backup import BackupManager
from sts_syn.config import AppConfig
from sts_syn.file_ops import ensure_clean_dir, local_dir_status, safe_replace_directory
from sts_syn.manifest import write_manifest


def _component_label(component: str) -> str:
    return {
        'preferences': '长期进度目录 preferences',
        'saves': '当前对局目录 saves',
        'runs': '历史记录目录 runs',
    }[component]


def _ensure_runtime(config: AppConfig, adb: ADBClient, logger: logging.Logger) -> str:
    if not adb.check_adb_available():
        raise AdbError(f'adb not available: {config.adb_path}')
    serial = adb.resolve_device(config.device_serial)
    logger.info('Using device serial: %s', serial)
    if not adb.directory_exists(config.android_root) and config.android_root_candidates:
        detected = adb.detect_first_existing_root(config.android_root_candidates)
        if detected:
            logger.warning('Configured Android root not found, but candidate exists: %s', detected)
    return serial


def _write_result_manifest(
    session_dir: Path,
    config: AppConfig,
    command_name: str,
    serial: str,
    component: str,
    direction: str,
    source: str,
    target: str,
    dry_run: bool,
    force: bool = False,
    source_file_count: int | None = None,
    target_file_count: int | None = None,
) -> None:
    write_manifest(
        session_dir / 'manifest.json',
        {
            'command': command_name,
            'serial': serial,
            'component': component,
            'direction': direction,
            'dry_run': dry_run,
            'force': force,
            'source': source,
            'target': target,
            'source_file_count_after': source_file_count,
            'target_file_count_after': target_file_count,
            'component_note': _component_label(component),
            'config': config.to_manifest_dict(),
        },
    )


def perform_pull(
    config: AppConfig,
    adb: ADBClient,
    backup_manager: BackupManager,
    logger: logging.Logger,
    component: str,
    command_name: str,
    dry_run: bool,
) -> int:
    serial = _ensure_runtime(config, adb, logger)
    remote_path = config.android_paths.get(component)
    local_path = config.pc_paths.get(component)

    if not adb.directory_exists(remote_path):
        raise AdbError(f'Android directory does not exist: {remote_path}')

    if dry_run:
        logger.info('[dry-run] Would back up %s before pull', component)
        logger.info('[dry-run] Would pull %s -> %s via temporary directory', remote_path, local_path)
        logger.info('[dry-run] Would create post-backup and manifest for %s', component)
        return 0

    session_dir = backup_manager.create_session_dir(command_name)
    logger.info('Created backup session: %s', session_dir)
    backup_manager.backup_components(session_dir, [component], stage='pre')

    staging_root = config.temp_root / session_dir.name / 'pull'
    ensure_clean_dir(staging_root)
    staging_dir = staging_root / component
    adb.pull(remote_path, staging_dir, check=True)

    safe_replace_directory(staging_dir, local_path, logger)
    logger.info('Pull completed for %s', component)

    backup_manager.backup_components(session_dir, [component], stage='post')
    _write_result_manifest(
        session_dir=session_dir,
        config=config,
        command_name=command_name,
        serial=serial,
        component=component,
        direction='android_to_pc',
        source=remote_path,
        target=str(local_path),
        dry_run=dry_run,
        source_file_count=adb.get_dir_status(remote_path).file_count,
        target_file_count=local_dir_status(local_path).file_count,
    )
    backup_manager.prune_old_backups()
    return 0


def perform_push(
    config: AppConfig,
    adb: ADBClient,
    backup_manager: BackupManager,
    logger: logging.Logger,
    component: str,
    command_name: str,
    dry_run: bool,
    force: bool,
) -> int:
    serial = _ensure_runtime(config, adb, logger)
    remote_path = config.android_paths.get(component)
    local_path = config.pc_paths.get(component)

    if not local_path.exists():
        raise FileNotFoundError(f'PC directory does not exist: {local_path}')

    if component == 'saves' and not force:
        raise RuntimeError(
            'push-save is blocked by default because saves may overwrite an active run. '
            'Re-run with --force after confirming both game clients are closed.'
        )

    if component == 'saves':
        logger.warning('Dangerous operation: pushing current run saves may overwrite progress.')
        if adb.directory_exists(remote_path) or local_path.exists():
            logger.warning('saves detected on at least one side: this may overwrite current run state.')

    if dry_run:
        logger.info('[dry-run] Would back up %s before push', component)
        logger.info('[dry-run] Would push %s -> %s', local_path, remote_path)
        logger.info('[dry-run] Would create post-backup and manifest for %s', component)
        return 0

    session_dir = backup_manager.create_session_dir(command_name)
    logger.info('Created backup session: %s', session_dir)
    backup_manager.backup_components(session_dir, [component], stage='pre')

    adb.ensure_remote_dir(config.android_root)
    trash_path = f'{remote_path}.backup_replace'
    if adb.directory_exists(trash_path):
        adb.delete_remote_dir(trash_path)
    if adb.directory_exists(remote_path):
        adb.move_remote_dir(remote_path, trash_path)
    adb.ensure_remote_dir(remote_path)

    try:
        adb.push_directory_contents(local_path, remote_path, check=True)
    except Exception:
        if adb.directory_exists(remote_path):
            adb.delete_remote_dir(remote_path)
        if adb.directory_exists(trash_path):
            adb.move_remote_dir(trash_path, remote_path)
        raise
    else:
        if adb.directory_exists(trash_path):
            adb.delete_remote_dir(trash_path)

    logger.info('Push completed for %s', component)
    backup_manager.backup_components(session_dir, [component], stage='post')
    _write_result_manifest(
        session_dir=session_dir,
        config=config,
        command_name=command_name,
        serial=serial,
        component=component,
        direction='pc_to_android',
        source=str(local_path),
        target=remote_path,
        dry_run=dry_run,
        force=force,
        source_file_count=local_dir_status(local_path).file_count,
        target_file_count=adb.get_dir_status(remote_path).file_count,
    )
    backup_manager.prune_old_backups()
    return 0

