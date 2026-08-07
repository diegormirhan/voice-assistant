"""Orchestrates the full voice loop: VAD -> STT -> LLM -> TTS, with barge-in."""

import asyncio
from pathlib import Path

from audio.capture import AudioCapture
from audio.playback import AudioPlayback
from audio.vad import SpeechSegmenter
from speech.llm import LlamaClient
from speech.sentence_buffer import SentenceBuffer
from speech.stt import WhisperSTT
from speech.tts import PiperTTS
from vision.screenshot import Screenshot


class Orchestrator:
    def __init__(self, model_path: Path):
        self._tts = PiperTTS(model_path)
        self._playback = AudioPlayback(self._tts.sample_rate)
        self._stt = WhisperSTT()
        self._llm = LlamaClient()
        self._shot = Screenshot()
        self._buffer = SentenceBuffer()
        self._llm_task: asyncio.Task | None = None
        self._loop: asyncio.AbstractEventLoop | None = None

        # VAD callbacks run on the audio thread (sync); we forward them to
        # the event loop so the async pipeline below can await them.
        self._segmenter = SpeechSegmenter(
            on_segment=self._on_segment,
            on_speech_start=self._on_speech_start,
        )
        self._capture = AudioCapture(on_audio=self._segmenter.add)

    # -- public ---------------------------------------------------------

    def start(self):
        """Starts mic + playback. Call inside a running event loop."""
        self._loop = asyncio.get_event_loop()
        self._playback.start()
        self._capture.start()

    def stop(self):
        self._capture.stop()
        self._playback.stop()
        if self._llm_task and not self._llm_task.done():
            self._llm_task.cancel()

    async def run(self):
        """Keeps the loop alive until KeyboardInterrupt."""
        self.start()
        try:
            await asyncio.Event().wait()
        except (KeyboardInterrupt, asyncio.CancelledError):
            pass
        finally:
            self.stop()

    # -- callbacks from the audio thread (sync) --------------------------

    def _on_speech_start(self):
        self._schedule(self._barge_in())

    def _on_segment(self, segment):
        self._schedule(self._handle_segment(segment))

    def _schedule(self, coro):
        # Forwards a coroutine from the audio thread to the event loop.
        if self._loop is not None:
            asyncio.run_coroutine_threadsafe(coro, self._loop)

    # -- async pipeline ---------------------------------------------------

    async def _barge_in(self):
        # User started speaking: cut playback and cancel the LLM task.
        self._playback.interrupt()
        if self._llm_task and not self._llm_task.done():
            self._llm_task.cancel()
            self._llm_task = None
        self._buffer.flush()  # drop any partial sentence

    async def _handle_segment(self, segment):
        text = await self._stt.transcribe(segment.tobytes())
        if not text:
            return
        print(f"[stt] {text}")

        self._playback.clear_interrupt()
        image = self._shot.capture()
        self._llm_task = asyncio.create_task(self._respond(text, image))

    async def _respond(self, prompt: str, image_b64: str):
        try:
            async for token in self._llm.stream(prompt, image_b64):
                if self._playback.interrupted:
                    break
                self._speak(self._buffer.add(token))

            self._speak(self._buffer.flush())
        except asyncio.CancelledError:
            pass  # barge-in cancelled this response

    def _speak(self, sentence):
        # Synthesizes + enqueues a sentence; None means nothing to say.
        if sentence:
            print(f"[tts] {sentence}")
            self._playback.speak(self._tts.synthesize(sentence))
