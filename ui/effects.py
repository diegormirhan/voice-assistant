"""Windows composition effects (acrylic glass, rounded corners, minimize).

Every call is a safe no-op off Windows or on older builds, so the same code
runs on any platform for design iteration.

Bugs fixed vs. the previous version:
  * `WS_CAPTION` was OR-ed into a frameless translucent window, which makes
    DWM paint a native frame/shadow strip over the glass card. Only
    MINIMIZEBOX/MAXIMIZEBOX are needed for the native minimise animation.
  * the rounded-corner preference was applied but the window was ALSO
    clipped with `setMask()` from a polygonised path, producing jagged
    aliased corners and killing per-pixel alpha. Masking is gone: the corner
    radius now comes from DWM (window) + QSS (card), matched at 8px.
  * dark/light mode was never reported to DWM, so the native backdrop tint
    stayed dark in light theme.
"""

from __future__ import annotations

import ctypes
import sys

IS_WINDOWS = sys.platform == "win32"

# dwmapi.h
_DWMWA_USE_IMMERSIVE_DARK_MODE = 20
_DWMWA_WINDOW_CORNER_PREFERENCE = 33
_DWMWA_SYSTEMBACKDROP_TYPE = 38

_DWMWCP_ROUND = 2
_DWMSBT_TRANSIENTWINDOW = 3  # acrylic

# winuser.h
_GWL_STYLE = -16
_WS_MINIMIZEBOX = 0x00020000
_WS_MAXIMIZEBOX = 0x00010000
_SW_MINIMIZE = 6

_WCA_ACCENT_POLICY = 19
_ACCENT_ENABLE_ACRYLICBLURBEHIND = 4
_ACCENT_ENABLE_BLURBEHIND = 3


class _AccentPolicy(ctypes.Structure):
    _fields_ = [
        ("AccentState", ctypes.c_int),
        ("AccentFlags", ctypes.c_int),
        ("GradientColor", ctypes.c_uint),
        ("AnimationId", ctypes.c_int),
    ]


class _WinCompAttrData(ctypes.Structure):
    _fields_ = [
        ("Attribute", ctypes.c_int),
        ("Data", ctypes.c_void_p),
        ("SizeOfData", ctypes.c_size_t),
    ]


def _dwm_set(hwnd: int, attribute: int, value: int) -> bool:
    if not IS_WINDOWS or not hwnd:
        return False
    try:
        val = ctypes.c_int(int(value))
        return ctypes.windll.dwmapi.DwmSetWindowAttribute(
            ctypes.c_void_p(hwnd), attribute, ctypes.byref(val), ctypes.sizeof(val)
        ) == 0
    except (OSError, AttributeError):
        return False


def _legacy_acrylic(hwnd: int, tint: int, blur_only: bool = False) -> bool:
    """Windows 10 fallback: SetWindowCompositionAttribute acrylic."""
    if not IS_WINDOWS or not hwnd:
        return False
    try:
        accent = _AccentPolicy()
        accent.AccentState = (
            _ACCENT_ENABLE_BLURBEHIND if blur_only else _ACCENT_ENABLE_ACRYLICBLURBEHIND
        )
        accent.AccentFlags = 0
        accent.GradientColor = ctypes.c_uint(tint & 0xFFFFFFFF).value
        accent.AnimationId = 0

        data = _WinCompAttrData()
        data.Attribute = _WCA_ACCENT_POLICY
        data.SizeOfData = ctypes.sizeof(accent)
        data.Data = ctypes.cast(ctypes.pointer(accent), ctypes.c_void_p)
        return bool(
            ctypes.windll.user32.SetWindowCompositionAttribute(
                ctypes.c_void_p(hwnd), ctypes.byref(data)
            )
        )
    except (OSError, AttributeError):
        return False


def enable_glass(hwnd: int, *, dark: bool, tint: int) -> str:
    """Rounded acrylic backdrop for a frameless translucent window.

    Returns the backend that took effect: "dwm", "legacy" or "none".
    """
    if not IS_WINDOWS or not hwnd:
        return "none"

    _dwm_set(hwnd, _DWMWA_WINDOW_CORNER_PREFERENCE, _DWMWCP_ROUND)
    _dwm_set(hwnd, _DWMWA_USE_IMMERSIVE_DARK_MODE, 1 if dark else 0)

    if _dwm_set(hwnd, _DWMWA_SYSTEMBACKDROP_TYPE, _DWMSBT_TRANSIENTWINDOW):
        return "dwm"
    if _legacy_acrylic(hwnd, tint):
        return "legacy"
    if _legacy_acrylic(hwnd, tint, blur_only=True):
        return "legacy"
    return "none"


def enable_native_animations(hwnd: int) -> None:
    """Allow Windows to animate minimise/restore on a frameless window."""
    if not IS_WINDOWS or not hwnd:
        return
    try:
        user32 = ctypes.windll.user32
        style = user32.GetWindowLongW(ctypes.c_void_p(hwnd), _GWL_STYLE)
        user32.SetWindowLongW(
            ctypes.c_void_p(hwnd), _GWL_STYLE, style | _WS_MINIMIZEBOX | _WS_MAXIMIZEBOX
        )
    except (OSError, AttributeError):
        pass


def minimize_animated(hwnd: int) -> bool:
    if not IS_WINDOWS or not hwnd:
        return False
    try:
        return bool(ctypes.windll.user32.ShowWindow(ctypes.c_void_p(hwnd), _SW_MINIMIZE))
    except (OSError, AttributeError):
        return False
