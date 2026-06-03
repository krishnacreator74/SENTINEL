
"""
Owner Recognition for Sentinel Voice
Handles detection of trusted users via voice patterns
"""

from typing import Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime
import json
import os
import hashlib


@dataclass
class VoiceProfile:
    """Voice profile for a trusted user"""
    user_id: str
    username: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    voice_features: Dict = field(default_factory=dict)
    phrase_patterns: Dict[str, float] = field(default_factory=dict)
    prosody_patterns: Dict[str, float] = field(default_factory=dict)
    confidence_threshold: float = 0.7
    registered_phrases: List[str] = field(default_factory=list)
    last_verified: Optional[datetime] = None
    trust_level: float = 0.5


class VoiceProfileManager:
    """
    Manages voice profiles for trusted users
    Stores and compares voice patterns
    """
    
    def __init__(self, data_dir: str = "voice/profiles"):
        self.data_dir = data_dir
        self.profiles: Dict[str, VoiceProfile] = {}
        self._ensure_storage()
    
    def _ensure_storage(self):
        """Ensure storage directory exists"""
        os.makedirs(self.data_dir, exist_ok=True)
    
    def _generate_id(self, content: str) -> str:
        """Generate ID from voice features hash"""
        feature_hash = hashlib.md5(
            json.dumps(sorted(content.items()), default=str).encode()
        ).hexdigest()[:8]
        return f"vp_{feature_hash}"
    
    def register_profile(self, user_id: str, username: Optional[str] = None,
                        voice_features: Optional[Dict] = None,
                        phrases: Optional[List[str]] = None) -> VoiceProfile:
        """Register a new voice profile"""
        profile_id = self._generate_id(voice_features or {})
        
        profile = VoiceProfile(
            user_id=user_id,
            username=username,
            voice_features=voice_features or {},
            registered_phrases=phrases or [],
            confidence_threshold=0.7
        )
        
        self.profiles[user_id] = profile
        
        self._save_to_storage()
        return profile
    
    def update_profile(self, user_id: str, **kwargs):
        """Update an existing profile"""
        if user_id in self.profiles:
            profile = self.profiles[user_id]
            
            for key, value in kwargs.items():
                if hasattr(profile, key):
                    setattr(profile, key, value)
            
            profile.last_verified = datetime.now()
            self._save_to_storage()
    
    def get_profile(self, user_id: str) -> Optional[VoiceProfile]:
        """Get a voice profile"""
        return self.profiles.get(user_id)
    
    def verify_voice(self, voice_data: Dict, user_id: str) -> Dict:
        """
        Verify if voice matches a registered profile
        Returns confidence score and verification status
        """
        profile = self.get_profile(user_id)
        
        if not profile:
            return {
                "verified": False,
                "reason": "No profile found",
                "confidence": 0.0
            }
        
        # Simple feature matching
        matched_features = 0
        total_features = len(profile.voice_features)
        
        if voice_data:
            for feature, expected_val in profile.voice_features.items():
                actual_val = voice_data.get(feature)
                if actual_val is not None:
                    # Simple threshold matching
                    if abs(actual_val - expected_val) < 0.1:  # 10% tolerance
                        matched_features += 1
        
        # Check phrase patterns
        pattern_matches = 0
        for phrase, confidence in profile.phrase_patterns.items():
            if phrase in voice_data.get("transcript", ""):
                pattern_matches += confidence * 0.1
        
        # Calculate overall confidence
        feature_confidence = matched_features / total_features if total_features > 0 else 0
        overall_confidence = max(profile.confidence_threshold, 
                               feature_confidence + pattern_matches)
        
        verified = overall_confidence >= profile.confidence_threshold
        
        result = {
            "verified": verified,
            "confidence": overall_confidence,
            "profile_found": profile is not None,
            "threshold": profile.confidence_threshold
        }
        
        if verified:
            profile.last_verified = datetime.now()
            profile.trust_level = min(1.0, profile.trust_level + 0.05)
            self._save_to_storage()
        
        return result
    
    def add_phrase_pattern(self, user_id: str, phrase: str, confidence: float):
        """Add a phrase pattern to a profile"""
        profile = self.get_profile(user_id)
        if profile:
            profile.phrase_patterns[phrase] = confidence
            self._save_to_storage()
    
    def register_phrase(self, user_id: str, phrase: str):
        """Register a phrase as verified"""
        profile = self.get_profile(user_id)
        if profile:
            profile.registered_phrases.append(phrase)
            # Update phrase pattern with high confidence
            self.add_phrase_pattern(user_id, phrase, 0.95)
            self._save_to_storage()
    
    def get_trusted_users(self) -> List[VoiceProfile]:
        """Get all trusted users"""
        return list(self.profiles.values())
    
    def get_trusted_count(self) -> int:
        """Count of trusted users"""
        return len(self.profiles)
    
    def get_high_trust_users(self, min_trust: float = 0.8) -> List[VoiceProfile]:
        """Get users with high trust level"""
        return [p for p in self.profiles.values() 
                if p.trust_level >= min_trust]
    
    def save_to_storage(self):
        """Save profiles to storage"""
        storage_file = os.path.join(self.data_dir, "profiles.json")
        
        data = {
            "profiles": {
                user_id: {
                    "user_id": p.user_id,
                    "username": p.username,
                    "voice_features": p.voice_features,
                    "phrase_patterns": p.phrase_patterns,
                    "prosody_patterns": p.prosody_patterns,
                    "confidence_threshold": p.confidence_threshold,
                    "registered_phrases": p.registered_phrases,
                    "last_verified": p.last_verified.isoformat() if p.last_verified else None,
                    "trust_level": p.trust_level
                }
                for user_id, p in self.profiles.items()
            }
        }
        
        with open(storage_file, 'w') as f:
            json.dump(data, f, indent=2)
    
    def _save_to_storage(self):
        """Internal save to storage"""
        self.save_to_storage()
    
    @classmethod
    def load_from_storage(cls, data_dir: str = "voice/profiles") -> "VoiceProfileManager":
        """Load profiles from storage"""
        manager = VoiceProfileManager(data_dir)
        storage_file = os.path.join(data_dir, "profiles.json")
        
        if os.path.exists(storage_file):
            with open(storage_file, 'r') as f:
                data = json.load(f)
            
            for user_id, profile_data in data["profiles"].items():
                profile = VoiceProfile(
                    user_id=profile_data["user_id"],
                    username=profile_data.get("username"),
                    voice_features=profile_data.get("voice_features", {}),
                    phrase_patterns=profile_data.get("phrase_patterns", {}),
                    prosody_patterns=profile_data.get("prosody_patterns", {}),
                    confidence_threshold=profile_data.get("confidence_threshold", 0.7),
                    registered_phrases=profile_data.get("registered_phrases", []),
                    last_verified=datetime.fromisoformat(
                        profile_data["last_verified"]
                    ) if profile_data.get("last_verified") else None,
                    trust_level=profile_data.get("trust_level", 0.5)
                )
                manager.profiles[user_id] = profile
        
        return manager


# Global profile manager
_profile_manager: Optional[VoiceProfileManager] = None


def get_voice_profiles() -> VoiceProfileManager:
    """Get or create the voice profile manager"""
    global _profile_manager
    if _profile_manager is None:
        _profile_manager = VoiceProfileManager()
    return _profile_manager


def register_trusted_voice(user_id: str, username: Optional[str] = None,
                          voice_features: Optional[Dict] = None,
                          phrases: Optional[List[str]] = None) -> VoiceProfile:
    """Convenience function to register a trusted voice"""
    manager = get_voice_profiles()
    return manager.register_profile(user_id, username, voice_features, phrases)


def verify_voice(voice_data: Dict, user_id: str) -> Dict:
    """Convenience function to verify voice"""
    manager = get_voice_profiles()
    return manager.verify_voice(voice_data, user_id)
