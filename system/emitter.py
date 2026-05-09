"""
A simple event emitter system.
Used for decoupled communication between components, 
especially for triggering side effects like app launches or HUD updates without tight coupling to the main pipeline.
The Emitter class allows registering handlers for specific events and emitting those events with arbitrary arguments. 
This is particularly useful for handling system commands that should bypass the LLM and for updating the UI or HUD in response to certain triggers.
"""

class Emitter:
    def __init__(self):
        self.handlers = {}

    def on(self, event, fn):
        self.handlers.setdefault(event, []).append(fn)

    def emit(self, event, *args, **kwargs):
        for fn in self.handlers.get(event, []):
            fn(*args, **kwargs)