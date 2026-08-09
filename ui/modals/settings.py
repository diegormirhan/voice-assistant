"""Settings dialog: VAD, TTS, microphone, interface, appearance.

Bugs fixed vs. the previous version:
  * dragging the dialog crashed on PySide6 6.7+ (`event.y()` was removed from
    QMouseEvent); it now uses `position()` and the native system move.
  * "Restaurar padrões" silently skipped `volume`, `model_profile`, `voice`
    and `minimize_to_tray`, so a reset left the app half-default.
  * closing with Esc/the X returned "accepted" in some paths, so unsaved
    slider edits were applied anyway. Cancel now always discards.
  * the theme select changed the value but nothing previewed it, and the
    dialog kept the *old* palette after a change; theme changes now apply
    live to the dialog and the whole app.
  * the microphone level bar was a disabled QSlider (a control, not a meter)
    that never moved because nothing fed it.
  * the dialog had no scrolling, so on a 768p display the buttons were
    unreachable.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from .. import config_store, effects
from ..qss import build_qss
from ..theme import T, Palette, palette_for
from ..widgets.level_meter import LevelMeter
from ..widgets.toggle_switch import ToggleSwitch

_LABEL_WIDTH = 148


class SettingsModal(QDialog):
    saved = Signal(dict)
    theme_previewed = Signal(str)

    def __init__(self, config: dict, palette: Palette, parent=None):
        super().__init__(parent)
        self._config = config_store.sanitize(config)
        self._palette = palette
        self._toggles: list[ToggleSwitch] = []

        self.setWindowTitle("Configurações")
        self.setModal(True)
        self.setMinimumWidth(500)
        self.setMaximumHeight(720)
        self.setWindowFlags(
            Qt.WindowType.Dialog
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowSystemMenuHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

        self._build_ui()
        self._apply_palette(palette)

    # -- construction ------------------------------------------------------

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        card = QFrame()
        card.setObjectName("dialogCard")
        root.addWidget(card)

        shell = QVBoxLayout(card)
        shell.setContentsMargins(26, 22, 26, 22)
        shell.setSpacing(12)

        header = QHBoxLayout()
        title = QLabel("Configurações")
        title.setProperty("role", "title")
        header.addWidget(title)
        header.addStretch(1)
        shell.addLayout(header)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        body = QWidget()
        layout = QVBoxLayout(body)
        layout.setContentsMargins(0, 0, 6, 0)
        layout.setSpacing(9)
        scroll.setWidget(body)
        shell.addWidget(scroll, 1)

        cfg = self._config

        # Voice detection --------------------------------------------------
        self._add_section(layout, "DETECÇÃO DE VOZ")
        self.min_speech, min_row = self._slider_row(100, 1000, cfg["min_speech_ms"], "ms")
        layout.addLayout(self._form(("Mín. de fala"), min_row))
        self.hangover, hang_row = self._slider_row(300, 3000, cfg["hangover_ms"], "ms")
        layout.addLayout(self._form("Silêncio (hangover)", hang_row))

        # TTS --------------------------------------------------------------
        self._add_section(layout, "SÍNTESE DE VOZ")
        self.length_scale, ls_row = self._slider_row(
            80, 200, int(round(cfg["length_scale"] * 100)), "×", scale=100
        )
        layout.addLayout(self._form("Velocidade", ls_row))
        self.noise_scale, ns_row = self._slider_row(
            30, 100, int(round(cfg["noise_scale"] * 100)), "×", scale=100
        )
        layout.addLayout(self._form("Expressividade", ns_row))
        self.volume, vol_row = self._slider_row(
            0, 100, int(round(cfg["volume"] * 100)), "%"
        )
        layout.addLayout(self._form("Volume da saída", vol_row))

        # Microphone -------------------------------------------------------
        self._add_section(layout, "MICROFONE")
        mic_row = QHBoxLayout()
        mic_row.setSpacing(10)
        self.mic_meter = LevelMeter(self._palette)
        self.mic_meter.set_muted(cfg["mic_muted"])
        self.mic_meter.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        mic_row.addWidget(self.mic_meter, 1)
        mute_label = QLabel("Mudo")
        mute_label.setProperty("role", "hint")
        mic_row.addWidget(mute_label)
        self.mic_mute = self._toggle(cfg["mic_muted"])
        self.mic_mute.toggled.connect(self.mic_meter.set_muted)
        mic_row.addWidget(self.mic_mute)
        layout.addLayout(self._form("Nível de entrada", mic_row))

        # Interface --------------------------------------------------------
        self._add_section(layout, "INTERFACE")
        self.vision = self._toggle(cfg["vision_enabled"])
        layout.addLayout(
            self._toggle_row(
                "Visão do desktop",
                self.vision,
                "Captura a tela no instante da fala para dar contexto visual.",
            )
        )
        self.transcript = self._toggle(cfg["transcript_visible"])
        layout.addLayout(
            self._toggle_row(
                "Painel de transcrição",
                self.transcript,
                "Mostra a conversa da sessão atual (não é salva em disco).",
            )
        )
        self.always_top = self._toggle(cfg["always_on_top"])
        layout.addLayout(self._toggle_row("Sempre no topo", self.always_top))
        self.to_tray = self._toggle(cfg["minimize_to_tray"])
        layout.addLayout(
            self._toggle_row(
                "Minimizar para a bandeja",
                self.to_tray,
                "Ao minimizar, esconde a janela e mantém o ícone na bandeja.",
            )
        )

        # Appearance -------------------------------------------------------
        self._add_section(layout, "APARÊNCIA")
        self.theme = QComboBox()
        self.theme.addItem("Escuro", "dark")
        self.theme.addItem("Claro", "light")
        index = self.theme.findData(cfg["theme"])
        self.theme.setCurrentIndex(index if index >= 0 else 0)
        self.theme.currentIndexChanged.connect(self._on_theme_changed)
        layout.addLayout(self._form("Tema", self.theme))

        layout.addStretch(1)

        # Footer -----------------------------------------------------------
        footer = QHBoxLayout()
        footer.setSpacing(9)

        reset_btn = QPushButton("Restaurar padrões")
        reset_btn.setProperty("variant", "ghost")
        reset_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        reset_btn.clicked.connect(self._on_reset)
        footer.addWidget(reset_btn)
        footer.addStretch(1)

        cancel_btn = QPushButton("Cancelar")
        cancel_btn.setProperty("variant", "ghost")
        cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel_btn.clicked.connect(self.reject)
        footer.addWidget(cancel_btn)

        save_btn = QPushButton("Salvar")
        save_btn.setProperty("variant", "primary")
        save_btn.setDefault(True)
        save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        save_btn.clicked.connect(self._on_save)
        footer.addWidget(save_btn)

        shell.addLayout(footer)

    # -- palette / glass ---------------------------------------------------

    def _apply_palette(self, palette: Palette) -> None:
        self._palette = palette
        self.setStyleSheet(build_qss(palette))
        self.mic_meter.set_palette(palette)
        for toggle in self._toggles:
            toggle.set_palette(palette)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        effects.enable_glass(
            int(self.winId()), dark=self._palette.is_dark, tint=self._palette.acrylic_tint
        )
        parent = self.parentWidget()
        if parent is not None:
            center = parent.frameGeometry().center()
            geo = self.frameGeometry()
            geo.moveCenter(center)
            self.move(geo.topLeft())

    # -- live feed ---------------------------------------------------------

    def set_mic_level(self, level: float) -> None:
        self.mic_meter.set_level(level)

    # -- builders ----------------------------------------------------------

    def _toggle(self, checked: bool) -> ToggleSwitch:
        switch = ToggleSwitch(self._palette, checked=checked)
        self._toggles.append(switch)
        return switch

    def _add_section(self, layout: QVBoxLayout, text: str) -> None:
        layout.addSpacing(6)
        label = QLabel(text)
        label.setProperty("role", "section")
        layout.addWidget(label)
        line = QFrame()
        line.setObjectName("hairline")
        line.setFixedHeight(1)
        layout.addWidget(line)

    def _form(self, label_text: str, widget_or_layout) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(12)
        label = QLabel(label_text)
        label.setProperty("role", "label")
        label.setFixedWidth(_LABEL_WIDTH)
        row.addWidget(label)
        if isinstance(widget_or_layout, QHBoxLayout):
            row.addLayout(widget_or_layout, 1)
        else:
            row.addWidget(widget_or_layout, 1)
        return row

    def _toggle_row(
        self, label_text: str, toggle: ToggleSwitch, hint: str = ""
    ) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(12)
        column = QVBoxLayout()
        column.setSpacing(1)
        label = QLabel(label_text)
        label.setProperty("role", "label")
        column.addWidget(label)
        if hint:
            hint_label = QLabel(hint)
            hint_label.setProperty("role", "hint")
            hint_label.setWordWrap(True)
            column.addWidget(hint_label)
        row.addLayout(column, 1)
        row.addWidget(toggle, 0, Qt.AlignmentFlag.AlignVCenter)
        return row

    def _slider_row(self, lo: int, hi: int, value: int, suffix: str, scale: int = 1):
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(lo, hi)
        slider.setValue(max(lo, min(hi, int(value))))
        slider.setSingleStep(max(1, (hi - lo) // 40))
        slider.setPageStep(max(1, (hi - lo) // 10))

        readout = QLabel()
        readout.setProperty("role", "value")
        readout.setFixedWidth(58)
        readout.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )

        def render(v: int) -> None:
            readout.setText(f"{v / scale:.2f}{suffix}" if scale > 1 else f"{v}{suffix}")

        render(slider.value())
        slider.valueChanged.connect(render)

        row = QHBoxLayout()
        row.setSpacing(10)
        row.addWidget(slider, 1)
        row.addWidget(readout)
        return slider, row

    # -- actions -----------------------------------------------------------

    def _on_theme_changed(self) -> None:
        name = self.theme.currentData() or "dark"
        self._apply_palette(palette_for(name))
        effects.enable_glass(
            int(self.winId()), dark=self._palette.is_dark, tint=self._palette.acrylic_tint
        )
        self.theme_previewed.emit(name)

    def _on_reset(self) -> None:
        d = config_store.DEFAULTS
        self.min_speech.setValue(d["min_speech_ms"])
        self.hangover.setValue(d["hangover_ms"])
        self.length_scale.setValue(int(round(d["length_scale"] * 100)))
        self.noise_scale.setValue(int(round(d["noise_scale"] * 100)))
        self.volume.setValue(int(round(d["volume"] * 100)))
        self.mic_mute.setChecked(d["mic_muted"], animate=True)
        self.vision.setChecked(d["vision_enabled"], animate=True)
        self.transcript.setChecked(d["transcript_visible"], animate=True)
        self.always_top.setChecked(d["always_on_top"], animate=True)
        self.to_tray.setChecked(d["minimize_to_tray"], animate=True)
        index = self.theme.findData(d["theme"])
        if index >= 0:
            self.theme.setCurrentIndex(index)

    def _on_save(self) -> None:
        self._config.update(
            min_speech_ms=self.min_speech.value(),
            hangover_ms=self.hangover.value(),
            length_scale=self.length_scale.value() / 100,
            noise_scale=self.noise_scale.value() / 100,
            volume=self.volume.value() / 100,
            mic_muted=self.mic_mute.isChecked(),
            vision_enabled=self.vision.isChecked(),
            transcript_visible=self.transcript.isChecked(),
            always_on_top=self.always_top.isChecked(),
            minimize_to_tray=self.to_tray.isChecked(),
            theme=self.theme.currentData() or "dark",
        )
        self.saved.emit(config_store.sanitize(self._config))
        self.accept()

    # -- dragging ----------------------------------------------------------

    def mousePressEvent(self, event) -> None:
        if (
            event.button() == Qt.MouseButton.LeftButton
            and event.position().y() < 56
        ):
            handle = self.windowHandle()
            if handle is not None and handle.startSystemMove():
                event.accept()
                return
        super().mousePressEvent(event)

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key.Key_Escape:
            self.reject()
            event.accept()
            return
        super().keyPressEvent(event)

    def reject(self) -> None:
        # Discard everything, including a live theme preview.
        original = config_store.sanitize(self._config).get("theme", "dark")
        self.theme_previewed.emit(original)
        super().reject()
