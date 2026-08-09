"""Segmented realtime audio level meter (microphone input / TTS output)."""

from __future__ import annotations

from PySide6.QtCore import QRectF, QSize, Qt, QTimer
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QWidget

from ..theme import Palette

_SEGMENTS = 22


class LevelMeter(QWidget):
    """Smoothed, decaying level bar.

    Feed it raw RMS values; it interpolates so a 20 Hz backend still looks
    like a 60 fps meter, and holds a decaying peak marker.
    """

    def __init__(self, palette: Palette, parent=None):
        super().__init__(parent)
        self._palette = palette
        self._target = 0.0
        self._level = 0.0
        self._peak = 0.0
        self._muted = False
        self.setFixedHeight(10)
        self.setMinimumWidth(120)

        self._timer = QTimer(self)
        self._timer.setInterval(16)
        self._timer.timeout.connect(self._tick)

    # -- api ---------------------------------------------------------------

    def set_level(self, value: float) -> None:
        self._target = max(0.0, min(1.0, float(value)))

    def set_muted(self, muted: bool) -> None:
        self._muted = bool(muted)
        self.update()

    def set_palette(self, palette: Palette) -> None:
        self._palette = palette
        self.update()

    # -- lifecycle: never animate while invisible --------------------------

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._timer.start()

    def hideEvent(self, event) -> None:
        super().hideEvent(event)
        self._timer.stop()

    def sizeHint(self) -> QSize:
        return QSize(160, 10)

    # -- internals ---------------------------------------------------------

    def _tick(self) -> None:
        target = 0.0 if self._muted else self._target
        self._level += (target - self._level) * 0.25
        self._peak = max(self._peak - 0.012, self._level)
        self.update()

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        pal = self._palette

        w, h = float(self.width()), float(self.height())
        gap = 2.0
        seg_w = max(1.5, (w - gap * (_SEGMENTS - 1)) / _SEGMENTS)
        radius = min(2.0, seg_w / 2)

        idle = QColor(pal.text_faint)
        idle.setAlpha(60)

        lit = int(round(self._level * _SEGMENTS))
        peak_index = int(round(self._peak * _SEGMENTS)) - 1

        for i in range(_SEGMENTS):
            x = i * (seg_w + gap)
            ratio = i / max(1, _SEGMENTS - 1)
            if self._muted:
                color = idle
            elif i < lit:
                color = QColor(pal.accent) if ratio < 0.72 else QColor(pal.danger)
            elif i == peak_index:
                color = QColor(pal.accent)
                color.setAlpha(120)
            else:
                color = idle
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(color)
            p.drawRoundedRect(QRectF(x, 0, seg_w, h), radius, radius)
        p.end()
