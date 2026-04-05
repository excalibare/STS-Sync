from __future__ import annotations

import argparse
from pathlib import Path

from sts_syn.adb_client import ADBClient, AdbError
from sts_syn.backup import BackupManager
from sts_syn.commands.status import run_status
from sts_syn.commands.sync_ops import perform_pull, perform_push
from sts_syn.commands.sync_safe import run_sync_safe
from sts_syn.config import AppConfig
from sts_syn.manifest import write_manifest
from sts_syn.utils.logging_utils import setup_logging


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog='sts_sync',
        description='Safely sync Slay the Spire saves between Windows PC and Android using ADB.',
    )
    parser.add_argument(
        '--config',
        type=Path,
        default=Path('config.json'),
        help='Path to config JSON file (default: ./config.json)',
    )
    parser.add_argument('--device-serial', help='Override device serial from config.json')
    parser.add_argument('--dry-run', action='store_true', help='Show actions without copying data')
    parser.add_argument('--verbose', action='store_true', help='Enable verbose console logging')
    parser.add_argument(
        '--force',
        action='store_true',
        help='Allow dangerous operations such as push-save',
    )

    subparsers = parser.add_subparsers(dest='command', required=True)
    for name in (
        'status',
        'backup',
        'sync-safe',
        'pull-progress',
        'push-progress',
        'pull-save',
        'push-save',
        'pull-runs',
        'push-runs',
    ):
        subparsers.add_parser(name)
    return parser


def _load_config(path: Path) -> AppConfig:
    if not path.exists():
        raise FileNotFoundError(
            f'config file not found: {path}. Copy config.example.json to config.json first.'
        )
    return AppConfig.load(path.resolve())


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    config = _load_config(args.config)
    if args.device_serial:
        config = AppConfig(
            config_path=config.config_path,
            adb_path=config.adb_path,
            device_serial=args.device_serial,
            pc_root=config.pc_root,
            pc_paths=config.pc_paths,
            android_root=config.android_root,
            android_paths=config.android_paths,
            android_root_candidates=config.android_root_candidates,
            backup_root=config.backup_root,
            temp_root=config.temp_root,
            log_root=config.log_root,
            backup_keep=config.backup_keep,
        )
    config.ensure_runtime_dirs()

    logger = setup_logging(config.log_root, verbose=args.verbose)
    logger.info('Starting sts_sync command=%s dry_run=%s', args.command, args.dry_run)

    adb = ADBClient(
        adb_path=config.adb_path,
        logger=logger,
        device_serial=config.device_serial,
        dry_run=args.dry_run,
    )
    backup_manager = BackupManager(config, adb, logger)

    try:
        if args.command == 'status':
            return run_status(config, adb, logger)
        if args.command == 'backup':
            if not adb.check_adb_available():
                raise AdbError(f'adb not available: {config.adb_path}')
            serial = adb.resolve_device(config.device_serial)
            if args.dry_run:
                logger.info('[dry-run] Would create a full backup for all components')
                return 0
            session_dir = backup_manager.create_session_dir('backup')
            copied = backup_manager.full_backup(session_dir)
            write_manifest(
                session_dir / 'manifest.json',
                {
                    'command': 'backup',
                    'serial': serial,
                    'dry_run': args.dry_run,
                    'copied': copied,
                    'config': config.to_manifest_dict(),
                },
            )
            backup_manager.prune_old_backups()
            logger.info('Backup completed: %s', session_dir)
            return 0
        if args.command == 'sync-safe':
            return run_sync_safe(config, adb, backup_manager, logger, dry_run=args.dry_run)
        if args.command == 'pull-progress':
            return perform_pull(
                config, adb, backup_manager, logger, 'preferences', args.command, args.dry_run
            )
        if args.command == 'push-progress':
            return perform_push(
                config,
                adb,
                backup_manager,
                logger,
                'preferences',
                args.command,
                args.dry_run,
                args.force,
            )
        if args.command == 'pull-save':
            logger.warning('pull-save targets current run data; make sure the game is closed.')
            return perform_pull(config, adb, backup_manager, logger, 'saves', args.command, args.dry_run)
        if args.command == 'push-save':
            logger.warning('push-save is dangerous and requires --force.')
            return perform_push(
                config,
                adb,
                backup_manager,
                logger,
                'saves',
                args.command,
                args.dry_run,
                args.force,
            )
        if args.command == 'pull-runs':
            return perform_pull(config, adb, backup_manager, logger, 'runs', args.command, args.dry_run)
        if args.command == 'push-runs':
            return perform_push(
                config,
                adb,
                backup_manager,
                logger,
                'runs',
                args.command,
                args.dry_run,
                args.force,
            )
        parser.error(f'unknown command: {args.command}')
        return 2
    except Exception as exc:  # noqa: BLE001
        logger.exception('Command failed: %s', exc)
        print(f'Error: {exc}')
        return 1
