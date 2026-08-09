"""Application bootstrap.

`app.py` used to hold the whole window (500 lines) plus the entry point; it is
now only the QApplication setup so the window can be imported and tested
without side effects.

Bugs fixed vs. the previous version:
  * `sys.exit(app.exec())` ran even when window construction raised, hiding
    the traceback behind an empty exit; failures are now reported.
  * the taskbar grouped the app under the generic "python.exe" icon on
    Windows because no AppUserModelID was set.
  * `QFont("Segoe UI", 10)` was applied without a fallback, so on a machine
    without Segoe UI every label fell back to an unstyled default.
"""

from __future__ import annotations

import ctypes
import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication

from .app_icon import app_icon
from .main_window import MainWindow

APP_ID = "voiceassistant.local.ui.1"


def _set_windows_app_id() -> None:
    if sys.platform != "win32":
        return
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_ID)
    except (OSError, AttributeError):
        pass


def create_app(argv: list[str] | None = None) -> QApplication:
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    app = QApplication(argv if argv is not None else sys.argv)
    app.setApplicationName("Assistente de Voz")
    app.setApplicationDisplayName("Assistente de Voz")
    app.setOrganizationName("Assistente de Voz")

    font = QFont()
    font.setFamilies(["Segoe UI Variable Text", "Segoe UI", "Inter", "sans-serif"])
    font.setPointSize(10)
    app.setFont(font)

    # Rounded multi-size icon: the raw square art looked like a hard tile in
    # the taskbar. (The old Path(ICON_ICO) check was also cwd-relative.)
    icon = app_icon()
    if not icon.isNull():
        app.setWindowIcon(icon)

    # Closing the last window must not quit while we live in the tray.
    app.setQuitOnLastWindowClosed(False)
    return app


def main() -> int:
    _set_windows_app_id()
    app = create_app()
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
