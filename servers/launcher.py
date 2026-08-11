"""Starts/stops the native server processes (whisper-server, llama-server)."""

import config
from servers.llama import LlamaServer
from servers.whisper import WhisperServer

def start_all(profile_name: str | None = None):
    """Boots both servers for the profile and waits until they accept requests."""
    whisper = WhisperServer(config.WHISPER_BIN, config.WHISPER_MODEL,
                            config.WHISPER_HOST, config.WHISPER_PORT)
    llm, mmproj = config.llm_paths(profile_name)
    llama = LlamaServer(config.LLAMA_BIN, llm, mmproj,
                        config.LLAMA_HOST, config.LLAMA_PORT)
    whisper.start()
    print(f"[servers] whisper-server pronto em :{config.WHISPER_PORT}")
    llama.start()
    print(f"[servers] llama-server pronto em :{config.LLAMA_PORT}")
    return whisper, llama

def stop_all(whisper, llama):
    llama.stop()
    whisper.stop()