import queue
import threading
from pathlib import Path
from typing import Generator, Optional

import numpy as np
from piper import PiperVoice


DEFAULT_VOICE_PATH = (
    Path(__file__).resolve().parent.parent.parent / "models" / "piper" / "pt_BR-faber-medium.onnx"
)
SAMPLE_RATE = 22050
DTYPE = np.int16


class PiperEngine:
    def __init__(self, voice_path: str = str(DEFAULT_VOICE_PATH)) -> None:
        if not Path(voice_path).exists():
            raise FileNotFoundError(
                f"Piper voice not found: {voice_path}\n"
                f"Run: python scripts/download_models.py"
            )
        self._voice = PiperVoice.load(voice_path)
        self._sample_rate = self._voice.config.sample_rate

    @property
    def sample_rate(self) -> int:
        return self._sample_rate

    def synthesize_stream(
        self,
        text: str,
        stop_event: Optional[threading.Event] = None,
    ) -> Generator[np.ndarray, None, None]:
        if not text.strip():
            return
        for chunk in self._voice.synthesize_stream_raw(text):
            if stop_event is not None and stop_event.is_set():
                break
            audio = np.frombuffer(chunk.audio_int16_bytes, dtype=DTYPE)
            yield audio


if __name__ == "__main__":
    voice = DEFAULT_VOICE_PATH
    if not voice.exists():
        print(f"voice not found: {voice}")
        print("run: python scripts/download_models.py")
    else:
        eng = PiperEngine(str(voice))
        stop = threading.Event()
        chunks = list(eng.synthesize_stream("Ola, tudo bem?", stop))
        total = sum(len(c) for c in chunks)
        print(f"synthesized {len(chunks)} chunks, {total} samples ({total/eng.sample_rate:.2f}s)")
