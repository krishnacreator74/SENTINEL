
"""
Layer 1: Session Memory for Sentinel
Short-term, transient memory that persists within a session
Replaces: memory_chat.py
"""

from typing import Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime
import json
import os


@dataclass
class MessageMemory:
    """A single memory from a message"""
    message_id: str
    text: str
    timestamp: datetime = field(default_factory=datetime.now)
    sender: str
    tokens_used: int = 0
    metadata: Dict = field(default_factory=dict)


class SessionMemory:
    """
    Layer 1: Session-based memory
    Stores transient memory that lasts for the session
    """
    
    def __init__(self, max_size: int = 1000):
        self.messages: List[MessageMemory] = []
        self.max_size = max_size
        self.context_window: List[str] = []
        self.context_size = 50  # Last N messages for context
        self.user_preferences: Dict[str, any] = {}
    
    def add_message(self, message_id: str, text: str, 
                   sender: str, tokens: int = 0,
                   metadata: Optional[Dict] = None) -> MessageMemory:
        """Add a new message memory"""
        mem = MessageMemory(
            message_id=message_id,
            text=text,
            sender=sender,
            tokens_used=tokens,
            metadata=metadata or {}
        )
        
        self.messages.append(mem)
        
        # Trim if over max size
        if len(self.messages) > self.max_size:
            self.messages = self.messages[-self.max_size:]
        
        return mem
    
    def get_context(self, num_messages: Optional[int] = None) -> List[str]:
        """Get recent messages for context"""
        num = num_messages or self.context_size
        messages = self.messages[-num:] if num else self.messages
        
        return [m.text for m in messages]
    
    def get_context_window(self) -> str:
        """Get context window as string"""
        return "\n".join(self.get_context())
    
    def get_user_preference(self, key: str, default: any = None) -> any:
        """Get a user preference"""
        return self.user_preferences.get(key, default)
    
    def set_user_preference(self, key: str, value: any):
        """Set a user preference"""
        self.user_preferences[key] = value
    
    def get_all_messages(self) -> List[Dict]:
        """Get all messages as dict list"""
        return [
            {
                "message_id": m.message_id,
                "text": m.text,
                "timestamp": m.timestamp.isoformat(),
                "sender": m.sender,
                "tokens": m.tokens_used,
                "metadata": m.metadata
            }
            for m in self.messages
        ]
    
    def save_to_file(self, path: str):
        """Save session memory to file"""
        data = {
            "messages": self.get_all_messages(),
            "preferences": self.user_preferences
        }
        
        with open(path, 'w') as f:
            json.dump(data, f, indent=2)
    
    @classmethod
    def load_from_file(cls, path: str) -> "SessionMemory":
        """Load session memory from file"""
        mem = cls()
        
        with open(path, 'r') as f:
            data = json.load(f)
        
        for msg_data in data["messages"]:
            mem.messages.append(MessageMemory(
                message_id=msg_data["message_id"],
                text=msg_data["text"],
                sender=msg_data["sender"],
                tokens=msg_data.get("tokens", 0),
                metadata=msg_data.get("metadata", {})
            ))
        
        mem.user_preferences = data.get("preferences", {})
        return mem


# Singleton-like session storage
_session_storage: Optional[SessionMemory] = None


def get_session_memory() -> SessionMemory:
    """Get or create the session memory instance"""
    global _session_storage
    if _session_storage is None:
        _session_storage = SessionMemory()
    return _session_storage


def clear_session_memory():
    """Clear session memory"""
    global _session_storage
    if _session_storage:
        _session_storage = SessionMemory()
        print("Session memory cleared")


def add_session_memory(message_id: str, text: str, sender: str, 
                      tokens: int = 0, metadata: Optional[Dict] = None):
    """Convenience function to add to session memory"""
    mem = get_session_memory()
    mem.add_message(message_id, text, sender, tokens, metadata)


# Compatibility function for old code
def get_chat_memory() -> SessionMemory:
    """Alias for get_session_memory"""
    return get_session_memory()
