"""config.json load/save — validated, clamped and written atomically.

Bugs fixed here vs. the previous version:
  * a corrupt/hand-edited value (wrong type, out of range, unknown theme)
    used to crash the UI at startup; every field is now coerced + clamped;
  * `save()` wrote in place, so a crash mid-write left a truncated file;
    it now writes to a temp file and replaces atomically;
  * `save()` raised on a read-only folder and took the app down with it.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "config.json"

DEFAULTS: dict[str, Any] = {
    "theme": "dark",
    "always_on_top": True,
    "minimize_to_tray": True,
    "min_speech_ms": 250,
    "hangover_ms": 1000,
    "length_scale": 1.3,
    "noise_scale": 0.6,
    "volume": 1.0,
    "mic_muted": False,
    "vision_enabled": True,
    "transcript_visible": False,
    "transcript_expanded": False,
    "model_profile": "padrao",
    "voice": "pt_BR-faber-medium",
    "window_w": 880,
    "window_h": 660,
}

# key -> (low, high) for numeric clamping.
_RANGES: dict[str, tuple[float, float]] = {
    "min_speech_ms": (100, 1000),
    "hangover_ms": (300, 3000),
    "length_scale": (0.8, 2.0),
    "noise_scale": (0.3, 1.0),
    "volume": (0.0, 1.0),
    "window_w": (640, 6000),
    "window_h": (480, 4000),
}

_CHOICES: dict[str, tuple[str, ...]] = {
    "theme": ("dark", "light"),
    "model_profile": ("padrao", "leve"),
}


def _coerce(key: str, value: Any) -> Any:
    default = DEFAULTS[key]
    try:
        if isinstance(default, bool):
            value = bool(value)
        elif isinstance(default, int):
            value = int(round(float(value)))
        elif isinstance(default, float):
            value = float(value)
        else:
            value = str(value)
    except (TypeError, ValueError):
        return default

    if key in _RANGES:
        lo, hi = _RANGES[key]
        value = type(default)(min(max(value, lo), hi))
    if key in _CHOICES and value not in _CHOICES[key]:
        return default
    return value


def sanitize(data: dict[str, Any] | None) -> dict[str, Any]:
    """Returns a complete config: defaults overlaid with valid saved values."""
    out = dict(DEFAULTS)
    for key, value in (data or {}).items():
        if key in DEFAULTS:
            out[key] = _coerce(key, value)
    return out


def load() -> dict[str, Any]:
    raw: dict[str, Any] = {}
    if CONFIG_PATH.exists():
        try:
            parsed = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
            if isinstance(parsed, dict):
                raw = parsed
        except (json.JSONDecodeError, OSError, UnicodeDecodeError):
            raw = {}
    return sanitize(raw)


def save(config: dict[str, Any]) -> bool:
    """Atomically persists the known keys. Never raises."""
    payload = sanitize(config)
    text = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
    tmp_path = None
    try:
        CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_path = tempfile.mkstemp(
            dir=str(CONFIG_PATH.parent), prefix=".config-", suffix=".tmp"
        )
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_path, CONFIG_PATH)
        return True
    except OSError:
        if tmp_path:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
        return False
