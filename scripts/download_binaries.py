"""Downloads the compiled Vulkan binaries from HuggingFace if missing.

Repo: https://huggingface.co/diegomirhan/voice-assistant-binaries
Repo must be public or have a token set in HF_TOKEN.
"""

import sys
from pathlib import Path

try: # imported as a package (python main.py)
    from .downloads import batch
except ImportError: # run directly (python scripts/download_binaries.py)
    from downloads import batch


def _bin_dir() -> Path:
    # Persistent, writable: beside the app binary (frozen) or the project
    # root (development). Downloads write here so they survive restarts.
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent / "bin"
    return Path(__file__).resolve().parent.parent / "bin"


BIN = _bin_dir()

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


_BASE = "https://huggingface.co/diegomirhan/voice-assistant-binaries/resolve/main"

def _targets() -> list[tuple[Path, str]]:
    return [(BIN / dest, f"{_BASE}/{dest}") for dest in FILES]

def download_all(progress = None) -> None:
    """progress: optional callable(done_bytes: int, total_bytes: int)."""
    batch(_targets(), progress)

def main() -> None:
    download_all(
        progress = lambda d, t: print(
            f"\r  {d/1e6:.1f}/{t/1e6:.0f} MB", end="", flush=True
        ) if t else None
    )
    print()

if __name__ == "__main__":
    main()
