"""Asset path resolution that survives symlinks and PyInstaller bundles."""

from __future__ import annotations

import sys
from pathlib import Path

_HERE = Path(__file__).absolute().parent


def _candidates(name: str) -> list[Path]:
    paths = [_HERE / name]
    bundle = getattr(sys, "_MEIPASS", None)
    if bundle:
        base = Path(bundle)
        paths += [base / "ui" / name, base / name]
    paths.append(_HERE.parent / name)
    return paths


def asset(name: str) -> Path | None:
    """First existing path for `name`, or None when the asset is missing."""
    for path in _candidates(name):
        try:
            if path.is_file():
                return path
        except OSError:
            continue
    return None


def asset_str(name: str) -> str:
    path = asset(name)
    return str(path) if path is not None else ""


ICON_ICO = "icon.ico"
ICON_JPG = "icon.jpg"
