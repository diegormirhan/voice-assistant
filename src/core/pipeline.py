import asyncio
import base64
import queue
import re
import threading
import logging
from typing import Callable, Optional

from src.core.state import AssistantState, StateManager

# Configura o logger do módulo
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s | %(message)s",
)
log = logging.getLogger(__name__)

SENTENCE_RE = re.compile(r"([.!?]\s+|\n+)")


def sentence_split(buffer: str) -> tuple[list[str], str]:
    """Divide o buffer de tokens do LLM em sentenças completas.
    Retorna a lista de sentenças e o restante que ainda não formou frase.
    """
    parts = SENTENCE_RE.split(buffer)
    sentences: list[str] = []
    current = ""
    for part in parts:
        current += part
        # Fecha a sentença se terminar com pontuação ou contiver quebra de linha
        if (part.strip() and part.strip()[-1] in ".!?\n") or ("\n" in part):
            if current.strip():
                sentences.append(current.strip())
                current = ""
    return sentences, current


class Pipeline:
    def __init__(
        self,
        transcript_q: "queue.Queue[str]",
        llm_stream_q: "queue.Queue[str]",
        interrupt_event: threading.Event,
        state: StateManager,
        stop_event: threading.Event,
        get_screenshot: Optional[Callable[[], bytes]] = None,
    ) -> None:
        self._transcript_q = transcript_q
        self._llm_stream_q = llm_stream_q
        self._interrupt_event = interrupt_event
        self._state = state
        self._get_screenshot = get_screenshot
        self._llm_client = None
        self._stop_event = stop_event
        self._llm_task: Optional[asyncio.Task] = None

    def set_llm_client(self, client) -> None:
        self._llm_client = client

    async def _consume_transcripts(self) -> None:
        log.info("[pipeline] _consume_transcripts iniciado")
        while not self._stop_event.is_set():
            try:
                text = await asyncio.to_thread(self._transcript_q.get, True, 0.1)
            except queue.Empty:
                continue
            log.debug(f"[pipeline] transcript: {text!r}")
            print(f"  [você] {text}")

            if self._interrupt_event.is_set():
                self._interrupt_event.clear()

            self._state.transition(AssistantState.THINKING)

            image_b64 = None
            if self._get_screenshot is not None:
                try:
                    image_b64 = base64.b64encode(self._get_screenshot()).decode("ascii")
                except Exception as e:
                    log.warning(f"Screenshot failed: {e}")
                    image_b64 = None

            self._llm_task = asyncio.create_task(self._run_llm_turn(text, image_b64))
            try:
                await self._llm_task
            except asyncio.CancelledError:
                pass

    async def _run_llm_turn(self, text: str, image_b64: Optional[str]) -> None:
        if self._llm_client is None:
            return
        self._state.transition(AssistantState.SPEAKING)
        log.info(f"[pipeline] chamando LLM com: {text!r}")
        buffer = ""
        token_count = 0
        try:
            async for delta in self._llm_client.stream_chat(text, image_b64):
                if self._interrupt_event.is_set():
                    if hasattr(self._llm_client, "reset_history"):
                        self._llm_client.reset_history()
                    raise asyncio.CancelledError()
                buffer += delta
                token_count += 1
                sentences, buffer = sentence_split(buffer)
                for s in sentences:
                    print(f"  [assistente] {s}")
                    try:
                        self._llm_stream_q.put_nowait(s)
                    except queue.Full:
                        pass
            if buffer.strip():
                print(f"  [assistente] {buffer.strip()}")
                self._llm_stream_q.put_nowait(buffer.strip())
            log.info(f"[pipeline] LLM respondeu com {token_count} tokens")
        except asyncio.TimeoutError:
            log.error("LLM stream timeout – turno cancelado")
            if hasattr(self._llm_client, "reset_history"):
                self._llm_client.reset_history()
        except asyncio.CancelledError:
            raise
        except Exception as e:
            log.exception(f"[pipeline] llm error: {e}")
            if hasattr(self._llm_client, "reset_history"):
                self._llm_client.reset_history()
        finally:
            self._state.transition(AssistantState.LISTENING)

    async def run(self) -> None:
        await self._consume_transcripts()

    def shutdown(self) -> None:
        if self._llm_task is not None and not self._llm_task.done():
            self._llm_task.cancel()

if __name__ == "__main__":
    s = "Ola! Como vai? Eu estou bem, e voce? Tudo certo."
    sentences, leftover = sentence_split(s)
    print(f"sentences: {sentences}")
    print(f"leftover: {leftover!r}")
