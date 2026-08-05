import asyncio
import queue
import threading
from typing import Optional

import numpy as np
from ollama import AsyncClient


DEFAULT_MODEL = "minicpm-v4.5:latest"
DEFAULT_HOST = "http://localhost:11434"
KEEP_ALIVE = "876000h"  # ~100 anos: modelo fica residente na VRAM até fechar o app
SYSTEM_PROMPT = (
    "Você é uma assistente de voz pessoal, concisa e direta. "
    "Responda SEMPRE à pergunta falada do usuário em no máximo 2 frases, em português brasileiro. "
    "Uma captura de tela do desktop pode estar anexada como contexto, mas IGNORE-A "
    "completamente a menos que o usuário pergunte explicitamente sobre o que está na tela. "
    "NUNCA descreva a tela espontaneamente. "
    "NUNCA use emojis, emoticons, kaomojis ou caracteres especiais Unicode. "
    "Responda APENAS com texto puro."
)
HISTORY_WINDOW = 5


class OllamaClient:
    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        host: str = DEFAULT_HOST,
        keep_alive: str = KEEP_ALIVE,
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
        # Imagem é passada APENAS no turno atual; o histórico guarda só texto
        # (reenviar imagens antigas estoura o contexto rápido).
        user_msg: dict = {"role": "user", "content": user_text}
        if image_b64 is not None:
            user_msg["images"] = [self._resize_image(image_b64)]
        chat_messages = self._messages + [user_msg]
        self._messages.append({"role": "user", "content": user_text})
        self._trim_history()

        stream = await self._client.chat(
            model=self._model,
            messages=chat_messages,
            stream=True,
            keep_alive=self._keep_alive,

            options={"num_predict": 200, "num_ctx": 16384},
        )
        full = ""
        async for chunk in stream:
            msg = getattr(chunk, "message", None)
            delta = getattr(msg, "content", "") or ""
            if delta:
                full += delta
                yield delta
        if full:
            self._messages.append({"role": "assistant", "content": full})

    @staticmethod
    def _resize_image(image_b64: str) -> str:
        # Screenshot do desktop em resolução cheia estoura o contexto do LLM
        # (~10k tokens). Redimensiona p/ 768px na maior aresta antes de enviar.
        from io import BytesIO

        from PIL import Image

        img = Image.open(BytesIO(__import__("base64").b64decode(image_b64)))
        img.thumbnail((768, 768))
        buf = BytesIO()
        img.save(buf, format="JPEG", quality=80)
        return __import__("base64").b64encode(buf.getvalue()).decode("ascii")


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
