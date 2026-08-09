"""Assistant state machine + the single signal bus between UI and backend.

The UI never talks to the orchestrator directly: it listens to `Bus`.
Whatever produces the events (the simulator today, the real orchestrator
later) only has to emit these signals from any thread — Qt queues them onto
the GUI thread, so this is the thread-safe seam described in UI.md.
"""

from __future__ import annotations

from enum import Enum

from PySide6.QtCore import QObject, Signal


class AssistantState(Enum):
    OFF = "off"
    LOADING = "loading"
    LISTENING = "listening"
    THINKING = "thinking"
    SPEAKING = "speaking"

    @property
    def is_active(self) -> bool:
        return self is not AssistantState.OFF

    @property
    def label(self) -> str:
        return {
            AssistantState.OFF: "Desligado",
            AssistantState.LOADING: "Carregando modelos",
            AssistantState.LISTENING: "Ouvindo",
            AssistantState.THINKING: "Pensando",
            AssistantState.SPEAKING: "Falando",
        }[self]


class Bus(QObject):
    """Signals consumed by the UI. Emit from any thread."""

    # Lifecycle / status
    state_changed = Signal(object)          # AssistantState
    error = Signal(str)

    # Audio levels, 0.0..1.0
    mic_level = Signal(float)               # microphone RMS (input)
    output_level = Signal(float)            # TTS playback RMS (output)

    # Transcript (session only)
    user_said = Signal(str)
    assistant_said = Signal(str)

    # Binary download
    download_progress = Signal(int)         # 0..100
    download_finished = Signal(bool, str)   # ok, message
