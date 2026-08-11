"""Main window: frameless, translucent, acrylic 4:3 glass panel.
"""

from __future__ import annotations
import config



from PySide6.QtCore import QEvent, QSize, Qt, QTimer
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QAbstractButton,
    QAbstractScrollArea,
    QAbstractSpinBox,
    QApplication,
    QComboBox,
    QLineEdit,
    QSlider,
    QFrame,
    QLabel,
    QMainWindow,
    QMenu,
    QSystemTrayIcon,
    QVBoxLayout,
    QWidget,
)

from . import config_store, effects, icons
from .app_icon import app_icon
from .modals.info import VoiceProfileInfoModal
from .modals.settings import SettingsModal
from .qss import build_qss
from .backend import Backend
from .state import AssistantState, Bus
from .theme import T, palette_for
from .widgets.backdrop import LiquidBackdrop
from .widgets.center_button import CenterButton
from .widgets.title_bar import TitleBar
from .widgets.transcript import TranscriptPanel
from .window_anim import WindowAnimator



class MainWindow(QMainWindow):
    def __init__(self, bus: Bus | None = None):
        super().__init__()
        self._config = config_store.load()
        self._palette = palette_for(self._config["theme"])
        self._state = AssistantState.OFF
        self._settings_modal: SettingsModal | None = None
        self._quitting = False

        self.bus = bus or Bus()
        self.backend = Backend(self.bus, config.TTS_MODEL, self)

        self.setWindowTitle("Assistente de Voz")
        self.setWindowFlags(
            Qt.WindowType.Window
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowSystemMenuHint
            | Qt.WindowType.WindowMinimizeButtonHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        # The title bar packs status + two pills + ⓘ + window buttons; below this
        # width the row squeezes past its minimum and the children overlap.
        self.setMinimumSize(QSize(820, 620))
        self.resize(self._config["window_w"], self._config["window_h"])
        window_icon = app_icon()
        if not window_icon.isNull():
            self.setWindowIcon(window_icon)

        self._anim = WindowAnimator(self)
        self._build_ui()
        self._connect_bus()
        self._apply_theme(self._palette)
        self._apply_always_on_top(self._config["always_on_top"], reshow=False)
        self._center_on_screen()
        self._setup_tray()

        # winId() is only valid once the platform window exists.
        QTimer.singleShot(0, self._apply_native_chrome)

    # -- construction ------------------------------------------------------

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        outer = QVBoxLayout(central)
        outer.setContentsMargins(0, 0, 0, 0)

        self._card = QFrame()
        self._card.setObjectName("glassCard")
        outer.addWidget(self._card)

        # Liquid-glass wash: lives inside the card, below every control.
        self._backdrop = LiquidBackdrop(self._palette, self._card)
        self._backdrop.lower()
        self._card.installEventFilter(self)

        layout = QVBoxLayout(self._card)
        layout.setContentsMargins(T.pad_window, 10, T.pad_window, T.pad_window)
        layout.setSpacing(T.gap)

        self.title_bar = TitleBar(self._palette, self._config)
        self.title_bar.settings_requested.connect(self._open_settings)
        self.title_bar.info_requested.connect(self._open_profile_info)
        self.title_bar.download_requested.connect(self._start_download)
        self.title_bar.minimize_requested.connect(self._minimize)
        self.title_bar.close_requested.connect(self._close_animated)
        self.title_bar.profile_changed.connect(
            lambda value: self._update_config(model_profile=value)
        )
        self.title_bar.voice_changed.connect(
            lambda value: self._update_config(voice=value)
        )
        layout.addWidget(self.title_bar)

        accent = QFrame()
        accent.setObjectName("accentLine")
        accent.setFixedHeight(1)
        layout.addWidget(accent)

        layout.addStretch(1)
        self.power = CenterButton(self._palette)
        self.power.toggled_on.connect(self._on_power_toggled)
        layout.addWidget(self.power, 0, Qt.AlignmentFlag.AlignHCenter)

        self.hint = QLabel("Clique para conversar")
        self.hint.setProperty("role", "hint")
        self.hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.hint)
        layout.addStretch(1)

        self.transcript = TranscriptPanel(
            self._palette, expanded=self._config["transcript_expanded"]
        )
        self.transcript.expanded_changed.connect(
            lambda value: self._update_config(transcript_expanded=value)
        )
        self.transcript.setVisible(self._config["transcript_visible"])
        layout.addWidget(self.transcript)

    def _connect_bus(self) -> None:
        self.bus.state_changed.connect(self._on_state_changed)
        self.bus.mic_level.connect(self._on_mic_level)
        self.bus.output_level.connect(self._on_output_level)
        self.bus.user_said.connect(self.transcript.add_user)
        self.bus.assistant_said.connect(self.transcript.add_assistant)
        self.bus.download_progress.connect(self.title_bar.download_btn.set_progress)
        self.bus.download_finished.connect(self.title_bar.download_btn.finish)
        self.bus.error.connect(self._on_error)

    def eventFilter(self, watched, event):
        # The backdrop is not in the layout (it must sit under the controls),
        # so it follows the card geometry manually. Watching the card's own
        # resize is required: during MainWindow.resizeEvent the card still
        # reports its previous size, which left the wash clipped.
        if watched is self._card and event.type() == QEvent.Type.Resize:
            self._backdrop.setGeometry(self._card.rect())
            self._backdrop.lower()
        return super().eventFilter(watched, event)

    # -- native chrome -----------------------------------------------------

    def _apply_native_chrome(self) -> None:
        hwnd = int(self.winId())
        effects.enable_native_animations(hwnd)
        effects.enable_glass(
            hwnd, dark=self._palette.is_dark, tint=self._palette.acrylic_tint
        )

    def _center_on_screen(self) -> None:
        screen = QGuiApplication.primaryScreen()
        if screen is None:
            return
        available = screen.availableGeometry()
        geo = self.frameGeometry()
        geo.moveCenter(available.center())
        self.move(geo.topLeft())

    # -- theme -------------------------------------------------------------

    def _apply_theme(self, palette) -> None:
        self._palette = palette
        self.setStyleSheet(build_qss(palette))
        self.title_bar.set_palette(palette)
        self.power.set_palette(palette)
        self.transcript.set_palette(palette)
        self._backdrop.set_palette(palette)
        if self.isVisible():
            effects.enable_glass(
                int(self.winId()), dark=palette.is_dark, tint=palette.acrylic_tint
            )

    def _apply_always_on_top(self, enabled: bool, *, reshow: bool = True) -> None:
        was_visible = self.isVisible()
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, bool(enabled))
        # Changing flags hides a visible window on Windows: show it back.
        if reshow and was_visible:
            self.show()

    # -- state -------------------------------------------------------------

    def _on_state_changed(self, state: AssistantState) -> None:
        self._state = state
        self.power.set_state(state)
        self._backdrop.set_state(state)
        self.title_bar.set_state(state)
        self.hint.setText(
            "Clique para conversar"
            if state is AssistantState.OFF
            else {
                AssistantState.LOADING: "Subindo whisper.cpp, llama.cpp e Piper…",
                AssistantState.LISTENING: "Pode falar — interrompa quando quiser",
                AssistantState.THINKING: "Processando com contexto visual…",
                AssistantState.SPEAKING: "Respondendo",
            }[state]
        )
        if self._tray is not None:
            self._tray.setToolTip(f"Assistente de Voz — {state.label}")

    def _on_power_toggled(self, turn_on: bool) -> None:
        if turn_on:
            self.backend.start()
        else:
            self.backend.stop()

    def _on_mic_level(self, level: float) -> None:
        if self._state in (AssistantState.LISTENING, AssistantState.OFF):
            self.power.set_amplitude(0.0 if self._config["mic_muted"] else level)
        if self._settings_modal is not None:
            self._settings_modal.set_mic_level(
                0.0 if self._config["mic_muted"] else level
            )

    def _on_output_level(self, level: float) -> None:
        if self._state is AssistantState.SPEAKING:
            self.power.set_amplitude(level * self._config["volume"])

    def _on_error(self, message: str) -> None:
        self.hint.setText(message)

    # -- actions -----------------------------------------------------------

    def _start_download(self) -> None:
        if self.title_bar.download_btn.is_running():
            return
        self.title_bar.download_btn.start()
        self.backend.start_download()

    def _open_profile_info(self) -> None:
        VoiceProfileInfoModal(self._palette, self).exec()

    def _open_settings(self) -> None:
        if self._settings_modal is not None:
            self._settings_modal.raise_()
            return

        modal = SettingsModal(self._config, self._palette, self)
        self._settings_modal = modal
        modal.saved.connect(self._on_settings_saved)
        modal.theme_previewed.connect(
            lambda name: self._apply_theme(palette_for(name))
        )
        try:
            modal.exec()
        finally:
            self._settings_modal = None
            modal.deleteLater()

    def _on_settings_saved(self, config: dict) -> None:
        self._config = config_store.sanitize(config)
        config_store.save(self._config)
        self._apply_theme(palette_for(self._config["theme"]))

        self.transcript.setVisible(self._config["transcript_visible"])
        if not self._config["transcript_visible"]:
            self.transcript.set_expanded(False, animate=False)
        self._apply_always_on_top(self._config["always_on_top"])
        self.backend.set_mic_muted(self._config["mic_muted"])

    def _update_config(self, **changes) -> None:
        self._config.update(changes)
        self._config = config_store.sanitize(self._config)
        config_store.save(self._config)

    # -- window controls ---------------------------------------------------

    def _minimize(self) -> None:
        if self._config["minimize_to_tray"] and self._tray is not None:
            self._anim.minimize(minimize_call=self.hide)
            return

        def sink() -> None:
            if not effects.minimize_animated(int(self.winId())):
                self.showMinimized()

        self._anim.minimize(minimize_call=sink)

    def _close_animated(self) -> None:
        self._anim.close(quit_call=self.quit_app)

    def changeEvent(self, event) -> None:
        # Growing back in when Windows (taskbar / Alt-Tab / tray) restores us.
        if event.type() == QEvent.Type.WindowStateChange:
            was_min = bool(event.oldState() & Qt.WindowState.WindowMinimized)
            if was_min and not self.isMinimized():
                self._anim.restore_from_minimized()
        super().changeEvent(event)

    def quit_app(self) -> None:
        self._quitting = True
        self.backend.stop()
        self._persist_geometry()
        config_store.save(self._config)
        if self._tray is not None:
            self._tray.hide()
        QApplication.instance().quit()

    def _persist_geometry(self) -> None:
        if self.isVisible() and not self.isMinimized():
            geo = self._anim.normal_geometry()
            self._config["window_w"] = geo.width()
            self._config["window_h"] = geo.height()

    def closeEvent(self, event) -> None:
        if not self._quitting:
            self._quitting = True
            self.backend.stop()
            self._persist_geometry()
            config_store.save(self._config)
            if self._tray is not None:
                self._tray.hide()
        event.accept()

    # -- tray --------------------------------------------------------------

    def _setup_tray(self) -> None:
        self._tray = None
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return

        icon = app_icon()
        if icon.isNull():
            icon = icons.power(32, self._palette.accent)

        tray = QSystemTrayIcon(icon, self)
        tray.setToolTip("Assistente de Voz")

        menu = QMenu(self)
        menu.addAction("Mostrar", self._restore_from_tray)
        menu.addAction("Configurações", self._open_settings)
        menu.addSeparator()
        menu.addAction("Sair", self.quit_app)
        tray.setContextMenu(menu)

        tray.activated.connect(self._on_tray_activated)
        tray.show()
        self._tray = tray

    def _on_tray_activated(self, reason) -> None:
        # Only a real click restores — a right-click just opens the menu.
        if reason in (
            QSystemTrayIcon.ActivationReason.Trigger,
            QSystemTrayIcon.ActivationReason.DoubleClick,
        ):
            self._restore_from_tray()

    def _restore_from_tray(self) -> None:
        already_visible = self.isVisible() and not self.isMinimized()
        self.showNormal()
        self.raise_()
        self.activateWindow()
        if not already_visible:
            self._anim.restore_from_minimized()

    # -- dragging / keyboard -----------------------------------------------

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self._in_drag_zone(event):
            handle = self.windowHandle()
            if handle is not None and handle.startSystemMove():
                event.accept()
                return
        super().mousePressEvent(event)

    def _in_drag_zone(self, event) -> bool:
        """True anywhere on the top strip that is not an interactive control.

        The previous version only accepted the title bar's own rect and only
        when `childAt` returned nothing, so the window padding around the bar,
        the gaps between the pills and any decorative child (frames, spacer
        widgets, the status label's container) were dead zones — dragging felt
        broken. Now the whole header band drags, and only real controls
        (buttons, combo boxes, inputs) opt out.
        """
        point = event.position().toPoint()
        bottom = self.title_bar.mapTo(self, self.title_bar.rect().bottomLeft()).y()
        if point.y() > bottom:
            return False
        child = self.childAt(point)
        while child is not None and child is not self:
            if isinstance(child, (QAbstractButton, QComboBox, QAbstractSpinBox,
                                  QLineEdit, QSlider, QAbstractScrollArea)):
                return False
            child = child.parentWidget()
        return True

    def keyPressEvent(self, event) -> None:
        key = event.key()
        if key == Qt.Key.Key_Space:
            self.power.click()
            event.accept()
            return
        if key == Qt.Key.Key_Escape:
            self._minimize()
            event.accept()
            return
        if key == Qt.Key.Key_Comma and event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            self._open_settings()
            event.accept()
            return
        super().keyPressEvent(event)
