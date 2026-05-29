"""Default Mode Network - Divergent Association + Creativity"""

import random
import time
from typing import Any


class DefaultNetwork:
    """
    Active during 'idle' time. Generates novel connections.
    
    Principles:
    - Random association: connect unrelated concepts
    - Incubation: solutions emerge after stepping away
    - Bisociation: combine ideas from different frames
    """

    def __init__(self):
        self.concept_pool: list[str] = []
        self.insights: list[dict] = []

    def add_concept(self, concept: str) -> None:
        self.concept_pool.append(concept)
        if len(self.concept_pool) > 200:
            self.concept_pool = self.concept_pool[-200:]

    def daydream(self, n_associations: int = 3) -> list[dict]:
        """Generate random associations between concepts."""
        if len(self.concept_pool) < 4:
            return []
        results = []
        for _ in range(n_associations):
            a, b = random.sample(self.concept_pool, 2)
            insight = {
                "concepts": [a, b],
                "prompt": f"如果把 '{a}' 和 '{b}' 结合会怎样？",
                "timestamp": time.time(),
            }
            results.append(insight)
            self.insights.append(insight)
        return results

    def get_recent_insights(self, n: int = 5) -> list[dict]:
        return self.insights[-n:]
