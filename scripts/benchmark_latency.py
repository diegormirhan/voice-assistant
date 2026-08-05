import sys, time, wave, torch
from pathlib import Path
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

TEST_WAV = Path(__file__).resolve().parent.parent / "models" / "sherpa" / "sherpa-onnx-whisper-base" / "test_wavs" / "0.wav"


def _percentile(data: list[float], p: float) -> float:
    if not data:
        return 0.0
    return float(np.percentile(data, p))


def _report(name: str, samples: list[float]) -> None:
    if not samples:
        print(f"{name}: no samples")
        return
    print(
        f"{name}: p50={_percentile(samples, 50)*1000:.0f}ms "
        f"p95={_percentile(samples, 95)*1000:.0f}ms "
        f"p99={_percentile(samples, 99)*1000:.0f}ms "
        f"n={len(samples)}"
    )


def bench_vad(model) -> None:
    import torch

    frames = [torch.randn(512, dtype=torch.float32) for _ in range(30)]
    samples = []
    for _ in range(20):
        t0 = time.perf_counter()
        for f in frames:
            model(f, 16000)
        samples.append(time.perf_counter() - t0)
    _report("VAD (30 chunks)", samples)


def _load_wav(path: Path) -> np.ndarray:
    with wave.open(str(path), "rb") as w:
        assert w.getframerate() == 16000, f"expected 16kHz, got {w.getframerate()}"
        raw = w.readframes(w.getnframes())
    return np.frombuffer(raw, dtype=np.int16)


def bench_stt(recognizer, audio: np.ndarray) -> None:
    samples = []
    for _ in range(10):
        t0 = time.perf_counter()
        recognizer.transcribe(audio)
        samples.append(time.perf_counter() - t0)
    _report(f"STT ({len(audio)/16000:.1f}s audio)", samples)


def bench_tts(engine) -> None:
    samples = []
    for _ in range(5):
        t0 = time.perf_counter()
        for _ in engine.synthesize_stream("Ola, isso e um teste de latencia."):
            pass
        samples.append(time.perf_counter() - t0)
    _report("TTS (1 frase)", samples)


if __name__ == "__main__":
    from src.audio.capture import AudioCapture
    from src.stt.recognizer import SherpaRecognizer

    try:
        vad = AudioCapture.__new__(AudioCapture)
        vad._model = None
        from silero_vad import load_silero_vad

        vad._model = load_silero_vad(onnx=True)
        bench_vad(vad._model)
    except Exception as e:
        print(f"VAD: {e}")

    try:
        audio = _load_wav(TEST_WAV)
        stt = SherpaRecognizer()
        bench_stt(stt, audio)
    except Exception as e:
        print(f"STT: {e}")
