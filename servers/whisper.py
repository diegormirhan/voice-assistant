import subprocess, time, urllib.request
from pathlib import Path

class WhisperServer:
    """manages the whisper-server process (start, wait, stop)"""
    def __init__(self, bin_dir: Path, model_path: Path, host: str = "127.0.0.1", port: int = 9991):
        self._exe = bin_dir / "whisper-server.exe"
        self._model = model_path
        self._host = host
        self._port = port
        self._proc = None

    def start(self):
        """Launches whisper-server and waits until it accepts requests."""
        self._proc = subprocess.Popen([str(self._exe), "-m", str(self._model), "--language", "pt", "--port", str(self._port)])
        self._wait_ready()

    def _wait_ready(self, timeout: float = 30.0):
        """Polls the endpoint until the server responds."""
        url = f"http://{self._host}:{self._port}"
        deadline =time.time() + timeout
        while time.time() < deadline:
            try:
                urllib.request.urlopen(f"{url}/", timeout=1)
                return
            except Exception:
                time.sleep(0.5)
        raise RuntimeError("whisper-server failed to start")

    def stop(self):
        if self._proc is not None:
            self._proc.terminate()
            self._proc.wait(timeout=5)
            self._proc = None

