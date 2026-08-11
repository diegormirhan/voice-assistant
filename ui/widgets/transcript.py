"""Collapsible session transcript with real message bubbles."""

from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import (
    QEasingCurve,
    QPropertyAnimation,
    QSize,
    Qt,
    QTimer,
    Property,
    Signal,
)
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from .. import icons
from ..theme import T, Palette

_MAX_MESSAGES = 200
_BODY_HEIGHT = 320


class _Bubble(QFrame):
    _PADDING = 26  # 2 * 12px QSS padding + 1px border on each side

    def __init__(self, text: str, *, is_user: bool, timestamp: str, parent=None):
        super().__init__(parent)
        self.setObjectName("bubbleUser" if is_user else "bubbleAssistant")
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Minimum)
        self._text = text

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        self.meta = QLabel(f"{'Você' if is_user else 'Assistente'} · {timestamp}")
        self.meta.setObjectName("bubbleMetaOnAccent" if is_user else "bubbleMeta")
        layout.addWidget(self.meta)

        self.body = QLabel()
        # Qt auto-detects rich text, so a transcription containing "<b>" was
        # still rendered as HTML. Force plain text.
        self.body.setTextFormat(Qt.TextFormat.PlainText)
        self.body.setText(text)
        self.body.setWordWrap(True)
        self.body.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        self.body.setStyleSheet("background: transparent; border: none;")
        layout.addWidget(self.body)

    def apply_max_width(self, available: int) -> None:
        """Size the bubble to its text, capped at 78% of the viewport.

        Bugs fixed: the bubble used `QSizePolicy.Maximum` plus a layout stretch
        factor, so its width came from the wrapped label's *minimum* hint —
        long messages were squeezed into a ~150px column and clipped on the
        right. Width is now derived from the text metrics and only wraps once
        it hits the cap, which is recomputed on every resize.
        """
        cap = max(180, int(available * 0.78))
        metrics = self.body.fontMetrics()
        text_w = max(
            metrics.horizontalAdvance(self._text),
            self.meta.fontMetrics().horizontalAdvance(self.meta.text()),
        )
        width = min(cap, text_w + self._PADDING + 2)
        width = max(width, 120)
        self.setFixedWidth(width)
        self.body.setFixedWidth(width - self._PADDING)




class _Body(QScrollArea):
    """Scroll area whose preferred height is the current body cap.

    QScrollArea's own hint comes from the (resizable) content widget, so the
    panel used to settle at whatever the bubbles needed instead of the intended
    body height. Reporting the cap as the hint lets the layout grow the panel to
    `_BODY_HEIGHT` when there is room and shrink it to 0 when there is not.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._cap = 0

    def set_cap(self, cap: int) -> None:
        self._cap = max(0, int(cap))
        self.updateGeometry()

    def sizeHint(self) -> QSize:
        return QSize(super().sizeHint().width(), self._cap)

    def minimumSizeHint(self) -> QSize:
        return QSize(super().minimumSizeHint().width(), 0)


class TranscriptPanel(QFrame):
    expanded_changed = Signal(bool)

    def __init__(self, palette: Palette, expanded: bool = False, parent=None):
        super().__init__(parent)
        self._palette = palette
        self._expanded = bool(expanded)
        self._count = 0

        # Let the surrounding layout compress the panel instead of pushing it
        # out of the card when the window is short.
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        self.setMinimumHeight(0)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(6)

        # Header ----------------------------------------------------------
        header = QHBoxLayout()
        header.setSpacing(6)

        self._toggle = QPushButton("  Transcrição")
        self._toggle.setProperty("variant", "quiet")
        self._toggle.setCheckable(True)
        self._toggle.setChecked(self._expanded)
        self._toggle.setCursor(Qt.CursorShape.PointingHandCursor)
        self._toggle.setIconSize(QSize(12, 12))
        self._toggle.clicked.connect(self._on_toggle_clicked)
        header.addWidget(self._toggle)

        self._counter = QLabel("")
        self._counter.setProperty("role", "hint")
        header.addWidget(self._counter)
        header.addStretch(1)

        self._clear_btn = QPushButton()
        self._clear_btn.setObjectName("iconBtn")
        self._clear_btn.setFixedSize(26, 26)
        self._clear_btn.setIconSize(QSize(13, 13))
        self._clear_btn.setToolTip("Limpar transcrição da sessão")
        self._clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._clear_btn.clicked.connect(self.clear)
        header.addWidget(self._clear_btn)

        root.addLayout(header)

        # Body ------------------------------------------------------------
        self._scroll = _Body()
        self._scroll.setObjectName("transcriptScroll")
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        # Bug fixed: the body height used to be pinned in both directions
        # (min == max). In a short window the vertical layout could not shrink
        # the panel, so the bubble list overflowed past the rounded card and
        # was painted outside the window. The height is now a *cap*: the panel
        # takes up to `_BODY_HEIGHT` when there is room and compresses (down to
        # zero) when there is not, so nothing ever escapes the card.
        self._scroll.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        self._scroll.viewport().setMinimumHeight(0)
        self._set_body_height(_BODY_HEIGHT if self._expanded else 0)

        holder = QWidget()
        self._list = QVBoxLayout(holder)
        self._list.setContentsMargins(2, 2, 8, 2)
        self._list.setSpacing(8)
        self._list.addStretch(1)
        self._scroll.setWidget(holder)
        root.addWidget(self._scroll, 1)

        self._empty = QLabel("A conversa desta sessão aparece aqui.")
        self._empty.setProperty("role", "hint")
        self._empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty.setVisible(self._expanded)
        root.addWidget(self._empty)

        self._anim = QPropertyAnimation(self, b"body_height", self)
        self._anim.setDuration(T.slow_ms)
        self._anim.setEasingCurve(QEasingCurve.Type.InOutCubic)

        self.set_palette(palette)

    # -- animated body height ---------------------------------------------

    def _set_body_height(self, value) -> None:
        height = max(0, int(value))
        self._body_height = height
        self._scroll.setMaximumHeight(height)
        self._scroll.setMinimumHeight(0)
        self._scroll.set_cap(height)
        self._scroll.setVisible(height > 0)

    def _get_body_height(self) -> int:
        return getattr(self, "_body_height", 0)

    body_height = Property(int, _get_body_height, _set_body_height)

    # -- api ---------------------------------------------------------------

    def is_expanded(self) -> bool:
        return self._expanded

    def set_palette(self, palette: Palette) -> None:
        self._palette = palette
        self._toggle.setIcon(
            icons.chevron(12, palette.text_dim, down=self._expanded)
        )
        self._clear_btn.setIcon(icons.trash(13, palette.text_dim))

    def set_expanded(self, expanded: bool, *, animate: bool = True) -> None:
        expanded = bool(expanded)
        self._expanded = expanded
        if self._toggle.isChecked() != expanded:
            self._toggle.setChecked(expanded)
        self._toggle.setIcon(icons.chevron(12, self._palette.text_dim, down=expanded))
        self._empty.setVisible(expanded and self._count == 0)

        target = _BODY_HEIGHT if expanded else 0
        self._anim.stop()
        if animate:
            self._anim.setStartValue(self._get_body_height())
            self._anim.setEndValue(target)
            self._anim.start()
        else:
            self._set_body_height(target)
        if expanded:
            QTimer.singleShot(T.slow_ms, self._scroll_to_bottom)
        self.expanded_changed.emit(expanded)

    def add_user(self, text: str) -> None:
        self._add(text, is_user=True)

    def add_assistant(self, text: str) -> None:
        self._add(text, is_user=False)

    def clear(self) -> None:
        while self._list.count() > 1:
            item = self._list.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self._count = 0
        self._counter.setText("")
        self._empty.setVisible(self._expanded)

    # -- internals ---------------------------------------------------------

    def _on_toggle_clicked(self) -> None:
        self.set_expanded(self._toggle.isChecked())

    def _add(self, text: str, *, is_user: bool) -> None:
        text = (text or "").strip()
        if not text:
            return

        bubble = _Bubble(
            text, is_user=is_user, timestamp=datetime.now().strftime("%H:%M")
        )
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        if is_user:
            row.addStretch(1)
            row.addWidget(bubble, 0)
        else:
            row.addWidget(bubble, 0)
            row.addStretch(1)

        wrapper = QWidget()
        wrapper.setLayout(row)
        self._list.insertWidget(self._list.count() - 1, wrapper)

        self._count += 1
        self._counter.setText(f"· {self._count}")
        self._empty.setVisible(False)
        self._trim()
        # The viewport width is only meaningful after the insert is laid out,
        # so size the bubbles on the next loop turn instead of guessing now.
        self._relayout_bubbles()
        QTimer.singleShot(0, self._relayout_bubbles)
        QTimer.singleShot(0, self._scroll_to_bottom)

    def _available_width(self) -> int:
        viewport = self._scroll.viewport().width()
        if viewport <= 1:
            viewport = self.width()
        if viewport <= 1:
            viewport = 640
        return max(200, viewport - 12)

    def _relayout_bubbles(self) -> None:
        available = self._available_width()
        for index in range(self._list.count() - 1):
            item = self._list.itemAt(index)
            wrapper = item.widget() if item is not None else None
            if wrapper is None:
                continue
            for bubble in wrapper.findChildren(_Bubble):
                bubble.apply_max_width(available)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._relayout_bubbles()



    def _trim(self) -> None:
        while self._list.count() - 1 > _MAX_MESSAGES:
            item = self._list.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def _scroll_to_bottom(self) -> None:
        bar = self._scroll.verticalScrollBar()
        bar.setValue(bar.maximum())
