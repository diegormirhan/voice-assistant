"""Explainer dialog: what the "Perfil" and "Voz" selects actually change.

The selects used to hide all of this in a tooltip, which is invisible on a
touch screen and disappears the moment you move the mouse. This dialog says it
once, properly, with the real model names, sizes and trade-offs.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
)

from .. import effects, icons
from ..qss import build_qss
from ..theme import Palette


_WIDTH = 468
_CARD_WIDTH = _WIDTH - 2 * 26          # dialog card padding
_BLOCK_WIDTH = _CARD_WIDTH - 2 * 15    # info block padding
_ITEM_WIDTH = _BLOCK_WIDTH - 2 * 9     # bullet chip padding


def _lock_wrapped_height(
    label: QLabel, width: int, pad_x: int = 0, pad_y: int = 0
) -> None:
    """Pin a word-wrapped label to its real height.

    A wrapped QLabel reports `heightForWidth`, but the surrounding nested
    frames resolve their own height first, so the last line of every bullet was
    being clipped. Measuring against the known column width fixes it.
    """
    label.setFixedWidth(width)
    # QSS padding shrinks the text area, so measure the inner width and add the
    # vertical padding back — otherwise the last line gets clipped.
    label.setMinimumHeight(label.heightForWidth(width - pad_x) + pad_y)


class VoiceProfileInfoModal(QDialog):
    """Read-only explainer, opened from the ⓘ button in the title bar."""

    def __init__(self, palette: Palette, parent=None):
        super().__init__(parent)
        self._palette = palette

        self.setWindowTitle("Perfil e voz")
        self.setModal(True)
        self.setFixedWidth(_WIDTH)
        self.setWindowFlags(
            Qt.WindowType.Dialog
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowSystemMenuHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

        self._wrapped: list[tuple[QLabel, int, int, int]] = []
        self._build_ui()
        self.setStyleSheet(build_qss(palette))
        # Re-measure once the stylesheet is live: font metrics and padding only
        # settle after the QSS is applied.
        for label, width, pad_x, pad_y in self._wrapped:
            _lock_wrapped_height(label, width, pad_x, pad_y)
        self.adjustSize()

    # -- construction ------------------------------------------------------

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        card = QFrame()
        card.setObjectName("dialogCard")
        root.addWidget(card)

        shell = QVBoxLayout(card)
        shell.setContentsMargins(26, 22, 26, 20)
        shell.setSpacing(12)

        title = QLabel("Perfil e voz")
        title.setProperty("role", "title")
        shell.addWidget(title)

        lede = QLabel(
            "Os dois seletores da barra superior decidem <b>quem pensa</b> e "
            "<b>quem fala</b>. Tudo roda localmente, na sua GPU."
        )
        lede.setProperty("role", "hint")
        lede.setWordWrap(True)
        self._wrap(lede, _CARD_WIDTH)
        shell.addWidget(lede)

        shell.addWidget(
            self._block(
                icons.chip(18, self._palette.accent),
                "Perfil do modelo",
                "Define qual modelo de linguagem responde. Trocar o perfil "
                "recarrega os pesos — leva alguns segundos.",
                [
                    ("Padrão", "Qwen3.5-9B Q4 · ~5,5 GB de VRAM · mais capaz, "
                               "melhor em raciocínio e contexto longo."),
                    ("Leve", "Qwen3-VL-4B Q4 · ~2,5 GB de VRAM · responde antes, "
                             "ideal com a GPU ocupada ou em notebooks."),
                ],
            )
        )

        shell.addWidget(
            self._block(
                icons.waveform(18, self._palette.accent),
                "Voz",
                "Define a voz sintetizada (Piper) usada nas respostas faladas. "
                "Velocidade, expressividade e volume ficam em Configurações.",
                [
                    ("pt-BR · Faber", "Voz masculina brasileira, qualidade média — "
                                      "o melhor equilíbrio entre naturalidade e latência."),
                ],
            )
        )

        note = QLabel(
            "Ambas as escolhas são salvas no seu perfil e restauradas ao abrir o app."
        )
        note.setProperty("role", "hint")
        note.setWordWrap(True)
        self._wrap(note, _CARD_WIDTH)
        shell.addWidget(note)

        footer = QHBoxLayout()
        footer.addStretch(1)
        ok = QPushButton("Entendi")
        ok.setProperty("variant", "primary")
        ok.setDefault(True)
        ok.setCursor(Qt.CursorShape.PointingHandCursor)
        ok.clicked.connect(self.accept)
        footer.addWidget(ok)
        shell.addLayout(footer)

        # Re-assert the width after the layout is populated: SetMinimumSize
        # would otherwise let the wrapped labels squeeze the dialog narrow.
        self.setFixedWidth(_WIDTH)
        self.adjustSize()

    def _wrap(self, label: QLabel, width: int, pad_x: int = 0, pad_y: int = 0) -> None:
        _lock_wrapped_height(label, width, pad_x, pad_y)
        self._wrapped.append((label, width, pad_x, pad_y))

    def _block(
        self, icon, heading: str, body: str, items: list[tuple[str, str]]
    ) -> QFrame:
        frame = QFrame()
        frame.setObjectName("infoBlock")
        column = QVBoxLayout(frame)
        column.setContentsMargins(15, 13, 15, 13)
        column.setSpacing(7)

        head = QHBoxLayout()
        head.setSpacing(9)
        glyph = QLabel()
        pm: QPixmap = icon.pixmap(18, 18)
        glyph.setPixmap(pm)
        glyph.setFixedWidth(20)
        head.addWidget(glyph, 0, Qt.AlignmentFlag.AlignTop)
        label = QLabel(heading)
        label.setProperty("role", "label")
        head.addWidget(label, 1)
        column.addLayout(head)

        text = QLabel(body)
        text.setProperty("role", "hint")
        text.setWordWrap(True)
        self._wrap(text, _BLOCK_WIDTH)
        column.addWidget(text)

        for name, detail in items:
            row = QLabel(f"<b>{name}</b> · {detail}")
            row.setObjectName("infoItem")
            row.setWordWrap(True)
            self._wrap(row, _ITEM_WIDTH, 18, 12)
            column.addWidget(row)

        return frame

    # -- window chrome -----------------------------------------------------

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        self.setFixedWidth(_WIDTH)
        self.adjustSize()
        effects.enable_glass(
            int(self.winId()),
            dark=self._palette.is_dark,
            tint=self._palette.acrylic_tint,
        )
        parent = self.parentWidget()
        if parent is not None:
            center = parent.frameGeometry().center()
            geo = self.frameGeometry()
            geo.moveCenter(center)
            self.move(geo.topLeft())

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton and event.position().y() < 56:
            handle = self.windowHandle()
            if handle is not None and handle.startSystemMove():
                event.accept()
                return
        super().mousePressEvent(event)

    def keyPressEvent(self, event) -> None:  # noqa: N802
        if event.key() == Qt.Key.Key_Escape:
            self.reject()
            event.accept()
            return
        super().keyPressEvent(event)
