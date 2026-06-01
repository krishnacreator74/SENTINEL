# Hikari — App Flow Document
**Version:** 1.0  

---

## 1. First Launch Flow

```
App launches for first time
        │
        ▼
No voice_print.npy detected
        │
        ▼
Hikari speaks:
"I am Hikari. Before we begin, I need to recognize your voice.
Say your name and a few sentences."
        │
        ▼
Whisper records ~2 minutes of voice
        │
        ▼
Voice profile saved → voice_print.npy
        │
        ▼
Hikari speaks:
"Now set a passphrase. Say it clearly."
        │
        ▼
Passphrase recorded → hashed → saved to layer3_core.json
        │
        ▼
layer3_core.json initialized with defaults
arc_level: 1, relationship_score: 0
        │
        ▼
Hikari speaks (Arc 1 cold):
"Setup complete. I am your AI assistant. What do you need."
        │
        ▼
→ IDLE STATE
```

---

## 2. Normal Session Start Flow

```
App launches (not first time)
        │
        ▼
Load layer3_core.json
Load last 3 episodes from layer2_episodes.json
Initialize layer1_session.json
        │
        ▼
Check last_seen timestamp
        │
        ├── Been < 1 day → normal greeting
        ├── Been 1-3 days → slight comment about absence
        └── Been 3+ days → relationship score -5, she noticed
        │
        ▼
Hikari gives session-opening line (arc-appropriate)
        │
        ▼
→ IDLE STATE
```

---

## 3. Wake Word Flow

```
IDLE STATE
        │
        ▼
Whisper listening passively
        │
        ▼
"Hikari" detected
        │
        ▼
Voice similarity check against voice_print.npy
        │
        ├── Score > 0.85 → OWNER confirmed → LISTENING STATE
        └── Score < 0.85 → STRANGER STATE
                              │
                              ▼
                          Cold Arc 1 response
                          "How can I help you."
                          (no personality, no warmth)
```

---

## 4. Conversation Flow

```
LISTENING STATE
        │
        ▼
Whisper captures full input
        │
        ▼
Input classified by 1.7B router:
        │
        ├── "needs tool" → pipeline handles (existing Sentinel tools)
        ├── "needs minecraft action" → plugin handles
        ├── "needs memory lookup" → layer 3 query
        └── "just conversation" → straight to Hikari 9B
        │
        ▼
Prompt builder assembles full dynamic prompt
        │
        ▼
LM Studio API call → Qwen 9B
        │
        ▼
Response via Piper TTS (sentence by sentence, HUD updates)
        │
        ▼
→ CONVERSATION STATE (30s window open)
        │
        ├── User speaks again → loop back to Whisper capture
        └── 30s silence → session highlight logged → IDLE STATE
```

---

## 5. Minecraft Session Flow

```
System detects minecraft.exe is focused
        │
        ▼
→ MINECRAFT STATE
Log watcher activates on latest.log
Game context section enabled in prompt
        │
        ▼
┌─────────────────────────────────────────┐
│         MINECRAFT EVENT LOOP            │
│                                         │
│  Log line detected                      │
│         │                               │
│         ▼                               │
│  Event parser classifies it             │
│         │                               │
│         ├── Priority 1 (death etc)      │
│         │   → Hikari speaks IMMEDIATELY │
│         │   → Prompt gets death context │
│         │   → She reacts via personality│
│         │                               │
│         ├── Priority 2                  │
│         │   → Added to game_context     │
│         │   → Mentioned if you talk     │
│         │                               │
│         └── Priority 3                  │
│             → Silent state update only  │
│                                         │
└─────────────────────────────────────────┘
        │
        ▼
User says "Hikari" mid-game
        │
        ▼
→ CONVERSATION STATE (game context still active)
She knows exactly what's happening in your game
        │
        ▼
Conversation ends → back to MINECRAFT STATE
        │
        ▼
minecraft.exe loses focus / closes
        │
        ▼
Session highlight saved to layer1
→ IDLE STATE
```

---

## 6. RTS / Summon Mode Flow (Phase 3)

```
User says "Hikari take over" or "Hikari go"
        │
        ▼
Hikari confirms (arc-appropriate):
Arc 1: "Understood. Taking control."
Arc 3: "Fine, I'll handle it since you clearly can't."
        │
        ▼
User switches to spectator/creative mode
        │
        ▼
Python bridge.py sends spawn command to bot.js
        │
        ▼
Mineflayer bot spawns in world
        │
        ▼
Hikari autonomous loop begins:
  1. Check state (health, location, inventory)
  2. Decide action via LLM
  3. Execute via Mineflayer commands
  4. React to unexpected events
  5. Narrate interesting moments to you
  6. Loop every ~10 minutes
        │
        ▼
User says "Hikari stop" or rejoins survival
        │
        ▼
Bot despawns, control returns
Hikari gives brief summary of what she did
→ MINECRAFT STATE
```

---

## 7. Autonomous Life Flow (Phase 3 — Owner Offline)

```
Owner closes app / goes offline
        │
        ▼
If Minecraft server still running:
Autonomous loop continues independently
        │
        ▼
Every ~10 minutes:
  Check state → decide → act → journal entry
        │
        ▼
wants_to_tell_owner events queued in diary
        │
        ▼
Owner comes back online
        │
        ▼
Session start detects diary entries flagged wants_to_tell_owner: true
        │
        ▼
Before normal greeting, Hikari says:
"...something happened while you were gone."
Then tells you about it in her voice, not a summary
        │
        ▼
Diary entries cleared, folded into Layer 2 episodic memory
→ Normal session continues
```

---

## 8. Session End Flow

```
App closing detected
        │
        ▼
layer1_session.json finalized
        │
        ▼
1.7B background worker fires:
  - Summarize session into episode
  - Flag any milestone moments
  - Extract inside jokes created
  - Update relationship score
  - Check if arc threshold crossed
        │
        ├── Arc threshold crossed?
        │   → arc_level +1 in layer3_core.json
        │   → Next session she's subtly different
        │
        ▼
Episode saved to layer2_episodes.json
layer3_core.json updated (score, hours, milestones)
layer1_session.json wiped
        │
        ▼
App exits cleanly
```

---

## 9. Chat Window Flow

```
User clicks orb → right click menu → "Chat"
        │
        ▼
ChatWindow opens (existing Sentinel component, reskinned)
        │
        ▼
Text input available (no wake word needed)
Same conversation state machine applies
Same dynamic prompt — she's the same Hikari in text
        │
        ▼
User closes window
→ State returns to whatever it was before
```
