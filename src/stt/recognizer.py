import queue
import threading
from typing import Optional

import numpy as np
from faster_whisper import WhisperModel


# Modelo e parâmetros de transcrição
# "medium" é o melhor custo/benefício pra CPU int8 em português.
# Se estiver lento, troque pra "small". Se precisar de mais precisão, "large-v3-turbo".
MODEL_SIZE = "medium"
DEVICE = "cpu"
COMPUTE_TYPE = "int8"
SAMPLE_RATE = 16000
MIN_TEXT_LEN = 3

# Frases fantasma que o Whisper alucina em silêncio/ruído
DISCARD = {
    ".", "..", "...", "obrigado.", "legendas", "subtitles",
    "thank you.", "thanks for watching.", "thank you for watching.",
    "obrigado por assistir.", "inscreva-se.", "tchau.",
}


class FasterWhisperRecognizer:
    """STT usando Faster-Whisper (CTranslate2) — otimizado pra CPU int8."""

    def __init__(
        self,
        model_size: str = MODEL_SIZE,
        device: str = DEVICE,
        compute_type: str = COMPUTE_TYPE,
    ) -> None:
        print(f"  [stt] carregando faster-whisper ({model_size}, {compute_type})...")
        self._model = WhisperModel(
            model_size,
            device=device,
            compute_type=compute_type,
            cpu_threads=4,
        )
        print(f"  [stt] modelo carregado")

    def transcribe(self, audio: np.ndarray) -> str:
        if audio.dtype == np.int16:
            audio = audio.astype(np.float32) / 32768.0

        segments, _info = self._model.transcribe(
            audio,
            language="pt",
            beam_size=3,               # 3 é bom equilíbrio velocidade/precisão no CPU
            vad_filter=False,           # já temos Silero VAD externo
            condition_on_previous_text=False,  # evita alucinações em segmentos curtos
        )
        text = " ".join(seg.text.strip() for seg in segments)
        return text.strip()

    def is_valid(self, text: str) -> bool:
        if len(text) < MIN_TEXT_LEN:
            return False
        return text.lower().strip(" .!?") not in DISCARD


def run_stt_thread(
    input_q: "queue.Queue[np.ndarray]",
    output_q: "queue.Queue[str]",
    stop_event: threading.Event,
    recognizer: FasterWhisperRecognizer,
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
                output_q.put_nowait(text)

    thread = threading.Thread(target=_loop, name="STT", daemon=True)
    thread.start()
    return thread


if __name__ == "__main__":
    rec = FasterWhisperRecognizer()
    print("recognizer loaded OK")
