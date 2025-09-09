import os
import random
from typing import List
import logging

logger = logging.getLogger(__name__)

class NameService:
    def __init__(self):
        self.names = self._load_names()
    
    def _load_names(self) -> List[str]:
        """Load names from names.txt file"""
        try:
            names_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'names.txt')
            with open(names_file, 'r') as f:
                names = [line.strip() for line in f if line.strip()]
            if len(names) < 4:
                raise ValueError("Need at least 4 names in names.txt")
            return names
        except Exception as e:
            logger.error(f"Error loading names: {e}")
            # Fallback names
            return [
                'AlphaWolf', 'BraveLion', 'CloudRunner', 'DreamCatcher',
                'EagleEye', 'FireSpirit', 'GoldenHawk', 'HappyPanda'
            ]
    
    def get_random_names(self, count: int = 4) -> List[str]:
        """Get random names for selection"""
        if count > len(self.names):
            count = len(self.names)
        return random.sample(self.names, count)
    
    def get_deterministic_names(self, seed: str, count: int = 4) -> List[str]:
        """Get deterministic names based on a seed (e.g., participant_id + room_id)"""
        if count > len(self.names):
            count = len(self.names)
        
        # Use seed to create deterministic random state
        rng = random.Random(seed)
        return rng.sample(self.names, count)

# Global name service instance
name_service = NameService()