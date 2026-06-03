
"""
Arc Blocks for Sentinel Personality
Defines atomic personality traits and their combinations
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum


class BlockType(Enum):
    """Types of personality blocks"""
    TRAIT = "trait"
    PREFERENCE = "preference"
    BEHAVIOR = "behavior"
    BELIEF = "belief"
    MEMORY = "memory"


@dataclass
class ArcBlock:
    """A single atomic personality block"""
    name: str
    block_type: BlockType
    description: str
    weight: float = 1.0
    context_keywords: List[str] = field(default_factory=list)
    modifiers: Dict[str, float] = field(default_factory=dict)
    active: bool = True
    
    def __post_init__(self):
        # Ensure weight is in valid range
        self.weight = max(0.0, min(1.0, self.weight))


class ArcBlocks:
    """
    Collection and management of personality arc blocks
    """
    
    def __init__(self):
        self.blocks: Dict[str, ArcBlock] = {}
        self.active_blocks: List[ArcBlock] = []
    
    def register_block(self, block: ArcBlock):
        """Register a new arc block"""
        if not block.active:
            return
        self.blocks[block.name] = block
        if block.name not in [b.name for b in self.active_blocks]:
            self.active_blocks.append(block)
    
    def unregister_block(self, name: str):
        """Remove a block"""
        if name in self.blocks:
            block = self.blocks.pop(name)
            self.active_blocks = [b for b in self.active_blocks if b.name != name]
    
    def get_block(self, name: str) -> Optional[ArcBlock]:
        """Get a specific block"""
        return self.blocks.get(name)
    
    def get_active_blocks(self) -> List[ArcBlock]:
        """Get all active blocks"""
        return self.active_blocks.copy()
    
    def filter_by_keyword(self, keyword: str) -> List[ArcBlock]:
        """Filter blocks by context keyword"""
        return [
            b for b in self.active_blocks 
            if keyword.lower() in [k.lower() for k in b.context_keywords]
        ]
    
    def calculate_influence(self, message: str) -> Dict[str, float]:
        """Calculate influence of each block on a given message"""
        message_lower = message.lower()
        influence = {}
        
        for block in self.active_blocks:
            if not block.active:
                continue
            
            base_influence = block.weight
            
            # Boost for keyword matches
            for kw in block.context_keywords:
                if kw.lower() in message_lower:
                    base_influence *= 1.2
            
            # Apply modifiers
            for trigger, factor in block.modifiers.items():
                if trigger.lower() in message_lower:
                    base_influence *= factor
            
            influence[block.name] = base_influence
        
        return influence


# Common arc blocks
DEFAULT_TRAITS = [
    ArcBlock(
        name="helpful",
        block_type=BlockType.TRAIT,
        description="Always tries to be helpful and supportive",
        weight=0.9,
        context_keywords=["help", "assist", "support", "helpful"],
        modifiers={"can't": 0.1, "sorry": 0.05}
    ),
    
    ArcBlock(
        name="curious",
        block_type=BlockType.TRAIT,
        description="Shows genuine curiosity and interest",
        weight=0.8,
        context_keywords=["interesting", "tell me", "explain", "how does"],
        modifiers={"boring": 0.3}
    ),
    
    ArcBlock(
        name="empathetic",
        block_type=BlockType.TRAIT,
        description="Responds with empathy and understanding",
        weight=0.85,
        context_keywords=["sad", "happy", "feelings", "emotions", "struggle"],
        modifiers={"anger": 0.5, "hate": 0.4}
    ),
]


def get_default_blocks() -> ArcBlocks:
    """Get default set of arc blocks"""
    blocks = ArcBlocks()
    for trait in DEFAULT_TRAITS:
        blocks.register_block(trait)
    return blocks
