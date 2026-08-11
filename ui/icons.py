"""Vector icons painted with QPainter — no icon font, no image assets."""

from __future__ import annotations

import math
from typing import Callable

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QGuiApplication, QIcon, QPainter, QPen, QPixmap

DrawFn = Callable[[QPainter, float], None]


def _dpr() -> float:
    app = QGuiApplication.instance()
    if app is None:
        return 1.0
    screen = QGuiApplication.primaryScreen()
    return float(screen.devicePixelRatio()) if screen else 1.0


def _pixmap(size: int, color: QColor, width: float, draw: DrawFn) -> QPixmap:
    ratio = max(1.0, _dpr())
    pm = QPixmap(int(round(size * ratio)), int(round(size * ratio)))
    pm.setDevicePixelRatio(ratio)
    pm.fill(Qt.GlobalColor.transparent)

    painter = QPainter(pm)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.scale(ratio, ratio)
    pen = QPen(color, width)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    painter.setPen(pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    draw(painter, float(size))
    painter.end()
    return pm


def _icon(size: int, color: str, width: float, draw: DrawFn) -> QIcon:
    return QIcon(_pixmap(size, QColor(color), width, draw))


def close(size: int = 14, color: str = "#f2f3f7") -> QIcon:
    def draw(p: QPainter, s: float) -> None:
        m = s * 0.26
        p.drawLine(QPointF(m, m), QPointF(s - m, s - m))
        p.drawLine(QPointF(s - m, m), QPointF(m, s - m))

    return _icon(size, color, 1.5, draw)


def minimize(size: int = 14, color: str = "#f2f3f7") -> QIcon:
    def draw(p: QPainter, s: float) -> None:
        m = s * 0.24
        p.drawLine(QPointF(m, s * 0.58), QPointF(s - m, s * 0.58))

    return _icon(size, color, 1.5, draw)


def maximize(size: int = 14, color: str = "#f2f3f7") -> QIcon:
    def draw(p: QPainter, s: float) -> None:
        m = s * 0.26
        r = QRectF(m, m, s - 2 * m, s - 2 * m)
        p.drawRoundedRect(r, s * 0.08, s * 0.08)

    return _icon(size, color, 1.4, draw)


def restore(size: int = 14, color: str = "#f2f3f7") -> QIcon:
    """Front square plus the visible corner of a second one behind it.

    Two full overlapping squares turn to mud at 13px, so the back square is
    reduced to its top-right elbow — exactly how Windows draws it.
    """

    def draw(p: QPainter, s: float) -> None:
        m = s * 0.24
        off = s * 0.16
        front = QRectF(m, m + off, s - 2 * m - off, s - 2 * m - off)
        p.drawRoundedRect(front, s * 0.07, s * 0.07)
        p.drawLine(
            QPointF(front.left() + off, front.top() - off),
            QPointF(front.right() + off, front.top() - off),
        )
        p.drawLine(
            QPointF(front.right() + off, front.top() - off),
            QPointF(front.right() + off, front.bottom() - off),
        )

    return _icon(size, color, 1.35, draw)


def gear(size: int = 18, color: str = "#f2f3f7") -> QIcon:
    def draw(p: QPainter, s: float) -> None:
        cx = cy = s / 2
        inner, ring, tooth = s * 0.13, s * 0.29, s * 0.42
        p.drawEllipse(QPointF(cx, cy), inner, inner)
        p.drawEllipse(QPointF(cx, cy), ring, ring)
        for i in range(6):
            a = i * math.pi / 3 + math.pi / 12
            p.drawLine(
                QPointF(cx + ring * math.cos(a), cy + ring * math.sin(a)),
                QPointF(cx + tooth * math.cos(a), cy + tooth * math.sin(a)),
            )

    return _icon(size, color, 1.25, draw)


def download(size: int = 16, color: str = "#f2f3f7") -> QIcon:
    def draw(p: QPainter, s: float) -> None:
        cx = s / 2
        top, tip = s * 0.14, s * 0.56
        wing = s * 0.17
        p.drawLine(QPointF(cx, top), QPointF(cx, tip))
        p.drawLine(QPointF(cx - wing, tip - wing), QPointF(cx, tip))
        p.drawLine(QPointF(cx + wing, tip - wing), QPointF(cx, tip))
        left, right = s * 0.2, s * 0.8
        base_top, base = s * 0.72, s * 0.84
        p.drawLine(QPointF(left, base_top), QPointF(left, base))
        p.drawLine(QPointF(left, base), QPointF(right, base))
        p.drawLine(QPointF(right, base), QPointF(right, base_top))

    return _icon(size, color, 1.3, draw)


def check(size: int = 14, color: str = "#4ade9b") -> QIcon:
    def draw(p: QPainter, s: float) -> None:
        p.drawLine(QPointF(s * 0.2, s * 0.54), QPointF(s * 0.42, s * 0.74))
        p.drawLine(QPointF(s * 0.42, s * 0.74), QPointF(s * 0.8, s * 0.28))

    return _icon(size, color, 1.7, draw)


def chevron(size: int = 12, color: str = "#f2f3f7", down: bool = False) -> QIcon:
    def draw(p: QPainter, s: float) -> None:
        m = s * 0.3
        if down:
            p.drawLine(QPointF(m, s * 0.4), QPointF(s / 2, s * 0.66))
            p.drawLine(QPointF(s / 2, s * 0.66), QPointF(s - m, s * 0.4))
        else:
            p.drawLine(QPointF(s * 0.4, m), QPointF(s * 0.66, s / 2))
            p.drawLine(QPointF(s * 0.66, s / 2), QPointF(s * 0.4, s - m))

    return _icon(size, color, 1.4, draw)


def trash(size: int = 14, color: str = "#a6abbd") -> QIcon:
    def draw(p: QPainter, s: float) -> None:
        p.drawLine(QPointF(s * 0.16, s * 0.28), QPointF(s * 0.84, s * 0.28))
        p.drawArc(
            QRectF(s * 0.24, s * 0.28, s * 0.52, s * 0.62),
            0,
            -180 * 16,
        )
        p.drawLine(QPointF(s * 0.24, s * 0.28), QPointF(s * 0.24, s * 0.72))
        p.drawLine(QPointF(s * 0.76, s * 0.28), QPointF(s * 0.76, s * 0.72))
        p.drawLine(QPointF(s * 0.38, s * 0.28), QPointF(s * 0.42, s * 0.14))
        p.drawLine(QPointF(s * 0.62, s * 0.28), QPointF(s * 0.58, s * 0.14))

    return _icon(size, color, 1.25, draw)


def power(size: int = 22, color: str = "#f2f3f7") -> QIcon:
    def draw(p: QPainter, s: float) -> None:
        r = s * 0.3
        rect = QRectF(s / 2 - r, s / 2 - r, r * 2, r * 2)
        p.drawArc(rect, 60 * 16, 240 * 16)
        p.drawLine(QPointF(s / 2, s * 0.14), QPointF(s / 2, s * 0.44))

    return _icon(size, color, 2.0, draw)


def mic(size: int = 14, color: str = "#a6abbd", muted: bool = False) -> QIcon:
    def draw(p: QPainter, s: float) -> None:
        p.drawRoundedRect(
            QRectF(s * 0.38, s * 0.14, s * 0.24, s * 0.42), s * 0.12, s * 0.12
        )
        p.drawArc(QRectF(s * 0.26, s * 0.34, s * 0.48, s * 0.42), 0, -180 * 16)
        p.drawLine(QPointF(s / 2, s * 0.76), QPointF(s / 2, s * 0.88))
        if muted:
            p.drawLine(QPointF(s * 0.16, s * 0.86), QPointF(s * 0.84, s * 0.12))

    return _icon(size, color, 1.25, draw)


# ── Select / info glyphs ───────────────────────────────────────────────────


def pixmap(draw: DrawFn, size: int, color: str, width: float = 1.35) -> QPixmap:
    """Escape hatch for widgets that paint a glyph themselves (e.g. selects)."""
    return _pixmap(size, QColor(color), width, draw)


def _chevron_draw(p: QPainter, s: float) -> None:
    m = s * 0.28
    p.drawLine(QPointF(m, s * 0.4), QPointF(s / 2, s * 0.64))
    p.drawLine(QPointF(s / 2, s * 0.64), QPointF(s - m, s * 0.4))


def chevron_pixmap(size: int = 10, color: str = "#a6abbd") -> QPixmap:
    return _pixmap(size, QColor(color), 1.5, _chevron_draw)


def chip(size: int = 15, color: str = "#a6abbd") -> QIcon:
    """Silicon die with pins — the model profile glyph."""

    def draw(p: QPainter, s: float) -> None:
        outer = QRectF(s * 0.24, s * 0.24, s * 0.52, s * 0.52)
        p.drawRoundedRect(outer, s * 0.09, s * 0.09)
        inner = QRectF(s * 0.39, s * 0.39, s * 0.22, s * 0.22)
        p.drawRoundedRect(inner, s * 0.05, s * 0.05)
        for frac in (0.38, 0.5, 0.62):
            v = s * frac
            p.drawLine(QPointF(v, s * 0.24), QPointF(v, s * 0.12))
            p.drawLine(QPointF(v, s * 0.76), QPointF(v, s * 0.88))
            p.drawLine(QPointF(s * 0.24, v), QPointF(s * 0.12, v))
            p.drawLine(QPointF(s * 0.76, v), QPointF(s * 0.88, v))

    return _icon(size, color, 1.2, draw)


def waveform(size: int = 15, color: str = "#a6abbd") -> QIcon:
    """Five bars of speech — the voice glyph."""

    def draw(p: QPainter, s: float) -> None:
        cy = s / 2
        for i, frac in enumerate((0.22, 0.46, 0.72, 0.42, 0.2)):
            x = s * (0.16 + i * 0.17)
            half = s * frac / 2
            p.drawLine(QPointF(x, cy - half), QPointF(x, cy + half))

    return _icon(size, color, 1.5, draw)


def info(size: int = 16, color: str = "#a6abbd") -> QIcon:
    def draw(p: QPainter, s: float) -> None:
        r = s * 0.36
        p.drawEllipse(QPointF(s / 2, s / 2), r, r)
        p.drawLine(QPointF(s / 2, s * 0.46), QPointF(s / 2, s * 0.7))
        p.drawPoint(QPointF(s / 2, s * 0.33))

    return _icon(size, color, 1.3, draw)
