"""
session.py — Session orchestrator for Note Taker.

Coordinates audio, screen, LLM, and dedup.
Only this file writes to disk.
Raw model output NEVER goes to file directly — everything goes through
parse_boxes() and dedup first.
"""

import os
import queue
import time
import threading
import datetime

from . import config
from .audio   import load_whisper, build_workers
from .capture import capture, img_hash, screen_changed, is_diagram, save_diagram
from .dedup   import DedupStore
from .llm     import write_note, parse_boxes, is_skip


class Session:
    """
    A single note-taking session.

    Lifecycle:
        sess = Session(region, session_dir)
        sess.start()    # non-blocking
        sess.stop()     # signal stop, wait for clean shutdown
    """

    def __init__(self, region: tuple, session_dir: str):
        self.region   = region
        self.dir      = session_dir
        self.path     = os.path.join(session_dir, "notes.txt")

        self._q       = queue.Queue()
        self._stop    = threading.Event()
        self._dedup   = DedupStore()
        self._workers = []

        self._prev_img   = None
        self._prev_hash  = None
        self._diag_idx   = 0
        self._thread     = threading.Thread(
            target=self._run, daemon=True, name="Session"
        )

    # ── Public API ─────────────────────────────────────────────────────────────
    def start(self):
        self._workers = build_workers(self._q, self._stop)
        for w in self._workers:
            w.start()
        self._write_header()
        self._thread.start()
        print(f"\n[Session] Active → {self.path}")
        print("[Session] Say 'stop notes' or Ctrl+C to end\n")

    def stop(self, timeout: float = 6.0):
        print("\n[Session] Stopping...")
        self._stop.set()
        self._thread.join(timeout=timeout)
        self._write_footer()
        print(f"[Session] Saved → {self.path}")

    def is_running(self) -> bool:
        return self._thread.is_alive()

    # ── Main loop ──────────────────────────────────────────────────────────────
    def _run(self):
        last_write = time.time()

        while not self._stop.is_set():
            time.sleep(1)
            now      = time.time()
            interval = (now - last_write) >= config.INTERVAL_SECONDS

            try:
                img = capture(self.region)
                h   = img_hash(img)
            except Exception as e:
                print(f"[Capture error] {e}")
                continue

            changed = (
                self._prev_img is not None
                and self._prev_hash != h
                and screen_changed(img, self._prev_img)
            )

            speech     = self._drain_audio()
            has_speech = bool(speech)

            # Stop command from mic
            if speech and any(p in speech.lower() for p in config.STOP_PHRASES):
                print(f"[Session] Stop command: '{speech}'")
                self._stop.set()
                break

            # Only proceed if something genuinely happened
            if not (changed or has_speech or (interval and has_speech)):
                self._prev_img  = img
                self._prev_hash = h
                continue

            # Save diagram if needed
            diagram = None
            if changed and is_diagram(img):
                self._diag_idx += 1
                path    = save_diagram(img, self.dir, self._diag_idx)
                diagram = os.path.basename(path)
                print(f"[Diagram] → {path}")

            # LLM call with compact known-state context
            try:
                known = self._dedup.compact_summary()
                raw   = write_note(speech, img, known, diagram)
            except Exception as e:
                print(f"[LLM error] {e}")
                self._prev_img  = img
                self._prev_hash = h
                last_write      = now
                continue

            # Process through parser + dedup — never write raw output
            if not is_skip(raw):
                self._process_and_write(raw, diagram)
            else:
                print("[Note] Model returned SKIP.")

            self._prev_img  = img
            self._prev_hash = h
            last_write      = now

    def _drain_audio(self) -> str:
        chunks = []
        while True:
            try:
                chunks.append(self._q.get_nowait())
            except queue.Empty:
                break
        return " ".join(chunks).strip()

    # ── Note processing ────────────────────────────────────────────────────────
    def _process_and_write(self, raw: str, diagram: str | None):
        """
        Parse → dedup → write.

        __meta__ lines (e.g. [DIAGRAM: ...]) are written through only if
        at least one real box had new content this cycle. This prevents
        diagram references appearing repeatedly with no new facts.
        """
        boxes        = parse_boxes(raw)
        written_text = []
        had_real_box = False

        for heading, lines in boxes:

            # Meta lines (diagram refs etc) — hold until we know a real box passed
            if heading == "__meta__":
                continue

            # Run dedup on each line within this heading
            new_lines = self._dedup.filter_box(heading, lines)
            if not new_lines:
                print(f"[Dedup] '{heading}' — all lines already known, skipping.")
                continue

            had_real_box = True
            width    = max(len(heading) + 6, 47)
            top      = f"┌─ {heading} {'─' * (width - len(heading) - 4)}┐"
            bottom   = f"└{'─' * (width - 1)}┘"
            box_text = "\n".join([top] + new_lines + [bottom])
            written_text.append(box_text)

        # Only append diagram refs if at least one box had new content
        if had_real_box and diagram:
            written_text.append(f"[DIAGRAM: {diagram}]")

        if not written_text:
            print("[Note] Nothing new after dedup.")
            return

        entry = "\n\n".join(written_text)
        self._write_entry(entry)

    # ── File I/O ───────────────────────────────────────────────────────────────
    def _write_header(self):
        os.makedirs(self.dir, exist_ok=True)
        header = (
            f"SENTINEL NOTES\n"
            f"Session : {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
            f"Model   : {config.MODEL_NAME}  |  Audio: {config.CAPTURE_METHOD}\n"
            f"{'─' * 50}\n\n"
        )
        with open(self.path, "w", encoding="utf-8") as f:
            f.write(header)

    def _write_entry(self, text: str):
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(text + "\n\n")
        print(f"\n{'━' * 45}\n{text}\n{'━' * 45}\n")

    def _write_footer(self):
        footer = (
            f"{'─' * 50}\n"
            f"Ended   : {datetime.datetime.now().strftime('%H:%M:%S')}\n"
            f"Facts   : {self._dedup.fact_count()} unique facts stored\n"
            f"Topics  : {', '.join(self._dedup.known_headings())}\n"
        )
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(footer)