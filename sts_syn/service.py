from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from sts_syn.adb_client import ADBClient, AdbError
from sts_syn.backup import BackupManager
from sts_syn.commands.sync_ops import perform_pull, perform_push
from sts_syn.commands.sync_safe import run_sync_safe
from sts_syn.config import AppConfig
from sts_syn.file_ops import local_dir_status
from sts_syn.manifest import write_manifest
from sts_syn.models import COMPONENTS, DeviceInfo, DirStatus


@dataclass(frozen=True)
class EnvironmentStatus:
    adb_available: bool
    configured_serial: str | None
    selected_serial: str | None
    serial_required: bool
    device_message: str
    android_root_exists: bool
    android_root_detected: str | None
    pc_root_exists: bool
    pc_status: dict[str, DirStatus]
    android_status: dict[str, DirStatus]
    devices: list[DeviceInfo]


class SyncService:
    def __init__(self, config: AppConfig, logger: logging.Logger, dry_run: bool = False) -> None:
        self.config = config
        self.logger = logger
        self.dry_run = dry_run

    def create_adb(self, device_serial: str | None = None) -> ADBClient:
        serial = device_serial if device_serial is not None else self.config.device_serial
        return ADBClient(
            adb_path=self.config.adb_path,
            logger=self.logger,
            device_serial=serial,
            dry_run=self.dry_run,
        )

    def inspect_environment(self, device_serial: str | None = None) -> EnvironmentStatus:
        adb = self.create_adb(device_serial)
        adb_available = adb.check_adb_available()
        devices: list[DeviceInfo] = []
        selected_serial: str | None = device_serial or self.config.device_serial
        serial_required = False
        device_message = 'ADB unavailable'
        android_root_exists = False
        android_root_detected: str | None = None
        android_status = {
            component: DirStatus(path=self.config.android_paths.get(component), exists=False, file_count=None, latest_mtime=None)
            for component in COMPONENTS
        }

        if adb_available:
            try:
                devices = adb.list_devices()
            except AdbError as exc:
                device_message = str(exc)
            else:
                online_devices = [item for item in devices if item.state == 'device']
                if selected_serial:
                    if any(item.serial == selected_serial and item.state == 'device' for item in devices):
                        adb.device_serial = selected_serial
                        device_message = f'Connected: {selected_serial}'
                    else:
                        device_message = f'Selected device not online: {selected_serial}'
                elif len(online_devices) == 1:
                    selected_serial = online_devices[0].serial
                    adb.device_serial = selected_serial
                    device_message = f'Connected: {selected_serial}'
                elif len(online_devices) > 1:
                    serial_required = True
                    device_message = 'Multiple devices detected; please choose a serial.'
                else:
                    device_message = 'No online adb device detected.'

                if adb.device_serial:
                    try:
                        android_root_exists = adb.directory_exists(self.config.android_root)
                        if not android_root_exists and self.config.android_root_candidates:
                            android_root_detected = adb.detect_first_existing_root(self.config.android_root_candidates)
                        android_status = {
                            component: adb.get_dir_status(self.config.android_paths.get(component))
                            for component in COMPONENTS
                        }
                    except AdbError as exc:
                        device_message = str(exc)

        pc_status = {component: local_dir_status(self.config.pc_paths.get(component)) for component in COMPONENTS}
        return EnvironmentStatus(
            adb_available=adb_available,
            configured_serial=self.config.device_serial,
            selected_serial=selected_serial,
            serial_required=serial_required,
            device_message=device_message,
            android_root_exists=android_root_exists,
            android_root_detected=android_root_detected,
            pc_root_exists=self.config.pc_root.exists(),
            pc_status=pc_status,
            android_status=android_status,
            devices=devices,
        )

    def run_backup(self, device_serial: str | None = None) -> int:
        adb = self.create_adb(device_serial)
        backup_manager = BackupManager(self.config, adb, self.logger)
        if not adb.check_adb_available():
            raise AdbError(f'adb not available: {self.config.adb_path}')
        serial = adb.resolve_device(device_serial or self.config.device_serial)
        if self.dry_run:
            self.logger.info('[dry-run] Would create a full backup for all components')
            return 0
        session_dir = backup_manager.create_session_dir('backup')
        copied = backup_manager.full_backup(session_dir)
        write_manifest(
            session_dir / 'manifest.json',
            {
                'command': 'backup',
                'serial': serial,
                'dry_run': self.dry_run,
                'copied': copied,
                'config': self.config.to_manifest_dict(),
            },
        )
        backup_manager.prune_old_backups()
        self.logger.info('Backup completed: %s', session_dir)
        return 0

    def run_command(self, command: str, device_serial: str | None = None, force: bool = False) -> int:
        adb = self.create_adb(device_serial)
        backup_manager = BackupManager(self.config, adb, self.logger)

        if command == 'sync-safe':
            return run_sync_safe(self.config, adb, backup_manager, self.logger, dry_run=self.dry_run)
        if command == 'pull-progress':
            return perform_pull(self.config, adb, backup_manager, self.logger, 'preferences', command, self.dry_run)
        if command == 'push-progress':
            return perform_push(self.config, adb, backup_manager, self.logger, 'preferences', command, self.dry_run, force)
        if command == 'pull-save':
            self.logger.warning('pull-save targets current run data; make sure the game is closed.')
            return perform_pull(self.config, adb, backup_manager, self.logger, 'saves', command, self.dry_run)
        if command == 'push-save':
            self.logger.warning('push-save is dangerous and requires --force.')
            return perform_push(self.config, adb, backup_manager, self.logger, 'saves', command, self.dry_run, force)
        if command == 'pull-runs':
            return perform_pull(self.config, adb, backup_manager, self.logger, 'runs', command, self.dry_run)
        if command == 'push-runs':
            return perform_push(self.config, adb, backup_manager, self.logger, 'runs', command, self.dry_run, force)
        if command == 'backup':
            return self.run_backup(device_serial=device_serial)
        raise ValueError(f'Unknown command: {command}')


