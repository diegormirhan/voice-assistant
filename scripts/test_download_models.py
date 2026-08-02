import sys
from pathlib import Path


SHERPA_DIR = Path(__file__).resolve().parent.parent / "models" / "sherpa"
SHERPA_DIR.mkdir(parents=True, exist_ok=True)

PIPER_DIR = Path(__file__).resolve().parent.parent / "models" / "piper"
PIPER_DIR.mkdir(parents=True, exist_ok=True)

SHERPA_MODEL = "sherpa-onnx-whisper-small.en-2024-08-20"
SHERPA_URL = f"https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/{SHERPA_MODEL}.tar.bz2"

PIPER_VOICE = "pt_BR-faber-medium"
PIPER_VOICE_URL = f"https://huggingface.co/rhasspy/piper-voices/resolve/main/pt/pt_BR/faber/medium/{PIPER_VOICE}.onnx"
PIPER_CONFIG_URL = f"https://huggingface.co/rhasspy/piper-voices/resolve/main/pt/pt_BR/faber/medium/{PIPER_VOICE}.onnx.json"


def _is_extracted(model_name: str, target_dir: Path) -> bool:
    marker = target_dir / ".extracted"
    expected = target_dir / model_name
    return marker.exists() and expected.exists()


def download_sherpa() -> None:
    if _is_extracted(SHERPA_MODEL, SHERPA_DIR):
        print(f"[download_models] {SHERPA_MODEL} already extracted")
        return
    print(f"[download_models] downloading {SHERPA_MODEL}...")
    import urllib.request
    import tarfile

    tar_path = SHERPA_DIR / f"{SHERPA_MODEL}.tar.bz2"
    urllib.request.urlretrieve(SHERPA_URL, tar_path)
    with tarfile.open(tar_path, "r:bz2") as tar:
        tar.extractall(SHERPA_DIR)
    tar_path.unlink()
    (SHERPA_DIR / ".extracted").touch()
    print(f"[download_models] sherpa model extracted to {SHERPA_DIR}")


def download_piper() -> None:
    onnx_path = PIPER_DIR / f"{PIPER_VOICE}.onnx"
    json_path = PIPER_DIR / f"{PIPER_VOICE}.onnx.json"
    if onnx_path.exists() and json_path.exists() and onnx_path.stat().st_size > 1_000_000:
        print(f"[download_models] piper voice {PIPER_VOICE} already downloaded")
        return
    print(f"[download_models] downloading piper voice {PIPER_VOICE}...")
    import urllib.request
    urllib.request.urlretrieve(PIPER_VOICE_URL, onnx_path)
    urllib.request.urlretrieve(PIPER_CONFIG_URL, json_path)
    print(f"[download_models] piper voice saved to {PIPER_DIR}")


def main() -> int:
    print("Silero VAD: ja vem dentro do pacote silero-vad (pip install silero-vad)")
    print()
    download_sherpa()
    download_piper()
    print("\n[download_models] done")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
