from __future__ import annotations

import logging

from sts_syn.config import AppConfig
from sts_syn.ui.main_window import launch_gui


def run_gui(config: AppConfig, logger: logging.Logger, dry_run: bool = False) -> int:
    return launch_gui(config=config, logger=logger, dry_run=dry_run)
