"""Voice assistant desktop UI (PySide6).

Public surface used by the backend:
    from ui import Bus, AssistantState, main
"""

from .state import AssistantState, Bus

__all__ = ["AssistantState", "Bus", "main"]


def main() -> int:
    """Lazy import so `import ui` does not require a display."""
    from .app import main as _main

    return _main()
