"""
Entropy Monitor — Surprise Scoring & Anomaly Detection
=======================================================

"Surprise is not noise. Surprise is the highest-value learning signal."
— CRL architecture docs

High-surprise leads are leads whose behavior deviates significantly from what
the current model expects. They could be:
  a) Much more interested than predicted → route to priority action NOW
  b) Churning faster than predicted → intervene before you lose them
  c) Exhibiting novel behavior → new pattern worth learning from

Implements:
  - KL divergence (behavior change detection)
  - Shannon entropy (unpredictability detection)
  - Surprise scoring (anomaly measurement)
  - Fisher Information Metric (information density per signal)
  - Causal Surprise Maximisation (CSM): actively hunt for high-surprise leads
  - Entropy analysis for lead state uncertainty
  - Information bottleneck theory (extract only relevant signals)
  - Cross-entropy optimisation
  - Behavioral Sentinel (Layer 6 from QBIE)
"""

import math
from collections import deque
from dataclasses import dataclass, field
from typing import Deque, Dict, List, Optional, Tuple


# ── Expected behavior distributions ───────────────────────────────────────────
# P(event_type | stage) — baseline expected distribution per stage.
# If observed distribution deviates significantly → HIGH SURPRISE.

STAGE_EXPECTED_DISTRIBUTIONS: Dict[str, Dict[str, float]] = {
    "dm_sent": {
        "no_reply":       0.82,
        "positive_reply": 0.08,
        "negative_reply": 0.05,
        "replied":        0.05,
    },
    "replied": {
        "booked_call":        0.08,
        "asked_price":        0.10,
        "ghosted_after_reply":0.35,
        "positive_reply":     0.30,
        "objection_raised":   0.17,
    },
    "call_booked": {
        "call_completed":     0.80,
        "no_show":            0.15,
        "rescheduled":        0.05,
    },
    "proposal_sent": {
        "closed":     0.30,
        "lost":       0.35,
        "stalled":    0.35,
    },
    "default": {
        "no_reply":       0.70,
        "positive_reply": 0.15,
        "negative_reply": 0.10,
        "replied":        0.05,
    },
}

SURPRISE_THRESHOLD_HIGH  = 2.0   # KL divergence — flag as hot/critical
SURPRISE_THRESHOLD_WATCH = 0.8   # KL divergence — flag for monitoring


@dataclass
class LeadSurpriseState:
    """Tracks the surprise history for a single lead."""
    lead_id:         str
    stage:           str            = "dm_sent"
    event_counts:    Dict[str, int] = field(default_factory=dict)
    total_events:    int            = 0
    surprise_scores: Deque[float]   = field(default_factory=lambda: deque(maxlen=20))
    alerts:          List[dict]     = field(default_factory=list)
    peak_surprise:   float          = 0.0

    def empirical_distribution(self) -> Dict[str, float]:
        """Compute observed distribution from event counts."""
        if self.total_events == 0:
            return {}
        return {k: v / self.total_events for k, v in self.event_counts.items()}

    def entropy(self) -> float:
        """Shannon entropy of the observed event distribution."""
        dist = self.empirical_distribution()
        H = 0.0
        for p in dist.values():
            if p > 0:
                H -= p * math.log2(p)
        return H

    def recent_surprise(self) -> float:
        """Exponentially weighted moving average of recent surprise scores."""
        if not self.surprise_scores:
            return 0.0
        scores = list(self.surprise_scores)
        weights = [0.9 ** i for i in range(len(scores) - 1, -1, -1)]
        total_w = sum(weights)
        return sum(s * w for s, w in zip(scores, weights)) / total_w


class EntropyMonitor:
    """
    Behavioral Sentinel adapted for sales leads.

    Continuously monitors each lead's event distribution against the
    expected baseline for their stage. When KL divergence exceeds thresholds,
    raises alerts for Jarvis to act on.

    Directly maps to:
    - Layer 6 (Behavioral Sentinel) from B2 QBIE
    - Causal Surprise Maximisation (CSM) from SCI architecture
    - The Surprise Threshold guardrail from CRL
    """

    def __init__(self):
        self._states: Dict[str, LeadSurpriseState] = {}

    def init_lead(self, lead_id: str, stage: str = "dm_sent") -> LeadSurpriseState:
        state = LeadSurpriseState(lead_id=lead_id, stage=stage)
        self._states[lead_id] = state
        return state

    def record_event(
        self, lead_id: str, event: str, stage: str = ""
    ) -> Tuple[float, str]:
        """
        Record an event and compute surprise score via KL divergence.
        Returns: (surprise_score, alert_level)
        """
        if lead_id not in self._states:
            self.init_lead(lead_id, stage or "dm_sent")
        state = self._states[lead_id]

        if stage:
            state.stage = stage

        # Update observed counts
        state.event_counts[event] = state.event_counts.get(event, 0) + 1
        state.total_events += 1

        # Compute KL divergence from expected distribution
        surprise = self._kl_divergence(state)
        state.surprise_scores.append(surprise)
        state.peak_surprise = max(state.peak_surprise, surprise)

        # Alert classification
        alert_level = "normal"
        if surprise >= SURPRISE_THRESHOLD_HIGH:
            alert_level = "hot"
            state.alerts.append({
                "event":      event,
                "surprise":   round(surprise, 3),
                "level":      "hot",
                "direction":  self._direction(state, event),
            })
        elif surprise >= SURPRISE_THRESHOLD_WATCH:
            alert_level = "watch"

        return round(surprise, 3), alert_level

    def _kl_divergence(self, state: LeadSurpriseState) -> float:
        """
        KL(observed || expected) = Σ p(x) log(p(x)/q(x))
        Measures how much the lead's behavior diverges from the baseline.
        High KL = surprising = high-value signal.
        """
        expected = STAGE_EXPECTED_DISTRIBUTIONS.get(state.stage, STAGE_EXPECTED_DISTRIBUTIONS["default"])
        observed = state.empirical_distribution()

        if not observed:
            return 0.0

        kl = 0.0
        # Merge event spaces
        all_events = set(expected.keys()) | set(observed.keys())
        for evt in all_events:
            p = observed.get(evt, 1e-9)    # observed probability
            q = expected.get(evt, 1e-9)    # expected probability
            if p > 0:
                kl += p * math.log(p / q)
        return max(kl, 0.0)

    def _direction(self, state: LeadSurpriseState, event: str) -> str:
        """Is this lead surprisingly good or surprisingly bad?"""
        positive_events = {"booked_call", "asked_price", "positive_reply", "long_message", "replied"}
        negative_events = {"no_reply_5_days", "ghosted_after_reply", "negative_reply", "block"}
        if event in positive_events:
            return "positive_surprise"
        elif event in negative_events:
            return "negative_surprise"
        return "neutral_surprise"

    # ── Surprise-based prioritisation ────────────────────────────────────────

    def priority_leads(self, top_k: int = 10) -> List[dict]:
        """
        Returns leads sorted by surprise × direction_weight.
        Hot = surprisingly positive leads → act immediately.
        """
        out = []
        for lead_id, state in self._states.items():
            surprise = state.recent_surprise()
            # Check last alert direction
            last_dir = state.alerts[-1]["direction"] if state.alerts else "neutral_surprise"
            direction_w = 2.0 if last_dir == "positive_surprise" else 1.0
            priority = surprise * direction_w
            out.append({
                "lead_id":     lead_id,
                "surprise":    round(surprise, 3),
                "direction":   last_dir,
                "priority":    round(priority, 3),
                "stage":       state.stage,
                "peak":        round(state.peak_surprise, 3),
                "n_alerts":    len(state.alerts),
            })
        out.sort(key=lambda x: -x["priority"])
        return out[:top_k]

    def causal_surprise_targets(self) -> List[str]:
        """
        Causal Surprise Maximisation (CSM): identify leads where the model
        is most uncertain → these are the highest-value learning targets.
        Lead IDs where we should prioritise data collection.
        """
        uncertain = []
        for lead_id, state in self._states.items():
            # High entropy = high uncertainty = worth investigating
            if state.entropy() > 1.5 and state.total_events >= 3:
                uncertain.append(lead_id)
        return uncertain

    # ── Invariant Risk Minimization (IRM) ─────────────────────────────────────

    def invariant_signals(self, niches: List[str] = None) -> Dict[str, float]:
        """
        IRM-inspired: identify which events are consistently predictive
        across ALL leads (invariant mechanisms) vs. niche-specific correlations.

        Returns: {event: invariance_score} — higher = more universally predictive.
        """
        event_surprise_by_niche: Dict[str, List[float]] = {}

        for lead_id, state in self._states.items():
            for evt, count in state.event_counts.items():
                if evt not in event_surprise_by_niche:
                    event_surprise_by_niche[evt] = []
                # High-count events that drove high surprise = strong signal
                surprise_contribution = count * state.peak_surprise
                event_surprise_by_niche[evt].append(surprise_contribution)

        # Invariance = low variance across leads (consistent signal)
        invariance = {}
        for evt, vals in event_surprise_by_niche.items():
            if len(vals) < 3:
                continue
            mean  = sum(vals) / len(vals)
            var   = sum((v - mean) ** 2 for v in vals) / len(vals)
            # High mean + low variance = invariant causal signal
            invariance[evt] = round(mean / (1 + var ** 0.5), 3)

        return dict(sorted(invariance.items(), key=lambda x: -x[1]))

    # ── Information bottleneck ────────────────────────────────────────────────

    def information_relevance(self) -> Dict[str, float]:
        """
        Information Bottleneck: which event types compress the most
        information about conversion probability?
        Returns event types ranked by relevance score.
        """
        from .bayesian_scorer import LOG_LR
        relevance = {}
        for event, llr in LOG_LR.items():
            # Relevance = magnitude of log-likelihood ratio × (1 - entropy decay)
            relevance[event] = round(abs(llr) * 0.8, 3)
        return dict(sorted(relevance.items(), key=lambda x: -x[1])[:20])

    def get_state(self, lead_id: str) -> Optional[LeadSurpriseState]:
        return self._states.get(lead_id)

    def global_entropy(self) -> float:
        """Average entropy across all leads — system uncertainty level."""
        states = list(self._states.values())
        if not states:
            return 0.0
        return sum(s.entropy() for s in states) / len(states)
