import threading
import numpy as np
import sounddevice as sd

class AudioPlayback:
    def __init__(self, sample_rate: int):
        self._sample_rate = sample_rate
        self._stream = None

    def start(self):
        self._stream = sd.OutputStream(
            samplerate=self._sample_rate,
            channels=1,
            dtype="int16",
            blocksize=512,
        )
        self._stream.start()

    def play(self, chunks, interrupt_event: threading.Event) -> None:
        with sd.OutputStream(
            samplerate=self._sample_rate,
            channels=1,
            dtype="int16",
            blocksize=512,
        ) as stream:
            for chunk_bytes, _ in chunks:
                if interrupt_event.is_set():
                    break
                self._write_chunk(stream, chunk_bytes, interrupt_event)

    def _write_chunk(self, stream, chunk_bytes: bytes, interrupt_event: threading.Event) -> None:
        # convert bytes to numpy array int16 (that's how sounddevice understands)
        audio = np.frombuffer(chunk_bytes, dtype=np.int16)
        # iterates through the array in slices of 512 samples
        for start in range(0, len(audio), 512):
            if interrupt_event.is_set():
                break
            stream.write(audio[start:start + 512])

    def stop(self):
        if self._stream:
            self._stream.stop()
            self._stream.close()
            self._stream = None