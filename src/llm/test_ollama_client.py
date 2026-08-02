import asyncio
import queue
import threading
from typing import Optional

import numpy as np
from ollama import AsyncClient


DEFAULT_MODEL = "qwen3.5:9b"
DEFAULT_HOST = "http://localhost:11434"
SYSTEM_PROMPT = (
    "Voce e uma assistente de voz concisa que ve o desktop do usuario. "
    "Responda em no maximo 2 frases, em portugues brasileiro."
)
HISTORY_WINDOW = 5


class OllamaClient:
    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        host: str = DEFAULT_HOST,
        keep_alive: str = "-1",
    ) -> None:
        self._model = model
        self._host = host
        self._keep_alive = keep_alive
        self._client = AsyncClient(host=host)
        self._messages: list[dict] = [
            {"role": "system", "content": SYSTEM_PROMPT}
        ]

    def reset_history(self) -> None:
        self._messages = [self._messages[0]]

    def _trim_history(self) -> None:
        if len(self._messages) > 1 + HISTORY_WINDOW * 2:
            self._messages = [self._messages[0]] + self._messages[-(HISTORY_WINDOW * 2):]

    async def preload(self) -> None:
        await self._client.chat(
            model=self._model,
            messages=[{"role": "user", "content": "ping"}],
            keep_alive=self._keep_alive,
            stream=False,
        )

    async def stream_chat(
        self,
        user_text: str,
        image_b64: Optional[str] = None,
    ):
        user_msg: dict = {"role": "user", "content": user_text}
        if image_b64 is not None:
            user_msg["images"] = [image_b64]
        self._messages.append(user_msg)
        self._trim_history()

        stream = await self._client.chat(
            model=self._model,
            messages=self._messages,
            stream=True,
            keep_alive=self._keep_alive,
        )
        full = ""
        async for chunk in stream:
            delta = chunk.get("message", {}).get("content", "")
            if delta:
                full += delta
                yield delta
        if full:
            self._messages.append({"role": "assistant", "content": full})


if __name__ == "__main__":
    async def _test():
        client = OllamaClient()
        print(f"client ready: model={client._model}, host={client._host}")
        try:
            await client.preload()
            print("preload OK")
        except Exception as e:
            print(f"preload skipped: {e}")

    asyncio.run(_test())
