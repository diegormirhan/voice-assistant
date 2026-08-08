import json, httpx

# Instructions given to the model before every prompt.
# TTS cannot pronounce symbols, emojis or special characters.
SYSTEM_PROMPT = (
    "Você é um assistente de voz pessoal que pode ver a tela do usuário quando uma imagem é enviada. "
    "A imagem é contexto auxiliar, NÃO o assunto da conversa: "
    "só descreva ou comente a tela se o usuário perguntar explicitamente sobre ela. "
    "Responda de forma proporcional ao que o usuário fala: "
    "cumprimentos e frases curtas merecem resposta curta (uma ou duas palavras). "
    "Responda apenas com texto falável: sem emojis, símbolos, marcadores, markdown, "
    "cifrões, abreviações ou asteriscos. Números por extenso. "
    "Frases curtas e naturais."
)

MAX_HISTORY = 5


class LlamaClient:
    """Streaming client for the llama-server (OpenAI-compatible API)."""

    def __init__(self, url: str = "http://127.0.0.1:9992", model: str = "qwen"):
        self._url = url
        self._model = model
        self._client = httpx.AsyncClient(timeout=None)
        self._history = []

    async def stream(self, prompt: str, image_b64: str = ""):
        """Yields response tokens one by one (streaming)."""
        content = prompt
        if image_b64:
            content = [
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"},
                },
                {"type": "text", "text": prompt},
            ]

        payload = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                *self._history,
                {"role": "user", "content": content},
            ],
            "stream": True,
        }

        answer = ""
        try:
            async with self._client.stream(
                "POST", f"{self._url}/v1/chat/completions", json=payload
            ) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    line = line.strip()
                    if not line or not line.startswith("data:"):
                        continue
                    data = line[len("data:"):].strip()
                    if data == "[DONE]":
                        break
                    try:
                        obj = json.loads(data)
                    except json.JSONDecodeError:
                        continue

                    choice = (obj.get("choices") or [{}])[0]
                    delta = choice.get("delta") or choice.get("message") or {}
                    token = delta.get("content")
                    if token:
                        answer += token
                        yield token
        finally:
            # Save history even if the consumer aborts early (barge-in,
            # first-sentence-only benchmark) — otherwise the LLM forgets.
            self._history.append({"role": "user", "content": prompt})
            self._history.append({"role": "assistant", "content": answer})
            self._history = self._history[-2 * MAX_HISTORY:]

    async def close(self):
        # Releases the HTTP connection pool on shutdown.
        await self._client.aclose()
