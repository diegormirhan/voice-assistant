import base64
import io

import mss
from PIL import Image

class Screenshot:
    """Captures the desktop and returns a base64 JPEG for the LLM."""

    MAX_WIDTH = 768

    def __init__(self):
        self._sct = mss.MSS()

    def capture(self) -> str:
        sct_img = self._sct.grab(self._sct.monitors[1])
        img = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")
        img.thumbnail((self.MAX_WIDTH, self.MAX_WIDTH))

        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=85)
        return base64.b64encode(buf.getvalue()).decode()