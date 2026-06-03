
"""
Layer 2: Ep
"""

from typing import Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime
import json
import hashlib
import os


@dataclass
class EpisodeMetadata:
    """Metadata about an episode"""
    episode_id: str
    summary: str
    key_themes: List[str] = field(default_factory=list)
    memorable_moments: List[str] = field(default_factory=list)
    emotional_summary: str = ""
    user_state_summary: str = ""
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)


class EpisodeStore:
    """
    Layer 2: Episode-based memory
    Stores compressed summaries of conversation episodes
    Episodes are created when conversation shifts significantly
    """
    
    def __init__(self):
        self.episodes: Dict[str, EpisodeMetadata] = {}
        self.episode_counter = 0
    
    def create_episode(self, summary: str, 
                      key_themes: Optional[List[str]] = None,
                      memorable_moments: Optional[List[str]] = None) -> EpisodeMetadata:
        """Create a new episode from recent conversation"""
        self.episode_counter += 1
        
        episode_id = f"ep_{self.episode_counter:04d}"
        
        episode = EpisodeMetadata(
            episode_id=episode_id,
            summary=summary,
            key_themes=key_themes or [],
            memorable_moments=memorable_moments or [],
            emotional_summary=self._summarize_emotion(summary),
            user_state_summary=self._summarize_state(summary)
        )
        
        self.episodes[episode_id] = episode
        return episode
    
    def _summarize_emotion(self, text: str) -> str:
        """Summarize emotional tone of text"""
        # Simplified emotion detection
        positive_words = ["happy", "great", "love", "amazing", "wonderful"]
        negative_words = ["sad", "terrible", "hate", "awful", "worried"]
        
        text_lower = text.lower()
        pos_count = sum(1 for word in positive_words if word in text_lower)
        neg_count = sum(1 for word in negative_words if word in text_lower)
        
        if pos_count > neg_count + 1:
            return "generally positive"
        elif neg_count > pos_count + 1:
            return "generally negative"
        elif pos_count + neg_count > 0:
            return "mixed emotions"
        else:
            return "neutral"
    
    def _summarize_state(self, text: str) -> str:
        """Summarize user's current state/intent"""
        # Simplified intent detection
        intent_words = ["help", "explain", "teach", "show me", "let's", 
                       "can you", "need to", "wants to"]
        
        text_lower = text.lower()
        intent_count = sum(1 for word in intent_words if word in text_lower)
        
        if intent_count >= 2:
            return "seeking assistance"
        elif len(text.split()) < 10:
            return "brief/greeting"
        else:
            return "ongoing discussion"
    
    def get_episode(self, episode_id: str) -> Optional[EpisodeMetadata]:
        """Get a specific episode"""
        return self.episodes.get(episode_id)
    
    def get_episodes(self, limit: Optional[int] = None) -> List[EpisodeMetadata]:
        """Get episodes, optionally limited"""
        episodes = list(self.episodes.values())
        
        if limit:
            # Sort by created_at descending and take first N
            episodes.sort(key=lambda e: e.created_at, reverse=True)
            episodes = episodes[:limit]
        
        return episodes
    
    def get_recent_episodes(self, count: int = 10) -> List[Dict]:
        """Get recent episodes as dict list"""
        episodes = self.get_episodes(count)
        return [
            {
                "id": e.episode_id,
                "summary": e.summary[:200],  # Truncate
                "themes": e.key_themes[:5],  # Limit themes
                "emotional": e.emotional_summary,
                "user_state": e.user_state_summary,
                "created": e.created_at.isoformat()
            }
            for e in episodes
        ]
    
    def search_episodes(self, query: str) -> List[EpisodeMetadata]:
        """Search episodes by content"""
        query_lower = query.lower()
        return [
            e for e in self.episodes.values()
            if query_lower in e.summary.lower()
            or any(query_lower in t.lower() for t in e.key_themes)
        ]
    
    def update_episode(self, episode_id: str, **kwargs):
        """Update episode metadata"""
        if episode_id in self.episodes:
            for key, value in kwargs.items():
                setattr(self.episodes[episode_id], key, value)
            self.episodes[episode_id].updated_at = datetime.now()
    
    def get_emotional_trend(self, limit: int = 20) -> List[Dict]:
        """Get emotional trend of recent episodes"""
        episodes = self.get_episodes(limit)
        return [
            {
                "episode_id": e.episode_id,
                "emotion": e.emotional_summary,
                "timestamp": e.created_at.isoformat()
            }
            for e in reversed(episodes)
        ]
    
    def save_to_file(self, path: str):
        """Save episodes to file"""
        data = {
            "episodes": {
                ep_id: {
                    "id": e.episode_id,
                    "summary": e.summary,
                    "themes": e.key_themes,
                    "emotional": e.emotional_summary,
                    "user_state": e.user_state_summary,
                    "created": e.created_at.isoformat()
                }
                for ep_id, e in self.episodes.items()
            }
        }
        
        with open(path, 'w') as f:
            json.dump(data, f, indent=2)
    
    @classmethod
    def load_from_file(cls, path: str) -> "EpisodeStore":
        """Load episodes from file"""
        store = cls()
        
        with open(path, 'r') as f:
            data = json.load(f)
        
        for ep_id, ep_data in data["episodes"].items():
            episode = EpisodeMetadata(
                episode_id=ep_data["id"],
                summary=ep_data["summary"],
                key_themes=ep_data.get("themes", []),
                emotional_summary=ep_data.get("emotional", ""),
                user_state_summary=ep_data.get("user_state", ""),
                created_at=datetime.fromisoformat(ep_data["created"])
            )
            store.episodes[ep_id] = episode
        
        return store


# Global episode store
_episode_store: Optional[EpisodeStore] = None


def get_episode_store() -> EpisodeStore:
    """Get or create the episode store"""
    global _episode_store
    if _episode_store is None:
        _episode_store = EpisodeStore()
    return _episode_store


def clear_episode_store():
    """Clear episode store"""
    global _episode_store
    if _episode_store:
        _episode_store = EpisodeStore()
        print("Episode store cleared")
