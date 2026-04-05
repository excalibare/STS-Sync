from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from sts_syn.utils.time_utils import iso_now


def write_manifest(path: Path, payload: dict[str, Any]) -> None:
    data = {'written_at': iso_now(), **payload}
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
