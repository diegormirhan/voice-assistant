import queue
import threading
from pathlib import Path
from typing import Optional

import numpy as np
import sherpa_onnx


SHERPA_MODEL_DIR = (
    Path(__file__).resolve().parent.parent.parent / "models" / "sherpa"
)
WHISPER_MODEL_NAME = "sherpa-onnx-whisper-small.en-2024-08-20"
SAMPLE_RATE = 16000
MIN_TEXT_LEN = 3
HALLUCINATIONS = {"", " ", ".", "..", "...", "obrigado.", "legendas", "subtitles"}


class SherpaRecognizer:
    def __init__(self, model_dir: Optional[Path] = None) -> None:
        self._model_dir = Path(model_dir) if model_dir else SHERPA_MODEL_DIR / WHISPER_MODEL_NAME
        if not self._model_dir.exists():
            raise FileNotFoundError(
                f"sherpa model not found: {self._model_dir}\n"
                f"Run: python scripts/download_models.py"
            )
        self._recognizer = sherpa_onnx.OfflineRecognizer.from_whisper(
            encoder=f"{self._model_dir}/base.en-encoder.int8.onnx",
            decoder=f"{self._model_dir}/base.en-decoder.int8.onnx",
        )

    def transcribe(self, audio: np.ndarray) -> str:
        if audio.dtype == np.int16:
            audio = audio.astype(np.float32) / 32768.0
        stream = self._recognizer.create_stream()
        stream.accept_waveform(SAMPLE_RATE, audio)
        self._recognizer.decode_streams([stream])
        text = (stream.result.text or "").strip()
        text = "".join(c for c in text if c.isprintable())
        return text

    def is_valid(self, text: str) -> bool:
        if len(text) < MIN_TEXT_LEN:
            return False
        if text.lower().strip(" .!?") in HALLUCINATIONS:
            return False
        return True


def run_stt_thread(
    input_q: "queue.Queue[np.ndarray]",
    output_q: "queue.Queue[str]",
    stop_event: threading.Event,
    recognizer: SherpaRecognizer,
) -> threading.Thread:
    def _loop():
        while not stop_event.is_set():
            try:
                audio = input_q.get(timeout=0.1)
            except queue.Empty:
                continue
            try:
                text = recognizer.transcribe(audio)
            except Exception as e:
                print(f"stt error: {e}")
                continue
            if recognizer.is_valid(text):
                try:
                    output_q.put_nowait(text)
                except queue.Full:
                    pass

    t = threading.Thread(target=_loop, name="STT", daemon=True)
    t.start()
    return t


if __name__ == "__main__":
    print(f"model dir: {SHERPA_MODEL_DIR / WHISPER_MODEL_NAME}")
    if not (SHERPA_MODEL_DIR / WHISPER_MODEL_NAME).exists():
        print("model not found. run: python scripts/download_models.py")
    else:
        rec = SherpaRecognizer()
        print("recognizer loaded OK")
