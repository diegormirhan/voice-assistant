import asyncio
import queue
import sys
import threading
import time

sys.path.insert(0, ".")
from src.core.pipeline import Pipeline
from src.core.state import StateManager
from src.llm.ollama_client import OllamaClient


async def main():
    tq, lq = queue.Queue(), queue.Queue()
    sm = StateManager()
    sm.on_change(lambda o, n: print(f"  [state] {o.value} -> {n.value}"))
    p = Pipeline(tq, lq, threading.Event(), sm)
    client = OllamaClient()
    p.set_llm_client(client)

    task = asyncio.create_task(p.run())
    await asyncio.sleep(0.3)

    # turno 1
    tq.put("O que e 2+2? Responda em 1 frase.")
    print(">>> turno 1 enviado")
    t0 = time.perf_counter()
    while time.perf_counter() - t0 < 20:
        try:
            s = lq.get(timeout=0.5)
            print(f"  [TTS] {s!r}")
        except queue.Empty:
            pass

    # turno 2 (sem falar, so pra ver se o pipeline volta a consumir)
    print("\n>>> turno 2 enviado")
    tq.put("E 3+3?")
    t0 = time.perf_counter()
    while time.perf_counter() - t0 < 20:
        try:
            s = lq.get(timeout=0.5)
            print(f"  [TTS] {s!r}")
        except queue.Empty:
            pass

    p.shutdown()
    task.cancel()


asyncio.run(main())
