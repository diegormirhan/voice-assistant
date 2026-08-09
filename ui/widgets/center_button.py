"""Central power button: circular, reactive glow ring, hover micro-interaction.

Bugs fixed vs. the previous version:
  * clicking it did nothing — there was no state handling at all, so the
    "ligar/desligar" control from UI.md was inert. It now toggles and emits
    `toggled_on`.
  * the 60 fps repaint timer ran forever, even with the assistant OFF and the
    window minimised (constant CPU/GPU wakeups). It now stops when the widget
    is hidden and idles at a low rate when OFF.
  * `set_amplitude()` never scheduled a repaint, so the ring only moved
    because of the unrelated animation timer.
  * `icon.jpg` was drawn as a rounded *square* on top of a circle, so its
    corners spilled outside the orb. The logo is now clipped to the circle
    and scaled with KeepAspectRatioByExpanding (no stretching).
  * the pixmap was cached once with no DPR, so it was blurry on scaled
    displays and never invalidated when the widget resized.
"""

from __future__ import annotations

import math


from PySide6.QtCore import (
    QEasingCurve,
    QPointF,
    QPropertyAnimation,
    QRectF,
    Qt,
    QTimer,
    Property,
    Signal,
)
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import QPushButton

from ..assets import ICON_JPG, asset
from ..state import AssistantState
from ..theme import T, Palette
from .status_ring import StatusRing


_ACTIVE_INTERVAL = 16   # ~60 fps while the assistant is working
_IDLE_INTERVAL = 90     # gentle breathing while OFF


class CenterButton(QPushButton):
    toggled_on = Signal(bool)

    def __init__(self, palette: Palette, parent=None):
        super().__init__("", parent)
        self._palette = palette
        self._ring = StatusRing()
        self._state = AssistantState.OFF
        self._amp = 0.0
        self._display_amp = 0.0
        self._phase = 0.0
        self._hover = 0.0
        self._logo: QPixmap | None = None
        self._logo_key: tuple[int, float] | None = None

        self._radius = float(T.ring_radius)
        span = int((T.ring_radius + T.ring_margin) * 2)
        self.setFixedSize(span, span)
        self.setObjectName("powerBtn")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setToolTip("Ligar o assistente")
        self.clicked.connect(self._on_clicked)

        self._hover_anim = QPropertyAnimation(self, b"hover_amount", self)
        self._hover_anim.setDuration(T.base_ms)
        self._hover_anim.setEasingCurve(QEasingCurve.Type.OutCubic)

        self._timer = QTimer(self)
        self._timer.setInterval(_IDLE_INTERVAL)
        self._timer.timeout.connect(self._tick)

    # -- animated hover property ------------------------------------------

    def _get_hover(self) -> float:
        return self._hover

    def _set_hover(self, value: float) -> None:
        self._hover = float(value)
        self.update()

    hover_amount = Property(float, _get_hover, _set_hover)

    # -- api ---------------------------------------------------------------

    def set_palette(self, palette: Palette) -> None:
        self._palette = palette
        self.update()

    def state(self) -> AssistantState:
        return self._state

    def set_state(self, state: AssistantState) -> None:
        if state is self._state:
            return
        self._state = state
        self._timer.setInterval(
            _IDLE_INTERVAL if state is AssistantState.OFF else _ACTIVE_INTERVAL
        )
        self.setToolTip(
            "Ligar o assistente"
            if state is AssistantState.OFF
            else f"{state.label} — clique para desligar"
        )
        if state is AssistantState.OFF:
            self._amp = 0.0
        self.update()

    def set_amplitude(self, amplitude: float) -> None:
        self._amp = max(0.0, min(1.0, float(amplitude)))
        if not self._timer.isActive():
            self.update()

    # -- lifecycle ---------------------------------------------------------

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._timer.start()

    def hideEvent(self, event) -> None:
        super().hideEvent(event)
        self._timer.stop()

    # -- interaction -------------------------------------------------------

    def _on_clicked(self) -> None:
        self.toggled_on.emit(self._state is AssistantState.OFF)

    def enterEvent(self, event) -> None:
        super().enterEvent(event)
        self._animate_hover(1.0)

    def leaveEvent(self, event) -> None:
        super().leaveEvent(event)
        self._animate_hover(0.0)

    def _animate_hover(self, target: float) -> None:
        self._hover_anim.stop()
        self._hover_anim.setStartValue(self._hover)
        self._hover_anim.setEndValue(target)
        self._hover_anim.start()

    def _tick(self) -> None:
        self._phase = (self._phase + 0.05) % (math.pi * 2000)
        self._display_amp += (self._amp - self._display_amp) * 0.18
        self.update()

    # -- painting ----------------------------------------------------------

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

        center = QPointF(self.width() / 2, self.height() / 2)
        # Micro-interaction: 1.02 scale on hover, per UI.md.
        radius = self._radius * (1.0 + 0.02 * self._hover)
        if self.isDown():
            radius *= 0.985

        self._ring.paint(
            p,
            palette=self._palette,
            state=self._state,
            center=center,
            radius=radius,
            amplitude=self._display_amp,
            phase=self._phase,
            hover=self._hover,
            limit=min(self.width(), self.height()) / 2.0 - 1.0,
        )

        if self.hasFocus():
            focus = QColor(self._palette.accent)
            focus.setAlpha(120)
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.setPen(QPen(focus, 1.4))
            p.drawEllipse(center, radius + 9, radius + 9)

        self._paint_logo(p, center, radius)
        p.end()

    def _paint_logo(self, p: QPainter, center: QPointF, radius: float) -> None:
        inner = radius - 5
        logo = self._logo_pixmap(int(inner * 2))
        if logo is not None and not logo.isNull():
            path = QPainterPath()
            path.addEllipse(center, inner, inner)
            p.save()
            p.setClipPath(path)
            if self._state is AssistantState.OFF:
                p.setOpacity(0.5)
            target = QRectF(
                center.x() - inner, center.y() - inner, inner * 2, inner * 2
            )
            p.drawPixmap(target, logo, QRectF(logo.rect()))
            p.restore()
            return

        # Fallback glyph: power symbol drawn from the palette.
        color = QColor(self._palette.text)
        color.setAlpha(90 if self._state is AssistantState.OFF else 225)
        pen = QPen(color, 2.6)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        arc_r = inner * 0.42
        # Gap centred on 12 o'clock so the stem sits exactly in it.
        p.drawArc(
            QRectF(center.x() - arc_r, center.y() - arc_r, arc_r * 2, arc_r * 2),
            125 * 16,
            290 * 16,
        )
        p.drawLine(
            QPointF(center.x(), center.y() - arc_r * 1.42),
            QPointF(center.x(), center.y() - arc_r * 0.22),
        )

    def _logo_pixmap(self, side: int) -> QPixmap | None:
        path = asset(ICON_JPG)
        if side <= 0 or path is None:
            return None
        ratio = float(self.devicePixelRatioF() or 1.0)
        key = (side, ratio)
        if self._logo_key == key and self._logo is not None:
            return self._logo

        source = QPixmap(str(path))
        if source.isNull():
            self._logo_key = key
            self._logo = None
            return None

        px = int(round(side * ratio))
        scaled = source.scaled(
            px,
            px,
            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation,
        )
        # Center-crop so the circle is filled without distortion.
        x = max(0, (scaled.width() - px) // 2)
        y = max(0, (scaled.height() - px) // 2)
        cropped = scaled.copy(x, y, px, px)
        cropped.setDevicePixelRatio(ratio)

        self._logo = cropped
        self._logo_key = key
        return cropped
