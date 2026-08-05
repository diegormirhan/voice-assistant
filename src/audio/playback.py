import queue
import threading
from typing import Optional

import numpy as np
import sounddevice as sd


class PlaybackThread:
    def __init__(
        self,
        audio_queue: "queue.Queue[np.ndarray]",
        stop_event: threading.Event,
        sample_rate: int = 22050,
        interrupt_event: Optional[threading.Event] = None,
    ) -> None:
        self._queue = audio_queue
        self._stop_event = stop_event
        self._interrupt_event = interrupt_event or threading.Event()
        self._sample_rate = sample_rate
        self._stream: Optional[sd.OutputStream] = None
        self._is_active = False
        self._lock = threading.Lock()

    @property
    def is_active(self) -> bool:
        # True se há áudio tocando OU pendente na fila (o InterruptionManager
        # usa isso pra decidir se um speech_start é barge-in).
        with self._lock:
            return self._is_active or not self._queue.empty()

    def start(self) -> threading.Thread:
        def _run() -> None:
            try:
                self._stream = sd.OutputStream(
                    samplerate=self._sample_rate,
                    channels=1,
                    dtype="int16",
                )
                self._stream.start()
            except Exception as e:
                print(f"playback start failed: {e}")
                return

            while not self._stop_event.is_set():
                if self._interrupt_event.is_set():
                    # barge-in: para de tocar e esvazia a fila imediatamente
                    with self._lock:
                        self._is_active = False
                    self._drain()
                    self._interrupt_event.clear()
                    continue

                try:
                    chunk = self._queue.get(timeout=0.05)
                except queue.Empty:
                    with self._lock:
                        self._is_active = False
                    continue

                if chunk is None or len(chunk) == 0:
                    continue

                with self._lock:
                    self._is_active = True
                try:
                    self._stream.write(chunk)
                except Exception as e:
                    print(f"playback write error: {e}")
                    with self._lock:
                        self._is_active = False

            with self._lock:
                self._is_active = False
            if self._stream is not None:
                self._stream.stop()
                self._stream.close()

        t = threading.Thread(target=_run, name="Playback", daemon=True)
        t.start()
        return t

    def _drain(self) -> None:
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
            except queue.Empty:
                break

    def stop(self) -> None:
        self._stop_event.set()


if __name__ == "__main__":
    q: "queue.Queue[np.ndarray]" = queue.Queue()
    stop = threading.Event()
    interrupt = threading.Event()
    pb = PlaybackThread(q, stop, interrupt_event=interrupt)
    pb.start()

    tone = np.random.randint(-1000, 1000, size=22050, dtype=np.int16)
    q.put(tone)
    print(f"is_active (com chunk na fila): {pb.is_active} (esperado True)")

    import time
    time.sleep(1.2)  # espera o tom de 1s terminar
    print(f"is_active (apos tocar): {pb.is_active} (esperado False)")

    q.put(tone)
    time.sleep(0.3)
    print(f"is_active (tocando): {pb.is_active} (esperado True)")
    interrupt.set()
    time.sleep(0.2)
    print(f"is_active (apos interrupt): {pb.is_active} (esperado False)")

    stop.set()
    print("stopped")
