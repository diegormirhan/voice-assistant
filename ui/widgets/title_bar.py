"""Frameless top bar: settings, binaries, model profile, voice, window controls."""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QWidget,
)

from .. import icons
from ..state import AssistantState
from ..theme import Palette
from .download_button import DownloadButton
from .select import PillSelect

PROFILES = (
    ("padrao", "Padrão", "Qwen3.5-9B Q4 (~5,5 GB) — mais capaz, exige mais VRAM."),
    ("leve", "Leve", "Qwen3-VL-4B Q4 (~2,5 GB) — mais rápido, menos VRAM."),
)

VOICES = (("pt_BR-faber-medium", "pt-BR · Faber", "Piper pt-BR, voz média."),)


class TitleBar(QFrame):
    settings_requested = Signal()
    download_requested = Signal()
    minimize_requested = Signal()
    close_requested = Signal()
    info_requested = Signal()
    profile_changed = Signal(str)
    voice_changed = Signal(str)

    def __init__(self, palette: Palette, config: dict, parent=None):
        super().__init__(parent)
        self._palette = palette
        self.setFixedHeight(46)
        self.setCursor(Qt.CursorShape.ArrowCursor)

        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)

        self.gear_btn = QPushButton()
        self.gear_btn.setObjectName("iconBtn")
        self.gear_btn.setFixedSize(32, 32)
        self.gear_btn.setIconSize(QSize(17, 17))
        self.gear_btn.setToolTip("Configurações")
        self.gear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.gear_btn.clicked.connect(self.settings_requested)
        row.addWidget(self.gear_btn)

        self.download_btn = DownloadButton(palette)
        self.download_btn.clicked.connect(self.download_requested)
        row.addWidget(self.download_btn)

        row.addStretch(1)

        self.status_label = QLabel(AssistantState.OFF.label)
        self.status_label.setProperty("role", "status")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        row.addWidget(self.status_label)

        row.addStretch(1)

        self.profile_select = PillSelect(
            palette, PROFILES, config.get("model_profile", "padrao"), icons.chip
        )
        self.profile_select.setToolTip(self.profile_select.current_tip())
        self.profile_select.currentIndexChanged.connect(self._on_profile_changed)
        row.addWidget(self.profile_select)

        self.voice_select = PillSelect(
            palette, VOICES, config.get("voice", "pt_BR-faber-medium"), icons.waveform
        )
        self.voice_select.setToolTip(self.voice_select.current_tip())
        self.voice_select.currentIndexChanged.connect(self._on_voice_changed)
        row.addWidget(self.voice_select)

        self.info_btn = QPushButton()
        self.info_btn.setObjectName("iconBtn")
        self.info_btn.setFixedSize(30, 30)
        self.info_btn.setIconSize(QSize(16, 16))
        self.info_btn.setToolTip("O que são perfil e voz?")
        self.info_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.info_btn.clicked.connect(self.info_requested)
        row.addWidget(self.info_btn)

        spacer = QWidget()
        spacer.setFixedWidth(6)
        row.addWidget(spacer)


        self.minimize_btn = QPushButton()
        self.minimize_btn.setObjectName("iconBtn")
        self.minimize_btn.setFixedSize(30, 30)
        self.minimize_btn.setIconSize(QSize(13, 13))
        self.minimize_btn.setToolTip("Minimizar")
        self.minimize_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.minimize_btn.clicked.connect(self.minimize_requested)
        row.addWidget(self.minimize_btn)


        self.close_btn = QPushButton()
        self.close_btn.setObjectName("closeBtn")
        self.close_btn.setFixedSize(30, 30)
        self.close_btn.setIconSize(QSize(13, 13))
        self.close_btn.setToolTip("Fechar")
        self.close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.close_btn.clicked.connect(self.close_requested)
        row.addWidget(self.close_btn)

        self.set_palette(palette)

    # -- api ---------------------------------------------------------------

    def set_palette(self, palette: Palette) -> None:
        self._palette = palette
        self.gear_btn.setIcon(icons.gear(17, palette.text_dim))
        self.minimize_btn.setIcon(icons.minimize(13, palette.text_dim))
        self.close_btn.setIcon(icons.close(13, palette.text_dim))
        self.info_btn.setIcon(icons.info(16, palette.text_dim))
        self.download_btn.set_palette(palette)
        self.profile_select.set_palette(palette)
        self.voice_select.set_palette(palette)

    def set_state(self, state: AssistantState) -> None:
        self.status_label.setText(state.label)

    # -- helpers -----------------------------------------------------------

    def _on_profile_changed(self, _index: int) -> None:
        self.profile_select.setToolTip(self.profile_select.current_tip())
        self.profile_changed.emit(self.profile_select.currentData())

    def _on_voice_changed(self, _index: int) -> None:
        self.voice_select.setToolTip(self.voice_select.current_tip())
        self.voice_changed.emit(self.voice_select.currentData())
