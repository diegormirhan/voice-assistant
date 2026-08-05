import queue
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.audio.playback import PlaybackThread
from src.core.interruption import InterruptionManager, drain_queue
from src.tts.piper_engine import PiperEngine


def run_tts_thread(
    llm_q: "queue.Queue[str]",
    tts_q: "queue.Queue[object]",
    stop_event: threading.Event,
    interrupt_event: threading.Event,
    engine: PiperEngine,
) -> threading.Thread:
    def _loop():
        while not stop_event.is_set():
            try:
                sentence = llm_q.get(timeout=0.1)
            except queue.Empty:
                continue
            if interrupt_event.is_set():
                drain_queue(llm_q)
                continue
            try:
                for audio in engine.synthesize_stream(sentence, stop_event):
                    if interrupt_event.is_set():
                        drain_queue(tts_q)
                        break
                    tts_q.put(audio)
            except Exception as e:
                print(f"tts error: {e}")

    t = threading.Thread(target=_loop, name="TTS", daemon=True)
    t.start()
    return t


def main() -> None:
    llm_q: "queue.Queue[str]" = queue.Queue()
    tts_q: "queue.Queue[object]" = queue.Queue()

    stop = threading.Event()
    interrupt = threading.Event()

    mgr = InterruptionManager(interrupt)
    engine = PiperEngine()

    pb = PlaybackThread(tts_q, stop, sample_rate=engine.sample_rate, interrupt_event=interrupt)
    pb.start()
    tts_thread = run_tts_thread(llm_q, tts_q, stop, interrupt, engine)

    print("=== Day 4 E2E (TTS + Playback) ===")
    print("Enviando 2 frases direto pro TTS...\n")

    llm_q.put("Ola, tudo bem?")
    llm_q.put("Estou funcionando perfeitamente.")

    time.sleep(8)
    stop.set()
    print("\nfim")


if __name__ == "__main__":
    main()
