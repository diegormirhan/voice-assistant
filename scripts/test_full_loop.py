import asyncio
import queue
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.audio.capture import AudioCapture, SAMPLE_RATE
from src.audio.playback import PlaybackThread
from src.core.interruption import InterruptionManager, drain_queue
from src.core.pipeline import Pipeline
from src.core.state import StateManager
from src.llm.ollama_client import OllamaClient
from src.stt.recognizer import FasterWhisperRecognizer, run_stt_thread
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
    vad_q: "queue.Queue[object]" = queue.Queue()
    transcript_q: "queue.Queue[str]" = queue.Queue()
    llm_q: "queue.Queue[str]" = queue.Queue()
    tts_q: "queue.Queue[object]" = queue.Queue()

    stop = threading.Event()
    interrupt = threading.Event()

    sm = StateManager()
    sm.on_change(lambda o, n: print(f"  [state] {o.value} -> {n.value}"))
    mgr = InterruptionManager(interrupt)

    # ---- Captura (mic + VAD + screenshot) ----
    capture = AudioCapture(vad_q, stop)
    capture.set_on_speech_start(lambda: print("  [capture] speech_start") or mgr.trigger_if_barge_in())
    capture.start()
    print("=== Day 4: loop completo. Fale algo! Ctrl+C para parar ===")

    # ---- STT ----
    recognizer = FasterWhisperRecognizer()
    run_stt_thread(vad_q, transcript_q, stop, recognizer)
    print("  [stt] thread iniciada")

    # ---- TTS + Playback ----
    engine = PiperEngine()
    run_tts_thread(llm_q, tts_q, stop, interrupt, engine)
    playback = PlaybackThread(tts_q, stop, sample_rate=engine.sample_rate, interrupt_event=interrupt)
    playback.start()
    print("  [tts/playback] iniciados")

    # evita o eco: mute no capture enquanto o assistente fala
    def _mute_while_playing():
        last = False
        while not stop.is_set():
            active = playback.is_active
            if active != last:
                capture.set_muted(active)
                last = active
            time.sleep(0.05)

    threading.Thread(target=_mute_while_playing, name="MuteSync", daemon=True).start()

    # sincroniza o estado "tocando?" do playback com o interruption manager
    def _sync_playback_state():
        mgr.set_playback_active(playback.is_active)

    def _monitor_playback():
        while not stop.is_set():
            _sync_playback_state()
            time.sleep(0.05)

    threading.Thread(target=_monitor_playback, name="PlaybackMonitor", daemon=True).start()

    # ---- Pipeline (LLM) ----
    pipeline = Pipeline(transcript_q, llm_q, interrupt, sm, stop, get_screenshot=capture.get_latest_screenshot)
    client = OllamaClient()
    pipeline.set_llm_client(client)
    asyncio.run(pipeline.run())

    stop.set()


if __name__ == "__main__":
    main()
