from __future__ import annotations

import logging

from sts_syn.adb_client import ADBClient, AdbError
from sts_syn.config import AppConfig
from sts_syn.file_ops import local_dir_status
from sts_syn.models import COMPONENTS
from sts_syn.utils.time_utils import format_dt


def run_status(config: AppConfig, adb: ADBClient, logger: logging.Logger) -> int:
    print('=== STS Sync Status ===')
    adb_ok = adb.check_adb_available()
    print(f"ADB available: {'yes' if adb_ok else 'no'}")
    if not adb_ok:
        return 1

    try:
        serial = adb.resolve_device(config.device_serial)
    except AdbError as exc:
        logger.error('%s', exc)
        print(f'Device: unavailable ({exc})')
        return 1

    print(f'Device serial: {serial}')
    print(f'Android root: {config.android_root}')
    print(f'PC root: {config.pc_root}')
    print()

    print('PC side:')
    for component in COMPONENTS:
        status = local_dir_status(config.pc_paths.get(component))
        print(
            f"  - {component}: exists={status.exists}, files={status.file_count or 0}, "
            f"latest={format_dt(status.latest_mtime)}"
        )

    print()
    print('Android side:')
    root_exists = adb.directory_exists(config.android_root)
    print(f'  - root exists={root_exists}')
    if not root_exists and config.android_root_candidates:
        detected = adb.detect_first_existing_root(config.android_root_candidates)
        if detected:
            print(f'  - detected alternative root: {detected}')
        else:
            print('  - no candidate Android root detected')

    for component in COMPONENTS:
        status = adb.get_dir_status(config.android_paths.get(component))
        print(
            f"  - {component}: exists={status.exists}, files={status.file_count or 0}, "
            f"latest={format_dt(status.latest_mtime)}"
        )

    return 0
