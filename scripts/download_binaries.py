"""Downloads the compiled Vulkan binaries from HuggingFace if missing.

Repo: https://huggingface.co/diegomirhan/voice-assistant-binaries
Repo must be public or have a token set in HF_TOKEN.
"""

import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BIN = ROOT / "bin"

# Files relative to bin/, same layout as bin/.
FILES = [
    "whisper-server/whisper-server.exe",
    "whisper-server/whisper.dll",
    "whisper-server/ggml.dll",
    "whisper-server/ggml-base.dll",
    "whisper-server/ggml-cpu.dll",
    "whisper-server/ggml-vulkan.dll",
    "llama-server/llama-server.exe",
    "llama-server/llama-server-impl.dll",
    "llama-server/llama-common.dll",
    "llama-server/llama.dll",
    "llama-server/mtmd.dll",
    "llama-server/ggml.dll",
    "llama-server/ggml-base.dll",
    "llama-server/ggml-cpu.dll",
    "llama-server/ggml-vulkan.dll",
]


def _url(dest: str) -> str:
    return f"https://huggingface.co/diegomirhan/voice-assistant-binaries/resolve/main/{dest}"


def download(dest: str) -> None:
    target = BIN / dest
    if target.exists():
        print(f"[skip] {dest} ja existe")
        return

    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(target.suffix + ".part")
    print(f"[down] {dest}")

    req = urllib.request.Request(_url(dest), headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req) as resp:
        total = int(resp.headers.get("Content-Length", 0))
        downloaded = 0
        with open(tmp, "wb") as f:
            while chunk := resp.read(1 << 16):
                f.write(chunk)
                downloaded += len(chunk)
                if total:
                    pct = downloaded / total * 100
                    print(f"\r  {downloaded/1e6:.1f}/{total/1e6:.0f} MB ({pct:.0f}%)", end="", flush=True)
    print()

    tmp.replace(target)


def main() -> None:
    for dest in FILES:
        download(dest)


if __name__ == "__main__":
    main()
