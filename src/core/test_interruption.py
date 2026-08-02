import threading
from typing import Optional


class InterruptionManager:
    def __init__(self, interrupt_event: threading.Event) -> None:
        self._interrupt_event = interrupt_event
        self._barge_in_active = False
        self._lock = threading.Lock()
        self._playback_is_active = False

    def set_playback_active(self, active: bool) -> None:
        self._playback_is_active = active

    def trigger_if_barge_in(self) -> bool:
        with self._lock:
            if self._barge_in_active:
                return False
            if not self._playback_is_active:
                return False
            self._barge_in_active = True
            self._interrupt_event.set()
            return True

    def reset(self) -> None:
        with self._lock:
            self._barge_in_active = False
            self._interrupt_event.clear()

    @property
    def is_barge_in_active(self) -> bool:
        return self._barge_in_active


def drain_queue(q) -> None:
    while not q.empty():
        try:
            q.get_nowait()
        except Exception:
            break


if __name__ == "__main__":
    import queue

    evt = threading.Event()
    mgr = InterruptionManager(evt)

    print(f"playback inactive + speech_start: barge_in={mgr.trigger_if_barge_in()} (expected False)")

    mgr.set_playback_active(True)
    print(f"playback active + speech_start: barge_in={mgr.trigger_if_barge_in()} (expected True)")
    print(f"  interrupt_event set: {evt.is_set()}")

    print(f"trigger novamente (reentrada): barge_in={mgr.trigger_if_barge_in()} (expected False)")

    mgr.reset()
    print(f"after reset: barge_in_active={mgr.is_barge_in_active}, evt={evt.is_set()}")
