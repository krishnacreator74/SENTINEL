# Hikari — Implementation Plan
**Version:** 1.0  
**Format:** Each step is self-contained — paste the step + relevant doc sections into AI and say "build this"

---

## How To Use This Document

Each step below tells you:
- **What to build**
- **Which docs to reference**
- **What files to create/modify**
- **How to test it worked**
- **What to paste into AI to get it built**

Work through steps in order. Each step builds on the last. Don't skip ahead.

---

## PHASE 1 — Give Her A Soul

---

### Step 1 — Project Restructure
**Time estimate:** 30 minutes  
**What:** Rename files, create new folders, set up Hikari project skeleton  

**Files to create:**
```
personality/ (new folder)
data/ (new folder)  
plugins/ (new folder)
core/state_machine.py (new)
core/prompt_builder.py (new)
personality/arcs.py (new)
personality/arc_blocks.py (new)
personality/relationship.py (new)
memory/layer1_session.py (new - replaces memory_chat.py)
memory/layer2_episodes.py (new)
memory/layer3_core.py (new - replaces memory_persistent.py)
memory/worker/worker.py (new)
voice/owner_recognition.py (new)
```

**Files to rename:**
```
core/ai.py → core/hikari_ai.py
```

**Test:** Project runs without errors after restructure (main.py imports still work)

**AI Prompt:**
```
"Using the Backend Schema doc (Section 1 file structure), 
restructure my Sentinel 1.0 project into the Hikari skeleton. 
Create empty files with correct imports. Don't write logic yet, 
just set up the structure. Here is my current project: [paste file list]"
```

---

### Step 2 — Config & Colors
**Time estimate:** 1 hour  
**What:** Update system/config.py, reskin UI to deep purple  

**Files to modify:**
```
system/config.py       — full rewrite per Backend Schema Section 10
ui/widget.py           — deep purple orb (#7B2FBE, #B57BEE)
ui/hud.py              — dark background (#0D0A14), violet accent (#A855F7)
ui/menu.py             — update label from "SENTINEL" to "HIKARI"
chat/window.py         — reskin to match palette
```

**Test:** App launches, orb is deep purple, HUD shows "HIKARI", colors match UI/UX Brief

**AI Prompt:**
```
"Using the UI/UX Brief doc and Backend Schema Section 10 (Config), 
update config.py and reskin the UI files. 
Here are the current files: [paste widget.py, hud.py, menu.py, config.py]"
```

---

### Step 3 — Arc System & Personality Blocks
**Time estimate:** 2 hours  
**What:** Build personality/arcs.py, arc_blocks.py, relationship.py  

**Files to create:**
```
personality/arcs.py        — ARC_BEHAVIORS dict (Backend Schema Section 6)
personality/arc_blocks.py  — IDENTITY_BLOCK, RESPONSE_RULES_BLOCK (Section 9)
personality/relationship.py — SCORE_EVENTS, ARC_THRESHOLDS, score tracker (Section 7)
```

**Test:** Can call `get_arc_behavior(1)` through `get_arc_behavior(5)` and get correct prompt blocks. Can call `add_score("good_conversation")` and score updates correctly.

**AI Prompt:**
```
"Build the arc system for Hikari using Backend Schema Sections 6, 7, and 9.
Create personality/arcs.py, personality/arc_blocks.py, personality/relationship.py.
Include unit tests for score tracking and arc advancement."
```

---

### Step 4 — Memory System (All 3 Layers)
**Time estimate:** 3-4 hours  
**What:** Build the complete 3-layer memory system  

**Files to create:**
```
memory/layer1_session.py   — session memory, current state tracking
memory/layer2_episodes.py  — episodic memory, read/write/compress
memory/layer3_core.py      — core permanent memory, load/save/update
data/layer3_core.json      — initialized with defaults on first run
```

**Test:** 
- Session memory initializes fresh each run
- Can write an episode and read it back
- Core memory persists across app restarts
- Relationship score saves and loads correctly

**AI Prompt:**
```
"Build the 3-layer memory system for Hikari.
Reference: Backend Schema Sections 2, 3, 4, and the Memory Architecture 
section from the planning doc.
Files to build: memory/layer1_session.py, layer2_episodes.py, layer3_core.py
Include initialization logic for first run (create data files if missing)."
```

---

### Step 5 — Dynamic Prompt Builder
**Time estimate:** 2 hours  
**What:** Build core/prompt_builder.py that assembles full prompt from all sources  

**Files to create:**
```
core/prompt_builder.py
```

**Logic:**
```python
build_hikari_prompt(state, game_context=None)
→ loads arc behavior from layer3_core arc_level
→ loads owner context from layer3_core
→ loads last 3 episodes from layer2_episodes
→ loads current session from layer1_session
→ assembles in correct section order (TRD Section 4)
→ returns complete system prompt string
```

**Test:** Call `build_hikari_prompt("IDLE")` and inspect output — should see all sections assembled correctly. Change arc_level in layer3_core.json and verify prompt changes.

**AI Prompt:**
```
"Build core/prompt_builder.py for Hikari.
Reference: TRD Section 4 (Dynamic Prompt Builder) and Backend Schema Section 9.
It should import from all 3 memory layers and personality/arcs.py.
Add a debug mode that prints each section separately so I can inspect the output."
```

---

### Step 6 — Conversation State Machine
**Time estimate:** 3 hours  
**What:** Replace run_voice_loop with proper state machine  

**Files to create/modify:**
```
core/state_machine.py      — new, defines states and transitions
main.py                    — refactor run_voice_loop to use state machine
```

**States to implement:** IDLE, LISTENING, CONVERSATION, MINECRAFT, STRANGER  
**Reference:** TRD Section 3, App Flow Sections 3 and 4  

**Test:** 
- Wake word triggers LISTENING correctly
- 30s silence returns to IDLE from CONVERSATION
- Conversation flows back and forth without needing wake word each time

**AI Prompt:**
```
"Refactor the voice loop in Hikari's main.py to use a proper state machine.
Reference: TRD Section 3 (Conversation State Machine) and App Flow Sections 3-4.
Current main.py: [paste main.py]
Create core/state_machine.py with the 5 states and transition logic."
```

---

### Step 7 — Owner Recognition
**Time estimate:** 2 hours  
**What:** Voice profile setup, similarity checking, stranger detection  

**Files to create:**
```
voice/owner_recognition.py
```

**Logic:**
- First launch: record 2 min, extract embedding, save voice_print.npy
- Each input: compare embedding, return similarity score
- Score > 0.85 → owner, else → STRANGER state
- Passphrase hash stored in layer3_core.json

**Test:** Record your voice, then test with a different voice (play a YouTube video) — should trigger STRANGER state

**AI Prompt:**
```
"Build voice/owner_recognition.py for Hikari.
Reference: TRD Section 7 (Owner Recognition) and App Flow Section 1 (First Launch).
Use Whisper's speaker diarization or numpy cosine similarity on voice embeddings.
Include first-launch setup flow and per-input checking."
```

---

### Step 8 — 1.7B Background Worker
**Time estimate:** 2 hours  
**What:** Worker that runs on session end, handles all memory bookkeeping  

**Files to create:**
```
memory/worker/worker.py
memory/worker/worker_prompts.py
```

**Tasks it handles:**
- Summarize session → episode
- Extract inside jokes
- Flag milestone moments
- Update relationship score
- Check arc advancement
- Weekly episode compression

**Test:** Run a test session, close app, verify episode appears in layer2_episodes.json with correct fields

**AI Prompt:**
```
"Build the 1.7B background worker for Hikari.
Reference: Memory Architecture section from planning doc, Backend Schema Sections 3-4.
Worker runs on session close via threading.Thread(daemon=True).
Uses WORKER_MODEL (Qwen 1.7B) via same LM Studio API.
Handles: session summarization, inside joke extraction, relationship scoring, arc check."
```

---

### ✅ PHASE 1 COMPLETE CHECKPOINT
At this point Hikari should:
- Have a deep purple orb
- Respond to "Hikari" wake word
- Hold back-and-forth conversations
- Have tsundere Arc 1 personality
- Recognize your voice, be cold to strangers
- Save and load memory across sessions
- Relationship score working in background

**This is already way better than Sentinel 1.0. Test everything here before moving to Phase 2.**

---

## PHASE 2 — Minecraft Companion

---

### Step 9 — Minecraft Log Watcher
**Time estimate:** 2 hours  
**What:** Build log watcher that tails latest.log and fires events  

**Files to create:**
```
plugins/minecraft/__init__.py
plugins/minecraft/log_watcher.py
plugins/minecraft/event_parser.py
```

**Reference:** TRD Section 6, Backend Schema Section 8  

**Test:** Launch Minecraft, die, verify death event fires in console within 3 seconds

**AI Prompt:**
```
"Build the Minecraft log watcher plugin for Hikari.
Reference: TRD Section 6 (Minecraft Plugin Technical Spec), Backend Schema Section 8.
Use the watchdog library to tail %APPDATA%/.minecraft/logs/latest.log.
Implement event_parser.py with all PRIORITY_1, PRIORITY_2, PRIORITY_3 patterns.
Fire events via existing Emitter system."
```

---

### Step 10 — Game State & Event Handler
**Time estimate:** 2 hours  
**What:** Game state tracker, priority event handler, inject into prompt  

**Files to create:**
```
plugins/minecraft/game_state.py
plugins/minecraft/event_handler.py
```

**Logic:**
- Priority 1 events → trigger immediate unprompted Hikari reaction
- Priority 2/3 events → update game_context_buffer in layer1_session
- Game context injected into prompt builder as Section 7 when MC active

**Test:** Die in Minecraft → Hikari reacts within 3 seconds without you saying anything

**AI Prompt:**
```
"Build game_state.py and event_handler.py for Hikari's Minecraft plugin.
Reference: App Flow Section 5, TRD Section 6 (Event Priority System).
Priority 1 events trigger immediate unprompted speech via existing speak pipeline.
Game context feeds into prompt_builder.py Section 7 (game context block)."
```

---

### Step 11 — Minecraft Memory
**Time estimate:** 1-2 hours  
**What:** mc_memory.json, recipe learning, named locations  

**Files to create:**
```
plugins/minecraft/mc_memory.py
data/mc_memory.json
```

**Reference:** Backend Schema Section 5  

**Test:** Teach Hikari a recipe verbally, restart app, verify she still knows it

**AI Prompt:**
```
"Build mc_memory.py for Hikari's Minecraft plugin.
Reference: Backend Schema Section 5 (mc_memory.json schema).
Handles: recipe storage, named locations, world notes.
Recipes stored as experiences with her_note field (her personality colors the memory).
Expose load/save/add_recipe/add_location functions."
```

---

### ✅ PHASE 2 COMPLETE CHECKPOINT
Hikari now:
- Watches your Minecraft game in real time
- Reacts to your death immediately (rampage mode via personality)
- Knows what's happening in your game during conversations
- Remembers recipes you teach her
- Remembers named locations

---

## PHASE 3 — Autonomous Life

---

### Step 12 — Mineflayer Bot Setup
**Time estimate:** 3-4 hours  
**What:** Node.js bot that can receive commands and control a Minecraft player  

**Files to create:**
```
plugins/minecraft/mineflayer/bot.js
plugins/minecraft/mineflayer/package.json
```

**Reference:** TRD Section 6 (Mineflayer Bridge Protocol)  

**Test:** Run bot.js, connect to singleplayer LAN world, send "follow" command, bot follows you

**AI Prompt:**
```
"Build the Mineflayer bot for Hikari's RTS mode.
Reference: TRD Section 6 (Mineflayer Bridge Protocol, Socket Config).
bot.js listens on localhost:25566 for JSON commands.
Implement: mine, attack, goto, craft, follow, report actions.
Bot sends back event JSON on completion/failure/obstacles."
```

---

### Step 13 — Python ↔ Node Bridge
**Time estimate:** 2 hours  
**What:** bridge.py that lets Hikari send commands to the bot  

**Files to create:**
```
plugins/minecraft/mineflayer/bridge.py
```

**Test:** Hikari says "go mine some wood" → Python parses intent → bridge.py sends command → bot mines wood

**AI Prompt:**
```
"Build bridge.py for Hikari's Mineflayer integration.
Reference: TRD Section 6 (Socket Config, command protocol).
Python TCP client on localhost:25566.
Expose: send_command(action, target), listen_for_events().
Integrate with hikari_ai.py so Hikari can trigger bot actions from conversation."
```

---

### Step 14 — Autonomous Decision Loop
**Time estimate:** 4-5 hours  
**What:** Loop that runs when owner is offline, Hikari makes her own decisions  

**Files to create/modify:**
```
plugins/minecraft/autonomous.py   (new)
data/mc_memory.json               (add autonomous_diary section)
```

**Reference:** PRD Phase 3, App Flow Sections 6 and 7  

**Test:** Go offline for 30 minutes with autonomous loop running, come back, verify diary entries exist in mc_memory.json with wants_to_tell_owner: true

**AI Prompt:**
```
"Build autonomous.py for Hikari's independent Minecraft life.
Reference: PRD Phase 3 (Autonomous Life), App Flow Sections 6-7, Backend Schema Section 5 (autonomous_diary).
Loop runs every ~10 minutes.
Each cycle: check state → LLM decides action → execute via bridge → journal entry.
Diary entries with wants_to_tell_owner: true get surfaced on owner's next login."
```

---

### ✅ PHASE 3 COMPLETE CHECKPOINT
Hikari now:
- Has a body in Minecraft (Mineflayer)
- Can be summoned for RTS mode
- Lives independently when you're offline
- Keeps a diary and tells you about it when you return

---

## PHASE 4 — Polish (Do These In Any Order)

### Step 15 — Mood Affects TTS
Modify voice.py to accept mood parameter → adjust Piper TTS speed/pitch per mood

### Step 16 — Unprompted System
Implement random timer in IDLE/MINECRAFT states → low-priority LLM call → she just says something

### Step 17 — Sprite (Optional)
Replace orb with simple PNG sprite, 4-5 expressions swapping based on state

### Step 18 — Relationship Milestones UI
Show milestone history in settings panel after Arc 2 unlocks

---

## Quick Reference — What To Paste Per Session

**Starting a new coding session:**
```
Paste: Implementation Plan (this doc)
Paste: The specific step you're working on
Paste: Relevant doc sections referenced in that step
Paste: Current version of files being modified
Say: "Build Step [N] — [name]"
```

**Debugging a step:**
```
Paste: The step spec
Paste: Current broken file
Paste: Error message
Say: "This step isn't working, here's the error"
```

**Continuing from last session:**
```
Paste: Implementation Plan
Say: "I completed steps 1-3. Starting step 4 now. Here are my current files: [paste]"
```

---

## Total Estimated Time

| Phase | Steps | Estimate |
|---|---|---|
| Phase 1 — Soul | 8 steps | 3-5 days |
| Phase 2 — Minecraft | 3 steps | 2-3 days |
| Phase 3 — Autonomous | 3 steps | 3-4 days |
| Phase 4 — Polish | 4 steps | 2-3 days |
| **Total** | **18 steps** | **~2-3 weeks** |

With your schedule (unemployed, can work daily) this is very achievable. Aim for 2 steps per day and you're done in under 2 weeks.
