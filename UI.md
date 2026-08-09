# Interface do Assistente de Voz — Especificação

## Ordem de implementação (crítica)

1. **UI primeiro**: a interface é construída e validada ANTES de qualquer
   alteração no backend (audio/speech/servers/core).
2. **Backend só com revisão**: qualquer mudança necessária nos módulos
   existentes (ex: expor RMS do mic no AudioCapture) será feita de forma
   incremental e **revisada pelo usuário** antes de integrar.

## Princípios de design (2026)

- **Glassmorphism**: janela com 50% de transparência + fundo com blur
  (efeito de vidro fosco sobre o desktop).
- **Formas suaves**: cantos arredondados (12–16px), sombras difusas,
  sem bordas duras.
- **Gradientes discretos**: acentos em gradiente (não cor sólida),
  com transição suave entre temas.
- **Micro-interações**: hover com leve escala (1.02), transições
  150–250ms com easing (não linear).
- **Paleta**: tons neutros (fundo) + um acento vibrante por tema
  (violeta no escuro, ciano no claro).

## Janela

- Proporção **4:3**, redimensionável, tamanho inicial sugerido 400x300.
- Transparência 50% + blur de fundo.
- **Temas**: Claro e Escuro (alternáveis, persistidos).
- **Sempre no topo**: configurável (toggle nas configurações).
- **Minimizar para a bandeja** do Windows (ícone), com restauração ao clicar.

## Mapa da janela

```
┌──────────────────────────────────────────────┐
│  ⚙ (engrenagem)  [1] [2] [3]          🗕  ✕  │  ← barra superior
│                                              │
│            ┌─────────────────┐               │
│            │   BOTÃO CENTRAL  │  ← ligar + anel
│            │   (glow reativo) │
│            └─────────────────┘               │
│                                              │
│   ┌──────────────────────────────────────┐   │
│   │  painel de transcrição (colapsável)  │   │
│   └──────────────────────────────────────┘   │
└──────────────────────────────────────────────┘
```

### Barra superior (3 controles)
| # | Controle | Descrição |
|---|----------|-----------|
| 1 | **Baixar binários** | Botão com ícone de download + barra de progresso inline |
| 2 | **Perfil de modelo** | Select: Leve / Padrão + tooltip hover explicando VRAM/tamanho |
| 3 | **Voz / Idioma** | Select: `pt-BR faber` por ora (estrutura extensível) |

### Botão central (coração da UI)
- Botão circular central para **ligar/desligar** o assistente.
- **Anel de glow animado** ao redor, que reage ao áudio em tempo real:
  - **Ouvindo** → pulsa na amplitude do mic (RMS de entrada)
  - **Falando** → pulsa na amplitude do áudio do TTS
  - **Pensando** → glow fixo azul + spinner sutil
  - **Carregando** → animação de loading girando até subir tudo
  - **Desligado** → cinza, estático
- Intensidade do glow = nível de áudio (fala humana no mic / voz do assistente).

### Painel de transcrição
- **Colapsável** (seta para abrir/fechar), só aparece se habilitado nas configurações.
- **Somente da sessão**: ao fechar e reabrir o app, o painel começa vazio.
- Rolável; falas do usuário e do assistente visualmente diferenciadas.

## Modal de configurações (engrenagem, canto superior esquerdo)

| Controle | Tipo |
|---|---|
| `MIN_SPEECH_MS` | Slider (100–1000ms) |
| `HANGOVER_MS` | Slider (300–3000ms) |
| Velocidade TTS (`length_scale`) | Slider (0.8–2.0) |
| `noise_scale` TTS | Slider (0.3–1.0) |
| **Nível do mic** | Barra de volume em tempo real + toggle de mute |
| Visão do desktop (privacidade) | Toggle |
| Painel de transcrição visível | Toggle |
| Sempre no topo | Toggle |
| Tema (Claro / Escuro) | Select |
| Botões | Salvar / Cancelar / Restaurar padrões |

> Mute e nível do mic ficam **nas configurações** (não na tela principal).

## Persistência

- Arquivo `config.json` ao lado do app.
- Salvo ao fechar; carregado no start.
- Campos: tema, volume, thresholds VAD, `length_scale`, `noise_scale`,
  perfil de modelo, toggles (visão, transcrição, sempre no topo).

## Integração com o backend

### Arquitetura da costura (UI ↔ backend)

- **`Bus`** (`ui/state.py`) é o **único** canal entre a UI e o backend.
  É um `QObject` com signals que o backend emite de qualquer thread; o Qt
  enfileira na thread da GUI (queued connections) — a costura thread-safe
  descrita em `ui/state.py`.
- **`ui/backend.py`** é o **adaptador** (Opção A): envolve o
  `core/orchestrator.py` e traduz eventos do orchestrator em signals do
  `Bus`. O `core/` permanece independente de Qt (reutilizável em CLI/testes).
- O **`ui/simulator.py`** é uma fase transitória: emite os mesmos signals
  do `Bus` com dados falsos. **Ao final da implementação do backend, o
  `simulator.py` é apagado** e o `main_window.py` passa a usar o
  `Backend` no lugar (a UI não muda — só troca `Simulator(self.bus, self)`
  por `Backend(self.bus, self)`).

Diagrama de threads:

```
thread do mic (captura/VAD)   thread asyncio (orchestrator)   thread Qt (UI)
┌──────────────────────────┐  ┌────────────────────────────┐  ┌─────────────────┐
│ AudioCapture → VAD       │  │ STT → LLM → TTS → Playback │  │ Bus (signals)   │
│ on_segment/on_speech_start│→│ eventos do orchestrator    │→│ → anel/hint/txt │
└──────────────────────────┘  └────────────────────────────┘  └─────────────────┘
```

### Mapeamento de eventos

| Evento do backend | Signal do `Bus` | Consumidor na UI |
|---|---|---|
| Estado mudou (OFF/LOADING/LISTENING/THINKING/SPEAKING) | `state_changed` | anel de glow, hint, título, título da janela |
| RMS do microfone (entrada) | `mic_level` | glow no botão + `LevelMeter` (configurações) |
| RMS do TTS (saída) | `output_level` | glow no botão (SPEAKING) |
| Transcrição do usuário | `user_said` | painel de transcrição |
| Frase do assistente | `assistant_said` | painel de transcrição |
| Progresso de download (0..100) | `download_progress` | `DownloadButton` |
| Download concluído (ok, msg) | `download_finished` | `DownloadButton` |
| Erro | `error` | hint de status |

### Fluxo de um turno completo

```
fala do usuário
  → VAD segmenta (on_segment)
  → STT transcreve → Bus.user_said.emit(texto)     [transcript]
  → estado THINKING → Bus.state_changed
  → screenshot (se visão habilitada) → LLM stream
  → SentenceBuffer acumula tokens até frase completa
  → TTS sintetiza a frase → Bus.assistant_said.emit(frase)  [transcript]
  → estado SPEAKING → Bus.state_changed
  → Playback toca (Bus.output_level durante a fala)
  → volta a LISTENING
```

### Barge-in

- Mic detecta fala **durante** o playback (`on_speech_start`).
- `Playback.interrupt()` corta o áudio + cancela a task do LLM.
- O `Bus` não precisa de signal próprio: o estado volta a LISTENING e o
  próximo turno começa (a fala que interrompeu vira a nova pergunta).

### Revisões de backend necessárias (cada uma aprovada pelo usuário)

| Módulo | Mudança | Fase |
|---|---|---|
| `audio/capture.py` | Expor RMS por bloco (callback `on_level`) | 2 |
| `audio/playback.py` | Expor RMS de saída (nível do que está tocando) | 5 |
| `scripts/download_binaries.py` | Callback/emissão de progresso (0..100) | 5 |
| `core/orchestrator.py` | Expor callbacks de estado/texto (sem depender do Qt) | 1–4 |

### Implementação por partes (5 fases)

1. **`ui/backend.py`** — adaptador + trocar `Simulator` (esqueleto de estado:
   `start` → LOADING → LISTENING; `stop` → OFF).
2. **Mic level** — `AudioCapture` expõe RMS → `Bus.mic_level` (revisão juntos).
3. **STT → transcript** — transcrever → `Bus.user_said`.
4. **LLM + TTS → estado + transcript** — THINKING/SPEAKING + `assistant_said`.
5. **Output level + download** — RMS de saída + progresso de download.

### Remoção do simulador

- Ao concluir a Fase 5, **apagar `ui/simulator.py`**.
- Trocar em `main_window.py`: `Simulator(self.bus, self)` → `Backend(self.bus, self)`.
- Validar o fluxo real completo (fala → resposta falada → barge-in).

## Estrutura de pastas (UI)

```
ui/
├── __init__.py
├── __main__.py         # python -m ui
├── app.py              # QApplication, AppUserModelID, fonte, ícone
├── main_window.py      # janela frameless + glass card + wiring do Bus + animator
├── window_anim.py      # animações de janela (minimize/restore/close) via Qt
├── app_icon.py         # ícone arredondado multi-tamanho (16–256px) + rim
├── state.py            # AssistantState (enum) + Bus (signals)
├── backend.py          # ADAPTADOR: orchestrator → Bus (substitui simulator)
├── simulator.py        # dados falsos p/ validação (APAGAR ao final)
├── theme.py            # Tokens (T) + Palette dark/light + palette_for()
├── qss.py              # build_qss(palette) — estilos centralizados
├── config_store.py     # config.json (sanitize/load/save atômicos)
├── effects.py          # DWM: acrylic, cantos, dark mode, minimizar
├── assets.py           # resolução de assets (symlink/PyInstaller)
├── icons.py            # ícones desenhados (gear, download, check, chip, waveform…)
├── icon.ico / icon.jpg
├── widgets/
│   ├── __init__.py
│   ├── title_bar.py        # barra superior (gear, download, selects, ⓘ, controles)
│   ├── select.py           # PillSelect — combo pill com glyph + chevron pintado
│   ├── center_button.py    # botão circular + hover + logo (icon.jpg)
│   ├── status_ring.py      # renderização do glow/anel por estado (limit-aware)
│   ├── backdrop.py         # liquid-glass: blobs azul/roxo animados + vignette
│   ├── download_button.py  # pill com progresso inline
│   ├── level_meter.py      # medidor de nível segmentado (mic/TTS)
│   ├── toggle_switch.py    # toggle animado acessível
│   └── transcript.py       # painel colapsável de transcrição (bubbles)
└── modals/
    ├── __init__.py
    ├── settings.py         # modal de configurações (scroll + live preview)
    └── info.py             # modal explicativo "Perfil e voz"
```

## Notas de implementação

- Primeira etapa: **apenas a UI** (sem tocar no backend), com dados
  simulados para validar visual/animações.
- Toda mudança no backend (RMS do mic, eventos de estado) passa por
  **revisão do usuário** antes de ser aplicada.
- Ao final, **`ui/simulator.py` é apagado** e o `Backend` assume.
