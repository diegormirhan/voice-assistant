"""Status ring renderer — the visual language of the assistant's state.

Layers, outside in:
  1. wide soft aura        — amplitude driven
  2. amplitude corona      — instantaneous audio energy
  3. crisp stroke / arcs   — state identity (spinner while LOADING)
  4. orb body              — subtle vertical gradient + inner highlight
"""

from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QLinearGradient, QPainter, QPen, QRadialGradient

from ..state import AssistantState
from ..theme import Palette


def _rgba(color: QColor, alpha: int) -> QColor:
    return QColor(color.red(), color.green(), color.blue(), max(0, min(255, alpha)))


class StatusRing:
    """Stateless painter: all inputs are arguments, nothing is cached."""

    def color_for(self, palette: Palette, state: AssistantState) -> QColor:
        return QColor(
            {
                AssistantState.OFF: palette.ring_off,
                AssistantState.LOADING: palette.ring_loading,
                AssistantState.LISTENING: palette.ring_listening,
                AssistantState.THINKING: palette.ring_thinking,
                AssistantState.SPEAKING: palette.ring_speaking,
            }[state]
        )

    def paint(
        self,
        p: QPainter,
        *,
        palette: Palette,
        state: AssistantState,
        center: QPointF,
        radius: float,
        amplitude: float,
        phase: float,
        hover: float = 0.0,
        limit: float | None = None,
    ) -> None:
        # `limit` is the largest radius that still fits inside the widget. Every
        # glow layer is scaled to it and fades to zero *before* reaching it, so
        # the aura never gets sliced off by the widget rectangle (the visible
        # hard circle in the previous version).
        max_glow = limit if limit and limit > radius + 6 else radius + 6
        color = self.color_for(palette, state)
        amp = max(0.0, min(1.0, amplitude))
        breath = 0.5 + 0.5 * math.sin(phase * 1.6)
        cx, cy = center.x(), center.y()

        # Boost visual energy when the user or the assistant is actively talking.
        is_voice_active = state in (AssistantState.LISTENING, AssistantState.SPEAKING)
        voice_boost = 1.55 if is_voice_active else 1.0

        if state is AssistantState.OFF:
            amp = 0.0
        elif state is AssistantState.THINKING:
            amp = 0.25 + 0.35 * breath
        elif state is AssistantState.LOADING:
            amp = 0.18 + 0.2 * breath
        else:
            amp = 0.35 + 0.65 * amp

        # 1 — wide aura (larger and more saturated when actively speaking/listening)
        head = max_glow - radius
        aura_r = radius + head * (0.62 + 0.38 * amp * voice_boost + 0.06 * hover)
        aura_r = min(aura_r, max_glow)
        aura_alpha = 6 if state is AssistantState.OFF else int(22 + 55 * amp * voice_boost)
        aura = QRadialGradient(cx, cy, aura_r)
        aura.setColorAt(0.4, _rgba(color, aura_alpha))
        aura.setColorAt(0.75, _rgba(color, aura_alpha // 2))
        aura.setColorAt(1.0, _rgba(color, 0))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(aura)
        p.drawEllipse(center, aura_r, aura_r)

        # 1b — orbiting colour lobes: the "radial que se mexe" around the orb.
        # Three blobs (state colour + blue + purple) circling the button, each
        # pushed outward by the live audio amplitude so speech is visible.
        if state is not AssistantState.OFF:
            lobes = (
                (color, 1.0, 0.0),
                (QColor("#2f7bf6"), -0.72, 2.2),
                (QColor("#b23cf0"), 0.55, 4.4),
            )
            p.save()
            p.setCompositionMode(QPainter.CompositionMode.CompositionMode_Plus)
            for lobe_color, speed, offset in lobes:
                angle = phase * speed * 1.15 + offset
                lobe_r = radius * (0.52 + 0.32 * amp * voice_boost)
                # Keep orbit + blob radius inside the aura envelope.
                orbit = radius * (0.82 + 0.30 * amp * voice_boost) + 12 * hover
                orbit = min(orbit, max(0.0, max_glow - lobe_r * 0.92))
                lx = cx + math.cos(angle) * orbit
                ly = cy + math.sin(angle * 1.12) * orbit
                lobe_alpha = int(95 + 195 * amp * voice_boost)
                grad = QRadialGradient(lx, ly, lobe_r)
                grad.setColorAt(0.0, _rgba(lobe_color, lobe_alpha))
                grad.setColorAt(0.45, _rgba(lobe_color, lobe_alpha // 3))
                grad.setColorAt(1.0, _rgba(lobe_color, 0))
                p.setBrush(grad)
                p.drawEllipse(QPointF(lx, ly), lobe_r, lobe_r)
            p.restore()

        # 2 — corona
        corona_r = min(radius + 13 + 18 * amp * voice_boost, max_glow * 0.94)
        corona_alpha = 8 if state is AssistantState.OFF else int(32 + 85 * amp * voice_boost)
        corona = QRadialGradient(cx, cy, corona_r)
        corona.setColorAt(0.64, _rgba(color, 0))
        corona.setColorAt(0.88, _rgba(color, corona_alpha))
        corona.setColorAt(1.0, _rgba(color, 0))
        p.setBrush(corona)
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(center, corona_r, corona_r)


        # 3 — stroke / spinner
        ring_r = radius + 4 + 2.5 * amp
        rect = QRectF(cx - ring_r, cy - ring_r, ring_r * 2, ring_r * 2)
        p.setBrush(Qt.BrushStyle.NoBrush)

        track = QPen(_rgba(color, 34 if state is AssistantState.OFF else 54), 1.6)
        p.setPen(track)
        p.drawEllipse(center, ring_r, ring_r)

        if state is AssistantState.LOADING:
            head = QPen(_rgba(color, 225), 2.6)
            head.setCapStyle(Qt.PenCapStyle.RoundCap)
            p.setPen(head)
            start = int(-phase * 220 / math.pi) * 16
            p.drawArc(rect, start, 100 * 16)
            tail = QPen(_rgba(color, 70), 2.0)
            tail.setCapStyle(Qt.PenCapStyle.RoundCap)
            p.setPen(tail)
            p.drawArc(rect, start + 118 * 16, 58 * 16)
        elif state is not AssistantState.OFF:
            active = QPen(_rgba(color, int(120 + 120 * amp)), 1.8 + 1.2 * amp)
            p.setPen(active)
            p.drawEllipse(center, ring_r, ring_r)

            if state is AssistantState.THINKING:
                dot = QPen(_rgba(color, 235), 3.2)
                dot.setCapStyle(Qt.PenCapStyle.RoundCap)
                p.setPen(dot)
                p.drawArc(rect, int(-phase * 200 / math.pi) * 16, 8 * 16)

        # 4 — orb body
        body = QLinearGradient(cx, cy - radius, cx, cy + radius)
        body.setColorAt(0.0, QColor(palette.orb_center))
        body.setColorAt(1.0, QColor(palette.orb_edge))
        p.setBrush(body)
        p.setPen(QPen(_rgba(color, 60 if state is AssistantState.OFF else 110), 1.2))
        p.drawEllipse(center, radius, radius)

        # inner top highlight (glass)
        gloss = QRadialGradient(cx, cy - radius * 0.6, radius * 1.25)
        gloss.setColorAt(0.0, QColor(255, 255, 255, 30 if palette.is_dark else 210))
        gloss.setColorAt(0.7, QColor(255, 255, 255, 0))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(gloss)
        p.drawEllipse(center, radius - 0.6, radius - 0.6)
