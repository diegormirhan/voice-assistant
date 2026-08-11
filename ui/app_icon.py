"""Rounded application icon used by the taskbar, Alt-Tab and the system tray."""

from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import (
    QColor,
    QIcon,
    QPainter,
    QPainterPath,
    QPixmap,
)

from .assets import ICON_ICO, ICON_JPG, asset

# Sizes Windows actually asks for: tray (16/20/24), taskbar (32/40/48), and
# the large variants used by Alt-Tab / task view.
_SIZES = (16, 20, 24, 32, 40, 48, 64, 128, 256)

_cache: QIcon | None = None


def _source() -> QPixmap | None:
    """Highest-quality source art available (jpg first — the .ico is small)."""
    for name in (ICON_JPG, ICON_ICO):
        path = asset(name)
        if path is None:
            continue
        pixmap = QPixmap(str(path))
        if not pixmap.isNull():
            return pixmap
    return None


def _round(source: QPixmap, side: int) -> QPixmap:
    out = QPixmap(side, side)
    out.fill(Qt.GlobalColor.transparent)

    p = QPainter(out)
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

    rect = QRectF(0.0, 0.0, float(side), float(side))
    clip = QPainterPath()
    clip.addEllipse(rect.adjusted(0.5, 0.5, -0.5, -0.5))
    p.setClipPath(clip)

    # Cover the circle without distorting the artwork.
    scaled = source.scaled(
        side,
        side,
        Qt.AspectRatioMode.KeepAspectRatioByExpanding,
        Qt.TransformationMode.SmoothTransformation,
    )
    p.drawPixmap(
        int((side - scaled.width()) / 2),
        int((side - scaled.height()) / 2),
        scaled,
    )

    # Hairline rim: keeps the silhouette crisp against any taskbar colour.
    p.setClipping(False)
    if side >= 20:
        p.setBrush(Qt.BrushStyle.NoBrush)
        pen_w = max(1.0, side / 32.0)
        from PySide6.QtGui import QPen  # local: keeps module import list tidy

        p.setPen(QPen(QColor(255, 255, 255, 46), pen_w))
        p.drawEllipse(rect.adjusted(pen_w / 2, pen_w / 2, -pen_w / 2, -pen_w / 2))
    p.end()
    return out


def app_icon() -> QIcon:
    """Rounded multi-size QIcon (cached). Empty QIcon when art is missing."""
    global _cache
    if _cache is not None:
        return _cache

    source = _source()
    icon = QIcon()
    if source is not None:
        for side in _SIZES:
            icon.addPixmap(_round(source, side))
    _cache = icon
    return icon
