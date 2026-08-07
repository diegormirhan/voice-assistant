from pathlib import Path
from typing import Iterator
from piper import PiperVoice

class PiperTTS:
    def __init__(self, model_path: Path):
        self._voice = PiperVoice.load(str(model_path))
        self.sample_rate = self._voice.config.sample_rate

    def synthesize(self, text: str) -> Iterator[tuple[bytes, int]]:
        for chunk in self._voice.synthesize(text):
            yield chunk.audio_int16_bytes, chunk.sample_rate
   
