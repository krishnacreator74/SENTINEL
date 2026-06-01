# Hikari — Technical Requirements Document (TRD)
**Version:** 1.0  
**Status:** Approved  

---

## 1. Tech Stack

### Core (inherited from Sentinel 1.0)
| Component | Technology |
|---|---|
| Language | Python 3.11+ |
| UI Framework | PyQt6 |
| STT | OpenAI Whisper (local) |
| TTS | Piper TTS (local) |
| LLM Interface | LM Studio (local server, OpenAI-compatible API) |
| HTTP Client | httpx |
| Threading | Python threading + Qt signals (UIBridge pattern) |

### New in Hikari
| Component | Technology |
|---|---|
| Minecraft Bot | Mineflayer (Node.js) |
| Bot Bridge | Python socket ↔ Node.js socket (localhost:25566) |
| Memory Storage | JSON files (structured, human-readable) |
| Background Worker | Qwen 1.7B via LM Studio (separate API call) |
| Voice Recognition | Whisper speaker diarization + numpy voice profile |
| Log Watching | Python watchdog library (file system events) |

### Models
| Model | Role | VRAM |
|---|---|---|
| Qwen 3 9B (primary) | Hikari personality, all responses | ~6GB |
| Qwen 3 1.7B (worker) | Memory summarization, routing, bookkeeping | ~2GB |
| Fallback option | Llama 3 8B or MythoMax 13B if Qwen breaks character | varies |

---

## 2. System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        HIKARI CORE                         │
│                                                             │
│  ┌─────────┐    ┌──────────┐    ┌─────────────────────┐   │
│  │  Voice  │    │  State   │    │   Prompt Builder    │   │
│  │  Loop   │───►│ Machine  │───►│  (dynamic assembly) │   │
│  │         │    │          │    └──────────┬──────────┘   │
│  └────┬────┘    └──────────┘               │               │
│       │                                    ▼               │
│  ┌────▼────┐                    ┌──────────────────────┐   │
│  │ Whisper │                    │    LM Studio API     │   │
│  │  STT    │                    │    Qwen 3 9B         │   │
│  └────┬────┘                    └──────────┬───────────┘   │
│       │                                    │               │
│  ┌────▼────┐                    ┌──────────▼───────────┐   │
│  │  Piper  │◄───────────────────│   Response Handler   │   │
│  │  TTS    │                    └──────────────────────┘   │
│  └─────────┘                                               │
└─────────────────────────────────────────────────────────────┘
         │                              │
         ▼                              ▼
┌─────────────────┐          ┌──────────────────────┐
│  Memory System  │          │   Minecraft Plugin   │
│                 │          │                      │
│  Layer 1 (RAM)  │          │  log_watcher.py      │
│  Layer 2 (JSON) │          │  event_parser.py     │
│  Layer 3 (JSON) │          │  event_handler.py    │
│                 │          │  game_state.py       │
│  1.7B Worker    │          │  mc_memory.py        │
└─────────────────┘          └──────────┬───────────┘
                                        │
                                        ▼
                             ┌──────────────────────┐
                             │   Mineflayer Bridge  │
                             │   (Phase 3 only)     │
                             │                      │
                             │  bridge.py (Python)  │
                             │  bot.js (Node.js)    │
                             └──────────────────────┘
```

---

## 3. Conversation State Machine

### States
```
IDLE        → Aware, passive, occasional unprompted comments
LISTENING   → Wake word triggered, waiting for input
CONVERSATION→ Back and forth, no wake word needed between turns
MINECRAFT   → Game running, watching log, reacting to events
STRANGER    → Unknown voice detected, cold mode enforced
```

### Transitions
```
IDLE ──── "Hikari" wake word ────────→ LISTENING
IDLE ──── minecraft.exe detected ────→ MINECRAFT
IDLE ──── unprompted timer fires ────→ speaks → IDLE

LISTENING ──── input received ───────→ CONVERSATION
LISTENING ──── 5s silence ───────────→ IDLE

CONVERSATION ──── 30s silence ───────→ IDLE
CONVERSATION ──── game focused ──────→ MINECRAFT (retains conversation)

MINECRAFT ──── death event ──────────→ she reacts via personality (not a state)
MINECRAFT ──── "Hikari" wake word ───→ CONVERSATION
MINECRAFT ──── game closes ──────────→ IDLE

ANY ──── unknown voice ──────────────→ STRANGER
STRANGER ──── owner voice confirmed─→ previous state restored
```

### Unprompted System
- Idle timer fires randomly between 10-30 minutes
- Checks current context (time, game state, last interaction)
- Low-priority LLM call generates an unprompted comment
- She just speaks — no wake word, no prompt from user
- Examples: noticing you've been playing 3 hours, commenting on weather in game, reacting to time of day

---

## 4. Dynamic Prompt Builder

### Assembly Order
```python
def build_hikari_prompt(state: str, game_context: str = None) -> str:
    core    = load_core_memory()       # Layer 3
    recent  = load_last_3_episodes()   # Layer 2
    session = load_current_session()   # Layer 1
    arc     = load_arc_behavior(core.arc_level)

    sections = [
        IDENTITY_BLOCK,                # static
        PERSONALITY_CORE_BLOCK,        # static
        arc,                           # dynamic — changes per arc level
        build_owner_context(core),     # dynamic — from Layer 3
        build_recent_history(recent),  # dynamic — from Layer 2
        build_right_now(session),      # dynamic — from Layer 1
        build_game_context(game_context) if game_context else "",  # dynamic — MC only
        RESPONSE_RULES_BLOCK,          # static
    ]
    return "\n\n".join(filter(None, sections))
```

---

## 5. Memory System — File Structure

```
memory/
├── layer1_session.json       # wiped each session, RAM-backed
├── layer2_episodes.json      # last 30 days, compressed weekly
├── layer3_core.json          # permanent, never wiped
└── worker/
    └── worker_prompts.py     # 1.7B worker task prompts
```

---

## 6. Minecraft Plugin — Technical Spec

### Log Watcher
```python
# Uses watchdog library
# Tails %APPDATA%/.minecraft/logs/latest.log
# Fires events via Emitter system (existing Sentinel pattern)
```

### Event Priority System
```
PRIORITY 1 — Immediate unprompted reaction
  Patterns: "was slain", "fell from", "drowned", "burned",
            "has made the advancement [The End]",
            "entered the Nether"

PRIORITY 2 — Added to context, mentioned if asked
  Patterns: weather changes, minor advancements, sleep

PRIORITY 3 — Silent context update only
  Patterns: chat, general game state
```

### Mineflayer Bridge Protocol (Phase 3)
```json
// Python → Node.js command
{
  "action": "mine | attack | goto | craft | follow | report",
  "target": "string or coordinates",
  "priority": "high | normal | low"
}

// Node.js → Python event
{
  "event": "arrived | completed | failed | obstacle | health_low",
  "data": {}
}
```

### Socket Config
```
Host: localhost
Port: 25566
Protocol: JSON over TCP
Direction: bidirectional
```

---

## 7. Owner Recognition

### Voice Profile Setup
```
1. First launch detected (no voice_print.npy exists)
2. Hikari prompts: "Say your name and a few sentences so I can recognize you"
3. Whisper processes audio → extract speaker embedding → save as voice_print.npy
4. On each input: compare embedding similarity score
5. Threshold: >0.85 similarity = owner confirmed
6. Below threshold → STRANGER state
```

### Passphrase Fallback
```
1. Setup: owner sets a secret passphrase
2. Stored as SHA256 hash in layer3_core.json
3. Stranger can speak passphrase to restore owner mode
4. Hikari pretends it's just a "mode" not a security feature 😂
```

---

## 8. What Is Kept From Sentinel 1.0

| File | Status | Action |
|---|---|---|
| `voice/voice.py` | Keep | No changes |
| `voice/ears.py` | Keep | No changes |
| `voice/wake.py` | Modify | Change wake word to "Hikari" |
| `core/ai.py` | Refactor | Rename to hikari_ai.py, update prompt builder calls |
| `core/pipeline.py` | Refactor | Add state machine awareness |
| `ui/bridge.py` | Keep | No changes |
| `ui/widget.py` | Modify | Deep purple reskin |
| `ui/hud.py` | Modify | Color theme update |
| `tools/tools.py` | Keep | No changes |
| `system/emitter.py` | Keep | No changes |
| `system/config.py` | Rewrite | New model config, new system prompt sections |
| `memory/*.py` | Rewrite | Entire new 3-layer system |
| `main.py` | Refactor | New state machine loop |

---

## 9. Performance Requirements

| Metric | Target |
|---|---|
| Wake word response | < 500ms |
| First word of TTS response | < 3 seconds |
| Log event to reaction | < 3 seconds |
| Memory save on session end | < 10 seconds |
| Autonomous loop cycle | ~10 minutes |
| RAM usage idle | < 200MB (excl. model) |
