import numpy as np
import sounddevice as sd


class AudioCapture:
    """Captures microphone audio in 16kHz mono int16 blocks.

    Each block is 512 samples (32ms) and is delivered to a callback.
    Keeps no state about speech/VAD - it only forwards raw audio.
    """

    SAMPLE_RATE = 16000   # Whisper expects 16kHz input
    BLOCK_SIZE = 512      # 512 samples = 32ms at 16kHz
    CHANNELS = 1
    DTYPE = "int16"

    def __init__(self, on_audio) -> None:
        """on_audio: callback receiving a np.ndarray int16 (512 samples) per call."""
        self._on_audio = on_audio
        self._stream = None

    def start(self):
        """Opens the mic stream and starts delivering audio blocks."""
        self._stream = sd.InputStream(
            samplerate=self.SAMPLE_RATE,
            blocksize=self.BLOCK_SIZE,
            channels=self.CHANNELS,
            dtype=self.DTYPE,
            callback=self._callback,
        )
        self._stream.start()

    def _callback(self, indata, frames, time_info, status):
        # sounddevice reuses `indata` between callbacks, so copy it to
        # avoid losing frames or corrupting the buffer downstream.
        self._on_audio(indata[:, 0].copy())

    def stop(self):
        """Closes the mic stream cleanly."""
        if self._stream:
            self._stream.stop()
            self._stream.close()
            self._stream = None


if __name__ == "__main__":
    # Smoke test: speak and watch the RMS value change.
    def on_audio(block):
        rms = float(np.sqrt(np.mean(block.astype(float) ** 2)))
        print(f"rms: {rms:.0f}")

    capture = AudioCapture(on_audio)
    capture.start()
    input("falando... Enter para parar!")
    capture.stop()
