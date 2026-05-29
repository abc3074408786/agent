"""
BrainOS - Bio-Inspired Cognitive Architecture

Modules modeled after brain regions:
- Thalamus: Information router + attention gating
- Prefrontal: Planning + working memory (7±2 chunks)
- Hippocampus: Memory formation + sleep consolidation
- Cerebellum: Prediction-comparison-correction loop
- Basal Ganglia: Habit formation + reward learning
- Amygdala: Risk assessment + emergency interrupt
- Default Network: Divergent association + creativity
- Mirror System: Observation learning + behavior imitation
"""

from agent.brain.core import BrainOS

__all__ = ["BrainOS"]
