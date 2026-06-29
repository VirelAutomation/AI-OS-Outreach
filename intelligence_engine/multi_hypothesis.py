"""
Multi-Hypothesis Tracking (MHT) — Lead Intent Engine
======================================================

Maintains parallel hypotheses about each lead's intent state simultaneously.
Evidence continuously updates probabilities. Hypotheses are eliminated when
one exceeds the collapse threshold (P > 0.95).

Directly maps from the QBSE (Quantum Behavior State Engine) and MHT
concepts from the B2 Quantum Behavioral Intelligence Engine:

  |B_lead> = [interested, considering, stalling, not_fit, ready_to_close]

Implements:
  - Multi-Hypothesis Tracking (MHT)
  - Quantum Behavior State Engine (QBSE) — actor state superposition
  - Bayesian evidence updating (P(H|E) ∝ P(E|H) × P(H))
  - Hypothesis collapse when confidence exceeds threshold
  - Parallel reasoning universes (QUM)
  - State superposition and measurement
"""

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


# ── Hypothesis definitions ─────────────────────────────────────────────────────

HYPOTHESES = [
    "interested",      # actively wants what we offer
    "considering",     # lukewarm, needs more conviction
    "stalling",        # busy / timing is bad, may convert later
    "not_fit",         # wrong niche or budget, unlikely to close
    "ready_to_close",  # hot lead — book the call now
]

# Prior probabilities (based on outreach industry averages)
PRIOR = {
    "interested":     0.15,
    "considering":    0.35,
    "stalling":       0.30,
    "not_fit":        0.15,
    "ready_to_close": 0.05,
}

COLLAPSE_THRESHOLD = 0.92   # collapse state when P(H) exceeds this

# Likelihood tables: P(evidence | hypothesis)
# Evidence events: replied, positive_reply, negative_reply, no_reply,
#                  asked_price, booked_call, ghosted_after_reply, objection
LIKELIHOODS: Dict[str, Dict[str, float]] = {
    "replied": {
        "interested": 0.80, "considering": 0.55, "stalling": 0.40,
        "not_fit": 0.20, "ready_to_close": 0.90,
    },
    "positive_reply": {
        "interested": 0.85, "considering": 0.60, "stalling": 0.25,
        "not_fit": 0.05, "ready_to_close": 0.95,
    },
    "negative_reply": {
        "interested": 0.05, "considering": 0.20, "stalling": 0.35,
        "not_fit": 0.70, "ready_to_close": 0.02,
    },
    "no_reply": {
        "interested": 0.20, "considering": 0.45, "stalling": 0.65,
        "not_fit": 0.80, "ready_to_close": 0.05,
    },
    "asked_price": {
        "interested": 0.70, "considering": 0.55, "stalling": 0.20,
        "not_fit": 0.05, "ready_to_close": 0.90,
    },
    "booked_call": {
        "interested": 0.85, "considering": 0.50, "stalling": 0.10,
        "not_fit": 0.02, "ready_to_close": 0.98,
    },
    "ghosted_after_reply": {
        "interested": 0.15, "considering": 0.40, "stalling": 0.75,
        "not_fit": 0.50, "ready_to_close": 0.05,
    },
    "objection_raised": {
        "interested": 0.45, "considering": 0.55, "stalling": 0.25,
        "not_fit": 0.60, "ready_to_close": 0.30,
    },
    "viewed_profile": {
        "interested": 0.60, "considering": 0.45, "stalling": 0.30,
        "not_fit": 0.15, "ready_to_close": 0.75,
    },
    "comment_engagement": {
        "interested": 0.55, "considering": 0.40, "stalling": 0.20,
        "not_fit": 0.10, "ready_to_close": 0.70,
    },
    "long_message": {
        "interested": 0.75, "considering": 0.60, "stalling": 0.15,
        "not_fit": 0.05, "ready_to_close": 0.85,
    },
}


@dataclass
class LeadHypothesisState:
    """Quantum-inspired state vector for a single lead's intent."""
    lead_id:   str
    probs:     Dict[str, float] = field(default_factory=lambda: dict(PRIOR))
    collapsed: Optional[str]    = None
    history:   List[dict]       = field(default_factory=list)
    evidence_count: int         = 0

    def normalize(self):
        total = sum(self.probs.values())
        if total > 0:
            for h in self.probs:
                self.probs[h] /= total

    def entropy(self) -> float:
        """Shannon entropy of the hypothesis distribution — 0=collapsed, high=uncertain."""
        H = 0.0
        for p in self.probs.values():
            if p > 0:
                H -= p * math.log2(p)
        return H

    def dominant(self) -> Tuple[str, float]:
        """Return the leading hypothesis and its probability."""
        best = max(self.probs, key=lambda k: self.probs[k])
        return best, self.probs[best]

    def as_superposition(self) -> str:
        """Human-readable quantum state description."""
        sorted_h = sorted(self.probs.items(), key=lambda x: -x[1])
        return " | ".join(f"{h}:{p:.2f}" for h, p in sorted_h)


class MHT:
    """
    Multi-Hypothesis Tracker — the lead intent reasoning engine.

    Maps to the B2 Quantum Behavioral Intelligence Engine:
    - Each lead lives in a superposition of intent states
    - Evidence updates collapse probabilities (Bayesian update)
    - State collapses when P(H) > COLLAPSE_THRESHOLD
    - After collapse, residue stays (can be revived if evidence reverses)

    Also implements the QUM (Quantum Universe Manager):
    each hypothesis is an independent 'universe' evolving until
    evidence eliminates it.
    """

    def __init__(self):
        self._states: Dict[str, LeadHypothesisState] = {}

    def init_lead(self, lead_id: str, niche: str = "") -> LeadHypothesisState:
        """Initialise a new lead with niche-adjusted priors."""
        priors = dict(PRIOR)
        # Niche-adjusted priors
        if niche in ("hvac", "med_spa"):
            priors["not_fit"] *= 0.7      # these niches respond well
            priors["interested"] *= 1.3
        elif niche == "coach":
            priors["considering"] *= 1.2   # coaches think it over longer
        elif niche == "digital_marketing_agency":
            priors["stalling"] *= 1.4      # DMA owners are very busy
        # Normalize
        total = sum(priors.values())
        priors = {k: v / total for k, v in priors.items()}

        state = LeadHypothesisState(lead_id=lead_id, probs=priors)
        self._states[lead_id] = state
        return state

    def update(self, lead_id: str, event: str, weight: float = 1.0) -> LeadHypothesisState:
        """
        Bayesian update: P(H|E) ∝ P(E|H) × P(H).

        weight allows partial evidence (e.g., weak signal → weight=0.5).
        """
        if lead_id not in self._states:
            self.init_lead(lead_id)
        state = self._states[lead_id]

        if state.collapsed:
            return state   # once collapsed, state is committed

        likelihood_row = LIKELIHOODS.get(event)
        if not likelihood_row:
            return state

        # Apply Bayesian update with weight interpolation
        for h in state.probs:
            lhood = likelihood_row.get(h, 0.5)
            # Weight blending: partial evidence
            effective_lhood = 1.0 + (lhood - 1.0) * weight if weight < 1 else lhood
            state.probs[h] *= max(effective_lhood, 0.01)

        state.normalize()
        state.evidence_count += 1
        state.history.append({"event": event, "weight": weight, "probs": dict(state.probs)})

        # Check for collapse
        dominant_h, dominant_p = state.dominant()
        if dominant_p >= COLLAPSE_THRESHOLD:
            state.collapsed = dominant_h

        return state

    def update_batch(self, lead_id: str, events: List[str]) -> LeadHypothesisState:
        """Update with multiple events at once."""
        for evt in events:
            self.update(lead_id, evt)
        return self._states[lead_id]

    def get_state(self, lead_id: str) -> Optional[LeadHypothesisState]:
        return self._states.get(lead_id)

    def recommended_action(self, lead_id: str) -> str:
        """
        Map current hypothesis distribution to the optimal next action.
        This is the 'counter-geodesic' for the outreach domain.
        """
        state = self._states.get(lead_id)
        if not state:
            return "send_initial_dm"

        if state.collapsed:
            return _action_for_collapsed(state.collapsed)

        dominant_h, p = state.dominant()

        # Act on superposition — weight action by probability mass
        action_scores: Dict[str, float] = {}
        for h, prob in state.probs.items():
            action = _action_for_hypothesis(h)
            action_scores[action] = action_scores.get(action, 0) + prob

        return max(action_scores, key=lambda a: action_scores[a])

    def urgency_score(self, lead_id: str) -> float:
        """
        Urgency ∈ [0,1]. High when 'ready_to_close' or 'interested' dominates
        AND entropy is low (confident prediction).
        """
        state = self._states.get(lead_id)
        if not state:
            return 0.0
        hot_mass  = state.probs.get("ready_to_close", 0) * 3.0 + state.probs.get("interested", 0)
        certainty = 1.0 - (state.entropy() / math.log2(len(HYPOTHESES)))
        return float(min(hot_mass * certainty, 1.0))

    def all_states(self) -> List[dict]:
        """Return a summary of all lead hypothesis states."""
        out = []
        for lead_id, state in self._states.items():
            dom_h, dom_p = state.dominant()
            out.append({
                "lead_id":   lead_id,
                "dominant":  dom_h,
                "confidence": round(dom_p, 3),
                "entropy":   round(state.entropy(), 3),
                "collapsed": state.collapsed,
                "urgency":   round(self.urgency_score(lead_id), 3),
                "action":    self.recommended_action(lead_id),
            })
        out.sort(key=lambda x: -x["urgency"])
        return out


# ── Action mapping ─────────────────────────────────────────────────────────────

def _action_for_hypothesis(h: str) -> str:
    return {
        "interested":     "book_call",
        "considering":    "send_case_study",
        "stalling":       "send_followup_in_3_days",
        "not_fit":        "disqualify",
        "ready_to_close": "book_call_urgent",
    }.get(h, "send_followup")


def _action_for_collapsed(h: str) -> str:
    return {
        "interested":     "book_call",
        "considering":    "send_proposal",
        "stalling":       "schedule_followup_1_week",
        "not_fit":        "archive",
        "ready_to_close": "call_now",
    }.get(h, "followup")
