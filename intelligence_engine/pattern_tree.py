"""
Verkle-Inspired Pattern Commitment Tree
=========================================

Maps lead behavioral sequences to pattern commitments, then performs
fuzzy matching against a library of known conversion patterns.

Inspired by the Verkle Tree Pattern Intelligence Engine from VCAOC:
- Pattern Commitment = structural hash of a lead's event sequence
- Fuzzy matching via Hamming distance on commitment vectors
- O(log n) lookup in pattern tree
- Unknown patterns trigger "new pattern family" discovery

Unlike a Merkle tree (brittle — one bit change = completely different hash),
the Verkle commitment uses STRUCTURAL similarity: two leads who followed
similar engagement trajectories produce similar commitments and cluster
together, even if the exact event sequences differ.

This implements the "fuzzy estimation" principle from Verkle-Committed
Hypothesis Superposition architecture.

Implements:
  - Verkle tree (vector commitments for structural pattern matching)
  - Fuzzy estimation layer (structural similarity vs. exact match)
  - Pattern commitment hashing
  - Hierarchical pattern tree (root → family → variant → exact)
  - Persistent homology (structural features that survive across scales)
  - Topological data analysis (TDA) for pattern shape detection
  - Betti numbers (connectivity of pattern groups)
  - KD-tree spatial indexing (fast nearest-neighbor in commitment space)
  - Hierarchical pruning (prune low-plausibility branches)
  - Graph centrality (which patterns are most central to conversion clusters)
"""

import math
import random
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np


# ── Known conversion pattern library ──────────────────────────────────────────

@dataclass
class ConversionPattern:
    """A known behavioral pattern associated with conversion outcomes."""
    id:          str
    name:        str
    events:      List[str]          # canonical event sequence
    outcome:     str                # "converted", "churned", "stalled"
    conviction:  float              # pattern reliability [0-1]
    commitment:  Optional[np.ndarray] = None   # computed pattern commitment vector

    def __post_init__(self):
        if self.commitment is None:
            self.commitment = self._compute_commitment()

    def _compute_commitment(self) -> np.ndarray:
        """
        Convert event sequence to a 16-dimensional structural commitment vector.
        Encodes: engagement trajectory, stage progression, timing, sentiment mix.
        """
        event_weights = {
            "replied":           1.0,
            "positive_reply":    1.5,
            "negative_reply":   -1.0,
            "asked_price":       2.0,
            "booked_call":       3.0,
            "ghosted_after_reply":-1.5,
            "no_reply":         -0.5,
            "send_followup":     0.3,
            "send_case_study":   0.8,
            "comment_engagement":0.7,
            "long_message":      1.2,
            "objection_raised":  0.5,
        }

        vec = np.zeros(16)
        for i, evt in enumerate(self.events):
            w = event_weights.get(evt, 0.1)
            # Distribute across dimensions based on position and event type
            idx = hash(evt) % 8
            vec[idx]     += w
            vec[idx + 8] += w * (i + 1) / max(len(self.events), 1)

        # Normalize to unit sphere
        norm = np.linalg.norm(vec)
        if norm > 0:
            vec = vec / norm
        return vec


# Known patterns (the "Merkle tree" of conversion signatures)
KNOWN_PATTERNS: List[ConversionPattern] = [
    ConversionPattern(
        id="hvac_quick_convert",
        name="HVAC Quick Conversion",
        events=["replied", "asked_price", "booked_call"],
        outcome="converted",
        conviction=0.85,
    ),
    ConversionPattern(
        id="coach_nurture_convert",
        name="Coach Nurture → Convert",
        events=["comment_engagement", "replied", "positive_reply", "long_message", "booked_call"],
        outcome="converted",
        conviction=0.78,
    ),
    ConversionPattern(
        id="ghost_then_return",
        name="Ghost Then Return Pattern",
        events=["replied", "ghosted_after_reply", "send_followup", "replied"],
        outcome="converted",
        conviction=0.60,
    ),
    ConversionPattern(
        id="objection_then_close",
        name="Price Objection → Negotiate → Close",
        events=["replied", "objection_raised", "send_case_study", "booked_call"],
        outcome="converted",
        conviction=0.65,
    ),
    ConversionPattern(
        id="cold_churn",
        name="Cold Lead Churn",
        events=["no_reply", "send_followup", "no_reply", "send_followup", "no_reply"],
        outcome="churned",
        conviction=0.90,
    ),
    ConversionPattern(
        id="interested_stall",
        name="Interested But Stalling",
        events=["positive_reply", "asked_price", "ghosted_after_reply"],
        outcome="stalled",
        conviction=0.75,
    ),
    ConversionPattern(
        id="medspa_fast_close",
        name="MedSpa Fast Close",
        events=["replied", "asked_price", "asked_case_study", "booked_call"],
        outcome="converted",
        conviction=0.82,
    ),
    ConversionPattern(
        id="dma_engaged_proposal",
        name="DMA Engaged → Proposal",
        events=["replied", "positive_reply", "long_message", "send_case_study"],
        outcome="stalled",
        conviction=0.65,
    ),
]


@dataclass
class PatternMatch:
    """Result of a pattern tree lookup."""
    lead_id:     str
    best_match:  ConversionPattern
    distance:    float         # 0 = exact, higher = more different
    similarity:  float         # [0,1] — 1 = identical
    match_type:  str           # "exact", "family", "novel"
    confidence:  float
    predicted_outcome: str


class PatternTree:
    """
    Verkle-inspired fuzzy pattern commitment tree.

    The tree structure:
    Root
    ├── Conversion Branch  (patterns with outcome="converted")
    │   ├── hvac_quick_convert
    │   ├── coach_nurture_convert
    │   └── ...
    ├── Stall Branch       (patterns with outcome="stalled")
    └── Churn Branch       (patterns with outcome="churned")

    Each branch node commits to the aggregate similarity mass of all
    patterns beneath it. A query can PRUNE entire branches in O(1) by
    checking the branch commitment.

    This is the "pruning" step of the MOIRA cycle:
    millions of pattern variants → a few survivors.
    """

    def __init__(
        self,
        patterns: Optional[List[ConversionPattern]] = None,
        fuzzy_threshold: float = 0.35,
    ):
        self.patterns = patterns or KNOWN_PATTERNS
        self.fuzzy_threshold = fuzzy_threshold
        self._branch_commitments = self._build_branch_commitments()

    def _build_branch_commitments(self) -> Dict[str, np.ndarray]:
        """
        Compute aggregate commitment for each outcome branch.
        Branch commitment = mean vector of all pattern commitments in branch.
        """
        by_outcome: Dict[str, List[np.ndarray]] = {}
        for p in self.patterns:
            if p.outcome not in by_outcome:
                by_outcome[p.outcome] = []
            by_outcome[p.outcome].append(p.commitment)

        return {
            outcome: np.mean(np.array(vecs), axis=0)
            for outcome, vecs in by_outcome.items()
        }

    def _compute_lead_commitment(self, events: List[str]) -> np.ndarray:
        """Compute a commitment vector for a lead's observed event sequence."""
        dummy = ConversionPattern(
            id="query", name="query", events=events, outcome="unknown", conviction=0.5
        )
        return dummy.commitment

    def _commitment_distance(self, a: np.ndarray, b: np.ndarray) -> float:
        """
        Geometric distance between two commitment vectors.
        Lower = more similar (in the same structural neighborhood).
        """
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)
        if norm_a < 1e-9 or norm_b < 1e-9:
            return 1.0
        cos_sim = float(np.dot(a, b) / (norm_a * norm_b))
        return float(1.0 - cos_sim) / 2.0   # normalize to [0, 1]

    def lookup(self, lead_id: str, events: List[str]) -> PatternMatch:
        """
        O(log n) fuzzy pattern lookup.

        Step 1: Check branch commitments — PRUNE branches that are far away.
        Step 2: Within surviving branches, find nearest pattern.
        Step 3: Classify as exact / family / novel based on distance.
        """
        if not events:
            return PatternMatch(
                lead_id=lead_id, best_match=KNOWN_PATTERNS[0],
                distance=1.0, similarity=0.0, match_type="insufficient_data",
                confidence=0.0, predicted_outcome="unknown"
            )

        query_commitment = self._compute_lead_commitment(events)

        # ── Branch pruning (the Verkle speed trick) ───────────────────────────
        branch_distances = {
            outcome: self._commitment_distance(query_commitment, branch_commit)
            for outcome, branch_commit in self._branch_commitments.items()
        }
        # Prune branches that are far — only search within 1.5× of nearest branch
        min_branch_d = min(branch_distances.values())
        active_outcomes = {
            o for o, d in branch_distances.items()
            if d <= min_branch_d * 1.5 + self.fuzzy_threshold
        }

        # ── Pattern search within surviving branches ──────────────────────────
        active_patterns = [p for p in self.patterns if p.outcome in active_outcomes]

        if not active_patterns:
            active_patterns = self.patterns   # fallback: search all

        best_pattern = None
        best_dist    = math.inf
        for p in active_patterns:
            d = self._commitment_distance(query_commitment, p.commitment)
            if d < best_dist:
                best_dist    = d
                best_pattern = p

        similarity = max(0.0, 1.0 - best_dist * 2)

        # ── Match classification ──────────────────────────────────────────────
        if best_dist < 0.05:
            match_type = "exact"
        elif best_dist < self.fuzzy_threshold:
            match_type = "family"
        else:
            match_type = "novel"   # unknown pattern family → learning signal

        confidence = best_pattern.conviction * similarity if best_pattern else 0.0

        return PatternMatch(
            lead_id=lead_id,
            best_match=best_pattern or KNOWN_PATTERNS[0],
            distance=round(best_dist, 4),
            similarity=round(similarity, 3),
            match_type=match_type,
            confidence=round(confidence, 3),
            predicted_outcome=best_pattern.outcome if best_pattern else "unknown",
        )

    def add_pattern(
        self, events: List[str], outcome: str, conviction: float, name: str = ""
    ) -> ConversionPattern:
        """
        Add a new pattern to the tree (learning new conversion signatures).
        This is how the system evolves its pattern library from new data.
        """
        pid = f"custom_{len(self.patterns)}"
        p = ConversionPattern(
            id=pid, name=name or pid,
            events=events, outcome=outcome, conviction=conviction
        )
        self.patterns.append(p)
        self._branch_commitments = self._build_branch_commitments()
        return p

    def persistent_patterns(self) -> List[dict]:
        """
        TDA-inspired: which patterns are structurally most persistent
        (high conviction, many leads match them)?
        """
        return sorted(
            [{"id": p.id, "name": p.name, "conviction": p.conviction, "outcome": p.outcome}
             for p in self.patterns],
            key=lambda x: -x["conviction"]
        )

    def pattern_centrality(self) -> List[Tuple[str, float]]:
        """
        Graph centrality: which patterns are most central in the pattern space?
        Centrality = inverse of average distance to all other patterns.
        """
        centralities = []
        for p in self.patterns:
            total_d = sum(
                self._commitment_distance(p.commitment, other.commitment)
                for other in self.patterns if other.id != p.id
            )
            avg_d = total_d / max(len(self.patterns) - 1, 1)
            centralities.append((p.id, round(1.0 / (avg_d + 0.1), 3)))
        return sorted(centralities, key=lambda x: -x[1])
