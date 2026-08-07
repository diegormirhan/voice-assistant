from pathlib import Path
from typing import Iterator

from piper import PiperVoice
from piper.config import SynthesisConfig


class PiperTTS:
    def __init__(self, model_path: Path, length_scale: float = 1.2, noise_scale: float = 0.5):
        self._voice = PiperVoice.load(str(model_path))
        self.sample_rate = self._voice.config.sample_rate

        # length_scale > 1.0 slows speech down (1.3 = ~30% slower).
        # noise_scale adds voice variation (low = stable, high = expressive).
        self._syn_config = SynthesisConfig(length_scale=length_scale, noise_scale=noise_scale)

    def synthesize(self, text: str) -> Iterator[tuple[bytes, int]]:
        for chunk in self._voice.synthesize(text, syn_config=self._syn_config):
            yield chunk.audio_int16_bytes, chunk.sample_rate
