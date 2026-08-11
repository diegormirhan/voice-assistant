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

DEFAULT_SETTINGS = {
    "min_speech_ms": 250,
    "hangover_ms": 1000,
    "length_scale": 1.3,
    "noise_scale": 0.6,
    "vision_enabled": True,
}


class Orchestrator:
    def __init__(self, model_path: Path, settings = None, on_mic_level = None, on_user_text = None,
                 on_state = None, on_assistant_text = None, on_output_level = None):
        self._settings = {**DEFAULT_SETTINGS, **(settings or {})}
        self._tts = PiperTTS(model_path, length_scale=self._settings["length_scale"], noise_scale=self._settings["noise_scale"])
        self._playback = AudioPlayback(self._tts.sample_rate, on_level=on_output_level)
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
            min_speech_ms=self._settings["min_speech_ms"],
            hangover_ms=self._settings["hangover_ms"],
        )
        self._on_state = on_state
        self._on_assistant_text = on_assistant_text
        self._on_mic_level = on_mic_level
        self._on_user_text = on_user_text
        self._capture = AudioCapture(
            on_audio = self._segmenter.add,
            on_level = self._on_mic_level,
        )

    def _emit_state(self, value: str) -> None:
        if self._on_state:
            self._on_state(value)

    async def apply_settings(self, settings) -> None:
        """Applies settings live, from the event loop (thread-safe)."""
        self._settings.update(settings)
        self._tts.set_style(self._settings["length_scale"], self._settings["noise_scale"])
        self._segmenter.apply(self._settings["min_speech_ms"], self._settings["hangover_ms"])

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
            self._llm_task = None

    async def aclose(self):
        """Realeases the STT/LLM HTTP clients. Await inside the event loop."""
        await self._stt.close()
        await self._llm.close()

    async def run(self):
        """Keeps the loop alive until KeyboardInterrupt."""
        self.start()
        try:
            await asyncio.Event().wait()
        except (KeyboardInterrupt, asyncio.CancelledError):
            pass
        finally:
            self.stop()
            await self.aclose()

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
        self._emit_state("listening")

    async def _handle_segment(self, segment):
        text = await self._stt.transcribe(segment.tobytes())
        if not text:
            return
        if self._on_user_text:
            self._on_user_text(text)

        self._playback.clear_interrupt()
        image = self._shot.capture() if self._settings["vision_enabled"] else ""
        self._emit_state("thinking")
        self._llm_task = asyncio.create_task(self._respond(text, image))

    async def _respond(self, prompt: str, image_b64: str):
        try:
            async for token in self._llm.stream(prompt, image_b64):
                if self._playback.interrupted:
                    break
                self._speak(self._buffer.add(token))

            self._speak(self._buffer.flush())
            await asyncio.to_thread(self._playback.wait_until_idle, 30.0)
            self._emit_state("listening")
        except asyncio.CancelledError:
            pass  # barge-in cancelled this response

    def _speak(self, sentence):
        # Synthesizes + enqueues a sentence; None means nothing to say.
        if sentence:
            if self._on_assistant_text:
                self._on_assistant_text(sentence)
            self._emit_state("speaking")
            self._playback.speak(self._tts.synthesize(sentence))
