# VoiceAssistant

A full-duplex, vision-enabled, 100% local voice assistant for Windows.

Talk to your computer, interrupt it mid-sentence, and get spoken answers that
are aware of what's on your screen — all offline, no cloud, no API keys.

![Status](https://img.shields.io/badge/status-active-2f7bf6)
![Platform](https://img.shields.io/badge/platform-Windows%2011-0078d4)
![Stack](https://img.shields.io/badge/stack-GGML%20%2B%20Vulkan-8f4cf0)

---

## Table of Contents

1. [Description](#description)
2. [Features](#features)
3. [Architecture](#architecture)
4. [Tech Stack](#tech-stack)
5. [Repository Structure](#repository-structure)
6. [Requirements](#requirements)
7. [Quick Start (development)](#quick-start-development)
8. [First Run](#first-run)
9. [Configuration](#configuration)
10. [Latency Budget](#latency-budget)
11. [Privacy](#privacy)
12. [Repository Hygiene](#repository-hygiene)
13. [Release & Distribution](#release--distribution)
14. [Troubleshooting](#troubleshooting)
15. [License](#license)

---

## Description

VoiceAssistant is a conversational assistant with **real full-duplex audio**:
you can interrupt the assistant at any moment (natural barge-in) and the system
**sees your desktop** at the instant you speak, giving it visual context to
answer with.

The entire pipeline runs **locally** with a single GPU infrastructure
(GGML + Vulkan) shared by speech-to-text and the LLM, keeping the design
clean and portable across AMD, NVIDIA, and Intel GPUs.

Target end-to-end latency: **under 2 seconds** from the end of your speech to
the first audible syllable of the reply.

[![Voice Assistant](https://i.imgur.com/LDQ2ypS.png)
---

## Features

- **Full-duplex (barge-in)** — interrupt the assistant while it talks; the
  interruption latency is under 100 ms and the speech that interrupted becomes
  the next question.
- **Desktop vision** — a screenshot is captured the instant you speak and sent
  to the LLM for visual context (toggleable for privacy).
- **100% local / private** — no cloud, no API keys, everything runs on your
  machine.
- **GPU-accelerated STT + LLM** — whisper.cpp and llama.cpp on **Vulkan**, one
  GPU backend for both bottlenecks; TTS runs on CPU without hurting latency.
- **Streaming voice** — transcripts arrive in real time; the answer is spoken
  sentence-by-sentence as it is generated (Piper, pt-BR female voice).
- **First-run downloads** — binaries and models are fetched from Hugging Face
  with a live progress bar, only for the selected profile.
- **Lazy startup** — the window opens instantly; servers and models only load
  when you press the central button.
- **Settings applied live** — VAD thresholds, TTS speed/expressiveness, vision
  toggle, volume and mute all take effect without restarting.

---

## Architecture

The app is orchestrated by an `asyncio` loop running on a dedicated thread. The
UI never talks to the pipeline directly — everything flows through a signal
`Bus` that is safe to emit from any thread.

```
                ┌──────────────────────────── UI (PySide6) ────────────────────────────┐
                │  main window · status ring (glow) · transcript · settings · download │
                └──────────────────────────────────┬───────────────────────────────────┘
                                                   │ Bus (Qt signals)
                                                   ▼
                ┌────────────────────────── BACKEND (asyncio thread) ──────────────────┐
                │  start servers → ensure models → build orchestrator → run voice loop │
                └──────────────────────────────────┬───────────────────────────────────┘
                                                   │
        HTTP streaming (VAD + STT)                  │ HTTP streaming (vision + text) + TTS/playback
                        ┌──────────────────────────┴──────────────────────────┐
                        ▼                                                       ▼
            ┌────────────────────────┐          ┌──────────────────────────────┐
            │ whisper-server (Vulkan)│          │ llama-server (Vulkan)         │
            │ port 9991              │          │ port 9992 (vision + text)     │
            └────────────────────────┘          └──────────────────────────────┘
```

**Components**

| Component | Module | Role |
|---|---|---|
| VAD | `audio/vad.py` | Silero VAD (ONNX), speech segmentation + barge-in |
| STT | `speech/stt.py` | Async client for whisper-server |
| LLM | `speech/llm.py` | Async streaming client for llama-server (vision + history) |
| TTS | `speech/tts.py` | Piper (ONNX), sentence-by-sentence synthesis |
| Playback | `audio/playback.py` | Streaming output thread with barge-in + output level |
| Capture | `audio/capture.py` | Microphone input (16 kHz) + input level |
| Orchestrator | `core/orchestrator.py` | VAD → STT → LLM → TTS loop, states, barge-in |
| Screenshot | `vision/screenshot.py` | Desktop capture → base64 JPEG |
| Servers | `servers/*` | Subprocess managers for whisper/llama |
| Launcher | `servers/launcher.py` | Boots both native servers for a profile |
| Backend bridge | `ui/backend.py` | Runs the orchestrator on a thread, bridges events to the `Bus` |
| UI | `ui/` | PySide6 window, widgets, settings, theme, transcript |

**Processes (3)**

| Process | Binary | Port | Role |
|---|---|---|---|
| whisper-server | `whisper-server.exe` (Vulkan) | 9991 | VAD + STT streaming |
| llama-server | `llama-server.exe` (Vulkan) | 9992 | LLM text + vision |
| VoiceAssistant | the app itself | — | UI + orchestrator + TTS |

---

## Tech Stack

| Layer | Technology | Why |
|---|---|---|
| VAD + STT | `whisper.cpp` (whisper-server) | GGML + Vulkan, streaming, multilingual |
| LLM | `llama.cpp` (llama-server) | GGML + Vulkan, text + vision, preloaded in VRAM |
| TTS | Piper (`piper-tts`, ONNX) | No torch, pt-BR female voice |
| Screenshot | `mss` + `Pillow` | ~5 ms capture, resized before the LLM |
| Audio I/O | `sounddevice` | Capture + playback via PortAudio |
| Orchestration | `asyncio` + queues + events | Predictable concurrency with barge-in |
| UI | `PySide6` (Qt) | Professional UI: QSS, animations, thread-safe signals |
| Packaging | PyInstaller + Inno Setup | Standalone `.exe` + installer |

---

## Repository Structure

```
voice-assistant/
├── main.py                  # entry: loads the UI (servers/models start on the button)
├── config.py                # paths, ports, profile selection (frozen-aware)
├── core/
│   └── orchestrator.py      # voice loop: VAD → STT → LLM → TTS, barge-in
├── servers/
│   ├── whisper.py           # whisper-server subprocess manager
│   ├── llama.py             # llama-server subprocess manager
│   ├── launcher.py          # boots both servers for a profile
│   └── models.py            # model profiles (leve/padrao) + download lists
├── speech/
│   ├── stt.py               # whisper-server client
│   ├── llm.py               # llama-server streaming client (vision + history)
│   ├── tts.py               # Piper synthesis
│   └── sentence_buffer.py   # LLM tokens → sentences
├── vision/
│   └── screenshot.py        # desktop → base64 JPEG
├── audio/
│   ├── capture.py           # mic input + level
│   ├── vad.py               # Silero VAD + segmentation + barge-in
│   └── playback.py          # output thread + barge-in + level
├── ui/                      # PySide6 (widgets, settings, theme, transcript)
│   ├── main_window.py
│   ├── backend.py           # adaptor: orchestrator thread → Bus signals
│   ├── state.py             # AssistantState + Bus
│   └── widgets/ modals/
├── scripts/
│   ├── downloads.py         # shared byte-accurate download helpers
│   ├── download_binaries.py # Vulkan binaries from Hugging Face
│   └── download_models.py   # models per profile
├── installer/
│   ├── app.spec             # PyInstaller spec
│   ├── setup.iss            # Inno Setup script
│   ├── build.ps1            # PyInstaller + Inno Setup pipeline
│   └── output/              # VoiceAssistantSetup.exe (built)
├── tests/                   # dev-only (gitignored)
├── bin/                     # native binaries (gitignored, first-run download)
├── models/                  # model cache (gitignored, first-run download)
├── pyproject.toml
└── README.md
```

---

## Requirements

- **Windows 11** (native, no WSL required)
- **GPU** with Vulkan drivers: AMD, NVIDIA, or Intel
- **Python 3.12+** and [uv](https://github.com/astral-sh/uv)
- Disk space on first run:
  - Binaries (Vulkan): ~128 MB
  - Models: ~2.5 GB (light profile) or ~6 GB (standard profile)
- **No** PyTorch, TensorFlow, CUDA, or WSL in the pipeline.

---

## Quick Start (development)

```powershell
# 1. Install dependencies (from the project root)
uv sync

# 2. Run the app (servers/models load on the central button)
python main.py
```

See [First Run](#first-run) for the initial setup.

---

## First Run

On first launch the app is **code-only**: the Vulkan binaries and the models
are not shipped. They are downloaded once from Hugging Face and cached in a
writable folder beside the executable.

### 1. Download the binaries

Click **Download** in the top bar. The Vulkan binaries (whisper-server,
llama-server + DLLs, ~128 MB) are saved to `bin/` next to the app.

### 2. Load the models and start

Press the **central button**. The app:

1. Checks the models for the selected profile and downloads the missing ones
   (live progress on the download pill; cancel by turning the app off).
2. Starts both servers — whisper-server on `:9991`, llama-server on `:9992`.
3. Loads the models and enters **listening** mode — just speak.

> If the binaries are missing, the app stops before downloading any models and
> shows: "Binários Vulkan ausentes — clique em 'Baixar' na barra superior."

### Model profiles

Choose the profile in the top bar before the first start:

| Profile | LLM | Download size |
|---|---|---|
| **Padrão** (default) | Qwen3.5-9B Q4 (vision) | ~6 GB |
| **Leve** | Qwen3-VL-4B Q4 (vision) | ~2.5 GB |

Only the selected profile is downloaded. Switching profiles later downloads
just the new LLM.

### Where the files go

- **Installed app** (from the installer): `%LOCALAPPDATA%\VoiceAssistant\`
- **Development** (`python main.py`): the project's `bin/` and `models/` folders

> Tip: to skip the download on later installs, copy your existing `models/`
> folder beside the executable.

---

## Configuration

Settings live in `config.json` (saved next to the app). Most of them are edited
from the **gear icon → Configurações** dialog and applied live.

| Key | Default | Meaning |
|---|---|---|
| `min_speech_ms` | 250 | Minimum speech length accepted by the VAD |
| `hangover_ms` | 1000 | Silence after speech before closing a segment |
| `length_scale` | 1.3 | TTS speed (higher = slower) |
| `noise_scale` | 0.6 | TTS expressiveness |
| `volume` | 1.0 | Output volume (0..1) |
| `mic_muted` | false | Mute the microphone |
| `vision_enabled` | true | Send a desktop screenshot to the LLM |
| `transcript_visible` | false | Show the transcript panel |
| `always_on_top` | true | Keep the window on top |
| `model_profile` | "padrao" | LLM profile: `leve` (4B) or `padrao` (9B) |
| `voice` | "pt_BR-faber-medium" | TTS voice |

---

## Latency Budget

| Stage | Target |
|---|---|
| VAD endpoint | < 100 ms |
| STT (whisper.cpp, Vulkan) | 200–600 ms |
| LLM first token (preloaded) | 200–500 ms |
| TTS first sentence (Piper, CPU) | 150–300 ms |
| **End-to-end** (end of speech → first syllable) | **< 2 s** |
| Barge-in | < 100 ms |

---

## Privacy

Everything runs locally. A screenshot is captured only when `vision_enabled` is
on, at the moment you start speaking. No audio, transcripts, or screen data
leave your machine.

---

## Repository Hygiene

Heavy or generated folders are **gitignored** and never committed:

```
__pycache__/  bin/  build/  dist/  models/  tests/
```

- **Code** lives in GitHub.
- **Binaries** and **models** are downloaded at first run from Hugging Face
  (see [Release & Distribution](#release--distribution)).

---

## Release & Distribution

The released installer is **light (~82 MB)** and contains only the Python app.
Binaries and models are fetched on first run.

See **[RELEASE.md](RELEASE.md)** for the step-by-step guide on building and
publishing a GitHub release.

---

## Troubleshooting

| Symptom | Likely cause / fix |
|---|---|
| App asks to "Download" on start | Binaries are not present yet — click **Download** in the top bar |
| "whisper-server failed to start!" | Binary missing or Vulkan not initialized |
| Ports 9991/9992 busy | Another instance is running — close it and retry |
| No mic glow / low level | Mic gain is low — raise it in Windows sound settings |
| Installer is light but app is slow to start | First run is downloading the models |
| Crashes only in the packaged app | Run `dist\VoiceAssistant\VoiceAssistant.exe` and check the error dialog |

---

## License

MIT — see `LICENSE` (add one before publishing if not present).
