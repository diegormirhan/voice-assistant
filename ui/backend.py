"""Real backend: runs the servers + core/orchestrator.py on a dedicated
asyncio thread and bridges events to the UI Bus.

Same public API as Simulator so main_window only swaps the class:
start / stop / set_mic_muted / start_download.

Everything heavy (servers, model load) is lazy inside `start()` — the window
opens instantly and the LOADING state reflects real startup.
"""

from __future__ import annotations
import asyncio, threading
from pathlib import Path
from core.orchestrator import Orchestrator
from servers import launcher
from servers.models import MODELS, all_downloads
from . import config_store
from .state import AssistantState, Bus

class _CancelDownload(Exception):
    """Raised by the progress callback when the user turns the app off."""

class Backend:
    def __init__(self, bus: Bus, model_path: Path, parent=None):
        self._bus = bus
        self._model_path = model_path
        self._orchestrator: Orchestrator | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._download: threading.Thread | None = None
        self._muted = False

    # -- api (Simulator-compatible)

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._bus.state_changed.emit(AssistantState.LOADING)
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        if self._loop is not None:
            try:
                asyncio.run_coroutine_threadsafe(
                    self._shutdown(), self._loop
                ).result(timeout=3)
            except Exception:
                pass
        if self._thread is not None:
            self._thread.join(timeout=10)
        self._thread = None
        self._loop = None

    def set_mic_muted(self, muted: bool) -> None:
        self._muted = bool(muted)

    def start_download(self) -> None:
        if self._download is not None and self._download.is_alive():
            return
        self._bus.download_progress.emit(0)
        self._download = threading.Thread(
            target=self._download_binaries, daemon=True
        )
        self._download.start()

    # -- downloads

    def _download_binaries(self) -> None:
        try:
            from scripts.download_binaries import download_all
            download_all(self._report_progress)
            self._bus.download_finished.emit(True, "Binários Vulkan prontos.")
        except _CancelDownload:
            pass  # app turned off mid-download
        except Exception as exc:
            self._bus.download_finished.emit(False, str(exc))

    def _report_progress(self, done: int, total: int) -> None:
        if self._stop_event.is_set():
            raise _CancelDownload()
        pct = 100 if total <= 0 else int(done / total * 100)
        self._bus.download_progress.emit(max(0, min(100, pct)))


    # -- internals

    def _run_loop(self) -> None:
        asyncio.set_event_loop(self._loop)
        self._loop.run_until_complete(self._main())

    async def _main(self) -> None:
        whisper = llama = None
        try:
            await asyncio.to_thread(self._ensure_models)
            if self._stop_event.is_set():
                return
            whisper, llama = await asyncio.to_thread(self._start_servers)
            if self._stop_event.is_set():
                return
            self._orchestrator = await asyncio.to_thread(self._build_orchestrator)
            self._orchestrator.start()
            self._bus.state_changed.emit(AssistantState.LISTENING)
            while not self._stop_event.is_set():
                await asyncio.sleep(0.2)
        except _CancelDownload:
            pass
        except Exception as exc:
            self._bus.error.emit(str(exc))
        finally:
            if self._orchestrator is not None:
                self._orchestrator.stop()
                await self._orchestrator.aclose()
            if whisper is not None:
                whisper.stop()
            if llama is not None:
                llama.stop()
            self._bus.state_changed.emit(AssistantState.OFF)

    def _profile(self) -> str:
        return config_store.load().get("model_profile", "padrao")

    def _ensure_models(self) -> None:
        """Downloads missing models for the selected profile (cancellable)."""
        profile = self._profile()
        missing = [
            (dest, url)
            for dest, url in all_downloads(profile)
            if not (MODELS / dest).exists()
        ]
        if not missing:
            return
        from scripts.download_models import download_all
        download_all(profile, self._report_progress)
        self._bus.download_finished.emit(True, "Modelos do perfil prontos.")

    def _start_servers(self):
        return launcher.start_all(self._profile())

    def _build_orchestrator(self) -> Orchestrator:
        return Orchestrator(
            self._model_path,
            on_mic_level=lambda v: self._bus.mic_level.emit(0.0 if self._muted else v),
            on_user_text=self._bus.user_said.emit,
            )

    async def _shutdown(self) -> None:
        self._stop_event.set()