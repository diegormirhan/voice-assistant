import json, httpx

class LlamaClient:
    """Streaming client for the llama-server (OpenAI-compatible API)."""

    def __init__(self, url: str = "http://127.0.0.1:9992", model: str = "qwen"):
        self._url = url
        self._model = model
        self._client = httpx.AsyncClient(timeout=None)

    async def stream(self, prompt: str):
        """Yields response tokens one by one (streaming)."""
        payload = {
            "model": self._model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": True,
        }

        async with self._client.stream(
            "POST", f"{self._url}/v1/chat/completion", json=payload
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
                    yield token

    async def close(self):
        # Releases the HTTP connection pool on shutdown.
        await self._client.aclose()
