# Release Guide — GitHub

Step-by-step guide to publish a new version of **VoiceAssistant** on GitHub.

---

## What gets released

The only artifact you upload is the **installer**. Everything heavy is
downloaded at first run, so the release stays small:

| Artifact | Path (after build) | Size |
|---|---|---|
| Installer | `installer/output/VoiceAssistantSetup.exe` | ~82 MB |

The binaries (Vulkan) and models are **not** uploaded here — the app fetches
them from Hugging Face on first run (see [Dependencies](#dependencies)).

---

## 1. Bump the version

Update `pyproject.toml`:

```toml
[project]
version = "0.1.1"   # ← new version
```

And `installer/setup.iss`:

```iss
#define MyAppVersion "0.1.1"   # ← must match pyproject.toml
```

> Keep both in sync — the installer reports this version in Windows.

---

## 2. Build the installer

Run from the project root:

```powershell
powershell -ExecutionPolicy Bypass -File installer\build.ps1
```

This runs two steps automatically:

1. **PyInstaller** → `dist\VoiceAssistant\` (one-folder bundle).
2. **Inno Setup** → `installer\output\VoiceAssistantSetup.exe`.

The bundle intentionally **excludes** `bin/`, `models/`, `tests/`, `build/`,
`dist/` and `__pycache__/` — see `installer/app.spec`.

---

## 3. Smoke-test the build

Before publishing:

1. Run `dist\VoiceAssistant\VoiceAssistant.exe` directly.
2. Confirm only the app window opens (no console window).
3. Click **Download** in the top bar → binaries appear in `dist\VoiceAssistant\bin`.
4. (Optional, offline check) copy your `models\` folder next to the exe and
   verify a full turn: press the central button, speak, hear the answer.

---

## 4. Create the GitHub Release

1. Push your code and tag it:

   ```powershell
   git tag v0.1.1
   git push origin v0.1.1
   ```

2. On GitHub → **Releases → Draft a new release**:
   - **Tag**: `v0.1.1`
   - **Title**: `v0.1.1`
   - **Attach binaries**: upload `installer/output/VoiceAssistantSetup.exe`

3. Publish.

---

## 5. Release notes template

```markdown
## VoiceAssistant v0.1.1

### New
- ...

### Fixed
- ...

### Notes
- 100% local: binaries and models are downloaded on first run from
  Hugging Face. No cloud, no API keys.
- Profiles: **Padrão** (Qwen3.5-9B, ~6 GB) and **Leve** (Qwen3-VL-4B, ~2.5 GB).
- Tested on Windows 11 with an AMD GPU (Vulkan).
```

---

## Dependencies (first-run downloads)

The app downloads these automatically and caches them beside the executable:

| What | Source | Size |
|---|---|---|
| Vulkan binaries | `diegomirhan/voice-assistant-binaries` (HF) | ~128 MB |
| VAD / whisper / TTS | official repos (see `servers/models.py`) | ~150 MB |
| LLM (per profile) | per profile (see `servers/models.py`) | ~2.5–6 GB |

> These are **not** part of the installer — keep them on Hugging Face and
> only version the code on GitHub.

---

## Checklist before publishing

- [ ] `pyproject.toml` and `installer/setup.iss` versions match
- [ ] `installer/build.ps1` completes without errors
- [ ] `installer/output/VoiceAssistantSetup.exe` exists (~82 MB)
- [ ] Smoke test passed (app opens, binaries download, full turn works)
- [ ] Installer tested on a clean machine (no Python installed)
- [ ] Release notes drafted
- [ ] Installer attached to the GitHub Release
