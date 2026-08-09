"""Liquid-glass backdrop: slow blue/purple blobs, heavily blurred.

Implementation notes
--------------------
`QGraphicsBlurEffect` on a full-size widget re-renders the whole subtree into
an offscreen surface every frame, which is far too expensive for a 60 fps
ambient layer. Instead the blobs are painted into a small pixmap (1/8 scale)
and upscaled with smooth interpolation: bilinear magnification of a tiny
buffer *is* a cheap gaussian-ish blur, and the cost is independent of the
window size.

The layer lives inside the glass card and is lowered below every control, so
the translucent surfaces above it read as frosted glass over moving colour.
"""

from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import (
    QColor,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPixmap,
    QRadialGradient,
)
from PySide6.QtWidgets import QWidget

from ..state import AssistantState
from ..theme import T, Palette


_SCALE = 8          # blob buffer downscale factor -> the actual blur radius
_IDLE_MS = 110
_ACTIVE_MS = 33     # ~30 fps is plenty for a slow-moving ambient layer


class LiquidBackdrop(QWidget):
    """Ambient animated colour wash behind the card contents."""

    # (hue base, orbit radius factor, orbit speed, size factor, phase offset)
    _BLOBS = (
        (0.00, 0.30, 0.17, 0.62, 0.0),
        (1.00, 0.38, -0.13, 0.54, 2.1),
        (2.00, 0.26, 0.23, 0.46, 4.2),
        (1.00, 0.44, -0.08, 0.70, 5.4),
        (0.00, 0.52, 0.11, 0.48, 1.2),
        (2.00, 0.58, -0.19, 0.40, 3.7),
    )

    # Per-theme colour trio (blue, purple) + the state accent is appended.
    # Both themes now start from black and layer a saturated dark blue/purple
    # blur on top, so the wash reads as deep glass instead of a pastel tint.
    _WASH = {
        True: ("#1026b4", "#4a12b8"),
        False: ("#2b4bf5", "#8b2df0"),
    }


    def __init__(self, palette: Palette, parent=None):
        super().__init__(parent)
        self._palette = palette
        self._state = AssistantState.OFF
        self._phase = 0.0
        self._energy = 0.0
        self._target_energy = 0.0
        self._buffer: QPixmap | None = None

        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

        self._timer = QTimer(self)
        self._timer.setInterval(_IDLE_MS)
        self._timer.timeout.connect(self._tick)

    # -- api ---------------------------------------------------------------

    def set_palette(self, palette: Palette) -> None:
        self._palette = palette
        self.update()

    def set_state(self, state: AssistantState) -> None:
        self._state = state
        self._target_energy = 0.0 if state is AssistantState.OFF else 1.0
        self._timer.setInterval(
            _IDLE_MS if state is AssistantState.OFF else _ACTIVE_MS
        )
        self.update()

    # -- lifecycle ---------------------------------------------------------

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._timer.start()

    def hideEvent(self, event) -> None:
        super().hideEvent(event)
        self._timer.stop()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._buffer = None

    def _tick(self) -> None:
        self._phase += 0.016 if self._state is AssistantState.OFF else 0.05
        self._energy += (self._target_energy - self._energy) * 0.06
        self.update()

    # -- painting ----------------------------------------------------------

    def _colors(self) -> tuple[QColor, QColor, QColor]:
        """Blue / purple / state-tinted trio driving the wash."""
        blue_hex, purple_hex = self._WASH[self._palette.is_dark]
        blue = QColor(blue_hex)
        purple = QColor(purple_hex)
        accent = QColor(
            {
                AssistantState.OFF: self._palette.ring_off,
                AssistantState.LOADING: self._palette.ring_loading,
                AssistantState.LISTENING: self._palette.ring_listening,
                AssistantState.THINKING: self._palette.ring_thinking,
                AssistantState.SPEAKING: self._palette.ring_speaking,
            }[self._state]
        )
        return blue, purple, accent

    def paintEvent(self, _event) -> None:
        w, h = self.width(), self.height()
        if w <= 0 or h <= 0:
            return

        bw, bh = max(1, w // _SCALE), max(1, h // _SCALE)
        if self._buffer is None or self._buffer.size().width() != bw:
            self._buffer = QPixmap(bw, bh)
        self._buffer.fill(Qt.GlobalColor.transparent)

        colors = self._colors()
        # Idle keeps a faint wash alive; active states bloom in colour.
        strength = 0.22 + 0.78 * max(0.0, min(1.0, self._energy))

        bp = QPainter(self._buffer)
        bp.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        bp.setPen(Qt.PenStyle.NoPen)
        cx, cy = bw / 2, bh / 2
        base = min(bw, bh)

        for index, (hue, orbit, speed, size, offset) in enumerate(self._BLOBS):
            angle = self._phase * speed * math.tau + offset
            wobble = 1.0 + 0.22 * math.sin(self._phase * 1.7 + offset)
            x = cx + math.cos(angle) * base * orbit * wobble
            y = cy + math.sin(angle * 1.3) * base * orbit * 0.72 * wobble
            radius = base * size * (0.85 + 0.25 * wobble)

            color = QColor(colors[int(hue) % 3])
            alpha = int((104 if self._palette.is_dark else 118) * strength)
            if index >= 3:
                alpha = int(alpha * 0.7)

            grad = QRadialGradient(QPointF(x, y), radius)
            grad.setColorAt(0.0, QColor(color.red(), color.green(), color.blue(), alpha))
            grad.setColorAt(
                0.5, QColor(color.red(), color.green(), color.blue(), int(alpha * 0.45))
            )
            grad.setColorAt(1.0, QColor(color.red(), color.green(), color.blue(), 0))
            bp.setBrush(grad)
            bp.drawEllipse(QPointF(x, y), radius, radius)
        bp.end()

        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        # Clip to the card's rounded rect so the wash never bleeds past corners.
        clip = QPainterPath()
        clip.addRoundedRect(
            QRectF(0, 0, w, h), T.window_radius, T.window_radius
        )
        p.setClipPath(clip)

        # Base: black first (kept slightly translucent so the native acrylic
        # blur behind the window still shows through), then the colour blur.
        # The light theme keeps a much thinner black veil so its dark text
        # stays readable.
        dark = self._palette.is_dark
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(0, 0, 0, 216 if dark else 34))
        p.drawRect(QRectF(0, 0, w, h))

        # Deep blue/purple ground under the moving blobs.
        base = QLinearGradient(0.0, 0.0, float(w), float(h))
        if dark:
            base.setColorAt(0.0, QColor(10, 14, 54, 120))
            base.setColorAt(0.5, QColor(2, 3, 10, 150))
            base.setColorAt(1.0, QColor(26, 6, 56, 120))
        else:
            base.setColorAt(0.0, QColor(198, 212, 255, 150))
            base.setColorAt(0.5, QColor(245, 245, 255, 120))
            base.setColorAt(1.0, QColor(216, 200, 255, 150))
        p.setBrush(base)
        p.drawRect(QRectF(0, 0, w, h))

        p.drawPixmap(QRectF(0, 0, w, h), self._buffer, QRectF(0, 0, bw, bh))

        # Vignette: darkens (or brightens) the corners so the centre orb reads
        # as the focal point and the blobs never look like they end abruptly.
        vignette = QRadialGradient(QPointF(w / 2, h * 0.42), max(w, h) * 0.78)
        edge = QColor(0, 0, 0, 210) if dark else QColor(255, 255, 255, 120)
        vignette.setColorAt(0.45, QColor(edge.red(), edge.green(), edge.blue(), 0))
        vignette.setColorAt(1.0, edge)
        p.setBrush(vignette)
        p.drawRect(QRectF(0, 0, w, h))


        # Top sheen — the specular edge that sells "glass".
        sheen = QLinearGradient(0.0, 0.0, 0.0, max(1.0, h * 0.34))
        top = QColor(255, 255, 255, 22 if dark else 34)
        sheen.setColorAt(0.0, top)
        sheen.setColorAt(1.0, QColor(255, 255, 255, 0))
        p.setBrush(sheen)
        p.drawRect(QRectF(0, 0, w, h * 0.34))
        p.end()

