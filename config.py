"""Centralized paths, ports and model profile selection."""

from pathlib import Path

from servers.models import MODELS, absolute, profile

ROOT = Path(__file__).resolve().parent
BIN = ROOT / "bin"

# Servers (llama.cpp / whisper.cpp).
WHISPER_BIN = BIN / "whisper-server"
LLAMA_BIN = BIN / "llama-server"
WHISPER_HOST = "127.0.0.1"
WHISPER_PORT = 9991
LLAMA_HOST = "127.0.0.1"
LLAMA_PORT = 9992

# TTS model (shared across profiles).
TTS_MODEL = MODELS / "piper/pt_BR-faber-medium.onnx"
WHISPER_MODEL = MODELS / "whisper/ggml-small.bin"

# Which LLM profile to use: "leve" or "padrao" (user choice, no VRAM scan).
MODEL_PROFILE = "padrao"


def llm_paths() -> tuple[Path, Path]:
    """Returns (llm, mmproj) absolute paths for the active profile."""
    p = profile(MODEL_PROFILE)
    return absolute(p.llm), absolute(p.mmproj)
