import threading, queue
import numpy as np
import sounddevice as sd

class AudioPlayback:
    """Plays TTS audio on a dedicated thread with barge-in support."""

    def __init__(self, sample_rate: int):
        self._sample_rate = sample_rate                 # TTS sample rate (22050)
        self._queue = queue.Queue()                     # speak() puts, _run() takes
        self._interrupt = threading.Event()             # barge-in flag
        self._shutdown = threading.Event()              # app closing flag
        self._idle = threading.Event()                  # set when queue empty
        self._idle.set()
        self._lock = threading.Lock()                   # guards _queue/_idle
        self._stream: sd.OutputStream | None = None     # one stream, opened in start()
        self._thread: threading.Thread | None = None    # playback thread

    def start(self):
        # One stream for the whole session (reopening per sentence adds gaps).
        self._stream = sd.OutputStream(
            samplerate=self._sample_rate,
            channels=1,
            dtype="int16",
            blocksize=512,
        )
        self._stream.start()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def speak(self, chunks):
        """Enqueues audio chunks (non-blocking); the LLM keeps generating."""
        with self._lock:
            self._idle.clear()
            for chunk_bytes, _ in chunks:
                if self._interrupt.is_set():
                    break
                self._queue.put(chunk_bytes)

    def _run(self):
        # Playback thread loop; stays alive the whole app.
        while not self._shutdown.is_set():
            try:
                chunk_bytes = self._queue.get(timeout=0.5)
            except queue.Empty:
                self._mark_idle()
                continue
            if self._interrupt.is_set():
                continue  # skip stale audio after barge-in
            self._write_chunk(chunk_bytes)
            self._mark_idle()

    def _mark_idle(self):
        # Called when the queue has nothing more to play.
        with self._lock:
            if self._queue.empty():
                self._idle.set()

    def _write_chunk(self, chunk_bytes: bytes):
        audio = np.frombuffer(chunk_bytes, dtype=np.int16)
        assert self._stream is not None  # created in start()
        # 512-sample slices so barge-in can cut mid-chunk.
        for start in range(0, len(audio), 512):
            if self._interrupt.is_set() or self._shutdown.is_set():
                break
            self._stream.write(audio[start:start + 512])

    def interrupt(self):
        """Barge-in: set flag, discard queued audio, abort the stream."""
        self._interrupt.set()
        with self._lock:
            while not self._queue.empty():
                self._queue.get_nowait()
            self._idle.set()
        if self._stream:
            self._stream.abort()  # stops immediately, drops buffered audio

    @property
    def interrupted(self) -> bool:
        """True while a barge-in is active."""
        return self._interrupt.is_set()

    def clear_interrupt(self):
        """Clears the barge-in flag and restarts the stream for the next reply."""
        self._interrupt.clear()
        if self._stream and self._stream.stopped:
            self._stream.start()  # resume after interrupt() called abort()

    def wait_until_idle(self, timeout: float) -> bool:
        """Blocks until playback finishes; True if idle, False on timeout."""
        return self._idle.wait(timeout)

    def stop(self):
        self._shutdown.set()
        self._interrupt.set()
        if self._thread:
            self._thread.join(timeout=1)
        if self._stream:
            self._stream.stop()
            self._stream.close()
            self._stream = None
