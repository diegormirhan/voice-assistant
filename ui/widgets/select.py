"""Pill select with a leading glyph and a hand-painted chevron."""

from __future__ import annotations

from typing import Callable, Iterable, Sequence

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import QComboBox, QListView, QSizePolicy

from .. import icons
from ..theme import Palette

Option = Sequence[str]  # (value, label, tip)


class PillSelect(QComboBox):
    def __init__(
        self,
        palette: Palette,
        options: Iterable[Option],
        current: str,
        glyph: Callable[[int, str], object],
        parent=None,
    ):
        super().__init__(parent)
        self._palette = palette
        self._glyph = glyph
        self._options = list(options)

        self.setObjectName("pillSelect")
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setIconSize(QSize(15, 15))
        self.setFixedHeight(32)

        # A real QListView lets the popup honour item padding and rounding.
        view = QListView()
        view.setUniformItemSizes(True)
        view.setSpacing(1)
        self.setView(view)

        for value, label, tip in self._options:
            self.addItem(label, value)
            self.setItemData(self.count() - 1, tip, Qt.ItemDataRole.ToolTipRole)

        self.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        self._fit_width()

        index = self.findData(current)
        self.setCurrentIndex(index if index >= 0 else 0)
        if self.count() < 2:
            self.setEnabled(False)
        self.set_palette(palette)

    def _fit_width(self) -> None:
        """Qt's sizeHint ignores the QSS left/right insets, so the longest
        label used to spill outside the pill and collide with the ⓘ button."""
        fm = self.fontMetrics()
        widest = max((fm.horizontalAdvance(label) for _v, label, _t in self._options), default=0)
        # 34px icon inset + 30px chevron inset + a little breathing room.
        self.setMinimumWidth(min(184, max(104, widest + 34 + 30 + 6)))

    # -- api ---------------------------------------------------------------

    def set_palette(self, palette: Palette) -> None:
        self._palette = palette
        colour = palette.text_dim if self.isEnabled() else palette.text_dim
        for i, _ in enumerate(self._options):
            self.setItemIcon(i, self._glyph(15, colour))  # type: ignore[arg-type]
        self._chevron = icons.chevron_pixmap(10, palette.text_dim)
        self.update()

    def current_tip(self) -> str:
        row = self.currentIndex()
        if 0 <= row < len(self._options):
            value, label, tip = self._options[row]
            return f"{label} — {tip}"
        return ""

    # -- painting ----------------------------------------------------------

    def paintEvent(self, event) -> None:  # noqa: N802
        super().paintEvent(event)
        pm = getattr(self, "_chevron", None)
        if pm is None:
            return
        w = pm.width() / pm.devicePixelRatio()
        h = pm.height() / pm.devicePixelRatio()
        painter = QPainter(self)
        painter.setOpacity(1.0 if self.isEnabled() else 0.45)
        painter.drawPixmap(
            int(self.width() - w - 11), int((self.height() - h) / 2), pm
        )
        painter.end()
