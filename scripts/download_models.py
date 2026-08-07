import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MODELS = ROOT / "models"

# (destino, url)
FILES = [
    # VAD Silero (ONNX)
    ("vad/silero_vad.onnx",
     "https://raw.githubusercontent.com/snakers4/silero-vad/master/src/silero_vad/data/silero_vad.onnx"),

    # STT Whisper (ggml, multilingue)
    ("whisper/ggml-small.bin",
     "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-small.bin"),

    # LLM Qwen3.5-9B (Q4_K_M, com visão)
    ("llm/Qwen3.5-9B-Q4_K_M.gguf",
     "https://huggingface.co/jc-builds/Qwen3.5-9B-VLM-Q4_K_M-GGUF/resolve/main/Qwen3.5-9B-Q4_K_M.gguf"),

    # mmproj (projetor de visão do LLM)
    ("llm/mmproj-F16.gguf",
     "https://huggingface.co/jc-builds/Qwen3.5-9B-VLM-Q4_K_M-GGUF/resolve/main/mmproj-F16.gguf"),

     # piper tts (modelo text-to-speech)
     ("piper/pt_BR-faber-medium.onnx",
      "https://huggingface.co/rhasspy/piper-voices/resolve/main/pt/pt_BR/faber/medium/pt_BR-faber-medium.onnx"),

    ("piper/pt_BR-faber-medium.onnx.json",
     "https://huggingface.co/rhasspy/piper-voices/resolve/main/pt/pt_BR/faber/medium/pt_BR-faber-medium.onnx.json"),

]


def download(dest: str, url: str) -> None:
    target = MODELS / dest
    if target.exists():
        print(f"[skip] {dest} ja existe")
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    print(f"[down] {dest}")

    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req) as resp:
        total = int(resp.headers.get("Content-Length", 0))
        downloaded = 0
        with open(target, "wb") as f:
            while chunk := resp.read(1 << 16):
                f.write(chunk)
                downloaded += len(chunk)
                if total:
                    pct = downloaded / total * 100
                    print(f"\r  {downloaded/1e6:.1f}/{total/1e6:.0f} MB ({pct:.0f}%)", end="", flush=True)
    print()


def main() -> None:
    for dest, url in FILES:
        download(dest, url)


if __name__ == "__main__":
    main()