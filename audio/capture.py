import numpy as np
import sounddevice as sd

class AudioCapture:
    """Just captures mic audio. No logic - only raw 32ms blocks."""

    def __init__(self, on_audio, on_level = None):
        """on_audio: callback receiving np.ndarray int16 (512 samples).
        on_level: optional callback receiving float RMS (0..1)."""
        self._on_audio = on_audio
        self._on_level = on_level
        self._stream = None

    def start(self):
        self._stream = sd.InputStream(
            samplerate=16000,
            blocksize=512,
            channels=1,
            dtype="int16",
            callback=self._callback,
        )
        self._stream.start()

    def _callback(self, indata, frames, time_info, status):
        block = indata[:, 0].copy()
        if self._on_level:
            rms = float(np.sqrt(np.mean(block.astype(np.float32) ** 2)) / 32768.0)
            self._on_level(min(1.0, (rms * 10.0) ** 0.5)) # scale up quiet speech
        self._on_audio(block)

    def stop(self):
        if self._stream:
            self._stream.stop()
            self._stream.close()
            self._stream = None