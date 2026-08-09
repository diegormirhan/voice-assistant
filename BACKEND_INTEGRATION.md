# Integração UI ↔ Backend — Guia de Implementação (5 Fases)

> Documento autocontido para implementar o pipeline real do assistente de voz,
> trocando o simulador da UI pelo backend verdadeiro. Leia este arquivo por
> inteiro antes de começar. Cada fase é concluída e validada antes da próxima.

---

## 0. Contexto do projeto

Assistente de voz full-duplex, 100% local, Windows 11, GPU AMD (Vulkan), sem
PyTorch/CUDA/WSL. Stack:

| Componente | Arquivo | Papel |
|---|---|---|
| VAD | `audio/vad.py` | Silero VAD ONNX, segmenta fala, `on_segment`/`on_speech_start` |
| STT | `speech/stt.py` | Cliente async do whisper-server (porta 9991) |
| LLM | `speech/llm.py` | Cliente async streaming do llama-server (porta 9992), visão + histórico |
| TTS | `speech/tts.py` | Piper ONNX, `synthesize(text) -> (bytes, sr)` |
| Playback | `audio/playback.py` | `AudioPlayback` thread + fila + barge-in |
| Captura | `audio/capture.py` | Mic 16kHz, callback por bloco |
| Orquestrador | `core/orchestrator.py` | Async: VAD → STT → LLM → TTS, barge-in |
| Screenshot | `vision/screenshot.py` | Captura desktop → base64 JPEG |
| Config | `config.py` | Caminhos, portas, perfil de modelo |
| Servidores | `servers/whisper.py`, `servers/llama.py` | Subprocess + health check |
| UI | `ui/` | PySide6, consome `Bus` (ver seção 1) |

**Comandos para rodar os servidores manualmente (para testes das fases):**
```powershell
# terminal 1
python -c "from pathlib import Path; from servers.whisper import WhisperServer; WhisperServer(Path('bin/whisper-server'), Path('models/whisper/ggml-small.bin')).start(); import time; time.sleep(3600)"
# terminal 2
python -c "from pathlib import Path; from servers.llama import LlamaServer; LlamaServer(Path('bin/llama-server'), Path('models/llm/Qwen3.5-9B-Q4_K_M.gguf'), Path('models/llm/mmproj-F16.gguf')).start(); import time; time.sleep(3600)"
```

Health check:
- whisper: `GET http://127.0.0.1:9991/`
- llama: `GET http://127.0.0.1:9992/health`

---

## 1. A costura UI ↔ backend: `Bus` (`ui/state.py`)

A UI **não fala com o backend diretamente**. Existe um `Bus` (QObject com
signals) que é o único canal. O backend emite signals de qualquer thread; o Qt
enfileira na thread da GUI automaticamente (queued connections).

```python
class Bus(QObject):
    state_changed = Signal(object)          # AssistantState
    error = Signal(str)
    mic_level = Signal(float)               # 0..1
    output_level = Signal(float)            # 0..1
    user_said = Signal(str)
    assistant_said = Signal(str)
    download_progress = Signal(int)         # 0..100
    download_finished = Signal(bool, str)   # ok, message
```

`AssistantState` (enum): `OFF`, `LOADING`, `LISTENING`, `THINKING`, `SPEAKING`.
Tem `.label` e `.is_active`.

**Contrato do `Bus` (o que a UI espera do backend):**

| Signal | Quando emitir | Efeito na UI |
|---|---|---|
| `state_changed` | estado mudou | anel do botão, hint, título, bandeja |
| `mic_level` | RMS do mic (LISTENING) | glow do botão + LevelMeter (config) |
| `output_level` | RMS do TTS tocando (SPEAKING) | glow do botão |
| `user_said` | transcrição do usuário | bolha no transcript |
| `assistant_said` | frase sintetizada | bolha no transcript |
| `download_progress` | progresso de download | DownloadButton |
| `download_finished` | download terminou | DownloadButton |
| `error` | qualquer falha | hint de status |

**Regra do mute:** o `main_window._on_mic_level` zera o nível se
`config["mic_muted"]`. O backend também não deve emitir nível alto quando
mudo — o `Simulator` faz isso via `set_mic_muted()`.

---

## 2. Como a UI consome o backend hoje (referência)

`ui/main_window.py`:
- `__init__(bus=None)`: cria `self.bus = bus or Bus()` e
  `self.simulator = Simulator(self.bus, self)` ← **esta linha será trocada**
- `_connect_bus()`: conecta todos os signals do Bus aos handlers da UI
- `_on_power_toggled(turn_on)`: chama `self.simulator.start()` / `stop()`
- `_on_settings_saved`: chama `self.simulator.set_mic_muted(...)`
- `_start_download`: chama `self.simulator.start_download()`

**O Simulator (`ui/simulator.py`) é o produtor FICTÍCIO.** Ele tem esta API:

```python
class Simulator(QObject):
    def __init__(self, bus: Bus, parent=None): ...
    def start(self) -> None          # LOADING → LISTENING → turnos falsos
    def stop(self) -> None           # OFF
    def set_mic_muted(self, muted: bool) -> None
    def start_download(self) -> None
```

O `Backend` real terá **a mesma API** (menos `start_download`, que vira chamada
a `scripts/download_binaries.py`), para o `main_window.py` mudar o mínimo.

---

## 3. O backend real hoje (`core/orchestrator.py`)

É async (asyncio), roda VAD/STT/LLM/TTS/playback, com barge-in. **Não sabe nada
de Qt/UI** — faz `print("[stt] ...")` e `print("[tts] ...")` em vez de emitir.

```python
class Orchestrator:
    def __init__(self, model_path: Path):
        self._tts = PiperTTS(model_path)
        self._playback = AudioPlayback(self._tts.sample_rate)
        self._stt = WhisperSTT()
        self._llm = LlamaClient()
        self._shot = Screenshot()
        self._buffer = SentenceBuffer()
        self._llm_task: asyncio.Task | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        # AudioCapture(on_audio=self._segmenter.add)
        # SpeechSegmenter(on_segment=self._on_segment, on_speech_start=self._on_speech_start)

    def start(self): ...        # loop = get_event_loop; playback.start(); capture.start()
    def stop(self): ...         # capture.stop(); playback.stop(); cancel llm_task
    async def run(self): ...    # start(); await asyncio.Event().wait() [keep-alive]
    # _on_speech_start → _schedule(_barge_in())
    # _on_segment → _schedule(_handle_segment(segment))
    # _handle_segment: transcribe → print → clear_interrupt → screenshot → _respond
    # _respond: llm.stream → buffer.add(token) → _speak(frase)
    # _speak: print → playback.speak(tts.synthesize(sentence))
```

**Pontos a alterar no orchestrator (revisados e aprovados):**
1. Não pode rodar `run()` direto num loop próprio se a UI tem o seu próprio
   loop — o `Backend` vai rodar o orchestrator num **thread dedicado com
   asyncio próprio**.
2. Os `print(...)` precisam virar **callbacks** (injeção leve) ou o `Backend`
   precisa capturá-los. **Decisão:** adicionar callbacks opcionais ao
   orchestrator (`on_state`, `on_user_text`, `on_assistant_text`,
   `on_mic_level`, `on_output_level`, `on_error`) — sem depender do Qt.

---

## 4. FASE 1 — Criar `ui/backend.py` (esqueleto de estado)

**Objetivo:** rodar o orchestrator real num thread asyncio e emitir
`state_changed` com o ciclo OFF → LOADING → LISTENING, e STOP → OFF. Sem
transcrição/TTS reais ainda (só o esqueleto de estado).

**Criar `ui/backend.py`:**

```python
"""Real backend: bridges core/orchestrator.py to the UI Bus.

Same public API as Simulator so main_window only swaps the class.
"""
import asyncio
import threading

from .state import AssistantState, Bus
from core.orchestrator import Orchestrator

class Backend:
    def __init__(self, bus: Bus, model_path, parent=None):
        self._bus = bus
        self._orchestrator = Orchestrator(model_path)
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._muted = False

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._bus.state_changed.emit(AssistantState.LOADING)
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        if self._loop and self._thread:
            asyncio.run_coroutine_threadsafe(self._shutdown(), self._loop).result(timeout=3)
            self._thread.join(timeout=2)
        self._thread = None

    def set_mic_muted(self, muted: bool) -> None:
        self._muted = bool(muted)

    # -- internals ------------------------------------------------------
    def _run_loop(self) -> None:
        asyncio.set_event_loop(self._loop)
        self._loop.run_until_complete(self._main())

    async def _main(self) -> None:
        self._orchestrator.start()
        self._bus.state_changed.emit(AssistantState.LISTENING)
        try:
            await asyncio.Event().wait()   # keep alive
        finally:
            self._orchestrator.stop()
            self._bus.state_changed.emit(AssistantState.OFF)

    async def _shutdown(self) -> None:
        self._orchestrator.stop()
        self._bus.state_changed.emit(AssistantState.OFF)
```

**Validar:** `python -m ui` → clicar no botão → estado LOADING → LISTENING
(hint muda); clicar de novo → OFF.

> **Nota:** o orchestrator atual **não** tem callbacks `on_*`. Na Fase 1 o
> estado é emitido pelo próprio `Backend` (LOADING/LISTENING/OFF). Os callbacks
> reais são adicionados ao orchestrator a partir da Fase 3 (revisar juntos).

---

## 5. FASE 2 — Mic level real (RMS do mic)

**Objetivo:** o glow do botão + LevelMeter reagem ao áudio real do mic.

**Revisão de backend (aprovada):** `audio/capture.py` deve expor o RMS de cada
bloco via callback opcional.

**Alterar `audio/capture.py`:**

```python
def __init__(self, on_audio, on_level=None):
    """on_audio: callback receiving np.ndarray int16 (512 samples).
    on_level: optional callback receiving float RMS (0..1)."""
    self._on_audio = on_audio
    self._on_level = on_level

def _callback(self, indata, frames, time_info, status):
    block = indata[:, 0].copy()
    if self._on_level:
        rms = float(np.sqrt(np.mean(block.astype(np.float32) ** 2)) / 32768.0)
        self._on_level(min(1.0, rms * 3.0))   # scale up quiet speech
    self._on_audio(block)
```

**Alterar `core/orchestrator.py`:** aceitar `on_mic_level` opcional no
`__init__` e passar `on_level=self._on_mic_level` ao `AudioCapture`.

**Alterar `ui/backend.py`:** passar `on_mic_level=lambda v: self._bus.mic_level.emit(v if not self._muted else 0.0)` ao orchestrator.

**Validar:** com servidores de pé, clicar ligar, falar → glow pulsa com a voz.
Abrir Configurações → barra "Nível de entrada" reage.

---

## 6. FASE 3 — STT → `Bus.user_said` (transcrição real)

**Objetivo:** falar → whisper transcreve → bolha do usuário no transcript.

**Alterar `core/orchestrator.py`:** adicionar callback `on_user_text`.

No `_handle_segment`, trocar `print(f"[stt] {text}")` por:

```python
if self._on_user_text:
    self._on_user_text(text)
```

**Alterar `ui/backend.py`:** passar
`on_user_text=self._bus.user_said.emit` ao orchestrator.

**Validar:** com servidores de pé, falar → texto aparece no painel de
transcrição (ativar o painel nas configurações antes).

---

## 7. FASE 4 — LLM + TTS → estado + `Bus.assistant_said`

**Objetivo:** ciclo completo: THINKING (ao enviar ao LLM) → frase → SPEAKING →
`assistant_said` por frase → volta a LISTENING.

**Alterar `core/orchestrator.py`:**
- Adicionar callbacks `on_state`, `on_assistant_text`, `on_output_level`.
- `_handle_segment`: após transcrever, emitir `on_state(THINKING)`.
- `_speak(sentence)`: emitir `on_assistant_text(sentence)` em vez de `print`;
  emitir `on_state(SPEAKING)`; quando a fila do playback esvaziar, emitir
  `on_state(LISTENING)`.
- `_barge_in`: emitir `on_state(LISTENING)`.

**Sincronização do estado SPEAKING → LISTENING:** o `AudioPlayback` tem
`wait_until_idle(timeout)` (retorna quando a fila esvazia e o áudio acaba).
No orchestrator, após enfileirar todas as frases, aguardar
`await asyncio.to_thread(self._playback.wait_until_idle, 30.0)` e então emitir
`on_state(LISTENING)`.

**Alterar `ui/backend.py`:** conectar os callbacks ao `Bus`:
```python
on_state=self._bus.state_changed.emit,
on_assistant_text=self._bus.assistant_said.emit,
```

**Validar:** fluxo completo falado: usuário pergunta → THINKING → frases do
assistente aparecem e tocam → volta a LISTENING.

---

## 8. FASE 5 — Output level + download progress + apagar Simulator

**Objetivo:** glow durante a fala do assistente + botão de download funcional.
**Final:** remover `ui/simulator.py`.

### 8a. Output level (RMS do TTS tocando)

**Revisão de backend (aprovada):** `audio/playback.py` deve expor o nível do
que está tocando via callback.

**Alterar `audio/playback.py`:**
- `__init__` aceita `on_level=None`.
- No `_write_chunk`, a cada fatia de 512, calcular RMS do `audio[start:start+512]`
  e chamar `on_level(rms_escalado)`.
- Chamar `on_level(0.0)` no `stop()` e quando a fila esvazia.

**Alterar `core/orchestrator.py`:** repassar `on_level` do `__init__` ao
`AudioPlayback` (callback `on_output_level`).

**Alterar `ui/backend.py`:** conectar ao `Bus.output_level`.

### 8b. Download de binários com progresso

**Revisão de backend (aprovada):** `scripts/download_binaries.py` deve aceitar
um callback de progresso.

**Alterar `scripts/download_binaries.py`:**
```python
def download_all(progress=None):
    """progress: optional callable(total_done: int, total_all: int)."""
    total = len(FILES)
    for i, dest in enumerate(FILES, 1):
        download(dest)
        if progress:
            progress(i, total)
```

**Alterar `ui/backend.py`:** `start_download()` roda `download_all` numa
thread e emite `download_progress(percent)` + `download_finished(ok, msg)`.

**Alterar `main_window.py`:** `_start_download` passa a chamar
`self.backend.start_download()` em vez de `self.simulator.start_download()`.

### 8c. Remover o Simulator

- Apagar `ui/simulator.py`.
- Em `ui/main_window.py`:
  - `from .simulator import Simulator` → `from .backend import Backend`
  - `self.simulator = Simulator(self.bus, self)` → `self.backend = Backend(self.bus, config.TTS_MODEL, self)`
  - Todos os `self.simulator.` → `self.backend.`
- Rodar `python -m ui` e validar o fluxo real completo: ligar → falar →
  resposta falada → interromper no meio (barge-in).

---

## 9. Checklist final (DoD da integração)

- [ ] `ui/backend.py` existe, roda o orchestrator em thread asyncio
- [ ] Estado OFF/LOADING/LISTENING/THINKING/SPEAKING refletido no anel/hint
- [ ] `mic_level` alimenta o glow + LevelMeter (Fase 2)
- [ ] `user_said` mostra transcrição do usuário (Fase 3)
- [ ] `assistant_said` mostra resposta + SPEAKING + volta LISTENING (Fase 4)
- [ ] `output_level` alimenta o glow na fala (Fase 5a)
- [ ] Download de binários com progresso (Fase 5b)
- [ ] `ui/simulator.py` apagado (Fase 5c)
- [ ] Barge-in: interromper o assistente corta o áudio e vira nova pergunta
- [ ] `python -m ui` roda o app com backend real de ponta a ponta

---

## 10. Arquivos que NÃO devem mudar (princípios)

- `core/orchestrator.py` **não deve importar Qt/PySide6** — os callbacks
  `on_*` são simples `Callable`. A ponte fica em `ui/backend.py`.
- `ui/state.py` (`Bus`) e os widgets da UI **não mudam** — já consomem os
  signals.
- Cada mudança em `audio/`, `core/`, `speech/`, `scripts/` é **revisada pelo
  usuário** antes de integrar (regra do `UI.md`).

## 11. Comandos úteis

```powershell
# rodar a UI (com simulador até a Fase 5c)
python -m ui

# servidores (testes das fases)
# (ver seção 0)

# benchmark E2E (fim da fala → primeira sílaba), alvo < 2s
python -m tests.benchmark_e2e
```
