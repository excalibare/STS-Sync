from __future__ import annotations

import argparse
from pathlib import Path

from sts_syn.commands.status import run_status
from sts_syn.config import AppConfig
from sts_syn.gui import run_gui
from sts_syn.service import SyncService
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
        'gui',
    ):
        subparsers.add_parser(name)
    return parser


def _load_config(path: Path) -> AppConfig:
    if not path.exists():
        raise FileNotFoundError(
            f'config file not found: {path}. Copy config.example.json to config.json first.'
        )
    return AppConfig.load(path.resolve())


def _override_serial(config: AppConfig, device_serial: str | None) -> AppConfig:
    if not device_serial:
        return config
    return AppConfig(
        config_path=config.config_path,
        adb_path=config.adb_path,
        device_serial=device_serial,
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


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    config = _override_serial(_load_config(args.config), args.device_serial)
    config.ensure_runtime_dirs()

    logger = setup_logging(config.log_root, verbose=args.verbose)
    logger.info('Starting sts_sync command=%s dry_run=%s', args.command, args.dry_run)
    service = SyncService(config=config, logger=logger, dry_run=args.dry_run)

    try:
        if args.command == 'status':
            return run_status(config, service.create_adb(config.device_serial), logger)
        if args.command == 'gui':
            return run_gui(config=config, logger=logger, dry_run=args.dry_run)
        if args.command == 'backup':
            return service.run_backup(device_serial=config.device_serial)
        return service.run_command(args.command, device_serial=config.device_serial, force=args.force)
    except Exception as exc:  # noqa: BLE001
        logger.exception('Command failed: %s', exc)
        print(f'Error: {exc}')
        return 1

