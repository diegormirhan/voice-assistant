from dataclasses import dataclass
import os

@dataclass
class Config:
    """Configurações da assistente de voz.
    Valores podem ser sobrescritos por variáveis de ambiente.
    """
    # Modelo LLM (mantendo Qwen3.5 por padrão)
    llm_model: str = os.getenv("LLM_MODEL", "minicpm-v4.5:latest")
    # Modelos de STT e TTS
    stt_model: str = os.getenv("STT_MODEL", "sherpa")
    tts_engine: str = os.getenv("TTS_ENGINE", "piper")
    # Parâmetros de contexto e timeout
    max_context_tokens: int = 2048
    llm_timeout_sec: int = 20
    # Diretórios internos
    model_dir: str = "models"
    assets_dir: str = "assets"
