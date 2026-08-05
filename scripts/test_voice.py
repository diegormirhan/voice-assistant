import queue
import sys
import time
from pathlib import Path

import numpy as np
import sounddevice as sd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.stt.recognizer import SherpaRecognizer

SAMPLE_RATE = 16000
BLOCKSIZE = 512


def main() -> None:
    print("Vai falar por 5 segundos. Fale em portugues: 'Qual e a previsao do tempo hoje?'")
    print("Comecando em 3 segundos...")
    time.sleep(3)

    frames: list[np.ndarray] = []

    def callback(indata, frames_, time_info, status):
        frames.append(indata[:, 0].copy())

    stream = sd.InputStream(
        samplerate=SAMPLE_RATE,
        blocksize=BLOCKSIZE,
        channels=1,
        dtype="int16",
        callback=callback,
    )
    stream.start()
    time.sleep(15.0)
    stream.stop()
    stream.close()

    audio = np.concatenate(frames)
    print(f"gravado: {len(audio)/SAMPLE_RATE:.1f}s")

    recognizer = SherpaRecognizer()
    t0 = time.perf_counter()
    text = recognizer.transcribe(audio)
    latency = time.perf_counter() - t0

    print(f"transcricao: {text!r}")
    print(f"latencia STT: {latency*1000:.0f}ms")


if __name__ == "__main__":
    main()
