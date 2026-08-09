"""Pill button that renders its own inline download progress.

UI.md asks for "botão com ícone de download + barra de progresso inline".
The old UI had the button but no progress affordance at all, and no way to
signal completion. This paints the progress as a gradient fill inside the
pill, keeps the label in sync, and locks itself while running.
"""

from __future__ import annotations

from PySide6.QtCore import QRectF, QSize, Qt
from PySide6.QtGui import QColor, QLinearGradient, QPainter
from PySide6.QtWidgets import QPushButton

from .. import icons
from ..theme import T, Palette


class DownloadButton(QPushButton):
    def __init__(self, palette: Palette, parent=None):
        super().__init__(parent)
        self._palette = palette
        self._progress: int | None = None
        self._done = False
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setIconSize(QSize(14, 14))
        self.setMinimumWidth(132)
        self.setToolTip("Baixar os binários Vulkan (whisper.cpp, llama.cpp, Piper)")
        self.set_palette(palette)
        self._sync_label()

    # -- api ---------------------------------------------------------------

    def set_palette(self, palette: Palette) -> None:
        self._palette = palette
        color = palette.text_dim if self._progress is None else palette.text
        self.setIcon(
            icons.check(14, palette.ring_listening)
            if self._done
            else icons.download(14, color)
        )
        self.update()

    def start(self) -> None:
        self._done = False
        self._progress = 0
        self.setEnabled(False)
        self._sync_label()

    def set_progress(self, percent: int) -> None:
        self._progress = max(0, min(100, int(percent)))
        self._sync_label()

    def finish(self, ok: bool, message: str = "") -> None:
        self._progress = None
        self._done = ok
        self.setEnabled(True)
        self.setToolTip(message or self.toolTip())
        self.set_palette(self._palette)
        self._sync_label()

    def is_running(self) -> bool:
        return self._progress is not None

    # -- internals ---------------------------------------------------------

    def _sync_label(self) -> None:
        if self._progress is not None:
            self.setText(f"  Baixando… {self._progress}%")
        elif self._done:
            self.setText("  Binários prontos")
        else:
            self.setText("  Binários")
        self.update()

    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        if self._progress is None or self._progress <= 0:
            return

        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        radius = float(T.pill_radius)
        inset = 1.0
        full = QRectF(
            inset, inset, self.width() - inset * 2, self.height() - inset * 2
        )

        p.setPen(Qt.PenStyle.NoPen)
        path_width = full.width() * (self._progress / 100.0)

        g0, g1 = self._palette.accent_gradient
        gradient = QLinearGradient(full.left(), 0, full.right(), 0)
        start = QColor(g0)
        end = QColor(g1)
        start.setAlpha(120)
        end.setAlpha(120)
        gradient.setColorAt(0.0, start)
        gradient.setColorAt(1.0, end)

        p.save()
        p.setClipRect(QRectF(full.left(), full.top(), path_width, full.height()))
        p.setBrush(gradient)
        p.drawRoundedRect(full, radius, radius)
        p.restore()
        p.end()
