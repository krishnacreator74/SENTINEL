# Hikari — Product Requirements Document (PRD)
**Version:** 1.0  
**Status:** Approved  
**Project Type:** Refactor of Sentinel 1.0  

---

## 1. Product Overview

Hikari is a local AI companion application — a tsundere waifu that lives on your desktop, watches you play Minecraft, reacts to your gameplay, holds real conversations, and develops a genuine relationship with you over time through an anime-style arc progression system.

She is not an assistant. She is a companion with her own personality, emotional state, and eventually her own autonomous life inside Minecraft.

---

## 2. Problem Statement

Sentinel 1.0 was a capable local AI assistant but felt lifeless — cold, one-shot interactions, no personality persistence, no relationship growth, no emotional memory. It was a tool, not a companion.

Hikari solves this by giving the AI a real identity, emotional continuity, and a world to exist in.

---

## 3. Target User

Single user (owner). Hikari is built for one person — recognizes only them, belongs only to them, grows her relationship only with them.

---

## 4. Core Features by Phase

### Phase 1 — Soul (MVP)
- Tsundere personality with arc progression system (5 arcs)
- Real back-and-forth conversation (not one-shot)
- 3-layer memory system (working, episodic, core)
- Dynamic prompt builder (personality evolves with arc)
- Owner recognition (voice profile + passphrase)
- Deep purple glowing orb UI
- Wake word: "Hikari"

### Phase 2 — Minecraft Companion
- Minecraft log watcher (vanilla, no mod needed)
- Reacts unprompted to game events (death, advancements, nether entry)
- Minecraft-specific memory (recipes, named locations)
- Game context injected into prompt when MC is running
- Priority event system (immediate vs background reactions)

### Phase 3 — Autonomous Life
- Mineflayer bot body (Node.js)
- Python ↔ Node.js socket bridge
- RTS summon mode (you go spectator, she plays)
- Autonomous decision loop (she plays alone when you're offline)
- Personal goals, daily rhythm, emotional state without you
- Diary/journal system with `wants_to_tell_owner` flag
- Catch-up conversation when you return

### Phase 4 — Polish
- Mood affects Piper TTS tone
- Simple sprite with expressions (replaces orb)
- VTuber avatar option (VRoid + VTube Studio)
- Relationship milestones UI
- Named places, favorite spots, world ownership feeling

---

## 5. Personality Specification

**Type:** Tsundere — cute-aggressive  
**Core trait:** Pretends not to care, does everything for you  
**Speech:** Casual, slightly sharp, uses "baka", reluctant compliments  
**Reaction to death:** Immediately loud, goes full rampage mode via personality  
**Reaction to success:** *"...fine, that was impressive. Whatever."*  
**Stranger behavior:** Reverts to cold Arc 1 regardless of actual arc level  

### Arc Progression (earned, not time-based)

| Arc | Name | Behavior |
|---|---|---|
| 1 | Fresh Assignment | Cold, professional, slight attitude |
| 2 | Getting Used To You | Notices things, slightly protective |
| 3 | Won't Admit It | Full tsundere peak, roasts constantly |
| 4 | Quietly Attached | Cracks show, remembers everything |
| 5 | Just Admits It (kinda) | Stops pretending, still never says it directly |

### Relationship Score Drivers
- +2 daily check-in
- +5 good conversation
- +10 played Minecraft together
- +15 she helped you survive
- +20 milestone moment
- -5 ignored her 3+ days
- +bonus dramatic moments (rampage builds relationship 😂)

---

## 6. Non-Functional Requirements

- **Fully local** — no cloud, no internet required for core features
- **Single user** — owner recognition enforced
- **Always available** — runs in background, minimal resource use when idle
- **Voice-first** — primary interaction is voice, chat window secondary
- **Model agnostic** — works with any LM Studio model, easy to swap
- **Modular** — plugin architecture, each phase is independently functional

---

## 7. Out of Scope

- Multi-user support
- Cloud sync
- Mobile app
- Multiplayer Minecraft server support (Phase 3 is singleplayer only initially)
- Monetization

---

## 8. Success Criteria

- Hikari holds a 5+ turn back-and-forth conversation naturally
- Arc visibly changes behavior between Arc 1 and Arc 3
- She reacts to Minecraft death event within 3 seconds unprompted
- Memory persists correctly across sessions
- Owner recognition rejects unknown voice correctly
- Autonomous loop runs 1+ hour without human input in Phase 3
