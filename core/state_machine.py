
"""
State Machine Implementation for Sentinel
Manages transitions between different operational states
"""

from enum import Enum
from typing import Dict, Callable, Optional
from datetime import datetime


class State(Enum):
    """Operational states for the system"""
    IDLE = "idle"
    LISTENING = "listening"
    PROCESSING = "processing"
    RESPONDING = "responding"
    ERROR = "error"


class StateMachine:
    """
    State machine for managing system states and transitions
    """
    
    def __init__(self):
        self._current_state = State.IDLE
        self._state_handlers: Dict[State, Callable] = {}
        self._transitions: Dict[str, Dict[str, Callable]] = {}
    
    def set_state(self, state: State, handler: Optional[Callable] = None):
        """Set the current state and optionally register a handler"""
        self._current_state = state
        if handler:
            self._state_handlers[state] = handler
    
    def transition(self, transition: str, next_state: State):
        """Handle a state transition"""
        if transition in self._transitions and next_state in self._transitions[transition]:
            return self._transitions[transition][next_state]()
        return None
    
    def register_transition(self, transition: str, 
                          from_state: State, 
                          to_state: State,
                          handler: Callable):
        """Register a transition handler"""
        if from_state not in self._transitions:
            self._transitions[from_state] = {}
        self._transitions[from_state][to_state] = handler
    
    @property
    def current_state(self) -> State:
        """Get current state"""
        return self._current_state
    
    @property
    def state_name(self) -> str:
        """Get current state name"""
        return self._current_state.value
    
    def on(self, state: State, handler: Callable):
        """Decorator for state handlers"""
        def decorator(func):
            self._state_handlers[state] = func
            return func
        return decorator
    
    def handle(self):
        """Execute current state handler if registered"""
        if self._current_state in self._state_handlers:
            return self._state_handlers[self._current_state]()


def create_state_machine() -> StateMachine:
    """Factory function to create a state machine instance"""
    return StateMachine()
