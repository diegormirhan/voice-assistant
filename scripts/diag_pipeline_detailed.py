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
    c = OllamaClient()
    p.set_llm_client(c)

    print("[1] preload...")
    await c.preload()
    print("[2] quente")

    async def run_pipeline():
        print("[3] pipeline.run() starting")
        await p.run()
        print("[4] pipeline.run() exited")

    task = asyncio.create_task(run_pipeline())
    print("[5] task criada")
    await asyncio.sleep(1)
    print(f"[6] task done: {task.done()}")

    tq.put("O que e 2+2? Responda em 1 frase.")
    print("[7] item na fila")
    t0 = time.perf_counter()
    while time.perf_counter() - t0 < 25:
        try:
            s = lq.get(timeout=0.5)
            print(f"[TTS] {s!r}")
        except queue.Empty:
            pass

    print("[8] fim")
    p.shutdown()
    task.cancel()
    await asyncio.gather(task, return_exceptions=True)


asyncio.run(main())
