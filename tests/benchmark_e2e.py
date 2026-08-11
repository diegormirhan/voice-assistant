"""Measures end-to-end latency: from the user finishing speech to the
assistant's first spoken syllable.

Flow:
  VAD closes segment -> t_end_speech
    -> STT transcribe
    -> LLM first token
    -> first TTS sentence -> t_first_audio

E2E = t_first_audio - t_end_speech   (target < 2s)

Usage: whisper-server + llama-server running, then:
  python -m tests.benchmark_e2e
  FALE ALGO e espere a resposta.
"""

import asyncio
import time
from pathlib import Path

from audio.capture import AudioCapture
from audio.playback import AudioPlayback
from audio.vad import SpeechSegmenter
from speech.llm import LlamaClient
from speech.sentence_buffer import SentenceBuffer
from speech.stt import WhisperSTT
from speech.tts import PiperTTS
from vision.screenshot import Screenshot

MODEL = Path("models/piper/pt_BR-faber-medium.onnx")


class E2E:
    def __init__(self):
        self._tts = PiperTTS(MODEL)
        self._playback = AudioPlayback(self._tts.sample_rate)
        self._stt = WhisperSTT()
        self._llm = LlamaClient()
        self._shot = Screenshot()
        self._buffer = SentenceBuffer()

        # Timing stages.
        self._t_end_speech: float | None = None
        self._t_stt: float | None = None
        self._t_first_token: float | None = None
        self._t_first_audio: float | None = None
        self._loop = asyncio.new_event_loop()
        self._thread = None
        self._respond_task: asyncio.Task | None = None

        self._segmenter = SpeechSegmenter(
            on_segment=self._on_segment,
            on_speech_start=self._on_speech_start,
        )
        self._capture = AudioCapture(on_audio=self._segmenter.add)

    # -- thread bridge ---------------------------------------------------

    def _schedule(self, coro):
        asyncio.run_coroutine_threadsafe(coro, self._loop)

    def _on_speech_start(self):
        # Barge-in: cut playback AND cancel the ongoing response.
        self._schedule(self._barge_in())

    async def _barge_in(self):
        self._playback.interrupt()
        if self._respond_task and not self._respond_task.done():
            self._respond_task.cancel()
            self._respond_task = None
        self._buffer.flush()  # drop partial sentence

    def _on_segment(self, segment):
        self._t_end_speech = time.perf_counter()
        print(f"[E2E] fala terminou em t={self._t_end_speech - self._t0:.2f}s")
        self._schedule(self._handle_segment(segment))

    # -- pipeline ---------------------------------------------------------

    async def _handle_segment(self, segment):
        t = time.perf_counter()
        text = await self._stt.transcribe(segment.tobytes())
        self._t_stt = time.perf_counter()
        print(f"[STT] {text!r} (+{(self._t_stt - t)*1000:.0f}ms)")

        if not text:
            return

        self._playback.clear_interrupt()
        image = self._shot.capture()
        self._respond_task = asyncio.create_task(self._respond(text, image))

    async def _respond(self, prompt: str, image_b64: str):
        try:
            t = time.perf_counter()
            async for token in self._llm.stream(prompt, image_b64):
                if self._t_first_token is None:
                    self._t_first_token = time.perf_counter()
                    print(f"[LLM] primeiro token (+{(self._t_first_token - t)*1000:.0f}ms)")
                sentence = self._buffer.add(token)
                if sentence:
                    self._speak(sentence)  # fala todas as frases (experiência real)
            self._speak(self._buffer.flush())  # frase final sem pontuação
        except asyncio.CancelledError:
            print("[E2E] resposta cancelada (barge-in)")

    def _speak(self, sentence):
        if not sentence:
            return
        self._playback.speak(self._tts.synthesize(sentence))
        # Registra o E2E (primeira sílaba) apenas na primeira frase.
        if self._t_first_audio is None:
            self._t_first_audio = time.perf_counter()
            assert self._t_end_speech is not None
            assert self._t_stt is not None
            print(f"[E2E] primeira silaba: {self._t_first_audio - self._t_end_speech:.2f}s "
                  f"(STT {self._t_stt - self._t_end_speech:.2f}s, "
                  f"LLM + 1a frase {self._t_first_audio - self._t_stt:.2f}s)")
        print(f"[TTS] {sentence}")

    # -- main --------------------------------------------------------------

    async def _loop_run(self):
        while True:
            await asyncio.sleep(3600)

    def run(self):
        self._t0 = time.perf_counter()
        self._loop_thread = __import__("threading").Thread(
            target=lambda: self._loop.run_until_complete(self._loop_run()),
            daemon=True,
        )
        self._loop_thread.start()

        self._playback.start()
        self._capture.start()

        print("FALE ALGO e espere a resposta. Ctrl+C para sair.")
        try:
            while True:
                time.sleep(0.2)
        except KeyboardInterrupt:
            pass
        finally:
            self._capture.stop()
            self._playback.stop()


if __name__ == "__main__":
    E2E().run()
