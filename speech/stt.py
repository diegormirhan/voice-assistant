import wave, io, httpx

class WhisperSTT:
    """Client for the whisper-server transcription endpoint"""

    def __init__(self, url: str = "http://127.0.0.1:9991"):
        self._url = url
        self._client = httpx.AsyncClient()

    async def transcribe(self, pcm: bytes) -> str:
        """Sends a PCM speech segment to whisper-server and returns the text."""
        wav = io.BytesIO()
        with wave.open(wav, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(16000)
            w.writeframes(pcm)
        wav.seek(0)

        files = {"file": ("segment.wav", wav, "audio/wav")}
        data = {"response_format": "json", "temperature": "0.0"}
        resp = await self._client.post(f"{self._url}/inference", files=files, data=data)
        resp.raise_for_status()
        return resp.json().get("text", "").strip()

    async def close(self):
        await self._client.aclose()

