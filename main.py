"""Entry point: starts the servers, runs the orchestrator, clean shutdown."""

import asyncio
from pathlib import Path

import config
from core.orchestrator import Orchestrator
from servers.llama import LlamaServer
from servers.whisper import WhisperServer


def start_servers():
    whisper = WhisperServer(config.WHISPER_BIN, config.WHISPER_MODEL,
                            config.WHISPER_HOST, config.WHISPER_PORT)
    llm, mmproj = config.llm_paths()
    llama = LlamaServer(config.LLAMA_BIN, llm, mmproj,
                        config.LLAMA_HOST, config.LLAMA_PORT)
    whisper.start()
    print(f"[main] whisper-server pronto em :{config.WHISPER_PORT}")
    llama.start()
    print(f"[main] llama-server pronto em :{config.LLAMA_PORT}")
    return whisper, llama


def stop_servers(whisper, llama):
    llama.stop()
    whisper.stop()


def main():
    whisper, llama = start_servers()
    try:
        orchestrator = Orchestrator(config.TTS_MODEL)
        asyncio.run(orchestrator.run())
    finally:
        stop_servers(whisper, llama)


if __name__ == "__main__":
    main()
