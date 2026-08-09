"""Window chrome animations: minimise, maximise/restore and close.

Why this exists: the window is frameless *and* `WA_TranslucentBackground`, so
Windows treats it as a layered window and skips the native genie/zoom
animations — pressing the buttons made the window teleport. The transitions are
therefore driven in Qt: geometry + windowOpacity tweens that mimic the shell.

Notes
  * maximise is emulated (geometry -> screen work area) instead of
    `showMaximized()`, because a real state change repaints instantly and would
    cancel the tween. The window keeps its own `is_maximized` flag.
  * every animation is re-entrancy guarded: clicking twice mid-flight is a
    no-op instead of leaving the window at an interpolated size.
  * `prefers_reduced_motion` short-circuits to the plain state change so the
    app still behaves for users with animations disabled system-wide.
"""

from __future__ import annotations

import os
from collections.abc import Callable

from PySide6.QtCore import (
    QEasingCurve,
    QObject,
    QParallelAnimationGroup,
    QPropertyAnimation,
    QRect,
)
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QWidget

DUR_MIN = 170
DUR_RESTORE = 210
DUR_MAX = 240
DUR_CLOSE = 150


def _work_area(widget: QWidget) -> QRect:
    screen = widget.screen() or QGuiApplication.primaryScreen()
    if screen is None:
        return widget.geometry()
    return screen.availableGeometry()


def _shrink(rect: QRect, factor: float) -> QRect:
    """Scale a rect around its own centre."""
    w = max(1, int(rect.width() * factor))
    h = max(1, int(rect.height() * factor))
    out = QRect(0, 0, w, h)
    out.moveCenter(rect.center())
    return out


class WindowAnimator(QObject):
    def __init__(self, window: QWidget):
        super().__init__(window)
        self._w = window
        self._group: QParallelAnimationGroup | None = None
        self._normal: QRect = window.geometry()
        self._min_size = window.minimumSize()
        self.is_maximized = False

    # -- helpers -----------------------------------------------------------

    @property
    def busy(self) -> bool:
        return self._group is not None

    def _unclamp(self) -> None:
        """Drop the minimum size so geometry tweens are not clipped."""
        self._min_size = self._w.minimumSize()
        self._w.setMinimumSize(1, 1)

    def _reclamp(self) -> None:
        self._w.setMinimumSize(self._min_size)

    def remember_normal_geometry(self) -> None:
        if not self.is_maximized:
            self._normal = self._w.geometry()

    def normal_geometry(self) -> QRect:
        return QRect(self._normal) if self.is_maximized else self._w.geometry()

    def _reduced_motion(self) -> bool:
        # Opt-out for users who disable animations, and for headless/offscreen
        # runs where tweening a hidden window is pointless.
        if os.environ.get("VOICE_ASSISTANT_REDUCED_MOTION") == "1":
            return True
        return QGuiApplication.instance() is None

    def _run(
        self,
        *,
        geometry: QRect | None,
        opacity: float | None,
        duration: int,
        curve: QEasingCurve.Type,
        done: Callable[[], None] | None = None,
    ) -> None:
        group = QParallelAnimationGroup(self)

        if geometry is not None:
            anim = QPropertyAnimation(self._w, b"geometry", group)
            anim.setDuration(duration)
            anim.setEasingCurve(curve)
            anim.setStartValue(self._w.geometry())
            anim.setEndValue(geometry)
            group.addAnimation(anim)

        if opacity is not None:
            fade = QPropertyAnimation(self._w, b"windowOpacity", group)
            fade.setDuration(duration)
            fade.setEasingCurve(QEasingCurve.Type.OutCubic)
            fade.setStartValue(self._w.windowOpacity())
            fade.setEndValue(opacity)
            group.addAnimation(fade)

        def finish() -> None:
            self._group = None
            if done is not None:
                done()

        group.finished.connect(finish)
        self._group = group
        group.start(QParallelAnimationGroup.DeletionPolicy.DeleteWhenStopped)

    # -- public transitions ------------------------------------------------

    def minimize(self, *, minimize_call: Callable[[], None]) -> None:
        """Sink toward the taskbar, then hand over to the real minimise."""
        if self.busy:
            return
        self.remember_normal_geometry()
        keep = self._w.geometry()

        area = _work_area(self._w)
        target = _shrink(keep, 0.72)
        target.moveCenter(keep.center())
        # Drift down toward the taskbar, like the shell's minimise.
        target.moveTop(min(area.bottom() - target.height() // 3, keep.center().y()))

        if self._reduced_motion():
            minimize_call()
            return

        # The window has a large minimumSize; without lifting it the geometry
        # tween is clamped and the sink is invisible (the old bug where the
        # animation looked like it simply did not run).
        self._unclamp()

        def done() -> None:
            minimize_call()
            # Restore the pre-animation frame so the taskbar thumbnail and the
            # next restore start from the real size.
            self._reclamp()
            self._w.setGeometry(keep)
            self._w.setWindowOpacity(1.0)

        self._run(
            geometry=target,
            opacity=0.0,
            duration=DUR_MIN,
            curve=QEasingCurve.Type.InCubic,
            done=done,
        )

    def restore_from_minimized(self) -> None:
        """Grow back in after the window becomes visible again."""
        if self.busy:
            return
        final = self._w.geometry()
        start = _shrink(final, 0.86)
        self._unclamp()
        self._w.setWindowOpacity(0.0)
        self._w.setGeometry(start)
        self._run(
            geometry=final,
            opacity=1.0,
            duration=DUR_RESTORE,
            curve=QEasingCurve.Type.OutCubic,
            done=self._reclamp,
        )

    def close(self, *, quit_call: Callable[[], None]) -> None:
        if self.busy:
            return
        if self._reduced_motion():
            quit_call()
            return
        self._unclamp()
        self._run(
            geometry=_shrink(self._w.geometry(), 0.94),
            opacity=0.0,
            duration=DUR_CLOSE,
            curve=QEasingCurve.Type.InCubic,
            done=quit_call,
        )
