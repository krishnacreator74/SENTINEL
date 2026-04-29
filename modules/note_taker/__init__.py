"""
note_taker/__init__.py

Public API for the Note Taker module.
Only two things are exported: start() and stop().

From Sentinel:
    from modules.note_taker import start, stop

From a standalone script:
    from note_taker import start, stop

Nothing else from inside the module needs to leak out.
"""

import os
import datetime
import threading

from .audio   import load_whisper
from .capture import RegionSelector, capture
from .llm     import write_note, lm_call
from .session import Session
from .        import config

# Module-level session handle — only one session runs at a time
_current_session: Session | None = None
_session_thread:  threading.Thread | None = None


def start(region: tuple | None = None) -> str:
    """
    Start a note-taking session.

    Args:
        region — (x, y, w, h) screen region to capture.
                 If None, shows the interactive region selector.

    Returns a status string.
    """
    global _current_session, _session_thread

    if _current_session and _current_session.is_running():
        return "Note-taking session already running."

    # Load Whisper if not already loaded
    load_whisper()

    # Ping LM Studio
    ping = lm_call(
        [{"role": "user", "content": "Reply with one word: OK"}],
        max_tokens=80,
    )
    if not ping:
        return "LM Studio not responding. Is it running on localhost:1234?"

    # Region selection
    if region is None:
        print("[Note Taker] Select capture region...")
        region = RegionSelector().select()
        if not region:
            return "Cancelled — no region selected."
        print(f"[Note Taker] Region: {region}")

    # Vision test
    try:
        test = write_note("", capture(region), "(none yet)", None)
        print(f"[Note Taker] Vision OK — '{test[:60]}'")
    except Exception as e:
        print(f"[Note Taker] Vision test failed: {e}")

    # Build session directory
    ts          = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    session_dir = os.path.join(config.NOTES_DIR, f"session_{ts}")

    _current_session = Session(region, session_dir)
    _current_session.start()

    return f"Note-taking started. Saving to {session_dir}"


def stop() -> str:
    """
    Stop the current note-taking session.
    Returns a status string with the path to the saved notes.
    """
    global _current_session

    if not _current_session or not _current_session.is_running():
        return "No active note-taking session."

    _current_session.stop()
    path = _current_session.path
    _current_session = None
    return f"Notes saved to {path}"


def is_active() -> bool:
    """Returns True if a session is currently running."""
    return _current_session is not None and _current_session.is_running()