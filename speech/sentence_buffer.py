class SentenceBuffer:
    """Accumulates LLM tokens and yields complete sentences."""

    def __init__(self):
        self._buffer = ""

    def add(self, token: str):
        self._buffer += token
        if self._buffer.endswith((".", "!", "?")):
            sentence = self._buffer.strip()
            self._buffer = ""
            return sentence
        return None

    def flush(self):
        sentence = self._buffer.strip()
        self._buffer = ""
        return sentence or None