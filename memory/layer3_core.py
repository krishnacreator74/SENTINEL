
"""
Layer 3: Core Memory for Sentinel
Persistent, long-term memory that survives across sessions
Replaces: memory_persistent.py
"""

from typing import Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime
import json
import os
import hashlib


@dataclass
class CoreMemoryItem:
    """A core memory item (fact, preference, fact, preference, fact, fact"""
    item_id: str
    content: str
    category: str  # "fact", "preference", "goal", "belief", "fact", "preference"
    confidence: float = 1.0
    source: str = "user"
    tags: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    last_accessed: datetime = field(default_factory=datetime.now)
    importance: float = 0.5


class CoreMemoryStore:
    """
    Layer 3: Core memory
    Persistent memory that survives across sessions
    Organized by categories with confidence scores
    """
    
    def __init__(self, data_dir: str = "memory/core"):
        self.data_dir = data_dir
        self.items: Dict[str, CoreMemoryItem] = {}
        self.categories: Dict[str, List[str]] = {}  # category -> item_ids
        self._ensure_storage()
    
    def _ensure_storage(self):
        """Ensure storage directory exists"""
        os.makedirs(self.data_dir, exist_ok=True)
        storage_file = os.path.join(self.data_dir, "core_memory.json")
        
        if not os.path.exists(storage_file):
            # Initialize empty store
            self._save_to_storage()
    
    def _generate_id(self, content: str, category: str) -> str:
        """Generate unique ID for an item"""
        content_hash = hashlib.md5(
            f"{content}{category}{datetime.now().isoformat()}".encode()
        ).hexdigest()[:12]
        return f"core_{content_hash}"
    
    def add_fact(self, content: str, category: str = "default",
                confidence: float = 1.0, source: str = "user",
                tags: Optional[List[str]] = None) -> CoreMemoryItem:
        """Add a fact to core memory"""
        item_id = self._generate_id(content, category)
        
        item = CoreMemoryItem(
            item_id=item_id,
            content=content,
            category=category,
            confidence=confidence,
            source=source,
            tags=tags or []
        )
        
        self.items[item_id] = item
        
        # Index by category
        if category not in self.categories:
            self.categories[category] = []
        self.categories[category].append(item_id)
        
        self._save_to_storage()
        return item
    
    def update_fact(self, item_id: str, content: Optional[str] = None,
                   confidence: Optional[float] = None,
                   tags: Optional[List[str]] = None):
        """Update an existing fact"""
        if item_id in self.items:
            item = self.items[item_id]
            
            if content is not None:
                item.content = content
                item.item_id = self._generate_id(item.content, item.category)
                self.items[item.item_id] = item
                del self.items[item_id]
                self.categories[item.category].remove(item_id)
                self.categories[item.category].append(item.item_id)
            
            if confidence is not None:
                item.confidence = confidence
            
            if tags is not None:
                item.tags = tags
            
            item.last_accessed = datetime.now()
            
            self._save_to_storage()
    
    def remove_fact(self, item_id: str):
        """Remove a fact"""
        if item_id in self.items:
            item = self.items.pop(item_id)
            if item.category in self.categories:
                if item_id in self.categories[item.category]:
                    self.categories[item.category].remove(item_id)
            
            self._save_to_storage()
    
    def get_fact(self, item_id: str) -> Optional[CoreMemoryItem]:
        """Get a fact by ID"""
        return self.items.get(item_id)
    
    def get_facts(self, category: Optional[str] = None) -> List[CoreMemoryItem]:
        """Get all facts, optionally filtered by category"""
        if category:
            item_ids = self.categories.get(category, [])
            return [self.items[item_id] for item_id in item_ids 
                    if item_id in self.items]
        return list(self.items.values())
    
    def search(self, query: str) -> List[CoreMemoryItem]:
        """Search facts by content"""
        query_lower = query.lower()
        return [
            item for item in self.items.values()
            if query_lower in item.content.lower()
        ]
    
    def get_relevant(self, context: str, max_results: int = 10) -> List[CoreMemoryItem]:
        """Get most relevant facts to a context"""
        # Simple relevance scoring
        relevance = []
        
        for item in self.items.values():
            score = 0
            
            # Boost by confidence
            score += item.confidence * 10
            
            # Boost by recency
            days_since = (datetime.now() - item.last_accessed).days
            recency_score = max(0, (5 - days_since) * 2)
            score += recency_score
            
            # Boost by category match
            if "default" not in item.category.lower():
                score += 5
            
            relevance.append((score, item))
        
        # Sort by score descending
        relevance.sort(key=lambda x: x[0], reverse=True)
        
        return [item for _, item in relevance[:max_results]]
    
    def get_preferred(self, topic: str = "") -> List[CoreMemoryItem]:
        """Get high-confidence items, optionally filtered by topic"""
        items = [
            item for item in self.items.values()
            if item.confidence >= 0.7
        ]
        
        if topic:
            topic_lower = topic.lower()
            items = [
                item for item in items
                if topic_lower in item.content.lower()
            ]
        
        return items
    
    def add_preference(self, content: str, key: str) -> CoreMemoryItem:
        """Add a user preference (stored separately with key for easy lookup)"""
        item = self.add_fact(
            content=content,
            category="preference",
            confidence=0.9,
            source="user",
            tags=[key]
        )
        return item
    
    def get_preference(self, key: str) -> Optional[CoreMemoryItem]:
        """Get preference by key"""
        items = self.get_facts(category="preference")
        for item in items:
            if key.lower() in item.content.lower() or key in item.tags:
                return item
        return None
    
    def update_preference(self, key: str, new_content: str) -> Optional[CoreMemoryItem]:
        """Update a preference by key"""
        item = self.get_preference(key)
        if item:
            self.update_fact(item.item_id, new_content)
            return self.get_fact(item.item_id)
        return None
    
    def add_goal(self, content: str, tags: Optional[List[str]] = None) -> CoreMemoryItem:
        """Add a goal to core memory"""
        return self.add_fact(
            content=content,
            category="goal",
            confidence=0.8,
            source="user",
            tags=tags
        )
    
    def remove_goal(self, item_id: str):
        """Remove a goal"""
        self.remove_fact(item_id)
    
    def list_goals(self) -> List[CoreMemoryItem]:
        """List all goals"""
        return self.get_facts(category="goal")
    
    def get_goals_in_progress(self) -> List[CoreMemoryItem]:
        """Get goals that are currently relevant"""
        goals = self.list_goals()
        active_keywords = ["want to", "need to", "looking for", "interested in"]
        
        return [
            goal for goal in goals
            if any(kw in goal.content.lower() for kw in active_keywords)
        ]
    
    def save_to_storage(self):
        """Save to storage file"""
        storage_file = os.path.join(self.data_dir, "core_memory.json")
        
        data = {
            "items": {
                item_id: {
                    "content": item.content,
                    "category": item.category,
                    "confidence": item.confidence,
                    "source": item.source,
                    "tags": item.tags,
                    "created_at": item.created_at.isoformat(),
                    "last_accessed": item.last_accessed.isoformat()
                }
                for item_id, item in self.items.items()
            },
            "categories": self.categories
        }
        
        with open(storage_file, 'w') as f:
            json.dump(data, f, indent=2)
    
    def _save_to_storage(self):
        """Internal save to storage"""
        self.save_to_storage()
    
    @classmethod
    def load_from_storage(cls, data_dir: str = "memory/core") -> "CoreMemoryStore":
        """Load from storage"""
        store = cls(data_dir)
        storage_file = os.path.join(data_dir, "core_memory.json")
        
        if os.path.exists(storage_file):
            with open(storage_file, 'r') as f:
                data = json.load(f)
            
            for item_id, item_data in data["items"].items():
                item = CoreMemoryItem(
                    item_id=item_data["item_id"],
                    content=item_data["content"],
                    category=item_data["category"],
                    confidence=item_data.get("confidence", 1.0),
                    source=item_data.get("source", "user"),
                    tags=item_data.get("tags", []),
                    created_at=datetime.fromisoformat(item_data["created_at"]),
                    last_accessed=datetime.fromisoformat(item_data["last_accessed"])
                )
                store.items[item_id] = item
            
            store.categories = data.get("categories", {})
        
        return store


# Global core memory store
_core_memory_store: Optional[CoreMemoryStore] = None


def get_core_memory() -> CoreMemoryStore:
    """Get or create the core memory store"""
    global _core_memory_store
    if _core_memory_store is None:
        _core_memory_store = CoreMemoryStore()
    return _core_memory_store


def clear_core_memory():
    """Clear core memory (warning: this is persistent data!)"""
    global _core_memory_store
    if _core_memory_store:
        _core_memory_store = CoreMemoryStore()
        print("Core memory cleared")


# Compatibility functions
def get_persistent_memory() -> CoreMemoryStore:
    """Alias for get_core_memory"""
    return get_core_memory()
