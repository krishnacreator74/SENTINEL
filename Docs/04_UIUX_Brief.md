# Hikari — UI/UX Brief
**Version:** 1.0  

---

## 1. Design Philosophy

Hikari's UI should feel like she chose it — not like a developer built a tool. It should be subtle, beautiful, slightly mysterious. Present without being intrusive. The orb lives in the corner of your screen and you forget it's there until it reacts to something.

**Keywords:** Ethereal. Feminine. Alive. Unobtrusive. Deep.

---

## 2. Color Palette

| Role | Color | Hex |
|---|---|---|
| Primary glow | Deep purple | `#7B2FBE` |
| Secondary glow | Soft violet | `#B57BEE` |
| Pulse highlight | Pale lavender | `#DDB8FF` |
| Orb core | Near white purple | `#EDE0FF` |
| HUD background | Dark near-black | `#0D0A14` |
| HUD text | Soft white | `#F0E8FF` |
| HUD accent | Violet | `#A855F7` |
| Stranger mode | Cold grey-blue | `#4A5568` |

---

## 3. The Orb

### Base Behavior
- Sits in bottom-right corner of screen (draggable)
- Always on top (like Sentinel 1.0)
- Size: ~80x80px default, slightly larger than Sentinel
- Semi-transparent background, no window chrome

### Orb States — Visual Mapping

| State | Visual |
|---|---|
| IDLE | Slow deep purple pulse, low glow, breathing rhythm |
| LISTENING | Brighter pulse, faster, lavender ring appears |
| SPEAKING | Animated energy waves, bright core, violet shimmer |
| MINECRAFT | Subtle green tint on pulse edge, otherwise same as IDLE |
| STRANGER | Glow dims to cold grey-blue, pulse slows noticeably |
| THINKING | Rotating inner shimmer, slightly dimmed outer glow |

### Glow Animation
- Idle breathing: 3-4 second cycle, subtle size variation (~5%)
- Listening: 1.5 second pulse, slightly expanded
- Speaking: Reacts to audio energy levels (existing Sentinel behavior, recolored)
- All transitions smooth — 300ms ease in/out

---

## 4. HUD (Sentence Display)

### Layout
- Appears top-center of screen when Hikari speaks longer responses
- Dark background `#0D0A14` with ~85% opacity, rounded corners
- Soft purple border `#7B2FBE` at 1px
- Sentences appear one at a time, current sentence highlighted in `#DDB8FF`
- Previous sentences fade to `#6B5B8A`
- Disappears after speech ends (1.5s fade out)

### Typography
- Font: Clean sans-serif (Segoe UI or system default)
- Size: 15px
- Line height: 1.6
- No bold, no headers — just clean flowing text

### Title Bar
- Small label top-left of HUD: "HIKARI" in `#A855F7`
- Replaces "SENTINEL" from Sentinel 1.0

---

## 5. Right-Click Menu

Clicking the orb opens a minimal radial or dropdown menu:

```
┌─────────────────┐
│  HIKARI         │
├─────────────────┤
│  Chat           │
│  Settings       │
│  Minecraft Mode │  (greyed out if MC not running)
│  ─────────────  │
│  Hide           │
│  Exit           │
└─────────────────┘
```

- Dark background matching HUD
- Purple accent on hover
- No heavy borders or shadows — minimal and clean

---

## 6. Chat Window

- Existing Sentinel ChatWindow reskinned to match Hikari palette
- Dark background, purple accents
- Her messages: left aligned, subtle purple bubble
- Your messages: right aligned, darker bubble
- Her name "Hikari" shown above her messages in `#A855F7`
- No avatar for now (Phase 4 adds sprite)
- Scrollable history, clean typography

---

## 7. Settings Panel (Minimal)

Accessible from right-click menu:

```
┌─────────────────────────────────────┐
│  HIKARI SETTINGS                    │
├─────────────────────────────────────┤
│  Model: [Qwen 3 9B          ▼]      │
│  Voice: [default            ▼]      │
│  Wake sensitivity: [====o   ]       │
│  Orb position: [reset to default]   │
│  ─────────────────────────────────  │
│  Re-register voice                  │
│  Change passphrase                  │
│  ─────────────────────────────────  │
│  Relationship: Arc 2 ████░░ 340/500 │
│  (shown after Arc 2 unlocked)       │
└─────────────────────────────────────┘
```

Relationship progress bar only appears after Arc 2 — Arc 1 she wouldn't show you that.

---

## 8. Stranger Mode Visual

When unknown voice detected:
- Orb dims to cold grey-blue `#4A5568`
- Pulse slows to ~6 second cycle
- HUD title changes to "HIKARI" but colder font weight
- Returns to purple the moment owner voice confirmed

This should feel noticeably different — like she closed off.

---

## 9. Phase 4 — Sprite (Future)

When sprite replaces orb:
- Simple PNG sprite, ~120x120px
- 4-5 expressions: neutral, flustered, angry, happy (rare), thinking
- Expression swaps based on state and conversation content
- Same position as orb, same right-click behavior
- VTuber upgrade: VRoid model via VTube Studio API (optional, later)

---

## 10. What Changes From Sentinel 1.0

| Element | Sentinel 1.0 | Hikari |
|---|---|---|
| Orb color | Blue/white | Deep purple |
| HUD background | Dark neutral | `#0D0A14` dark purple-black |
| HUD title | "SENTINEL" | "HIKARI" |
| Accent color | Blue/cyan | Violet `#A855F7` |
| App name | Sentinel | Hikari |
| Menu label | Sentinel | Hikari |
| Energy waves | Blue | Purple gradient |
