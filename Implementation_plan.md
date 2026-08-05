# Assistente de Voz Full-Duplex em Tempo Real — Stack GGML/Vulkan Unificada

> Projeto de portfólio para vagas de Machine Learning Engineering
> Duração estimada: 6 dias | Stack 100% local (Edge AI) | Windows 11 | GPU AMD

---

## Visão Geral

Assistente de voz conversacional **full-duplex + visão** real: o usuário pode interromper a IA a qualquer momento (barge-in natural) e o sistema **vê o desktop** no instante da fala para responder com contexto visual. Todo o pipeline roda **localmente** — sem nuvem, sem chaves — com latência-alvo de **< 2s** entre o fim da fala e o início da resposta audível.

### Decisão arquitetural central: GGML/Vulkan unificado

Todos os modelos de inferência pesada rodam na **mesma infraestrutura**: a biblioteca C++ **ggml** com backend **Vulkan** — cross-vendor (AMD, NVIDIA, Intel) e nativo no Windows sem WSL.

- **STT + VAD**: `whisper.cpp` (whisper-server, Vulkan)
- **LLM (texto + visão)**: `llama.cpp` (llama-server, Vulkan)
- **TTS**: Kokoro (82M, CPU) — leve o suficiente pra rodar em CPU com qualidade alta

Esses servidores C++ rodam como **processos separados** (subprocesses) orquestrados por um Python limpo via HTTP. Isso permite empacotar o app Windows com os binários nativos prontos — sem dependências Python frágeis, sem torch, sem CUDA.

### Diferenciais de portfólio
- **Engenharia de sistemas**: orchestrator asyncio + subprocesses de servidores C++ + barge-in consistente.
- Pipeline Edge AI multimodal **sem PyTorch/CUDA**: VAD+STT (ggml) → Screenshot + LLM (ggml/Vulkan) → TTS (Kokoro).
- **Uma infraestrutura GPU só** (Vulkan) para STT e LLM — decisão arquitetural limpa e portável.
- Empacotamento como produto desktop (.exe + instalador) com binários nativos Vulkan.

---

## Restrição Crítica de Hardware

- GPU **AMD** (sem CUDA), **sem WSL**, Windows 11 nativo.
- **PROIBIDO**: `torch`, `tensorflow`, `jax` ou qualquer dependência que puxe CUDA no pipeline.
- Inferência via **GGML + Vulkan** (C++ nativo, cross-vendor).

### Onde cada modelo roda (decisão arquitetural)

| Componente | Backend | Dispositivo | Justificativa |
|---|---|---|---|
| Screenshot | `mss` (C) | CPU | Captura de tela em ~5ms; sem GPU |
| VAD | Silero-VAD (ggml, embutido no whisper.cpp) | **GPU (Vulkan)** | Vem junto do whisper.cpp (`--vad`); ~864KB |
| STT | whisper.cpp (ggml) | **GPU (Vulkan)** | streaming real, multilingue (pt-BR), sem janela fixa de 30s |
| LLM (visão) | llama.cpp (ggml) | **GPU (Vulkan)** | qwen3.5:9b Q4 (~5.5GB); pré-carregado na VRAM |
| TTS | Kokoro (82M) | CPU | 82M params; pt-BR; qualidade alta; CPU com folga |

> **A aceleração em GPU cobre STT e LLM** — os dois gargalos. O TTS (82M) roda em CPU sem comprometer o orçamento. Vulkan é o backend cross-vendor: os mesmos binários funcionam em AMD, NVIDIA e Intel.

> **Modelo pré-carregado na VRAM**: o `llama-server` carrega o modelo na inicialização e permanece residente durante a sessão (`--n-gpu-layers` máximo). Sem cold-start entre turnos.

---

## Stack Técnico

| Camada | Tecnologia | Justificativa |
|---|---|---|
| VAD + STT | `whisper.cpp` (whisper-server) | GGML + Vulkan; streaming; VAD Silero embutido; multilingue |
| LLM | `llama.cpp` (llama-server) | GGML + Vulkan; texto + visão (qwen3.5:9b); pré-carregado |
| TTS | Kokoro (`kokoro` 82M) | Apache-2.0; pt-BR; qualidade alta; CPU leve |
| Screenshot | `mss` (C) + `Pillow` | Captura ~5ms; resize antes de enviar ao LLM |
| Audio I/O | `sounddevice` | Capture + playback unificados via PortAudio; callback-based |
| Orquestração | `asyncio` + `queue.Queue` + `threading.Event` | Concorrência previsível com barge-in |
| UI | `PySide6` | Qt profissional: QSS, animações, signals/slots thread-safe |
| Binários nativos | CMake + `-DGGML_VULKAN=1` | Compila whisper-server/llama-server Vulkan uma vez; distribui no app |
| Empacotamento | PyInstaller + Inno Setup | .exe standalone + instalador Windows |

**Python: 3.12** — wheels garantidos para `sounddevice`, `Pillow`, `PySide6`, `kokoro`; sem a restrição do torch-directml.

---

## Arquitetura de Processos e Threads

```
┌──────────────────────────────────────────────────────────────────────┐
│                          PYTHON APP                                  │
│                                                                      │
│  ┌─────────────────────┐         ┌──────────────────────────────┐    │
│  │   UI (PySide6)      │◀────────│      ORCHESTRATOR (asyncio)  │    │
│  │   main thread       │ signals │  - state machine             │    │
│  └─────────────────────┘         │  - coordena filas/eventos    │    │
│                                  │  - barge-in                  │    │
│  ┌─────────────────────┐         └──────────────┬───────────────┘    │
│  │  audio/capture.py   │ mic → STT              │                    │
│  │  (sounddevice)      │      │                 │                    │
│  └─────────────────────┘      ▼                 ▼                    │
└──────────────────────────────────────────────────────────────────────┘
                │                                   │
                │  HTTP streaming                   │  HTTP streaming (visão + texto)
                ▼                                   ▼
┌───────────────────────────┐        ┌──────────────────────────────┐
│   whisper-server.exe      │        │      llama-server.exe        │
│   (C++ ggml, Vulkan)      │        │      (C++ ggml, Vulkan)      │
│   - VAD embutido          │        │      - qwen3.5:9b Q4         │
│   - STT streaming         │        │      - visão + texto         │
└───────────────────────────┘        └──────────────┬───────────────┘
                                                    │ frases (streaming)
                                                    ▼
┌──────────────────────────────────────────────────────────────────────┐
│   speech/tts.py (Kokoro, CPU) → áudio → audio/playback.py (sounddevice)│
└──────────────────────────────────────────────────────────────────────┘
```

### Processos (3)

| Processo | Binário | Backend | Porta (default) | Papel |
|---|---|---|---|---|
| whisper-server | `whisper-server.exe` | Vulkan | 9991 | VAD + STT streaming |
| llama-server | `llama-server.exe` | Vulkan | 9992 | LLM texto + visão |
| Python app | `main.py` | — | — | UI + orchestrator + TTS |

### Threads do app Python (5)

| Thread | Loop | Bloqueio | Responsabilidade |
|---|---|---|---|
| Main | Qt event loop | signals | render UI |
| Capture | `sd.InputStream(callback)` | callback | mic → manda p/ whisper-server |
| STT consumer | `httpx` streaming | I/O | recebe transcrições do whisper-server |
| LLM consumer | `httpx` streaming | I/O | recebe frases do llama-server → Kokoro |
| Playback | `tts_q.get(timeout)` | fila + stream | escreve áudio, monitora interrupt |

### Filas (todas `queue.Queue` thread-safe)

| Fila | Produtor | Consumidor | Payload | Propósito |
|---|---|---|---|---|
| `stt_lines_q` | STT consumer | Orchestrator | `str` | linha transcrita completa |
| `llm_sentence_q` | Orchestrator (LLM) | TTS | `str` | frase pronta p/ síntese |
| `tts_audio_q` | TTS | Playback | `np.ndarray` int16 | chunks de áudio |
| `interrupt_event` | Capture/VAD | Playback + Orchestrator | `threading.Event` | sinal de barge-in |

### Lógica de Barge-in

1. Capture manda áudio ao whisper-server continuamente (full-duplex real).
2. O VAD embutido (Silero) detecta `speech_start` **durante playback** → barge-in.
3. Protocolo: `interrupt_event.set()` → drena `tts_audio_q` → playback para no próximo chunk (< 20ms) → `asyncio.Task.cancel()` no LLM → TTS aborta frase corrente.
4. A fala que causou o barge-in **não é descartada** — vira a nova pergunta.
5. Estado global → `LISTENING`, propagado à UI via signals/slots.

**Latência-alvo de interrupção: < 100ms.**

### Orçamento de latência (E2E)

| Estágio | Alvo |
|---|---|
| VAD endpoint | < 100ms |
| STT (whisper.cpp, Vulkan, segmento 3-6s) | 200–600ms |
| LLM primeiro token (llama.cpp Vulkan, pré-carregado) | 200–500ms |
| TTS primeira frase (Kokoro, CPU) | 150–300ms |
| **E2E (fim da fala → primeira sílaba)** | **< 2s** |

---

## Estratégia de Distribuição (GitHub + HuggingFace)

O repositório GitHub guarda **apenas o código** (Python + scripts + configs). Tudo que é pesado fica fora:

| Artefato | Onde fica | Por quê |
|---|---|---|
| Código Python | GitHub (repo) | leve (~1MB) |
| Binários Vulkan (`whisper-server.exe`, `llama-server.exe`, `ggml-vulkan.dll`) | **HuggingFace** (repo privado/público) | 200-400MB; compilados com Vulkan por você |
| Modelos GGUF/ggml | **HuggingFace** (repos oficiais unsloth/jc-builds) | ~6.7GB; não versionar |
| Voz Kokoro | HuggingFace | ~200MB |

- `.gitignore` bloqueia `bin/` e `models/`.
- **First-run**: o app baixa binários + modelos automaticamente com barra de progresso.
- Licenças: binários whisper.cpp/llama.cpp são MIT (redistribuíveis); modelos Qwen3.5 e Kokoro permitem redistribuição com atribuição.

### Seleção de modelo conforme VRAM

No first-run, o app **detecta a VRAM da GPU** (via Vulkan) e oferece escolha ao usuário:

| Perfil | VRAM mínima | LLM | STT (whisper) | TTS |
|---|---|---|---|---|
| **Leve** | 4GB | Qwen3.5-4B Q4 (~2.5GB) | `base` ggml (~142MB) | Kokoro |
| **Recomendado** | 8GB | Qwen3.5-9B Q4 (~5.5GB) | `small` ggml (~466MB) | Kokoro |

- Detecção automática: ler VRAM via Vulkan API e sugerir perfil padrão.
- Usuário pode trocar manualmente (botão "modelo leve / padrão").
- `models.py` baixa **apenas** o perfil escolhido (evita download desnecessário).
- Se a VRAM for insuficiente no perfil escolhido, avisa e oferece o menor.

---

## Estrutura de Pastas

```
voice-assistant/
├── src/
│   ├── __init__.py
│   ├── main.py                  # entry: sobe servidores → orchestrator + UI
│   ├── config.py                # hiperparâmetros centralizados
│   │
│   ├── core/
│   │   ├── __init__.py
│   │   ├── events.py            # filas + callbacks tipados
│   │   ├── state.py             # AssistantState (LISTENING/THINKING/SPEAKING)
│   │   └── orchestrator.py      # coordena tudo via asyncio
│   │
│   ├── servers/
│   │   ├── __init__.py
│   │   ├── whisper.py           # gerencia whisper-server (subprocess + HTTP)
│   │   ├── llama.py             # gerencia llama-server (subprocess + HTTP)
│   │   └── models.py            # download/verificação dos modelos ggml
│   │
│   ├── speech/
│   │   ├── __init__.py
│   │   ├── stt.py               # cliente HTTP do whisper-server
│   │   └── tts.py               # Kokoro (CPU) — síntese por frase
│   │
│   ├── vision/
│   │   ├── __init__.py
│   │   └── screenshot.py        # mss + resize (imagem pro LLM)
│   │
│   ├── audio/
│   │   ├── __init__.py
│   │   ├── capture.py           # sounddevice mic input
│   │   └── playback.py          # sounddevice output
│   │
│   └── ui/
│       ├── __init__.py
│       └── app.py               # PySide6 main window
│
├── bin/                         # binários nativos (gitignored)
│   ├── whisper-server.exe
│   ├── llama-server.exe
│   └── *.dll                    # ggml, ggml-vulkan, etc.
│
├── models/                      # cache de modelos (gitignored)
│   ├── whisper/                 # modelos ggml do whisper.cpp
│   └── llm/                     # modelo Q4 do llama.cpp
│
├── installer/
│   ├── setup.iss                # script Inno Setup
│   └── bundle.ps1               # copia binários + modelos
│
├── scripts/
│   ├── download_models.py       # baixa modelos ggml (whisper + llm) conforme VRAM
│   ├── download_binaries.py     # baixa binários Vulkan do HuggingFace
│   ├── build_vulkan.ps1         # compila whisper.cpp + llama.cpp com Vulkan
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

> Mudanças vs. plano anterior (sherpa/piper/ollama): VAD e STT viram `servers/whisper.py` + `speech/stt.py`; `llm/ollama_client` vira `servers/llama.py`; `tts/piper_engine` vira `speech/tts.py` (Kokoro); binários nativos ficam em `bin/`.

---

## Plano de Implementação — 6 Dias

---

### Dia 0 — Toolchain + Compilação Vulkan

**Objetivo:** Binários nativos Vulkan prontos e funcionando no gfx1201.

#### Tarefas

- [ ] Instalar VS Build Tools (workload C++): `winget install Microsoft.VisualStudio.2022.BuildTools`
- [ ] Instalar Vulkan SDK: `winget install KhronosGroup.VulkanSDK`
- [ ] Instalar CMake: `winget install Kitware.CMake`
- [ ] Clonar e compilar `whisper.cpp`: `cmake -B build -DGGML_VULKAN=1` → `whisper-server.exe` + `ggml-vulkan.dll`
- [ ] Clonar e compilar `llama.cpp`: mesma flag → `llama-server.exe`
- [ ] Copiar binários + DLLs para `bin/`
- [ ] **Validar**: rodar whisper-server e confirmar no log que o backend Vulkan carregou (não CPU)
- [ ] Baixar modelos ggml (whisper small multilingue + qwen3.5:9b Q4) para `models/`
- [ ] **Publicar binários no HuggingFace**: criar repo privado e subir `whisper-server.exe`, `llama-server.exe`, `ggml-vulkan.dll`, etc.
- [ ] Implementar `scripts/download_binaries.py`: baixa os binários do HF se ausentes (verifica hash, retoma download)
- [ ] Implementar `servers/models.py`: detecção de VRAM via Vulkan → seleção de perfil (leve 4B / padrão 9B)

**Critérios de aceite**
- `whisper-server` loga `ggml_vulkan: ... initialized` (ou equivalente) ao iniciar.
- `llama-server` loga Vulkan/GPU offload ao carregar o modelo.
- Ambos respondem a uma requisição HTTP de teste.

---

### Dia 1 — Captura + VAD + STT streaming (whisper.cpp)

**Objetivo:** Fala no mic → transcrição em streaming via whisper-server Vulkan.

#### Tarefas

- [ ] `scripts/download_models.py`: baixa modelo whisper ggml (multilingue) para `models/whisper/`
- [ ] `servers/whisper.py`: sobe `whisper-server.exe` como subprocess; verifica porta; restart automático se cair
- [ ] `audio/capture.py`: sounddevice InputStream (16kHz, int16) → manda chunks p/ whisper-server
- [ ] `speech/stt.py`: cliente HTTP streaming; recebe linhas transcritas; expõe callback `on_line(text)`
- [ ] Teste: falar → ver transcrições chegando em tempo real no terminal

**Critérios de aceite**
- Primeira transcrição parcial < 500ms após começar a falar.
- pt-BR transcrito com precisão aceitável.
- whisper-server estável por 10 min sem crash.

---

### Dia 2 — LLM via llama.cpp (texto + visão)

**Objetivo:** LLM respondendo em streaming com contexto visual.

#### Tarefas

- [ ] `scripts/download_models.py`: baixa qwen3.5:9b Q4 (formato gguf) para `models/llm/`
- [ ] `servers/llama.py`: sobe `llama-server.exe` (Vulkan, `--n-gpu-layers` máximo, modelo pré-carregado)
- [ ] `vision/screenshot.py`: `mss` captura desktop → resize 768px → base64
- [ ] Cliente LLM: POST /completion (ou /chat) com texto + imagem; streaming de tokens
- [ ] System prompt conciso: "assistente de voz que vê o desktop; responda em no máx. 2 frases"
- [ ] Teste: falar → ver resposta do LLM token a token no terminal

**Critérios de aceite**
- Primeiro token < 500ms com modelo pré-carregado (Vulkan).
- Imagem da tela enviada e compreendida pelo modelo.
- Histórico com janela deslizante (últimas 5 interações), sem reenviar imagens antigas.

---

### Dia 3 — Orchestrator asyncio + Barge-in

**Objetivo:** Coordenação completa com interrupção natural.

#### Tarefas

- [ ] `core/state.py`: enum `AssistantState` (LISTENING/THINKING/SPEAKING) + callbacks
- [ ] `core/events.py`: filas + callbacks tipados (on_line, on_sentence, on_state_change)
- [ ] `core/orchestrator.py`: coordena capture → STT → LLM → TTS → playback; gerencia `interrupt_event`
- [ ] Barge-in: speech_start durante playback → drena filas + cancela task LLM
- [ ] Teste: loop completo + interromper 10x seguidas sem travar

**Critérios de aceite**
- E2E < 2s (fim da fala → primeira sílaba).
- Barge-in < 100ms; 20 ciclos consecutivos sem deadlock.
- Estado correto propagado via callbacks.

---

### Dia 4 — TTS (Kokoro) + Playback

**Objetivo:** Voz sintetizada em streaming.

#### Tarefas

- [ ] `speech/tts.py`: Kokoro (pt-BR), `synthesize_stream(sentence) -> np.ndarray`
- [ ] `audio/playback.py`: sounddevice OutputStream; lê `tts_audio_q`; monitora `interrupt_event`
- [ ] Kokoro sintetiza frase por frase conforme chegam do LLM (streaming real)
- [ ] Teste: resposta falada por completo

**Critérios de aceite**
- Primeira sílaba < 300ms após a primeira frase do LLM.
- Voz pt-BR inteligível e natural.
- Interrupção corta o áudio imediatamente.

---

### Dia 5 — Integração E2E + UI (PySide6)

**Objetivo:** App desktop completo com feedback visual em tempo real.

#### Tarefas

- [ ] `ui/app.py`: janela PySide6 dark; status badge (Ouvindo/Pensando/Falando); mute toggle
- [ ] `ui` ↔ orchestrator via signals/slots (Qt thread-safe)
- [ ] `main.py`: bootstrap (sobe servidores, preload modelo, splash) + graceful shutdown
- [ ] `config.py`: todos os hiperparâmetros centralizados
- [ ] Teste E2E: 30 min de uso contínuo

**Critérios de aceite**
- UI responsiva durante todo o pipeline.
- Status reflete estado real com < 100ms de delay.
- 30 min sem degradação; shutdown libera GPU/mic corretamente.

---

### Dia 6 — Empacotamento: PyInstaller + Inno Setup

**Objetivo:** Instalador Windows profissional.

#### Tarefas

- [ ] Spec PyInstaller: incluir `bin/` (binários Vulkan) como data files; hooks p/ `kokoro`
- [ ] `scripts/build.ps1`: PyInstaller → `dist/` → Inno Setup
- [ ] `installer/setup.iss`: `%LOCALAPPDATA%\VoiceAssistant`; atalhos; uninstaller limpo
- [ ] Estratégia de distribuição: detectar Vulkan runtime (presente nos drivers AMD/NVIDIA/Intel modernos)
- [ ] **First-run flow**: splash com barra de progresso baixando binários + modelos (perfil conforme VRAM)
- [ ] **Instalador leve**: sem modelos embutidos (~100MB); modelos baixados no first-run do HuggingFace
- [ ] Teste em máquina limpa (VM)

**Critérios de aceite**
- Instalador funciona em Windows 11 fresh (sem Python).
- Vulkan detectado corretamente em GPUs variadas (AMD/NVIDIA/Intel).
- Instalador leve (~100MB, sem modelos); first-run baixa só o perfil escolhido (leve ~2.5GB / padrão ~6GB).
- Seleção de modelo por VRAM funciona: detecta e sugere perfil, permite troca manual.
- Uninstaller remove 100% dos arquivos.

---

## requirements.txt (referência)

```
# Audio I/O
sounddevice>=0.5.0
numpy>=1.24,<2.0

# Screenshot
mss>=10.0.0
Pillow>=10.0.0

# TTS (Kokoro)
kokoro>=0.9.4

# HTTP clients (servidores)
httpx>=0.27.0

# UI
PySide6>=6.7.0
```

> Subconjunto mínimo do Dia 1: `sounddevice`, `numpy`, `httpx`. O resto pode ser instalado junto.

---

## Riscos e Mitigações

| Risco | Probabilidade | Impacto | Mitigação |
|---|---|---|---|
| Vulkan não inicializar no gfx1201 | Média | Alto | Testar no Dia 0; fallback para HIP/ROCm ou CPU documentado |
| Compilação C++ falha no Windows | Média | Alto | Seguir guia do whisper.cpp; usar VS Build Tools + Vulkan SDK; logs |
| whisper.cpp VAD/STT pt-BR ruim | Média | Médio | Modelo multilingue; ajustar `--vad-threshold` e `--language pt` |
| Kokoro pt-BR precisa de espeak-ng | Baixa | Médio | Instalar espeak-ng (MSI) ou usar voz Kokoro pt-br dedicada |
| llama.cpp visão (mmproj) complicado | Média | Médio | Usar modelo Q4 com mmproj do mesmo release; testar no Dia 2 |
| DLLs Vulkan ausentes no instalador | Média | Alto | Incluir `ggml-vulkan.dll` + testar em VM limpa |
| Conflito threads + UI | Baixa | Baixo | Qt signals/slots são thread-safe por padrão |
| Barge-in com VAD do whisper-server | Média | Alto | Monitorar evento de speech_start; fallback para VAD próprio |
| Download first-run falha (rede/quota HF) | Média | Alto | Retomar download; verificar hash; fallback para espelho/URL alternativo |
| VRAM insuficiente no perfil escolhido | Média | Médio | Detecção de VRAM via Vulkan; sugerir perfil leve; aviso claro |
| Binários não versionados quebram o app | Baixa | Alto | Hash verificado no download; versão fixa no repo HF; changelog |

---

## Comandos de Setup Rápido

```powershell
# 1. Toolchain (uma vez)
winget install Microsoft.VisualStudio.2022.BuildTools --override "--wait --quiet --add Microsoft.VisualStudio.Workload.VCTools --includeRecommended"
winget install KhronosGroup.VulkanSDK
winget install Kitware.CMake

# 2. Compilar whisper.cpp + llama.cpp (Vulkan)
git clone https://github.com/ggml-org/whisper.cpp && cd whisper.cpp
cmake -B build -DGGML_VULKAN=1 -DCMAKE_BUILD_TYPE=Release
cmake --build build --config Release -j
git clone https://github.com/ggml-org/llama.cpp && cd llama.cpp
cmake -B build -DGGML_VULKAN=1 -DCMAKE_BUILD_TYPE=Release
cmake --build build --config Release -j

# 3. Copiar binários para bin/
# (whisper-server.exe, llama-server.exe + ggml*.dll)

# 4. Ambiente Python 3.12
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

# 5. Baixar modelos
python scripts/download_models.py

# 6. Rodar o app
python src/main.py
```

---

## Definição de Pronto (DoD)

- [ ] App roda 1 hora sem crash ou vazamento de memória.
- [ ] Latência E2E (fim da fala → primeira sílaba) < 2s.
- [ ] Barge-in funciona 20/20 tentativas consecutivas.
- [ ] Interrupção com latência < 100ms.
- [ ] STT e LLM rodando na GPU via Vulkan (verificado no log dos servidores).
- [ ] Screenshot capturada e enviada ao LLM corretamente no speech_start.
- [ ] Instalador funciona em Windows 11 sem Python pré-instalado.
- [ ] Vulkan detectado corretamente em GPUs variadas (AMD/NVIDIA/Intel).
- [ ] README com GIF de demonstração + instruções de instalação.
- [ ] Código tipado (mypy clean) e lint (ruff clean).
- [ ] `pip freeze` sem nenhuma dependência torch/CUDA no pipeline.
