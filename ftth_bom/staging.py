from __future__ import annotations

import shutil
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


@contextmanager
def staged_gpkg_path(source: str | Path, enabled: bool = True) -> Iterator[Path]:
    source_path = Path(source)
    if not enabled:
        yield source_path
        return

    with tempfile.TemporaryDirectory(prefix="ftth_bom_gpkg_") as temp_dir:
        staged = Path(temp_dir) / source_path.name
        shutil.copy2(source_path, staged)
        yield staged
