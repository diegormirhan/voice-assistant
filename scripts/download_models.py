import tarfile
import urllib.request
from pathlib import Path


MODELS_DIR = Path(__file__).resolve().parent.parent / "models"
SHERPA_DIR = MODELS_DIR / "sherpa"
PIPER_DIR = MODELS_DIR / "piper"

SHERPA_MODEL = "sherpa-onnx-whisper-small"
SHERPA_URL = f"https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/{SHERPA_MODEL}.tar.bz2"

PIPER_VOICE = "pt_BR-faber-medium"
PIPER_VOICE_URL = f"https://huggingface.co/rhasspy/piper-voices/resolve/main/pt/pt_BR/faber/medium/{PIPER_VOICE}.onnx"
PIPER_CONFIG_URL = f"https://huggingface.co/rhasspy/piper-voices/resolve/main/pt/pt_BR/faber/medium/{PIPER_VOICE}.onnx.json"

_HEADERS = {"User-Agent": "Mozilla/5.0"}


def _download(url: str, dest: Path) -> None:
    req = urllib.request.Request(url, headers=_HEADERS)
    with urllib.request.urlopen(req) as resp, open(dest, "wb") as f:
        while chunk := resp.read(1 << 16):
            f.write(chunk)


def download_sherpa() -> None:
    target = SHERPA_DIR / SHERPA_MODEL
    if target.exists():
        print(f"[models] {SHERPA_MODEL} ok")
        return
    SHERPA_DIR.mkdir(parents=True, exist_ok=True)
    archive = SHERPA_DIR / f"{SHERPA_MODEL}.tar.bz2"
    print(f"[models] downloading {SHERPA_MODEL} (~600MB)...")
    _download(SHERPA_URL, archive)
    with tarfile.open(archive, "r:bz2") as tar:
        tar.extractall(SHERPA_DIR)
    archive.unlink()
    print(f"[models] extracted -> {target}")


def download_piper() -> None:
    onnx = PIPER_DIR / f"{PIPER_VOICE}.onnx"
    config = PIPER_DIR / f"{PIPER_VOICE}.onnx.json"
    if onnx.exists() and config.exists():
        print(f"[models] {PIPER_VOICE} ok")
        return
    PIPER_DIR.mkdir(parents=True, exist_ok=True)
    print(f"[models] downloading {PIPER_VOICE}...")
    _download(PIPER_VOICE_URL, onnx)
    _download(PIPER_CONFIG_URL, config)
    print(f"[models] saved -> {PIPER_DIR}")


if __name__ == "__main__":
    download_sherpa()
    download_piper()
