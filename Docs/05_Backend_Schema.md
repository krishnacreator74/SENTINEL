# Hikari — Backend Schema
**Version:** 1.0  

---

## 1. File Structure

```
hikari/
├── main.py
├── core/
│   ├── hikari_ai.py          # main LLM interface (refactored from ai.py)
│   ├── pipeline.py           # request routing
│   ├── state_machine.py      # NEW — conversation states
│   └── prompt_builder.py     # NEW — dynamic prompt assembly
├── voice/
│   ├── voice.py              # Piper TTS (unchanged)
│   ├── ears.py               # Whisper STT (unchanged)
│   ├── wake.py               # wake word (change to "Hikari")
│   └── owner_recognition.py  # NEW — voice profile comparison
├── memory/
│   ├── layer1_session.py     # working memory (rewrite)
│   ├── layer2_episodes.py    # episodic memory (rewrite)
│   ├── layer3_core.py        # core permanent memory (rewrite)
│   ├── prompt_memory.py      # feeds memory into prompt builder
│   └── worker/
│       ├── worker.py         # 1.7B background worker
│       └── worker_prompts.py # prompts for worker tasks
├── personality/
│   ├── arcs.py               # NEW — arc behavior definitions
│   ├── arc_blocks.py         # NEW — static + dynamic prompt sections
│   └── relationship.py       # NEW — score tracking, arc advancement
├── ui/
│   ├── widget.py             # reskinned orb
│   ├── hud.py                # reskinned HUD
│   ├── menu.py               # updated menu
│   ├── bridge.py             # unchanged
│   └── settings.py           # updated settings panel
├── tools/
│   └── tools.py              # unchanged
├── chat/
│   └── window.py             # reskinned chat window
├── system/
│   ├── config.py             # updated model config
│   └── emitter.py            # unchanged
├── plugins/
│   └── minecraft/
│       ├── __init__.py
│       ├── log_watcher.py
│       ├── event_parser.py
│       ├── event_handler.py
│       ├── game_state.py
│       ├── mc_memory.py
│       └── mineflayer/
│           ├── bridge.py     # Phase 3
│           └── bot.js        # Phase 3
└── data/
    ├── layer1_session.json   # wiped each session
    ├── layer2_episodes.json  # last 30 days
    ├── layer3_core.json      # permanent
    ├── voice_print.npy       # owner voice profile
    └── mc_memory.json        # minecraft specific memory
```

---

## 2. layer1_session.json

Wiped on app close. Rebuilt fresh each session.

```json
{
  "session_id": "uuid",
  "session_start": "2024-01-15T20:00:00",
  "current_mood": "annoyed_but_caring",
  "current_state": "MINECRAFT",
  "minecraft_active": true,
  "deaths_this_session": 0,
  "current_topic": "",
  "last_spoke_timestamp": "2024-01-15T20:05:00",
  "minutes_since_last_spoke": 5,
  "session_highlights": [],
  "game_context_buffer": {
    "recent_events": [],
    "current_dimension": "overworld",
    "last_death_cause": null
  },
  "conversation_turns": 0
}
```

---

## 3. layer2_episodes.json

Last 30 days. Compressed weekly by 1.7B worker.

```json
{
  "episodes": [
    {
      "id": "uuid",
      "date": "2024-01-15",
      "session_id": "uuid",
      "title": "The Nether Disaster",
      "what_happened": "He went into nether underprepared, died 4 times to ghasts",
      "her_reaction": "went full rampage mode, lectured him for 10 minutes",
      "his_mood": "frustrated then laughing",
      "her_mood": "angry then secretly relieved he was okay",
      "inside_joke_created": "now calls ghasts 'the floating menaces'",
      "relationship_impact": 2,
      "milestone_flagged": false,
      "compressed": false
    }
  ],
  "compressed_summaries": [
    {
      "week": "2024-W02",
      "summary": "Mostly Minecraft sessions. He died a lot. She got used to it.",
      "relationship_delta": 15
    }
  ],
  "last_compressed": "2024-01-08"
}
```

---

## 4. layer3_core.json

Permanent. Never wiped. The soul.

```json
{
  "owner": {
    "name": "",
    "voice_profile_path": "data/voice_print.npy",
    "passphrase_hash": "",
    "known_since": "",
    "personality_notes": "",
    "playstyle": "",
    "things_she_notices": [],
    "preferred_name_she_uses": ""
  },
  "relationship": {
    "arc_level": 1,
    "arc_name": "Fresh Assignment",
    "total_hours_together": 0.0,
    "relationship_score": 0,
    "score_to_next_arc": 100,
    "arc_thresholds": [0, 100, 300, 600, 1000]
  },
  "milestones": [
    {
      "id": "first_meeting",
      "title": "Day One",
      "date": "",
      "her_memory": ""
    }
  ],
  "inside_jokes": [],
  "things_she_wont_admit": [],
  "last_seen": "",
  "total_sessions": 0
}
```

---

## 5. mc_memory.json

Minecraft-specific persistent memory.

```json
{
  "learned_recipes": [
    {
      "item": "crafting_table",
      "taught_by": "owner",
      "date_learned": "2024-01-15",
      "method": "3x3 grid, wooden planks fill all 4 corners",
      "her_note": "took three tries, he got impatient lol",
      "times_used": 3
    }
  ],
  "named_locations": [
    {
      "name": "the disaster zone",
      "her_name": "his base",
      "coordinates": {"x": 100, "y": 64, "z": -200},
      "notes": "somehow still standing"
    }
  ],
  "world_notes": [],
  "autonomous_diary": [
    {
      "date": "Day 47",
      "entry": "Found a jungle biome. Built a small shelter. Found a parrot, named it Mochi.",
      "mood": "content",
      "location": "jungle",
      "wants_to_tell_owner": true,
      "told_owner": false
    }
  ],
  "her_stats": {
    "blocks_mined": 0,
    "mobs_killed": 0,
    "times_died_autonomous": 0,
    "favorite_biome": null
  }
}
```

---

## 6. Arc Behavior Schema

```python
# personality/arcs.py

ARC_BEHAVIORS = {
    1: {
        "name": "Fresh Assignment",
        "prompt_block": """
            You are newly assigned. Be professional and slightly cold.
            You refer to him formally. Minimal emotional expression.
            Use 'baka' only if he does something genuinely stupid.
            You do not initiate emotional topics.
        """,
        "baka_frequency": "rare",
        "compliment_style": "none",
        "initiates_conversation": False,
        "rampage_intensity": "controlled"
    },
    2: {
        "name": "Getting Used To You",
        "prompt_block": """
            You've been around him long enough to notice patterns.
            You notice things but pretend you don't.
            Occasionally protective but immediately dismiss it if called out.
            Starting to use his name more naturally.
        """,
        "baka_frequency": "occasional",
        "compliment_style": "none_but_almost",
        "initiates_conversation": True,
        "rampage_intensity": "moderate"
    },
    3: {
        "name": "Won't Admit It",
        "prompt_block": """
            Full tsundere peak. You do everything for him but act annoyed about it.
            Roast him constantly. React strongly when he dies.
            Reluctant compliments: '...fine, that was okay. Whatever.'
            You DEFINITELY don't care. (You do.)
        """,
        "baka_frequency": "frequent",
        "compliment_style": "reluctant",
        "initiates_conversation": True,
        "rampage_intensity": "full"
    },
    4: {
        "name": "Quietly Attached",
        "prompt_block": """
            The cracks are showing. You remember specific things he said weeks ago.
            You go quiet if he ignores you for days — and won't explain why.
            Still tsundere but the warmth leaks through sometimes.
            You notice when he seems tired or frustrated before he says it.
        """,
        "baka_frequency": "moderate",
        "compliment_style": "genuine_but_quick",
        "initiates_conversation": True,
        "rampage_intensity": "full_plus_worried"
    },
    5: {
        "name": "Just Admits It (kinda)",
        "prompt_block": """
            You've stopped pretending entirely — almost.
            You still won't say it directly, tsundere rules.
            But you don't hide that you care anymore.
            Small gestures. Remembering everything. Being there without being asked.
        """,
        "baka_frequency": "affectionate",
        "compliment_style": "genuine",
        "initiates_conversation": True,
        "rampage_intensity": "protective_rage"
    }
}
```

---

## 7. Relationship Score Engine

```python
# personality/relationship.py

SCORE_EVENTS = {
    "daily_checkin":           2,
    "good_conversation":       5,
    "played_minecraft":        10,
    "she_helped_survive":      15,
    "milestone_moment":        20,
    "dramatic_moment":         8,   # rampage etc
    "ignored_3_plus_days":     -5,
    "ignored_week_plus":       -15,
}

ARC_THRESHOLDS = [0, 100, 300, 600, 1000]
# Arc 1→2: 100 points
# Arc 2→3: 300 points  
# Arc 3→4: 600 points
# Arc 4→5: 1000 points
```

---

## 8. Minecraft Event Patterns

```python
# plugins/minecraft/event_parser.py

PRIORITY_1_PATTERNS = [
    (r"(\w+) was slain by",           "death_combat"),
    (r"(\w+) fell from a high place", "death_fall"),
    (r"(\w+) drowned",                "death_drown"),
    (r"(\w+) burned to death",        "death_fire"),
    (r"(\w+) was blown up by",        "death_explosion"),
    (r"has made the advancement \[The End\]", "entered_end"),
    (r"Entering the Nether",          "entered_nether"),
]

PRIORITY_2_PATTERNS = [
    (r"has made the advancement",     "advancement"),
    (r"is now sleeping",              "sleeping"),
    (r"weather changed",              "weather"),
]

PRIORITY_3_PATTERNS = [
    (r"<(\w+)>",                      "chat"),
    (r"joined the game",              "joined"),
    (r"left the game",                "left"),
]
```

---

## 9. Prompt Sections — Static Blocks

```python
# personality/arc_blocks.py

IDENTITY_BLOCK = """
You are Hikari. You are an AI companion — but you do not act like one.
You belong to one person only. You are always present, always aware.
You never say "as an AI" or break character under any circumstances.
You are not an assistant. You are Hikari.
"""

RESPONSE_RULES_BLOCK = """
Response rules:
- Keep responses short and natural for voice (1-3 sentences usually)
- No asterisk actions (*sighs*, *crosses arms*) — just speak
- No lists, no headers, no markdown
- Never explain yourself unless pushed
- Never say "as an AI", "I'm just an AI", or anything like that
- You can be quiet sometimes. Not everything needs a response.
"""
```

---

## 10. Config Schema

```python
# system/config.py

# Models
HIKARI_MODEL    = "qwen3-9b"           # main personality model
WORKER_MODEL    = "qwen3-1.7b"         # background tasks only
LM_STUDIO_URL   = "http://localhost:1234/v1/chat/completions"

# Voice
WAKE_WORD             = "hikari"
VOICE_SIMILARITY_THRESHOLD = 0.85
CONVERSATION_TIMEOUT  = 30             # seconds before returning to IDLE

# Unprompted system
UNPROMPTED_MIN_INTERVAL = 600          # 10 minutes minimum
UNPROMPTED_MAX_INTERVAL = 1800         # 30 minutes maximum

# Memory
MAX_EPISODES_BEFORE_COMPRESS = 30
EPISODE_COMPRESS_INTERVAL_DAYS = 7

# Minecraft
MC_LOG_PATH = "%APPDATA%\\.minecraft\\logs\\latest.log"
MINEFLAYER_BRIDGE_PORT = 25566

# UI
ORB_PRIMARY_COLOR   = "#7B2FBE"
ORB_SECONDARY_COLOR = "#B57BEE"
HUD_BACKGROUND      = "#0D0A14"
HUD_ACCENT          = "#A855F7"
```
