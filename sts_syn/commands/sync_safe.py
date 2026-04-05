from __future__ import annotations

import logging

from sts_syn.adb_client import ADBClient
from sts_syn.backup import BackupManager
from sts_syn.commands.sync_ops import perform_pull
from sts_syn.config import AppConfig


def run_sync_safe(
    config: AppConfig,
    adb: ADBClient,
    backup_manager: BackupManager,
    logger: logging.Logger,
    dry_run: bool,
) -> int:
    logger.info('sync-safe only handles preferences')
    return perform_pull(
        config=config,
        adb=adb,
        backup_manager=backup_manager,
        logger=logger,
        component='preferences',
        command_name='sync-safe',
        dry_run=dry_run,
    )
