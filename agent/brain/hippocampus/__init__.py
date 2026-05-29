"""Hippocampus - Memory Formation + Sleep Consolidation"""

import hashlib
import time
import json
from pathlib import Path
from typing import Any, Optional
from collections import defaultdict


class Hippocampus:
    """
    Memory formation and consolidation.
    
    Principles:
    - Episodic memory: stores events with context + emotion
    - Consolidation: periodic 'sleep' moves short-term → long-term
    - Pattern completion: partial cue → full memory recall
    - Spaced repetition: frequently accessed memories strengthened
    - Forgetting curve: unused memories decay (Ebbinghaus)
    """

    def __init__(self, data_dir: Path | str = ".brain/hippocampus"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.short_term: list[dict] = []  # recent episodes
        self.long_term: list[dict] = []   # consolidated
        self.index: dict[str, list[int]] = defaultdict(list)  # keyword → memory indices
        self.max_short_term = 100
        self._load()

    def _load(self):
        lt_path = self.data_dir / "long_term.json"
        if lt_path.exists():
            self.long_term = json.loads(lt_path.read_text())
        idx_path = self.data_dir / "index.json"
        if idx_path.exists():
            self.index = defaultdict(list, json.loads(idx_path.read_text()))

    def _save(self):
        (self.data_dir / "long_term.json").write_text(json.dumps(self.long_term[-500:], ensure_ascii=False, default=str))
        (self.data_dir / "index.json").write_text(json.dumps(dict(self.index), ensure_ascii=False))

    def encode(self, event: str, context: dict = None, emotion: float = 0.0, tags: list[str] = None) -> dict:
        """
        Encode a new episodic memory.
        emotion: -1 (negative) to +1 (positive), stronger = more memorable
        """
        memory = {
            "id": hashlib.md5(f"{event}{time.time()}".encode()).hexdigest()[:8],
            "event": event,
            "context": context or {},
            "emotion": emotion,
            "tags": tags or [],
            "timestamp": time.time(),
            "access_count": 0,
            "strength": 0.5 + abs(emotion) * 0.5,  # emotional memories are stronger
        }
        self.short_term.append(memory)
        if len(self.short_term) > self.max_short_term:
            self.short_term = self.short_term[-self.max_short_term:]
        return memory

    def recall(self, cue: str, top_k: int = 5) -> list[dict]:
        """
        Pattern completion: given a partial cue, find matching memories.
        Searches both short-term and long-term.
        """
        cue_words = set(cue.lower().split())
        scored = []

        for mem in self.short_term + self.long_term:
            score = self._match_score(mem, cue_words)
            if score > 0.1:
                scored.append((score, mem))

        scored.sort(key=lambda x: x[0], reverse=True)
        results = [mem for _, mem in scored[:top_k]]

        # Boost access count (spaced repetition)
        for mem in results:
            mem["access_count"] = mem.get("access_count", 0) + 1
            mem["strength"] = min(1.0, mem.get("strength", 0.5) + 0.05)

        return results

    def sleep(self) -> dict:
        """
        Consolidation phase ('sleep'):
        1. Move important short-term memories to long-term
        2. Strengthen frequently accessed memories
        3. Let weak memories decay (forgetting)
        4. Extract patterns across memories
        """
        consolidated = 0
        forgotten = 0
        patterns = []

        # 1. Consolidate: strong short-term → long-term
        to_consolidate = [m for m in self.short_term if m["strength"] > 0.4]
        for mem in to_consolidate:
            self.long_term.append(mem)
            self._index_memory(mem, len(self.long_term) - 1)
            consolidated += 1

        # 2. Decay weak long-term memories
        survivors = []
        for mem in self.long_term:
            age_days = (time.time() - mem["timestamp"]) / 86400
            decay = 0.95 ** age_days  # Ebbinghaus-like
            mem["strength"] = mem["strength"] * decay
            if mem["strength"] > 0.1:
                survivors.append(mem)
            else:
                forgotten += 1
        self.long_term = survivors

        # 3. Extract patterns (co-occurring tags)
        tag_pairs = defaultdict(int)
        for mem in self.long_term[-50:]:
            tags = mem.get("tags", [])
            for i, t1 in enumerate(tags):
                for t2 in tags[i+1:]:
                    tag_pairs[(t1, t2)] += 1
        patterns = [{"tags": list(pair), "count": count} for pair, count in tag_pairs.items() if count >= 3]

        # 4. Clear consolidated from short-term
        self.short_term = [m for m in self.short_term if m["strength"] <= 0.4]

        self._save()
        return {"consolidated": consolidated, "forgotten": forgotten, "patterns": patterns}

    def _match_score(self, memory: dict, cue_words: set) -> float:
        """Score how well a memory matches the cue."""
        mem_text = f"{memory['event']} {' '.join(memory.get('tags', []))} {str(memory.get('context', ''))}".lower()
        mem_words = set(mem_text.split())
        overlap = len(cue_words & mem_words)
        if not cue_words:
            return 0
        base_score = overlap / len(cue_words)
        # Boost by strength and recency
        recency = max(0.1, 1.0 - (time.time() - memory["timestamp"]) / (7 * 86400))
        return base_score * memory.get("strength", 0.5) * (0.5 + 0.5 * recency)

    def _index_memory(self, memory: dict, idx: int) -> None:
        """Index memory by keywords for fast retrieval."""
        words = set(memory["event"].lower().split() + memory.get("tags", []))
        for word in words:
            if len(word) > 2:
                self.index[word].append(idx)

    def stats(self) -> dict:
        return {
            "short_term": len(self.short_term),
            "long_term": len(self.long_term),
            "avg_strength": sum(m["strength"] for m in self.long_term) / max(len(self.long_term), 1),
        }
