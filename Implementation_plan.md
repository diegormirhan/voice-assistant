# Assistente de Voz Full-Duplex em Tempo Real — No-Torch / AMD

> Projeto de portfólio para vagas de Machine Learning Engineering
> Duração estimada: 6 dias | Stack 100% local (Edge AI) | Windows 11 | GPU AMD

---

## Visão Geral

Assistente de voz conversacional **full-duplex + visão** real: o usuário pode interromper a IA a qualquer momento (barge-in natural) e o sistema **vê o desktop** no instante da fala para responder com contexto visual. Ao iniciar o app, o LLM já é pré-carregado na VRAM da GPU AMD e permanece residente até o usuário fechar o programa — zero latência de cold-start entre turnos. Toda inferência roda **localmente** — sem APIs de nuvem — com latência-alvo de **< 2s** entre o fim da fala do usuário e o início da resposta audível.

### Diferenciais de portfólio
- **Engenharia de sistemas assíncronos**: 6 threads + asyncio + queues, com barge-in consistente.
- Pipeline Edge AI multimodal **sem PyTorch/CUDA**: VAD (C) → Screenshot + STT (ONNX) → LLM Visão (Vulkan) → TTS (ONNX).
- **Modelo pré-carregado na VRAM**: zero cold-start entre turnos; gestão explícita de `keep_alive` via Ollama.
- Decisão arquitetural explícita: cada modelo no backend ideal para GPU AMD 16GB no Windows.
- Empacotamento como produto desktop (.exe + instalador).

---

## Restrição Crítica de Hardware

- GPU **AMD** (sem CUDA), **sem WSL**, Windows 11 nativo.
- **PROIBIDO**: `torch`, `tensorflow`, `jax` ou qualquer dependência que puxe CUDA.
- Inferência neural exclusivamente via **ONNX Runtime** e **llama.cpp (Vulkan)** através do Ollama.

### Onde cada modelo roda (decisão arquitetural)

| Componente | Backend | Dispositivo | Justificativa |
|---|---|---|---|
| Screenshot | `mss` (C) | CPU | Captura de tela em ~5ms; sem GPU |
| VAD | Silero VAD (ONNX via onnxruntime) | CPU | MIT, ~2MB, exportação ONNX oficial, probabilidade contínua 0–1, latência ~30ms |
| STT | sherpa-onnx (ONNX Runtime) | CPU (int8) | whisper small int8: RTF < 0.5 em CPU moderna; build DirectML do sherpa é otimização opcional |
| LLM (visão) | Ollama → llama.cpp | **GPU AMD via Vulkan** | qwen3.5:9b q4 (~5.5GB); pré-carregado na VRAM desde o boot |
| TTS | Piper (ONNX Runtime) | CPU | RTF << 1; síntese por frase é quase instantânea |

> A aceleração em GPU acontece onde o custo é real: **o LLM multimodal**. STT e TTS quantizados em CPU já cabem no orçamento de latência.

> **Modelo pré-carregado na inicialização**: `main.py` envia uma requisição `ollama.chat(keep_alive=-1)` antes de iniciar qualquer pipeline. O modelo `qwen3.5:9b` (~5.5GB dos 16GB disponíveis) fica residente na VRAM durante toda a sessão — sem GC entre turnos.

> Verificar GPU: `ollama ps` com a coluna `PROCESSOR` deve indicar `100% GPU`.

---

## Stack Técnico

| Camada | Tecnologia | Justificativa |
|---|---|---|
| Screenshot | `mss` (C) + `Pillow` | Captura de tela no `speech_start`; mss é o mais rápido (~5ms) |
| VAD | `Silero VAD` (ONNX) | MIT, exportação ONNX oficial (~2MB), usa `onnxruntime` já presente no stack, zero dependências novas |
| STT | `sherpa-onnx` | Whisper/Zipformer via ONNX Runtime, wheels Windows, sem torch |
| LLM | Ollama (`qwen3.5:9b`) | Vulkan/AMD nativo, visão + texto, pré-carregado na VRAM (`keep_alive=-1`) |
| TTS | `piper-tts` | ONNX puro, vozes pt-BR locais, síntese rápida por frase |
| Audio I/O | `sounddevice` | Capture + playback unificados via PortAudio; callback-based, mantido ativamente |
| UI | `PySide6` | Qt profissional: QSS (CSS-like), animações, signals/slots thread-safe |
| Orquestração | `asyncio` + `queue.Queue` + `threading.Event` | Concorrência previsível com barge-in |
| Empacotamento | PyInstaller + Inno Setup | .exe standalone + instalador Windows |

**Python: 3.12** — wheels garantidos para `pyaudio`, `sherpa-onnx` e `piper-tts`; sem a restrição de versão imposta pelo torch-directml.

---

## Arquitetura de Buffers e Threads

```
┌────────────────────────────────────────────────────────────────────┐
│                  MAIN THREAD (UI / PySide6)                        │
│                  render + status via signals/slots                  │
└───────────────────────────────▲────────────────────────────────────┘
                                │ callbacks thread-safe
                                │
┌───────────────────────────────┴────────────────────────────────────┐
│         ASYNCIO EVENT LOOP (thread dedicada) + PRELOAD             │
│                                                                    │
│  ┌──────────────┐    ┌─────────────────┐    ┌──────────────┐      │
│  │ Orchestrator │──▶│ Ollama stream    │──▶│ sentence cut │──┐    │
│  │ (state mgr)  │◀──│ Qwen VL (visão)  │    │ (. ! ? \n)   │  │   │
│  └──────▲───────┘    │ keep_alive=-1    │    └──────────────┘  │   │
│         │            └─────────────────┘                       │   │
│         │  transcript + screenshot (base64)                     │   │
└─────────┼──────────────────────────────────────────────────────┼───┘
          │                                                      │ llm_stream_q
          │                                                      │
┌─────────┴────────┐                                  ┌──────────▼────────┐
│    STT THREAD    │                                  │   TTS THREAD      │
│   sherpa-onnx    │                                  │  Piper (ONNX)     │
│ whisper int8 CPU │                                  │  pt-BR female     │
└─────────▲────────┘                                  └──────┬────────────┘
          │ vad_segments_q                                   │ tts_audio_q
          │                                                  ▼
┌─────────┴────────────────┐   interrupt_event    ┌──────────────────────┐
│     CAPTURE THREAD       │─────────────────────▶│   PLAYBACK THREAD    │
│ sounddevice 16kHz +      │                      │    sounddevice       │
│ Silero VAD 32ms +        │                      │    OutputStream      │
│ mss screenshot           │                      └──────────────────────┘
│ (no speech_start)        │
└─────────┬────────────────┘
          │ on_speech_start + _latest_screenshot
          │ (callback + thread-safe property)
          ▼
   ┌─────────────────────────┐
   │  INTERRUPTION MANAGER   │
   │  - detecta barge-in     │
   │  - set interrupt_event  │
   │  - drena filas (mutex)  │
   │  - cancela LLM task     │
   │  - lock de reentrada    │
   └─────────────────────────┘
```

### Threads (6 no total)

| Thread | Loop | Bloqueio | Responsabilidade |
|---|---|---|---|
| Main | Qt event loop | signals/slots | render, botões, status, animações |
| Capture | `sd.InputStream(callback)` | callback | VAD contínuo (Silero ONNX), segmenta fala, **screenshot no speech_start via mss**, dispara `on_speech_start` |
| STT | `vad_segments_q.get()` | fila | transcreve segmento → `transcript_q` |
| Asyncio | event loop | futures | orchestrator, Ollama streaming (visão + texto), sentence cutting |
| TTS | `llm_stream_q.get()` | fila | sintetiza frase → `tts_audio_q` |
| Playback | `tts_audio_q.get(timeout)` | fila + stream | escreve PCM, monitora `interrupt_event` |

### Filas (todas `queue.Queue` thread-safe) + Screenshot

| Canal | Produtor | Consumidor | Payload | Propósito |
|---|---|---|---|---|
| `_latest_screenshot` | Capture (no speech_start) | Orchestrator | `bytes` (PNG) | Screenshot do desktop no instante da fala; armazenado como atributo thread-safe no capture |
| `vad_segments_q` | Capture | STT | `np.ndarray` int16 16kHz | fala segmentada no endpoint |
| `transcript_q` | STT | Orchestrator | `str` | texto final do usuário |
| `llm_stream_q` | LLM (asyncio) | TTS | `str` (frase completa) | sentenças prontas p/ síntese |
| `tts_audio_q` | TTS | Playback | `np.ndarray` int16 22.05kHz | chunks de áudio sintetizado |
| `interrupt_event` | Interruption | Playback + Orchestrator | `threading.Event` | sinal de barge-in |

### Sample rates

| Sinal | Taxa | Formato |
|---|---|---|
| Capture (mic) | 16 kHz | int16 mono (exigência do webrtcvad) |
| STT input | 16 kHz | float32 normalizado [-1, 1] |
| Piper output | 22.05 kHz (pt_BR-faber-medium) | int16 mono |
| Playback | casar com a voz Piper escolhida | int16 mono |

### Lógica de Barge-in

1. Capture roda webrtcvad **continuamente**, inclusive durante o playback (full-duplex real).
2. Ao detectar `speech_start`, dispara o callback `on_speech_start` — sempre, não só durante playback.
3. O Interruption Manager verifica `playback.is_active`:
   - **Playback inativo** → ignora, é só o usuário começando a falar.
   - **Playback ativo** → é barge-in: executa o protocolo de interrupção.
4. Protocolo: `interrupt_event.set()` → drena `vad_segments_q` (parcial), `llm_stream_q`, `tts_audio_q` (com mutex por fila) → playback para no próximo chunk (< 20ms) → `asyncio.Task.cancel()` no LLM → TTS aborta a frase corrente.
5. **O segmento que causou o barge-in NÃO é descartado** — ele é a nova fala do usuário e segue para o STT. Uma nova screenshot é capturada no speech_start do barge-in e substitui a anterior.
6. Lock de reentrada impede barge-in duplo enquanto o protocolo executa.
7. Estado global → `LISTENING`, propagado à UI via signals/slots (Qt thread-safe).

**Latência-alvo de interrupção: < 100ms.**

### Orçamento de latência (E2E)

| Estágio | Alvo |
|---|---|
| screenshot (`mss`) | < 10ms (captura síncrona no speech_start) |
| VAD endpoint (após 450ms de silêncio) | < 100ms |
| STT whisper small int8 (segmento 3-5s, CPU) | 400–800ms |
| LLM primeiro token (qwen3.5:9b q4, Vulkan, pré-carregado) | 400–900ms |
| TTS primeira frase (Piper medium, CPU) | 200–400ms |
| **E2E (fim da fala → primeira sílaba)** | **< 2.5s** |

> Com modelo pré-carregado na VRAM, o primeiro token do LLM compete com um modelo de 3B texto — a diferença de tamanho (~9B vs ~3B) é compensada pela ausência de cold-start.

### Estratégia de Pré-carga do LLM (VRAM persistente)

O `qwen3.5:9b` (~5.5GB em q4) precisa estar **carregado na VRAM da GPU antes de qualquer interação** e permanecer lá até que o usuário feche o app. Sem isso, cada turno sofre +2-3s de cold-start.

**Implementação:**

1. `main.py` → `preload_ollama()` antes de iniciar a UI e o pipeline.
2. Envia `ollama.chat(model='qwen3.5:9b', messages=[{'role': 'user', 'content': 'ping'}], keep_alive=-1)` e aguarda o primeiro token (descarta).
3. `keep_alive=-1` instrui o servidor Ollama a nunca descarregar o modelo da VRAM.
4. Verifica com `ollama.ps()` se o modelo está com `PROCESSOR=100% GPU`.
5. Só depois a UI abre e o pipeline inicia.

**Shutdown:** o graceful shutdown (Ctrl+C / botão fechar) chama `ollama_client.unload_model()` — o OS também libera a VRAM ao encerrar o processo.

**Fallback:** se o Ollama não estiver rodando, `main.py` tenta iniciar via `subprocess`. Se falhar, exibe erro na UI.

---

## Estrutura de Pastas

```
voice-assistant/
├── src/
│   ├── __init__.py
│   ├── main.py                  # entry point: preload LLM → bootstrap + UI + asyncio thread
│   ├── config.py                # hiperparâmetros centralizados
│   │
│   ├── audio/
│   │   ├── __init__.py
│   │   ├── capture.py           # PyAudio + webrtcvad (thread dedicada)
│   │   └── playback.py          # sounddevice stream (thread dedicada)
│   │
│   ├── stt/
│   │   ├── __init__.py
│   │   └── recognizer.py        # sherpa-onnx wrapper (whisper small int8)
│   │
│   ├── llm/
│   │   ├── __init__.py
│   │   └── ollama_client.py     # AsyncClient visão + texto, keep_alive, preload
│   │
│   ├── tts/
│   │   ├── __init__.py
│   │   └── piper_engine.py      # Piper síntese por frase (ONNX)
│   │
│   ├── core/
│   │   ├── __init__.py
│   │   ├── pipeline.py          # orchestrator asyncio principal
│   │   ├── interruption.py      # state machine de barge-in
│   │   └── state.py             # AssistantState (LISTENING/THINKING/SPEAKING)
│   │
│   └── ui/
│       ├── __init__.py
│       ├── app.py               # PySide6 main window (QSS estilizado)
│       └── widgets.py           # level meter, status badge
│
├── assets/
│   └── icons/                   # ícones do app (ico, png)
│
├── models/                      # cache de modelos (gitignored)
│   ├── sherpa/                  # STT: whisper small int8 (ou zipformer)
│   └── piper/                   # TTS: voz pt-BR (.onnx + .onnx.json)
│
├── installer/
│   ├── setup.iss                # script Inno Setup
│   └── bundle_ollama.ps1        # empacota binário do Ollama
│
├── scripts/
│   ├── download_models.py       # baixa modelos sherpa + voz piper
│   ├── benchmark_latency.py     # mede latência E2E de cada estágio
│   └── build.ps1                # PyInstaller → Inno Setup
│
├── tests/
│   ├── test_capture.py
│   ├── test_stt.py
│   ├── test_tts.py
│   └── test_pipeline.py
│
├── requirements.txt
├── requirements-dev.txt
├── pyproject.toml
├── .gitignore
├── IMPLEMENTATION_PLAN.md
└── README.md
```

> Mudanças vs. plano anterior (torch): sem `voice_ref.wav`/`extract_voice.py` (Piper usa vozes pré-treinadas, sem clonagem), `transcriber.py` → `recognizer.py` (nomenclatura sherpa), `synthesizer.py` → `piper_engine.py`, `models/{silero,whisper,xtts,ollama}` → `models/{sherpa,piper}`.

---

## Plano de Implementação — 6 Dias

---

### Dia 1 — Fundação: Setup + Audio Capture + Cobra VAD + Screenshot

**Objetivo:** Captura de áudio com segmentação de fala via Picovoice Cobra e screenshot no speech_start.

#### Tarefas

- [ ] Criar venv Python 3.12 (`py -3.12 -m venv .venv`)
- [ ] `pip install -r requirements.txt`
- [ ] **Criar conta gratuita em https://console.picovoice.ai/ → obter AccessKey**
- [ ] Instalar Ollama + `ollama pull qwen3.5:9b`
- [ ] Verificar GPU: `ollama ps` após um prompt → `PROCESSOR` deve indicar GPU
- [ ] Implementar `src/audio/capture.py`
  - Loop `sounddevice.InputStream`: 16kHz, 16-bit, mono, `blocksize=512 (32ms)` — callback-based, sem polling
  - `cobra.process(pcm_frame)` aplicado dentro do callback (a cada 32ms)
  - Ring buffer de pré-trigger (~300ms) para não perder o início da fala
  - `cobra = Cobra(access_key=config.COBRA_ACCESS_KEY)` → `cobra.process(pcm_frame)` retorna float 0–1
  - Threshold: `probability >= 0.6` = voz ativa
  - State machine: **TRIGGER** = 5 frames consecutivos de fala (~160ms) abre segmento; **HANGOVER** = 15 frames de silêncio (~480ms) fecha segmento
  - Callback `on_speech_start` disparado em **todo** speech_start (base do barge-in)
  - **No `speech_start`, capturar screenshot do desktop via `mss`** → `self._latest_screenshot` (bytes PNG, thread-safe com `threading.Lock`)
  - Segmento fechado → `vad_segments_q.put()` (descartar segmentos < 250ms)
- [ ] Teste manual: falar no mic → ver segmentos chegando na fila + screenshot salva

**Critérios de aceite**
- Falso-positivo < 2% em 1 minuto de teste (Cobra é superior ao webrtcvad nisso).
- Início da fala preservado (sem clipping do primeiro fonema).
- Screenshot capturada em < 20ms no speech_start.
- Thread de capture roda estável por 5 min sem vazamento de memória.

---

### Dia 2 — Audição: STT com sherpa-onnx

**Objetivo:** Transcrição rápida dos segmentos de voz em CPU.

#### Tarefas

- [ ] Implementar `scripts/download_models.py`
  - Baixar `sherpa-onnx-whisper-small` (int8) → `models/sherpa/`
  - Spike: verificar se existe zipformer streaming pt-BR/multilíngue no catálogo sherpa-onnx; se sim, avaliar como alternativa
- [ ] Implementar `src/stt/recognizer.py`
  - Wrapper de `sherpa_onnx.OfflineRecognizer` (whisper small int8)
  - `transcribe(segment: np.ndarray) -> str` (int16 16kHz → float32 → `AcceptWaveform`)
  - Singleton para carregar o modelo uma única vez
- [ ] Integrar ao pipeline
  - Thread consumidora: `vad_segments_q` → STT → `transcript_q`
  - Filtrar transcrições vazias, < 3 caracteres e alucinações comuns ("...", "Obrigado.", "Legendas")
- [ ] Implementar `scripts/benchmark_latency.py` (p50/p95/p99 por estágio)

**Critérios de aceite**
- Latência p95 < 1s para segmentos de 5s em CPU.
- Qualidade de transcrição pt-BR aceitável (WER percebido baixo em frases comuns).
- Pipeline Capture → STT estável por 10 minutos.

---

### Dia 3 — Cérebro: Ollama Visão + Orchestrator + Pré-carga

**Objetivo:** LLM multimodal respondendo em streaming com pré-carga na VRAM.

#### Tarefas

- [ ] Implementar `src/llm/ollama_client.py`
  - `ollama.AsyncClient` com `stream_chat(messages) -> AsyncGenerator[str]`
  - `messages` inclui screenshot como `images: [base64_string]` (formato Ollama vision)
  - System prompt: "Você é uma assistente de voz concisa que vê o desktop. Responda em no máximo 2 frases, em português."
  - Janela deslizante de histórico (últimos 5 turnos, sem reenviar imagens antigas)
  - `preload(model='qwen3.5:9b', keep_alive=-1)` — envia ping e aguarda warm-up
- [ ] Implementar `src/core/state.py`
  - Enum `AssistantState` (LISTENING/THINKING/SPEAKING) + callbacks de transição para UI
- [ ] Implementar `src/core/pipeline.py`
  - `_consume_transcripts()`: pega `transcript_q` → busca screenshot do capture → envia texto + imagem ao LLM → limpa `_latest_screenshot`
  - `_consume_llm_stream()`: acumula tokens, corta em frases (`. ! ? \n`) → `llm_stream_q`
  - LLM task guardada como `asyncio.Task` (cancelável pelo barge-in)
  - Transições de estado: LISTENING → THINKING → SPEAKING → LISTENING
- [ ] **Bootstrap com pré-carga (em `main.py`)**
  - `preload_ollama()` → `ollama.chat(keep_alive=-1)` → confirma `ollama.ps()`
  - Só inicia UI e pipeline após o modelo estar quente na VRAM
- [ ] Teste: falar algo sobre o que está na tela → ver resposta multimodal no terminal

**Critérios de aceite**
- Primeiro token do LLM em < 900ms após fim da transcrição (Vulkan, pré-carregado).
- Streaming contínuo sem travamentos.
- Histórico mantido corretamente entre turnos (imagem não reenviada nos turnos seguintes).
- Modelo permanece na VRAM durante toda a sessão (verificar via `ollama ps` após 5 min).

---

### Dia 4 — Fala: Piper TTS + Playback + Barge-in

**Objetivo:** Voz sintetizada em streaming com interrupção natural.

#### Tarefas

- [ ] Estender `scripts/download_models.py`: baixar voz Piper `pt_BR-faber-medium` → `models/piper/`
- [ ] Implementar `src/tts/piper_engine.py`
  - Carregar `PiperVoice.load()` uma vez
  - `synthesize_stream(sentence) -> Generator[np.ndarray]`: chunks int16 22.05kHz → `tts_audio_q`
  - Respeitar `interrupt_event` entre frases (aborta síntese restante)
- [ ] Implementar `src/audio/playback.py`
  - Thread com `sounddevice.OutputStream` (casar sample rate com a voz)
  - Lê `tts_audio_q` com timeout → escreve no stream
  - Checa `interrupt_event` a cada chunk (~20ms) → stop + flush imediato
  - Expõe `is_active` para o Interruption Manager
- [ ] Implementar `src/core/interruption.py`
  - State machine de barge-in conforme seção "Lógica de Barge-in"
  - Drain de filas com mutex, lock de reentrada, cancel de LLM task
- [ ] Integração E2E do loop completo
- [ ] Teste de barge-in: interromper 10x seguidas

**Critérios de aceite**
- Primeira sílaba audível em < 2s após fim da fala do usuário.
- Interrupção com latência < 100ms.
- 20 ciclos de barge-in consecutivos sem deadlock ou crash.
- Voz sintetizada inteligível e natural o suficiente.

---

### Dia 5 — Interface: PySide6 + Integração E2E

**Objetivo:** App desktop com feedback visual em tempo real.

#### Tarefas

- [ ] Implementar `src/ui/app.py`
  - Janela PySide6 (~500x300, dark mode QSS)
  - Status badge: "Ouvindo..." / "Pensando..." / "Falando..."
  - Botão mute (pausa capture thread via flag)
  - Label última transcrição + label resposta em streaming
- [ ] Implementar `src/ui/widgets.py`
  - Level meter do mic (RMS dos frames do capture)
  - Indicador de estado com transição suave via QPropertyAnimation
- [ ] Integração UI ↔ Pipeline: callbacks → `Signal.emit()` (thread-safe nativo do Qt) — substitui `root.after()` com mais segurança
- [ ] Implementar `src/main.py`
  - **Pré-carga do LLM**: `preload_ollama()` → `ollama.chat(model='qwen3.5:9b', messages=[...], keep_alive=-1)` → aguarda warm-up → verifica `ollama.ps()` → só então inicia UI
  - Bootstrap: demais modelos carregam em background thread (splash)
  - UI na main thread (Qt event loop) + asyncio loop em thread dedicada
  - Graceful shutdown (fecha streams, mic, GPU, libera modelo Ollama, cancela tasks)
- [ ] Implementar `src/config.py` (todos os hiperparâmetros: thresholds VAD, paths, sample rates, modelo Ollama, voz Piper)
- [ ] Teste E2E: 30 min de uso contínuo

**Critérios de aceite**
- UI responsiva durante todo o pipeline.
- Status reflete estado real com < 100ms de delay.
- 30 min de conversa sem degradação.
- Shutdown libera mic/GPU corretamente.

---

### Dia 6 — Empacotamento: PyInstaller + Inno Setup

**Objetivo:** Instalador Windows profissional e distribuível.

#### Tarefas

- [ ] Spec PyInstaller customizado (`voice_assistant.spec`)
  - `--onedir`, incluir `models/` como data files
  - **Hooks custom para `sherpa_onnx`, `piper` e DLLs do `onnxruntime`** (dependências ocultas clássicas)
  - Incluir `_sounddevice_data` (DLL portaudio)
- [ ] Implementar `scripts/build.ps1`: PyInstaller → `dist/` → Inno Setup
- [ ] `installer/setup.iss`
  - Install dir: `%LOCALAPPDATA%\VoiceAssistant`
  - Detectar Ollama; se ausente, instalar ou guiar download
  - Atalhos Desktop + Start Menu, uninstaller limpo
- [ ] Estratégia Ollama: Opção B (recomendada) — detectar instalação existente + download guiado no primeiro run
- [ ] Teste em máquina limpa (VM)

**Critérios de aceite**
- Instalador funciona em Windows 11 fresh (sem Python).
- First-launch < 30s (modelos cacheados).
- Instalador < 2GB (sem torch, o footprint cai muito vs. plano anterior).
- Uninstaller remove 100% dos arquivos.
- `pip freeze` final: **zero** ocorrências de torch/CUDA.

---

## requirements.txt (Dia 1)

```
# --- Screenshot (C puro) ---
mss>=9.0.0
Pillow>=10.0.0

# --- Audio I/O (PortAudio, mantido ativamente) ---
sounddevice>=0.5.0
numpy>=1.24,<2.0

# --- VAD: Picovoice Cobra (deep-learning, probabilidade 0–1) ---
pvcobra>=2.0.0

# --- STT: sherpa-onnx (ONNX Runtime, sem torch) ---
sherpa-onnx>=1.12.0

# --- TTS: Piper (ONNX) ---
piper-tts==1.3.0

# --- LLM: cliente Ollama (server roda Vulkan/AMD) ---
ollama>=0.4.0

# --- UI ---
PySide6>=6.7.0
```

> Subconjunto mínimo do Dia 1: `pyaudio`, `numpy`, `pvcobra`, `mss`, `Pillow`. O resto pode ser instalado junto — não conflita.

## requirements-dev.txt

```
pytest>=8.0.0
ruff>=0.6.0
mypy>=1.10.0
```

---

## Riscos e Mitigações

| Risco | Probabilidade | Impacto | Mitigação |
|---|---|---|---|
| Ollama cair em CPU (GPU AMD não detectada) | Média | Alto | `ollama ps` p/ verificar; atualizar Ollama; fallback CPU documentado |
| Picovoice AccessKey expirada / limite de uso excedido | Baixa | Alto | Key gratuita cobre 3h/mês de áudio — monitorar no console; fallback para webrtcvad como plano B |
| webrtcvad falso-positivo com ruído ambiente | Alta | Médio | aggressiveness=3, hangover maior, filtro RMS |
| whisper small int8 lento em CPU antiga | Média | Alto | downgrade p/ base/tiny; avaliar zipformer streaming |
| Qwen VL não suportar bem português + visão simultâneos | Baixa | Médio | testar `qwen3.5:4b` como alternativa mais leve; ajustar prompt |
| Voz Piper pt-BR pouco natural | Baixa | Médio | testar outras vozes pt-BR do catálogo Piper |
| DLLs onnxruntime/sherpa ausentes no .exe | Alta | Alto | hooks PyInstaller custom + teste em VM limpa |
| Conflito threads + UI | Médio | Baixo | Qt signals/slots são thread-safe por padrão; nunca acessar widget diretamente de worker thread |
| Tamanho do instalador | Baixa | Baixo | Sem torch: footprint total ~1.5-2GB |

---

## Comandos de Setup Rápido

```powershell
# 1. Ambiente virtual (Python 3.12)
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1

# 2. Dependências
pip install -r requirements.txt

# 3. Picovoice AccessKey (gratuita)
#    Acesse https://console.picovoice.ai/ → crie conta → copie a key
#    Crie a variável de ambiente:
[System.Environment]::SetEnvironmentVariable('PICOCOBRA_ACCESS_KEY', 'sua-key-aqui', 'User')

# 4. Ollama + modelo LLM
winget install Ollama.Ollama
ollama pull qwen3.5:9b

# 5. Modelos STT + voz TTS
python scripts/download_models.py

# 6. Rodar o app
python src/main.py
```

---

## Definição de Pronto (DoD)

- [ ] App roda 1 hora sem crash ou vazamento de memória.
- [ ] Latência E2E (fim da fala → primeira sílaba) < 2.5s.
- [ ] Barge-in funciona 20/20 tentativas consecutivas.
- [ ] Interrupção com latência < 100ms.
- [ ] LLM pré-carregado na VRAM desde o boot (verificado via `ollama ps` em qualquer momento da sessão).
- [ ] Screenshot capturada e enviada ao LLM corretamente no speech_start (resposta contextual ao desktop).
- [ ] Instalador funciona em Windows 11 sem Python pré-instalado.
- [ ] Ollama rodando na GPU AMD (Vulkan) — verificado via `ollama ps`.
- [ ] README com GIF de demonstração + instruções de instalação.
- [ ] Código tipado (mypy clean) e lint (ruff clean).
- [ ] `pip freeze` sem nenhuma dependência torch/CUDA.
- [ ] Modelo permanece na VRAM por toda a sessão (sem unload automático).
