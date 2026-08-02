import asyncio
import base64
import queue
import re
import threading
from typing import Optional

import numpy as np

from src.core.test_state import AssistantState, StateManager


SENTENCE_END = re.compile(r"([.!?]\s+|\n+)")


def sentence_split(buffer: str) -> tuple[list[str], str]:
    parts = SENTENCE_END.split(buffer)
    sentences: list[str] = []
    current = ""
    for part in parts:
        if part is None:
            continue
        current += part
        if re.fullmatch(r"[.!?]\s+|\n+", part):
            s = current.strip()
            if s:
                sentences.append(s)
            current = ""
    return sentences, current


class Pipeline:
    def __init__(
        self,
        transcript_q: "queue.Queue[str]",
        llm_stream_q: "queue.Queue[str]",
        interrupt_event: threading.Event,
        state: StateManager,
        get_screenshot=None,
    ) -> None:
        self._transcript_q = transcript_q
        self._llm_stream_q = llm_stream_q
        self._interrupt_event = interrupt_event
        self._state = state
        self._get_screenshot = get_screenshot
        self._stop_event = asyncio.Event()
        self._llm_task: Optional[asyncio.Task] = None
        self._llm_client = None

    def set_llm_client(self, client) -> None:
        self._llm_client = client

    async def _consume_transcripts(self):
        while not self._stop_event.is_set():
            try:
                text = await asyncio.to_thread(self._transcript_q.get, True, 0.1)
            except queue.Empty:
                continue

            if self._interrupt_event.is_set():
                self._interrupt_event.clear()

            self._state.transition(AssistantState.THINKING)

            screenshot = None
            if self._get_screenshot is not None:
                try:
                    screenshot = self._get_screenshot()
                except Exception:
                    screenshot = None
            image_b64 = None
            if screenshot is not None:
                image_b64 = base64.b64encode(screenshot).decode("ascii")

            self._llm_task = asyncio.create_task(
                self._run_llm_turn(text, image_b64)
            )
            try:
                await self._llm_task
            except asyncio.CancelledError:
                pass
            self._state.transition(AssistantState.LISTENING)

    async def _run_llm_turn(self, text: str, image_b64: Optional[str]):
        if self._llm_client is None:
            return
        self._state.transition(AssistantState.SPEAKING)
        buffer = ""
        try:
            async for delta in self._llm_client.stream_chat(text, image_b64):
                if self._interrupt_event.is_set():
                    self._llm_client.reset_history()
                    raise asyncio.CancelledError()
                buffer += delta
                sentences, buffer = sentence_split(buffer)
                for s in sentences:
                    try:
                        self._llm_stream_q.put_nowait(s)
                    except queue.Full:
                        pass
            if buffer.strip():
                self._llm_stream_q.put_nowait(buffer.strip())
        except asyncio.CancelledError:
            raise

    async def run(self):
        await self._consume_transcripts()

    def shutdown(self):
        self._stop_event.set()
        if self._llm_task is not None and not self._llm_task.done():
            self._llm_task.cancel()


if __name__ == "__main__":
    sm = StateManager()
    sm.on_change(lambda o, n: print(f"  state: {o.value} -> {n.value}"))

    s = "Ola! Como vai? Eu estou bem, e voce? Tudo certo."
    sentences, leftover = sentence_split(s)
    print(f"sentences: {sentences}")
    print(f"leftover: {leftover!r}")
