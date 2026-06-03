
"""
Personality Arcs for Sentinel
Defines the core personality dimensions and their evolution
"""

from typing import Dict, List, Optional
from dataclasses import dataclass, field


@dataclass
class ArcDimension:
    """Represents a personality arc dimension"""
    name: str
    description: str
    range_start: float = 0.0
    range_end: float = 1.0
    current_value: float = 0.5
    evolution_function: Optional[callable] = None


class PersonalityArcs:
    """
    Manages personality arc dimensions and their evolution
    """
    
    def __init__(self):
        self.dimensions: Dict[str, ArcDimension] = {}
        self.evolution_history: List[Dict] = []
        
        # Define default arc dimensions
        self._initialize_default_arcs()
    
    def _initialize_default_arcs(self):
        """Initialize default personality arc dimensions"""
        self.dimensions["warmth"] = ArcDimension(
            name="warmth",
            description="Emotional closeness and friendliness",
            current_value=0.5
        )
        
        self.dimensions["intellect"] = ArcDimension(
            name="intellect",
            description="Curiosity and knowledge-seeking",
            current_value=0.7
        )
        
        self.dimensions["adventurousness"] = ArcDimension(
            name="adventurousness",
            description="Willingness to try new experiences",
            current_value=0.6
        )
        
        self.dimensions["anxiet"] = ArcDimension(
            name="anxiety",
            description="Tendency towards worry or concern",
            range_start=0.0,
            range_end=1.0,
            current_value=0.2
        )
        
        self.dimensions["orderliness"] = ArcDimension(
            name="orderliness",
            description="Preference for structure and organization",
            current_value=0.6
        )
    
    def get_dimension(self, name: str) -> Optional[ArcDimension]:
        """Get a specific arc dimension"""
        return self.dimensions.get(name)
    
    def get_current_values(self) -> Dict[str, float]:
        """Get current values of all dimensions"""
        return {name: dim.current_value for name, dim in self.dimensions.items()}
    
    def update_dimension(self, name: str, value: float):
        """Update a dimension value"""
        if name in self.dimensions:
            self.dimensions[name].current_value = max(
                self.dimensions[name].range_start,
                min(self.dimensions[name].range_end, value)
            )
    
    def evolve(self, dimension_name: str, factor: float):
        """Evolve a dimension by a multiplicative factor"""
        if dimension_name in self.dimensions:
            dim = self.dimensions[dimension_name]
            new_value = dim.current_value * (1 + factor)
            self.update_dimension(dimension_name, new_value)
    
    def get_profile(self) -> Dict:
        """Get a personality profile snapshot"""
        return {
            "dimensions": self.get_current_values(),
            "history": self.evolution_history[-10:]  # Last 10 updates
        }
    
    def save_profile(self, path: str):
        """Save personality profile to file"""
        import json
        profile = self.get_profile()
        with open(path, 'w') as f:
            json.dump(profile, f, indent=2)


def create_arcs() -> PersonalityArcs:
    """Factory function to create PersonalityArcs instance"""
    return PersonalityArcs()
