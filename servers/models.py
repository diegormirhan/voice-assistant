"""Model profiles and download lists.

The user picks a profile manually (leve or padrao). Only the LLM differs
between profiles; whisper and TTS are shared (COMMON). No VRAM detection.
"""

from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MODELS = ROOT / "models"


@dataclass(frozen=True)
class Profile:
    """The LLM files for one profile (llm + vision projector)."""

    name: str
    llm: str
    mmproj: str


def _hf(repo: str, filename: str) -> str:
    return f"https://huggingface.co/{repo}/resolve/main/{filename}"


LEVE = Profile(
    name="leve",
    llm="llm/Qwen3VL-4B-Instruct-Q4_K_M.gguf",
    mmproj="llm/mmproj-Qwen3VL-4B-Instruct-Q8_0.gguf",
)

PADRAO = Profile(
    name="padrao",
    llm="llm/Qwen3.5-9B-Q4_K_M.gguf",
    mmproj="llm/mmproj-F16.gguf",
)

PROFILES = {"leve": LEVE, "padrao": PADRAO}

# URL sources per profile (dest_path -> url).
SOURCES: dict[str, dict[str, str]] = {
    "leve": {
        LEVE.llm: _hf("Qwen/Qwen3-VL-4B-Instruct-GGUF", "Qwen3VL-4B-Instruct-Q4_K_M.gguf"),
        LEVE.mmproj: _hf("Qwen/Qwen3-VL-4B-Instruct-GGUF", "mmproj-Qwen3VL-4B-Instruct-Q8_0.gguf"),
    },
    "padrao": {
        PADRAO.llm: _hf("jc-builds/Qwen3.5-9B-VLM-Q4_K_M-GGUF", "Qwen3.5-9B-Q4_K_M.gguf"),
        PADRAO.mmproj: _hf("jc-builds/Qwen3.5-9B-VLM-Q4_K_M-GGUF", "mmproj-F16.gguf"),
    },
}

# Models always downloaded regardless of profile (VAD + whisper + TTS).
COMMON = [
    ("vad/silero_vad.onnx",
     "https://raw.githubusercontent.com/snakers4/silero-vad/master/src/silero_vad/data/silero_vad.onnx"),
    ("whisper/ggml-small.bin",
     _hf("ggerganov/whisper.cpp", "ggml-small.bin")),
    ("piper/pt_BR-faber-medium.onnx",
     _hf("rhasspy/piper-voices", "pt/pt_BR/faber/medium/pt_BR-faber-medium.onnx")),
    ("piper/pt_BR-faber-medium.onnx.json",
     _hf("rhasspy/piper-voices", "pt/pt_BR/faber/medium/pt_BR-faber-medium.onnx.json")),
]


def profile(name: str) -> Profile:
    """Returns the profile by name; raises KeyError for unknown names."""
    return PROFILES[name]


def all_downloads(name: str) -> list[tuple[str, str]]:
    """All files (dest, url) needed by the given profile, common ones included."""
    items = list(COMMON)
    for dest, url in SOURCES[name].items():
        items.append((dest, url))
    return items


def absolute(path: str) -> Path:
    """Converts a profile-relative model path to an absolute Path."""
    return MODELS / path
