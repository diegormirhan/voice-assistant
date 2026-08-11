"""Design tokens: palettes (dark/light) + shared geometry/motion tokens.

Every visual value used by the UI lives here. Widgets never hardcode a
colour, radius or duration — they read it from `Palette` / `Tokens` so the
theme switch is a single, complete operation.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Tokens:
    """Geometry + motion constants shared by both themes."""

    # Windows 11 rounds frameless windows at ~8px. Matching it exactly avoids
    # the corner artefact where the DWM backdrop bleeds outside the card.
    window_radius: int = 8
    card_radius: int = 14
    control_radius: int = 11
    pill_radius: int = 13
    bubble_radius: int = 14

    pad_window: int = 18
    gap: int = 12

    ring_radius: int = 78
    ring_margin: int = 90

    fast_ms: int = 140
    base_ms: int = 200
    slow_ms: int = 320

    font_ui: str = "Segoe UI"
    font_display: str = "Segoe UI Semibold"
    font_mono: str = "Cascadia Mono, Consolas, monospace"


T = Tokens()


@dataclass(frozen=True)
class Palette:
    name: str

    # Surfaces
    window: str          # translucent window base (sits over the acrylic blur)
    surface: str         # controls / panels
    surface_hover: str
    surface_active: str
    elevated: str        # dialogs, popups

    # Lines
    border: str
    border_strong: str

    # Text
    text: str
    text_dim: str
    text_faint: str

    # Accent
    accent: str
    accent_hover: str
    accent_soft: str
    accent_gradient: tuple[str, str]
    on_accent: str

    # Status ring
    ring_off: str
    ring_loading: str
    ring_listening: str
    ring_thinking: str
    ring_speaking: str

    # Center button body
    orb_center: str
    orb_edge: str

    danger: str
    danger_soft: str

    # Win32 tint used by the legacy acrylic fallback (0xAABBGGRR).
    acrylic_tint: int

    @property
    def is_dark(self) -> bool:
        return self.name == "dark"


DARK = Palette(
    name="dark",
    window="rgba(0, 0, 0, 96)",
    surface="rgba(255, 255, 255, 12)",
    surface_hover="rgba(255, 255, 255, 22)",
    surface_active="rgba(255, 255, 255, 32)",
    elevated="rgba(19, 20, 28, 236)",
    border="rgba(255, 255, 255, 24)",
    border_strong="rgba(255, 255, 255, 46)",
    text="#f2f3f7",
    text_dim="#a6abbd",
    text_faint="#6e7488",
    accent="#8b7cf6",
    accent_hover="#a394ff",
    accent_soft="rgba(139, 124, 246, 46)",
    accent_gradient=("#8b7cf6", "#4f8cf7"),
    on_accent="#0b0c12",
    ring_off="#3a3d4d",
    ring_loading="#7c9cf8",
    ring_listening="#4ade9b",
    ring_thinking="#6ea8fe",
    ring_speaking="#a894ff",
    # QColor only parses hex / SVG names — a CSS "rgb(...)" string silently
    # produced an invalid (black) colour, which flattened the orb.
    orb_center="#181923",
    orb_edge="#0e0f16",
    danger="#f2555a",
    danger_soft="rgba(242, 85, 90, 40)",
    acrylic_tint=0x99000000,
)

LIGHT = Palette(
    name="light",
    window="rgba(247, 248, 252, 176)",
    surface="rgba(15, 23, 42, 8)",
    surface_hover="rgba(15, 23, 42, 15)",
    surface_active="rgba(15, 23, 42, 24)",
    elevated="rgba(252, 253, 255, 240)",
    border="rgba(15, 23, 42, 20)",
    border_strong="rgba(15, 23, 42, 40)",
    text="#111726",
    text_dim="#5a6377",
    text_faint="#8b93a6",
    accent="#6d5bd0",
    accent_hover="#5b49c0",
    accent_soft="rgba(109, 91, 208, 30)",
    accent_gradient=("#6d5bd0", "#3f7ad6"),
    on_accent="#ffffff",
    ring_off="#c9cfdd",
    ring_loading="#4f7ad6",
    ring_listening="#129e6a",
    ring_thinking="#2f6fd0",
    ring_speaking="#7a52c8",
    orb_center="#ffffff",
    orb_edge="#edf0f9",
    danger="#dc3b41",
    danger_soft="rgba(220, 59, 65, 34)",
    acrylic_tint=0xC0FCF9F7,
)

PALETTES: dict[str, Palette] = {"dark": DARK, "light": LIGHT}


def palette_for(name: str) -> Palette:
    """Safe lookup — an unknown/corrupt theme name falls back to dark."""
    return PALETTES.get(str(name).lower(), DARK)
