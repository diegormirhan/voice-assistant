import numpy as np
import sounddevice as sd


class AudioCapture:
    """Just captures mic audio. No logic - only raw 32ms blocks."""

    def __init__(self, on_audio):
        """on_audio: callback receiving np.ndarray int16 (512 samples)."""
        self._on_audio = on_audio
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
        self._on_audio(indata[:, 0].copy())

    def stop(self):
        if self._stream:
            self._stream.stop()
            self._stream.close()
            self._stream = None