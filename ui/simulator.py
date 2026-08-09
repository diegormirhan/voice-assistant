"""Fake backend so the UI can be designed, reviewed and demoed standalone.

UI.md stage 1 is "apenas a UI, com dados simulados". Everything here talks to
the app exclusively through `Bus`, which is the same seam the real
orchestrator will use — deleting this file is the only change required when
the backend lands.
"""

from __future__ import annotations

import math
import random

from PySide6.QtCore import QObject, QTimer

from .state import AssistantState, Bus

_TURNS = [
    ("Que horas são agora?", "São 20h47 aqui no seu computador."),
    ("O que está na minha tela?", "Vejo um editor de código com um arquivo Python aberto."),
    ("Resuma isso pra mim.", "É a especificação da interface do assistente de voz."),
    ("Consegue rodar tudo offline?", "Sim — whisper.cpp, llama.cpp e Piper rodam localmente."),
]


class Simulator(QObject):
    """Drives states, audio levels, transcript and download progress."""

    def __init__(self, bus: Bus, parent=None):
        super().__init__(parent)
        self._bus = bus
        self._state = AssistantState.OFF
        self._phase = 0.0
        self._turn = 0
        self._muted = False
        self._download = 0

        self._levels = QTimer(self)
        self._levels.setInterval(50)
        self._levels.timeout.connect(self._emit_levels)

        self._script = QTimer(self)
        self._script.setSingleShot(True)
        self._script.timeout.connect(self._advance)

        self._dl_timer = QTimer(self)
        self._dl_timer.setInterval(90)
        self._dl_timer.timeout.connect(self._tick_download)

    # -- api ---------------------------------------------------------------

    def set_mic_muted(self, muted: bool) -> None:
        self._muted = bool(muted)

    def start(self) -> None:
        if self._state is not AssistantState.OFF:
            return
        self._set_state(AssistantState.LOADING)
        self._levels.start()
        self._script.start(2200)

    def stop(self) -> None:
        self._levels.stop()
        self._script.stop()
        self._set_state(AssistantState.OFF)
        self._bus.mic_level.emit(0.0)
        self._bus.output_level.emit(0.0)

    def start_download(self) -> None:
        if self._dl_timer.isActive():
            return
        self._download = 0
        self._bus.download_progress.emit(0)
        self._dl_timer.start()

    # -- internals ---------------------------------------------------------

    def _set_state(self, state: AssistantState) -> None:
        self._state = state
        self._bus.state_changed.emit(state)

    def _emit_levels(self) -> None:
        self._phase += 0.16
        if self._state is AssistantState.LISTENING and not self._muted:
            base = 0.5 + 0.5 * math.sin(self._phase * 1.7)
            level = max(0.0, min(1.0, base * 0.8 + random.uniform(-0.08, 0.12)))
            self._bus.mic_level.emit(level)
            self._bus.output_level.emit(0.0)
        elif self._state is AssistantState.SPEAKING:
            base = 0.55 + 0.45 * math.sin(self._phase * 3.1)
            level = max(0.0, min(1.0, base * 0.9 + random.uniform(-0.1, 0.1)))
            self._bus.output_level.emit(level)
            self._bus.mic_level.emit(0.06 if not self._muted else 0.0)
        else:
            self._bus.mic_level.emit(0.0 if self._muted else random.uniform(0.0, 0.05))
            self._bus.output_level.emit(0.0)

    def _advance(self) -> None:
        if self._state is AssistantState.OFF:
            return

        if self._state is AssistantState.LOADING:
            self._set_state(AssistantState.LISTENING)
            self._script.start(3200)
            return

        if self._state is AssistantState.LISTENING:
            question, _ = _TURNS[self._turn % len(_TURNS)]
            self._bus.user_said.emit(question)
            self._set_state(AssistantState.THINKING)
            self._script.start(1500)
            return

        if self._state is AssistantState.THINKING:
            _, answer = _TURNS[self._turn % len(_TURNS)]
            self._bus.assistant_said.emit(answer)
            self._set_state(AssistantState.SPEAKING)
            self._script.start(2600)
            return

        if self._state is AssistantState.SPEAKING:
            self._turn += 1
            self._set_state(AssistantState.LISTENING)
            self._script.start(3600)

    def _tick_download(self) -> None:
        self._download += random.randint(2, 7)
        if self._download >= 100:
            self._download = 100
            self._dl_timer.stop()
            self._bus.download_progress.emit(100)
            self._bus.download_finished.emit(True, "Binários Vulkan prontos.")
            return
        self._bus.download_progress.emit(self._download)
