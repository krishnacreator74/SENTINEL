
"""
Relationship Management for Sentinel
Tracks relationships with users and interaction history
"""

from typing import Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum


class RelationshipStatus(Enum):
    """Relationship status types"""
    STRANGER = "stranger"
    ACQUAINTANCE = "acquaintance"
    FRIEND = "friend"
    CLOSE_FRIEND = "close_friend"
    FAMILY = "family"


@dataclass
class UserInteraction:
    """Record of an interaction with a user"""
    timestamp: datetime
    message_length: int
    sentiment: str  # positive, neutral, negative
    topics: List[str]
    emotional_intensity: float = 0.0


@dataclass
class Relationship:
    """Represents a relationship with a specific user"""
    user_id: str
    username: Optional[str] = None
    status: RelationshipStatus = RelationshipStatus.STRANGER
    created_at: datetime = field(default_factory=datetime.now)
    last_interaction: Optional[datetime] = None
    interaction_count: int = 0
    total_positive: int = 0
    total_negative: int = 0
    
    interests: List[str] = field(default_factory=list)
    preferences: Dict[str, str] = field(default_factory=dict)
    memories: List[str] = field(default_factory=list)
    milestones: List[datetime] = field(default_factory=list)
    
    def add_interaction(self, interaction: UserInteraction):
        """Record a new interaction"""
        self.last_interaction = interaction.timestamp
        self.interaction_count += 1
        
        if interaction.sentiment == "positive":
            self.total_positive += 1
        elif interaction.sentiment == "negative":
            self.total_negative += 1
    
    def get_satisfaction_score(self) -> float:
        """Calculate relationship satisfaction score"""
        if self.interaction_count == 0:
            return 0.5
        
        positive_ratio = self.total_positive / self.interaction_count
        return min(1.0, 0.5 + (positive_ratio - 0.5) * 2)
    
    def update_status(self):
        """Update relationship status based on interaction metrics"""
        if self.interaction_count < 5:
            self.status = RelationshipStatus.STRANGER
        elif self.interaction_count < 15:
            self.status = RelationshipStatus.ACQUAINTANCE
        elif self.get_satisfaction_score() > 0.7:
            self.status = RelationshipStatus.CLOSE_FRIEND
        elif self.get_satisfaction_score() > 0.5:
            self.status = RelationshipStatus.FRIEND
        else:
            self.status = RelationshipStatus.ACQUAINTANCE
    
    def remember(self, event: str):
        """Remember an event about the user"""
        self.memories.append(f"{datetime.now()}: {event}")
    
    def celebrate_milestone(self):
        """Celebrate a relationship milestone"""
        self.milestones.append(datetime.now())


class RelationshipManager:
    """
    Manages all relationships and their evolution
    """
    
    def __init__(self):
        self.relationships: Dict[str, Relationship] = {}
        self.user_ids_seen: set = set()
    
    def get_or_create(self, user_id: str, username: Optional[str] = None) -> Relationship:
        """Get or create a relationship for a user"""
        if user_id not in self.relationships:
            self.relationships[user_id] = Relationship(
                user_id=user_id,
                username=username
            )
        return self.relationships[user_id]
    
    def get_relationship(self, user_id: str) -> Optional[Relationship]:
        """Get a specific relationship"""
        return self.relationships.get(user_id)
    
    def process_interaction(self, user_id: str, interaction: UserInteraction):
        """Process a new interaction"""
        rel = self.get_or_create(user_id)
        rel.add_interaction(interaction)
        rel.update_status()
        
        # Track new user
        if user_id not in self.user_ids_seen:
            self.user_ids_seen.add(user_id)
    
    def get_strangers(self) -> List[Relationship]:
        """Get all strangers"""
        return [r for r in self.relationships.values() 
                if r.status == RelationshipStatus.STRANGER]
    
    def get_close_friends(self) -> List[Relationship]:
        """Get all close friends"""
        return [r for r in self.relationships.values()
                if r.status == RelationshipStatus.CLOSE_FRIEND]
    
    def get_relationship_strength(self, user_id: str) -> float:
        """Get overall relationship strength score"""
        rel = self.get_relationship(user_id)
        if not rel:
            return 0.0
        
        strength = rel.get_satisfaction_score()
        
        # Boost based on interaction count
        interaction_boost = min(0.3, rel.interaction_count * 0.01)
        
        # Boost based on time invested
        if rel.last_interaction:
            days_active = (datetime.now() - rel.created_at).days
            time_boost = min(0.2, days_active * 0.001)
        else:
            time_boost = 0
        
        return min(1.0, strength + interaction_boost + time_boost)
    
    def save_all_relationships(self, path: str):
        """Save all relationships to file"""
        import json
        data = {
            "relationships": {},
            "user_ids": list(self.user_ids_seen)
        }
        
        for rel in self.relationships.values():
            rel_data = {
                "status": rel.status.value,
                "interactions": rel.interaction_count,
                "satisfaction": rel.get_satisfaction_score(),
                "memories": rel.memories[-5:],  # Last 5 memories
                "preferences": rel.preferences
            }
            data["relationships"][rel.user_id] = rel_data
        
        with open(path, 'w') as f:
            json.dump(data, f, indent=2)


def create_relationship_manager() -> RelationshipManager:
    """Factory function to create RelationshipManager instance"""
    return RelationshipManager()
