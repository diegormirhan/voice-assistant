# Assistente de Voz Full-Duplex em Tempo Real

> Projeto de portfólio para vagas de Machine Learning Engineering
> Duração estimada: 6 dias | Stack 100% local (Edge AI) | Windows 11

---

## Visão Geral

Assistente de voz conversacional com comportamento **full-duplex** real: o usuário pode interromper a IA a qualquer momento (barge-in natural), a resposta para imediatamente e o sistema volta a escutar. Toda inferência roda **localmente** — sem APIs de nuvem — com latência-alvo de **< 1s** entre o fim da fala do usuário e o início da resposta audível.

### Diferenciais de portfólio
- Demonstração de **engenharia de sistemas assíncronos** (multi-thread + asyncio + queues).
- Pipeline completo de Edge AI: **VAD → STT → LLM → TTS** com streaming em cada etapa.
- Clonagem de voz zero-shot com XTTSv2.
- Empacotamento como produto desktop (.exe + instalador).

---

## Requisitos de Hardware

| Componente | Mínimo | Recomendado |
|---|---|---|
| GPU | NVIDIA 6GB VRAM (GTX 1660) | NVIDIA 8GB+ (RTX 3060/4060) |
| RAM | 16 GB | 32 GB |
| CPU | 6 cores | 8+ cores |
| Disco | 20 GB livres (modelos) | SSD NVMe |
| Microfone | Qualquer USB | Headset dedicado |

> O modelo XTTSv2 + faster-whisper + llama3.2:3b somados consomem ~6-7GB de VRAM com quantização.

---

## Stack Técnico

| Camada | Tecnologia | Justificativa |
|---|---|---|
| VAD | `silero-vad` 5.1 | State-of-the-art em edge, < 2MB, latência ~30ms |
| STT | `faster-whisper` 1.0 (CTranslate2) | 4x mais rápido que Whisper original, quantizado |
| LLM | Ollama (`llama3.2:3b`) | Streaming nativo, modelo otimizado para CPU/GPU |
| TTS | `Coqui-TTS` / XTTSv2 | Clonagem zero-shot, streaming chunk-por-chunk |
| Audio I/O | `PyAudio` + `sounddevice` | PyAudio p/ capture loop; sounddevice p/ playback low-latency |
| UI | `CustomTkinter` | App desktop nativo sem overhead de Electron |
| Orquestração | `asyncio` + `queue.Queue` | Concorrência previsível com barge-in |
| Empacotamento | PyInstaller + Inno Setup | .exe standalone + instalador Windows profissional |

---

## Arquitetura de Threads e Buffers

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         MAIN THREAD (UI)                                │
│                CustomTkinter — render + status flags                    │
└─────────────────────────────┬───────────────────────────────────────────┘
                              │ root.after() thread-safe
                              ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    ASYNCIO EVENT LOOP (dedicated thread)                │
│                                                                         │
│   ┌────────────┐     ┌────────────┐     ┌────────────┐                │
│   │    STT     │────▶│    LLM     │────▶│    TTS     │────▶ playback_q│
│   │faster-whisp│     │ Ollama str │     │  XTTSv2    │                │
│   └─────▲──────┘     └─────┬──────┘     └─────┬──────┘                │
│         │                  │                  │                         │
└─────────┼──────────────────┼──────────────────┼─────────────────────────┘
          │                  │                  │
          │ vad_segments_q   │ llm_stream_q     │ tts_audio_q
          │                  │                  │
┌─────────┴──────────┐ ┌────┴───────┐    ┌─────┴────────┐  ┌────────────┐
│  CAPTURE THREAD    │ │ BARGE-IN   │    │ BARGE-IN     │  │  PLAYBACK  │
│  PyAudio + Silero  │ │ CANCELLER  │    │ INTERRUPT BUS│  │  THREAD    │
│  (blocking I/O)    │ └────────────┘    └──────────────┘  │sounddevice │
└────────────────────┘                                     └────────────┘
```

### Filas (todas `queue.Queue` thread-safe)

| Fila | Produtor | Consumidor | Tipo | Propósito |
|---|---|---|---|---|
| `vad_segments_q` | Capture | STT | `np.ndarray` PCM 16kHz | Áudio segmentado no fim da fala |
| `transcript_q` | STT | Orchestrator | `str` | Texto transcrito do usuário |
| `llm_stream_q` | LLM | TTS | `str` | Tokens agrupados por frase |
| `tts_audio_q` | TTS | Playback | `np.ndarray` PCM 24kHz | Chunks de áudio sintetizado |
| `interrupt_bus` | Silero | Playback + Orchestrator | `Event` | Sinal de barge-in |

### Lógica de Barge-in (interrupção)

1. Silero detecta `speech_start` enquanto `playback.is_active == True`.
2. Seta `interrupt_event.set()` + drena todas as filas (`q.queue.clear()`).
3. Playback thread monitora `interrupt_event` a cada 20ms → `stream.stop()`.
4. Orchestrator cancela task do LLM via `asyncio.Task.cancel()`.
5. Estado global volta para `LISTENING` — propagado à UI via `root.after()`.

**Latência-alvo de interrupção: < 80ms** (janela do Silero + stop do stream).

---

## Estrutura de Pastas

```
voice_assistant/
├── src/
│   ├── __init__.py
│   ├── main.py                  # entry point: uvloop + UI bootstrap
│   ├── config.py                # hiperparâmetros centralizados
│   │
│   ├── audio/
│   │   ├── __init__.py
│   │   ├── capture.py           # PyAudio + Silero VAD (thread dedicada)
│   │   ├── playback.py          # sounddevice stream (thread dedicada)
│   │   └── voice_ref.wav        # voz feminina 5-10s para XTTS clone
│   │
│   ├── stt/
│   │   ├── __init__.py
│   │   └── transcriber.py       # faster-whisper wrapper (large-v3 tiny)
│   │
│   ├── llm/
│   │   ├── __init__.py
│   │   └── ollama_client.py     # streaming async client + prompt system
│   │
│   ├── tts/
│   │   ├── __init__.py
│   │   └── synthesizer.py       # XTTSv2 streaming inference
│   │
│   ├── core/
│   │   ├── __init__.py
│   │   ├── pipeline.py          # orchestrator asyncio principal
│   │   ├── interruption.py      # state machine de barge-in
│   │   └── state.py             # estados globais (LISTENING/THINKING/SPEAKING)
│   │
│   └── ui/
│       ├── __init__.py
│       ├── app.py               # CustomTkinter main window
│       └── widgets.py           # waveform visualizer, status badge
│
├── assets/
│   ├── icons/                   # ícones do app (ico, png)
│   └── voice_samples/           # brutos extraídos do YouTube
│
├── models/                      # cache de modelos (gitignored)
│   ├── silero/
│   ├── whisper/
│   ├── xtts/
│   └── ollama/                  # symlink p/ instalação local do Ollama
│
├── installer/
│   ├── setup.iss                # script Inno Setup
│   └── bundle_ollama.ps1        # empacota binário do Ollama
│
├── scripts/
│   ├── extract_voice.py         # yt-dlp + ffmpeg → voice_ref.wav
│   ├── download_models.py       # warm-up de modelos no primeiro run
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

---

## Plano de Implementação — 6 Dias

---

### Dia 1 — Fundação: Setup + Audio Capture + Silero VAD + Voz de Referência

**Objetivo:** Pipeline de captura de áudio funcionando com segmentação inteligente de fala.

#### Tarefas

- [ ] Criar estrutura de pastas e ambiente virtual (`python -m venv .venv`)
- [ ] Instalar dependências do `requirements.txt` (PyTorch CUDA 12.1)
- [ ] Verificar Ollama instalado + puxar modelo `llama3.2:3b`
- [ ] Implementar `src/audio/capture.py`
  - Loop PyAudio contínuo (16kHz, 16-bit, mono, chunk 512 frames)
  - Integrar Silero VAD via `torch.hub.load('snakers4/silero-vad', 'silero_vad')`
  - Detectar `speech_start` e `speech_end` com thresholds ajustáveis
  - Ao detectar fim de fala → empacotar chunk → `vad_segments_q.put()`
- [ ] Implementar `scripts/extract_voice.py`
  - Baixar áudio dos YouTube links via `yt-dlp`
  - Selecionar trecho limpo 5-10s (feminino, sem trilha)
  - Exportar como `src/audio/voice_ref.wav` (mono, 22050Hz, 16-bit)
- [ ] Teste manual: falar no mic → ver segmentos chegando na fila

**Critérios de aceite**
- Silero segmenta fala real com falso-positivo < 5% em 1 minuto de teste.
- `voice_ref.wav` gerado com qualidade audível (sem clipping, sem ruído).
- Thread de capture roda estável por 5 min sem vazamento de memória.

**Links de referência para extração de voz:**
- https://youtu.be/10cEML9ial0
- https://youtu.be/5RpJCcPo6O4
- https://youtu.be/z5-Hya2Vn_M
- https://youtu.be/QZXE2-sFWxQ

---

### Dia 2 — Audição: STT com faster-whisper

**Objetivo:** Transcrição rápida e precisa dos segmentos de voz.

#### Tarefas

- [ ] Implementar `src/stt/transcriber.py`
  - Wrapper de `faster_whisper.WhisperModel` (modelo `large-v3` com `device="cuda"`)
  - Método `transcribe(audio_chunk) -> str`
  - Parametrizar `beam_size=5`, `language="pt"` (ou `None` p/ auto-detect)
  - Cache de instância do modelo (singleton)
- [ ] Integrar ao pipeline
  - Thread consumidora: `while True: chunk = vad_segments_q.get(); text = stt.transcribe(chunk); transcript_q.put(text)`
  - Filtrar transcrições vazias ou com < 3 caracteres
- [ ] Implementar `scripts/benchmark_latency.py`
  - Medir latência p50/p95/p99 de transcrição
- [ ] Ajustar thresholds do Silero para minimizar chunks parciais

**Critérios de aceite**
- Latência p95 < 800ms para frases de 5 segundos.
- Taxa de erro de transcrição aceitável em português.
- Pipeline Capture → STT estável por 10 minutos.

---

### Dia 3 — Cérebro: Ollama Streaming + Orchestrator

**Objetivo:** LLM respondendo em streaming com prompt system adequado.

#### Tarefas

- [ ] Implementar `src/llm/ollama_client.py`
  - Cliente assíncrono usando `ollama.AsyncClient`
  - Método `stream_chat(messages) -> AsyncGenerator[str]`
  - Prompt system: "Você é uma assistente de voz concisa. Responda em no máximo 2 frases."
  - Histórico de conversa com janela deslizante (últimas 5 interações)
- [ ] Implementar `src/core/pipeline.py`
  - Orchestrator asyncio com tasks:
    - `_consume_transcripts()`: lê `transcript_q` → manda pro LLM
    - `_consume_llm_stream()`: agrupa tokens por frase (`.\n!?`) → `llm_stream_q`
  - Gerenciamento de estado global (`LISTENING` → `THINKING` → `SPEAKING`)
- [ ] Implementar `src/core/state.py`
  - Enum `AssistantState` + callbacks de mudança de estado (para UI)
- [ ] Teste: falar → ver resposta do LLM chegando token a token no terminal

**Critérios de aceite**
- Primeiro token do LLM em < 500ms após fim da transcrição.
- Streaming contínuo sem travamentos.
- Histórico de conversa mantido corretamente entre turnos.

---

### Dia 4 — Fala: XTTSv2 Streaming + Barge-in

**Objetivo:** Voz sintetizada em streaming com interrupção natural.

#### Tarefas

- [ ] Implementar `src/tts/synthesizer.py`
  - Carregar XTTSv2 uma vez (`TTS("tts_models/multilingual/multi-dataset/xtts_v2")`)
  - Carregar `voice_ref.wav` como speaker embedding (clonagem zero-shot)
  - Método `synthesize_stream(text) -> Generator[np.ndarray]`
    - Gera áudio frase por frase
    - Retorna chunks PCM 24kHz prontos para playback
- [ ] Implementar `src/audio/playback.py`
  - Thread com `sounddevice.OutputStream` (24kHz, 16-bit, mono)
  - Lê `tts_audio_q` → escreve chunks no stream
  - Monitora `interrupt_event` a cada 20ms → `stream.stop()` + drain
- [ ] Implementar `src/core/interruption.py`
  - State machine de barge-in:
    - Escuta `interrupt_bus` + `capture.is_speech_active`
    - Coordena: parar playback + drenar filas + cancelar LLM task
  - Lock de reentrada (evita barge-in duplicado)
- [ ] Integração Capture → STT → LLM → TTS → Playback em loop
- [ ] Teste de barge-in: interromper a IA 10x seguidas sem travar

**Critérios de aceite**
- Primeira sílaba audível em < 1.5s após fim da fala do usuário.
- Interrupção (barge-in) com latência < 100ms.
- 20 ciclos de barge-in consecutivos sem deadlock ou crash.
- Voz sintetizada soa natural (sem artefatos audíveis).

---

### Dia 5 — Interface: CustomTkinter + Integração E2E

**Objetivo:** App desktop com feedback visual em tempo real.

#### Tarefas

- [ ] Implementar `src/ui/app.py`
  - janela principal CustomTkinter (500x300, dark mode)
  - Status badge: "Ouvindo..." / "Pensando..." / "Falando..."
  - Botão grande de ativar/desativar microfone (mute toggle)
  - Label com última transcrição do usuário
  - Label com resposta atual (streaming)
- [ ] Implementar `src/ui/widgets.py`
  - Waveform visualizer simplificado (nível de volume do mic)
  - Indicador de estado com transição suave (cores + texto)
- [ ] Integração UI ↔ Pipeline
  - Pipeline emite callbacks de estado → UI via `root.after(50, update_fn)`
  - Botão mute seta flag global que pausa capture thread
- [ ] Implementar `src/main.py` (entry point)
  - Bootstrap: inicializa modelos em background thread (splash screen)
  - Inicia UI na main thread + pipeline em asyncio thread
  - Graceful shutdown (Ctrl+C ou botão fechar)
- [ ] Implementar `src/config.py`
  - Hiperparâmetros centralizados (thresholds, modelo, sample rates)
- [ ] Teste E2E: 30 minutos de uso contínuo sem crash/vazamento

**Critérios de aceite**
- UI responsiva durante todo o pipeline (nunca trava).
- Status reflete estado real do pipeline com < 100ms de delay.
- App suporta 30 min de conversa contínua sem degradação.
- Graceful shutdown libera GPU/mic corretamente.

---

### Dia 6 — Empacotamento: PyInstaller + Inno Setup

**Objetivo:** Instalador Windows profissional e distribuível.

#### Tarefas

- [ ] Configurar PyInstaller
  - Spec file customizado (`voice_assistant.spec`)
    - Incluir modelos locais (Silero, XTTS, Whisper) como data files
    - Incluir `voice_ref.wav` como data file
    - Hook custom para `TTS` e `faster_whisper` (dependências ocultas)
  - Opção `--onedir` (não `--onefile`) para velocidade de launch
- [ ] Implementar `scripts/build.ps1`
  - Build PyInstaller → pasta `dist/voice_assistant/`
  - Copiar binário do Ollama + modelos para pasta de distribuição
  - Gerar `setup.exe` via Inno Setup
- [ ] Configurar Inno Setup (`installer/setup.iss`)
  - Install dir: `%LOCALAPPDATA%\VoiceAssistant`
  - Verificar se Ollama já está instalado; se não, instalar junto
  - Criar atalho no Desktop + Start Menu
  - Uninstaller limpo
- [ ] Estratégia para Ollama (desafio do tamanho)
  - Opção A: empacotar binário do Ollama + modelo na pasta do app (~4GB)
  - Opção B (recomendada): detectar Ollama existente + download guiado na primeira execução
- [ ] Teste em máquina limpa (VM ou PC de colega)

**Critérios de aceite**
- Instalador funciona em Windows 11 fresh (sem Python instalado).
- First-launch < 30s (modelos já cacheados).
- Tamanho do instalador < 5GB (com modelos).
- Uninstaller remove 100% dos arquivos.

---

## Riscos e Mitigações

| Risco | Probabilidade | Impacto | Mitigação |
|---|---|---|---|
| VRAM insuficiente p/ todos os modelos | Média | Alto | Usar `large-v3-turbo` no whisper; quantizar XTTS; fallback p/ CPU no STT |
| PyAudio falha no Windows | Alta | Médio | Ter `sounddevice` como fallback em ambos os lados |
| XTTSv2 primeira inferência lenta | Alta | Médio | Warm-up na inicialização (synth de frase dummy) |
| Ollama crash sob load | Baixa | Alto | Restart automático via subprocess monitor |
| Conflito de threads + UI | Média | Alto | Todo acesso à UI via `root.after()`; nunca acessar widgets de worker threads |
| Tamanho do .exe final > 5GB | Alta | Médio | Usar UPX compression; oferecer "lite installer" sem modelos (download guiado) |

---

## Comandos de Setup Rápido

```powershell
# 1. Criar ambiente virtual
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# 2. Instalar PyTorch com CUDA 12.1
pip install torch==2.3.1+cu121 torchaudio==2.3.1+cu121 --extra-index-url https://download.pytorch.org/whl/cu121

# 3. Instalar dependências
pip install -r requirements.txt

# 4. Instalar Ollama (se ainda não tiver)
winget install Ollama.Ollama

# 5. Baixar modelo LLM
ollama pull llama3.2:3b

# 6. (Opcional) Extrair voz de referência
python scripts/extract_voice.py

# 7. Rodar o app
python src/main.py
```

---

## Estratégia para o LinkedIn

### Post de lançamento (sugestão de estrutura)

1. **Hook**: "Construí um assistente de voz que roda 100% no meu PC — sem nuvem, sem APIs."
2. **Problema**: assistentes de voz dependem de nuvem = latência + privacidade.
3. **Solução**: pipeline Edge AI com VAD + STT + LLM + TTS, full-duplex real.
4. **Demo**: vídeo de 30s mostrando barge-in funcionando.
5. **Stack**: lista curta das tecnologias.
6. **Open source**: link pro repo (se aplicável).
7. **CTA**: "Comentem se querem tutorial detalhado."

### Palavras-chave para atrair recrutadores
`Machine Learning Engineering` · `Edge AI` · `Real-time Systems` · `Python` · `PyTorch` · `LLM` · `Speech Recognition` · `Text-to-Speech` · `Async Systems` · `Production ML`

---

## Definição de Pronto (DoD)

- [ ] App roda 1 hora sem crash ou vazamento de memória/VRAM.
- [ ] Latência E2E (fim da fala → início da resposta audível) < 1.5s.
- [ ] Barge-in funciona 100% das vezes em 20 tentativas consecutivas.
- [ ] Instalador funciona em Windows 11 sem Python pré-instalado.
- [ ] README com GIF de demonstração + instruções de instalação.
- [ ] Código revisado e tipado (mypy clean).