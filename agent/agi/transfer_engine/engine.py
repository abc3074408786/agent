"""
TransferEngine: Generalize knowledge from one domain to another.

When the agent learns "decompose complex problems into modules" in coding,
it can apply the same pattern to design, writing, or project management.
"""

from __future__ import annotations
from pathlib import Path
from typing import Optional

from agent.agi.base import AGIModule, Pattern, Experience


# Domain similarity matrix (how transferable knowledge is between domains)
DOMAIN_SIMILARITY: dict[tuple[str, str], float] = {
    ("python", "javascript"): 0.8,
    ("python", "devops"): 0.5,
    ("frontend", "design"): 0.7,
    ("backend", "database"): 0.6,
    ("architecture", "project_management"): 0.5,
    ("testing", "security"): 0.4,
    ("content", "copywriting"): 0.9,
    ("video", "audio"): 0.6,
    ("data_analysis", "business"): 0.7,
}


class TransferEngine(AGIModule):
    """
    Extracts abstract principles from domain-specific experiences
    and applies them to new domains.
    """

    def name(self) -> str:
        return "TransferEngine"

    def __init__(self, data_dir: Path):
        super().__init__(data_dir)
        self.abstract_patterns: list[Pattern] = []
        self._load()

    def _load(self):
        saved = self.load_state("abstract_patterns.json", [])
        self.abstract_patterns = [Pattern.from_dict(p) for p in saved]

    def _save(self):
        self.save_state("abstract_patterns.json", [p.to_dict() for p in self.abstract_patterns])

    def abstract_from_experience(self, pattern: Pattern) -> Optional[Pattern]:
        """
        Take a domain-specific pattern and generalize it.
        
        Example:
            Input:  "In Python, always write tests before refactoring" (domain: python)
            Output: "Before modifying existing work, create verification checkpoints" (domain: *)
        """
        # Abstraction rules
        abstractions = {
            "PREFER": "This approach works well in similar contexts",
            "AVOID": "This approach tends to fail",
            "SEQUENCE": "Ordering matters: preparation before execution",
        }

        for keyword, abstract_desc in abstractions.items():
            if keyword in pattern.abstract_rule:
                abstract = Pattern(
                    id=f"abstract-{pattern.id}",
                    description=f"[通用] {abstract_desc}: {pattern.description}",
                    abstract_rule=self._generalize_rule(pattern.abstract_rule),
                    source_domain=pattern.source_domain,
                    applicable_domains=self._find_transferable_domains(pattern.source_domain),
                    confidence=pattern.confidence * 0.7,  # reduce confidence for abstraction
                    examples=[pattern.description],
                )
                self.abstract_patterns.append(abstract)
                self._save()
                return abstract

        return None

    def find_applicable_patterns(self, target_domain: str, context: str = "") -> list[Pattern]:
        """Find abstract patterns applicable to a target domain."""
        applicable = []

        for pattern in self.abstract_patterns:
            # Check if target domain is in applicable list
            if target_domain in pattern.applicable_domains or pattern.source_domain == target_domain:
                applicable.append(pattern)
            # Check domain similarity
            elif self._domain_similarity(pattern.source_domain, target_domain) > 0.4:
                applicable.append(pattern)

        applicable.sort(key=lambda p: p.confidence, reverse=True)
        return applicable[:5]

    def transfer(self, pattern: Pattern, target_domain: str) -> str:
        """
        Adapt a pattern from one domain to another.
        Returns adapted advice string.
        """
        similarity = self._domain_similarity(pattern.source_domain, target_domain)
        confidence = pattern.confidence * similarity

        advice = (
            f"[迁移自 {pattern.source_domain}→{target_domain}, 信心={confidence:.0%}] "
            f"{pattern.abstract_rule}"
        )
        pattern.usage_count += 1
        self._save()
        return advice

    # ─── Helpers ───

    def _generalize_rule(self, specific_rule: str) -> str:
        """Remove domain-specific terms to create a general rule."""
        # Simple keyword replacement
        replacements = {
            "python": "目标语言/领域",
            "code": "工作产出",
            "test": "验证",
            "function": "组件",
            "file": "工件",
            "deploy": "交付",
            "refactor": "重构/优化",
            "bug": "问题",
        }
        result = specific_rule
        for specific, general in replacements.items():
            result = result.replace(specific, general)
        return result

    def _find_transferable_domains(self, source: str) -> list[str]:
        """Find domains where knowledge from source might apply."""
        transferable = []
        for (d1, d2), sim in DOMAIN_SIMILARITY.items():
            if d1 == source and sim > 0.4:
                transferable.append(d2)
            elif d2 == source and sim > 0.4:
                transferable.append(d1)
        return transferable or ["general"]

    def _domain_similarity(self, d1: str, d2: str) -> float:
        if d1 == d2:
            return 1.0
        return DOMAIN_SIMILARITY.get((d1, d2), DOMAIN_SIMILARITY.get((d2, d1), 0.2))
