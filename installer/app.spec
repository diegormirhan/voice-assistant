# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for the VoiceAssistant desktop app (one-folder).

Bundles only the Python app + the UI icons. Nothing heavy is shipped:
binaries (bin/), models (models/) and tests are intentionally excluded —
binaries and models are downloaded on first run to a persistent folder
beside the executable (see config.py / servers/models.py).
"""

from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

ROOT = Path(SPECPATH).parent  # project root (installer/..)

a = Analysis(
    [str(ROOT / "main.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=[
        (str(ROOT / "ui" / "icon.ico"), "ui"),
        (str(ROOT / "ui" / "icon.jpg"), "ui"),
    ]
    + collect_data_files("piper"),  # espeak-ng-data + voice data required by TTS
    hiddenimports=collect_submodules("piper"),  # phonemize_espeak/chinese/hebrew, phoneme_ids
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tests", "build", "dist", "__pycache__"],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="VoiceAssistant",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,  # keeps server/CLI logs visible; switch to False for release
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(ROOT / "ui" / "icon.ico"),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="VoiceAssistant",
)
