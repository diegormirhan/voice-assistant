import enum
import threading
from typing import Callable


class AssistantState(enum.Enum):
    IDLE = "IDLE"
    LISTENING = "LISTENING"
    THINKING = "THINKING"
    SPEAKING = "SPEAKING"
    INTERRUPTED = "INTERRUPTED"


class StateManager:
    def __init__(self) -> None:
        self._state = AssistantState.LISTENING
        self._lock = threading.Lock()
        self._callbacks: list[Callable[[AssistantState, AssistantState], None]] = []

    @property
    def current(self) -> AssistantState:
        with self._lock:
            return self._state

    def transition(self, new_state: AssistantState) -> None:
        with self._lock:
            old_state = self._state
            if old_state == new_state:
                return
            self._state = new_state
        for cb in self._callbacks:
            try:
                cb(old_state, new_state)
            except Exception:
                pass

    def on_change(self, cb: Callable[[AssistantState, AssistantState], None]) -> None:
        self._callbacks.append(cb)


if __name__ == "__main__":
    sm = StateManager()
    sm.on_change(lambda old, new: print(f"  {old.value} -> {new.value}"))
    sm.transition(AssistantState.THINKING)
    sm.transition(AssistantState.SPEAKING)
    sm.transition(AssistantState.LISTENING)
