"""
test.py — Standalone entry point for Note Taker.
Thin as possible. All logic lives in the note_taker module.

Run directly:
    python test.py
"""

import sys
import os
import threading

# Add parent dir so note_taker resolves as a package
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from note_taker import start, stop, is_active


def main():
    result = start()
    print(result)

    if not is_active():
        return

    try:
        while is_active():
            threading.Event().wait(timeout=1)
    except KeyboardInterrupt:
        print("\n[test.py] Ctrl+C received.")

    print(stop())


if __name__ == "__main__":
    main()