import asyncio
import queue
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.core.pipeline import Pipeline
from src.core.state import StateManager
from src.llm.ollama_client import OllamaClient


async def main() -> None:
    tq, lq = queue.Queue(), queue.Queue()
    sm = StateManager()
    sm.on_change(lambda old, new: print(f"  [state] {old.value} -> {new.value}"))
    p = Pipeline(tq, lq, threading.Event(), sm)
    client = OllamaClient()
    p.set_llm_client(client)

    # coloca o item ANTES de iniciar o pipeline
    tq.put("Explique em 3 frases, separadas por ponto, o que e machine learning.")

    print("preload (primeiro run ~15s)...")
    await client.preload()
    print("modelo quente\n")

    task = asyncio.create_task(p.run())
    t0 = time.perf_counter()

    while time.perf_counter() - t0 < 40:
        try:
            sentence = lq.get(timeout=0.5)
        except queue.Empty:
            continue
        print(f"[{time.perf_counter()-t0:6.2f}s] TTS recebeu: {sentence!r}")

    print("\nfim. shutdown...")
    p.shutdown()
    task.cancel()
    await asyncio.gather(task, return_exceptions=True)


if __name__ == "__main__":
    asyncio.run(main())
