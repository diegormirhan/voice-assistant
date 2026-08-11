"""Pill-shaped animated toggle switch (accessible + keyboard friendly)."""

from __future__ import annotations

from PySide6.QtCore import (
    Property,
    QEasingCurve,
    QPropertyAnimation,
    QRectF,
    QSize,
    Qt,
    Signal,
)
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QWidget

from ..theme import T, Palette


class ToggleSwitch(QWidget):
    toggled = Signal(bool)

    def __init__(self, palette: Palette, checked: bool = False, parent=None):
        super().__init__(parent)
        self._palette = palette
        self._checked = bool(checked)
        self._pos = 1.0 if self._checked else 0.0
        self.setFixedSize(40, 22)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        self._anim = QPropertyAnimation(self, b"knob_position", self)
        self._anim.setDuration(T.base_ms)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)

    # -- animated property ------------------------------------------------

    def _get_pos(self) -> float:
        return self._pos

    def _set_pos(self, value: float) -> None:
        self._pos = float(value)
        self.update()

    knob_position = Property(float, _get_pos, _set_pos)

    # -- api ---------------------------------------------------------------

    def isChecked(self) -> bool:
        return self._checked

    def setChecked(self, value: bool, *, animate: bool = False) -> None:
        value = bool(value)
        if value == self._checked:
            return
        self._checked = value
        if animate:
            self._animate()
        else:
            self._anim.stop()
            self._set_pos(1.0 if value else 0.0)
        self.toggled.emit(self._checked)

    def set_palette(self, palette: Palette) -> None:
        self._palette = palette
        self.update()

    def toggle(self) -> None:
        self.setChecked(not self._checked, animate=True)

    # -- interaction -------------------------------------------------------

    def _animate(self) -> None:
        self._anim.stop()
        self._anim.setStartValue(self._pos)
        self._anim.setEndValue(1.0 if self._checked else 0.0)
        self._anim.start()

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self.rect().contains(
            event.position().toPoint()
        ):
            self.toggle()
        event.accept()

    def keyPressEvent(self, event) -> None:
        if event.key() in (Qt.Key.Key_Space, Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.toggle()
            event.accept()
            return
        super().keyPressEvent(event)

    def sizeHint(self) -> QSize:
        return QSize(40, 22)

    # -- painting ----------------------------------------------------------

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        pal = self._palette
        w, h = float(self.width()), float(self.height())
        radius = h / 2

        off = QColor(pal.text_faint)
        off.setAlpha(110)
        on = QColor(pal.accent)
        track = QColor(
            int(off.red() + (on.red() - off.red()) * self._pos),
            int(off.green() + (on.green() - off.green()) * self._pos),
            int(off.blue() + (on.blue() - off.blue()) * self._pos),
            int(off.alpha() + (255 - off.alpha()) * self._pos),
        )

        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(track)
        p.drawRoundedRect(QRectF(0, 0, w, h), radius, radius)

        if self.hasFocus():
            ring = QColor(pal.accent)
            ring.setAlpha(90)
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.setPen(ring)
            p.drawRoundedRect(QRectF(0.75, 0.75, w - 1.5, h - 1.5), radius, radius)
            p.setPen(Qt.PenStyle.NoPen)

        knob_r = h * 0.36
        margin = (h - knob_r * 2) / 2
        x_min, x_max = margin + knob_r, w - margin - knob_r
        cx = x_min + self._pos * (x_max - x_min)

        p.setBrush(QColor("#ffffff") if pal.is_dark or self._checked else QColor("#ffffff"))
        p.drawEllipse(QRectF(cx - knob_r, h / 2 - knob_r, knob_r * 2, knob_r * 2))
        p.end()
