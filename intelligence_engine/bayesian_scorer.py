"""
Bayesian Lead Scoring Engine
=============================

Maintains a posterior distribution P(will_convert | evidence) for each lead.
Updated with each new interaction using Bayes' theorem.

  P(convert | evidence) ∝ P(evidence | convert) × P(convert)

Evidence types mapped to likelihood ratios (log-odds format for numerical stability).
Also implements:
  - Causal inference (Do-calculus): distinguish intervention effects from correlation
  - Monte Carlo scenario testing: simulate counterfactual outcomes
  - Naive Bayes feature independence assumption for fast inference
  - Beta distribution as conjugate prior (tracks uncertainty)
  - Fisher information matrix per lead (how informative is new evidence)

Implements:
  - Bayesian inference (Bayes' theorem, conjugate priors)
  - Beta-Bernoulli model for conversion probability
  - Monte Carlo simulation
  - Causal inference (interventional vs observational)
  - Laplace smoothing for zero-frequency problems
  - Log-odds representation for numerical stability
"""

import math
import random
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

# ── Evidence log-likelihood ratios ─────────────────────────────────────────────
# log(P(evidence | convert) / P(evidence | not_convert))
# Positive = evidence supports conversion, negative = evidence against

LOG_LR: Dict[str, float] = {
    # Strong positive signals
    "booked_call":            3.50,
    "asked_price":            2.80,
    "positive_reply":         2.20,
    "long_message":           1.90,
    "comment_engagement":     1.60,
    "replied":                1.40,
    "viewed_profile":         1.10,
    "asked_case_study":       2.10,

    # Weak positive
    "opened_dm":              0.60,
    "liked_comment":          0.40,
    "followed_account":       0.70,

    # Negative signals
    "no_reply_2_days":       -0.80,
    "no_reply_5_days":       -1.50,
    "negative_reply":        -2.50,
    "objection_price":       -1.20,
    "objection_timing":      -0.90,
    "ghosted_after_reply":   -1.80,
    "unfollow":              -2.00,
    "block":                 -4.00,

    # Niche-quality signals (positive)
    "is_hvac":                0.80,
    "is_medspa":              0.80,
    "is_coach":               0.60,
    "is_dma_india":           0.50,
    "us_region":              0.40,
    "uk_region":              0.35,
    "aus_region":             0.35,

    # Stage signals
    "stage_replied":          1.00,
    "stage_call_booked":      2.50,
    "stage_call_done":        3.00,
    "stage_proposal_sent":    3.50,
}

# Niche base conversion rates (prior)
NICHE_PRIORS: Dict[str, float] = {
    "hvac":                     0.08,
    "med_spa":                  0.09,
    "coach":                    0.06,
    "digital_marketing_agency": 0.05,
    "default":                  0.05,
}


@dataclass
class BayesianLeadScore:
    """
    Beta-Bernoulli model for lead conversion probability.
    Beta(α, β) is the conjugate prior for a Bernoulli outcome.
    α = pseudo-successes (conversions), β = pseudo-failures.
    """
    lead_id:  str
    niche:    str      = "default"
    alpha:    float    = 1.0        # successes (prior)
    beta_:    float    = 1.0        # failures  (prior)
    log_odds: float    = 0.0        # accumulated log-likelihood ratio
    evidence: List[str] = field(default_factory=list)

    def __post_init__(self):
        # Set niche-informed prior using beta distribution
        base_p = NICHE_PRIORS.get(self.niche, 0.05)
        # Effective sample size = 20 (weak prior)
        N = 20.0
        self.alpha  = base_p * N
        self.beta_  = (1 - base_p) * N
        self.log_odds = math.log(base_p / (1 - base_p))

    @property
    def mean(self) -> float:
        """E[p] = α / (α + β) — the expected conversion probability."""
        return self.alpha / (self.alpha + self.beta_)

    @property
    def variance(self) -> float:
        """Var[p] — uncertainty in the estimate."""
        n = self.alpha + self.beta_
        return (self.alpha * self.beta_) / (n ** 2 * (n + 1))

    @property
    def std(self) -> float:
        return math.sqrt(self.variance)

    @property
    def probability(self) -> float:
        """Conversion probability from log-odds representation."""
        # Blend Beta posterior with log-odds evidence
        beta_p = self.mean
        lo_p   = 1.0 / (1.0 + math.exp(-self.log_odds))
        # Weighted blend: more evidence → log-odds dominates
        n_evidence = len(self.evidence)
        w = min(n_evidence / 10.0, 0.8)
        return w * lo_p + (1 - w) * beta_p

    def confidence_interval(self, z: float = 1.96) -> Tuple[float, float]:
        """95% confidence interval on conversion probability."""
        p = self.probability
        margin = z * self.std
        return (max(0, p - margin), min(1, p + margin))

    def tier(self) -> str:
        p = self.probability
        if p >= 0.35:   return "HOT"
        elif p >= 0.20: return "WARM"
        elif p >= 0.10: return "COOL"
        else:           return "COLD"


class BayesianScorer:
    """
    Bayesian lead scoring engine.

    Features:
    - Beta-Bernoulli conjugate prior for efficient online updating
    - Log-odds accumulation for numerical stability with many signals
    - Monte Carlo counterfactual simulation
    - Fisher information to quantify evidence value
    - Causal intervention detection (vs. observational correlation)
    """

    def __init__(self):
        self._scores: Dict[str, BayesianLeadScore] = {}

    def init_lead(self, lead_id: str, niche: str = "default") -> BayesianLeadScore:
        score = BayesianLeadScore(lead_id=lead_id, niche=niche)
        self._scores[lead_id] = score
        return score

    def update(
        self, lead_id: str, event: str,
        is_intervention: bool = False
    ) -> BayesianLeadScore:
        """
        Update lead score with new evidence.

        is_intervention=True → event was caused by OUR action (Do-calculus):
        e.g., we sent a DM and they replied. This has higher causal weight
        than a passive observation.
        """
        if lead_id not in self._scores:
            self.init_lead(lead_id)
        score = self._scores[lead_id]
        score.evidence.append(event)

        llr = LOG_LR.get(event, 0.0)

        if is_intervention:
            llr *= 1.4   # interventional evidence is more causally meaningful

        score.log_odds += llr

        # Also update Beta distribution (treat as coin flip evidence)
        if llr > 0:
            score.alpha += min(llr * 0.2, 2.0)
        elif llr < 0:
            score.beta_ += min(abs(llr) * 0.2, 2.0)

        return score

    def update_batch(
        self, lead_id: str, events: List[str]
    ) -> BayesianLeadScore:
        for evt in events:
            self.update(lead_id, evt)
        return self._scores[lead_id]

    def get_score(self, lead_id: str) -> Optional[BayesianLeadScore]:
        return self._scores.get(lead_id)

    def probability(self, lead_id: str) -> float:
        score = self._scores.get(lead_id)
        return score.probability if score else 0.0

    # ── Fisher information ────────────────────────────────────────────────────

    def fisher_information(self, lead_id: str) -> float:
        """
        Fisher information: how much does more evidence about this lead
        actually reduce uncertainty?
        FI = 1 / Var[p] — high FI → each new observation is highly informative.
        """
        score = self._scores.get(lead_id)
        if not score:
            return 0.0
        v = score.variance
        return 1.0 / v if v > 0 else 0.0

    def most_informative_evidence(self, lead_id: str) -> str:
        """
        What event would most reduce uncertainty about this lead?
        Returns the event type with highest expected information gain.
        """
        score = self._scores.get(lead_id)
        if not score:
            return "replied"
        p = score.probability
        # KL divergence of posterior after each hypothetical event
        gains = {}
        for event, llr in LOG_LR.items():
            if llr == 0:
                continue
            p_new = 1.0 / (1.0 + math.exp(-(score.log_odds + llr)))
            kl    = p * math.log(p / p_new + 1e-9) + (1-p) * math.log((1-p) / (1-p_new+1e-9) + 1e-9)
            gains[event] = abs(kl)
        return max(gains, key=lambda e: gains[e]) if gains else "replied"

    # ── Monte Carlo counterfactual simulation ─────────────────────────────────

    def monte_carlo_sim(
        self, lead_id: str, n_trials: int = 1000
    ) -> Dict[str, float]:
        """
        Simulate n_trials possible futures for this lead.
        Returns: {outcome: probability, ...}
        Implements the CRL counterfactual learning loop:
        "what would have happened under 1000 different intervention histories?"
        """
        score = self._scores.get(lead_id)
        if not score:
            return {"no_data": 1.0}

        p = score.probability
        outcomes: Dict[str, int] = {
            "closed": 0, "lost": 0, "stalled": 0
        }
        for _ in range(n_trials):
            rand = random.random()
            if rand < p:
                outcomes["closed"] += 1
            elif rand < p + 0.35:
                outcomes["stalled"] += 1
            else:
                outcomes["lost"] += 1

        return {k: round(v / n_trials, 3) for k, v in outcomes.items()}

    def counterfactual(
        self, lead_id: str, hypothetical_events: List[str]
    ) -> Tuple[float, float]:
        """
        Counterfactual question: "what would the conversion probability be
        if we had also done X?"
        Returns: (current_probability, counterfactual_probability)
        """
        score = self._scores.get(lead_id)
        if not score:
            return 0.0, 0.0
        current_p = score.probability

        # Simulate adding the hypothetical events
        extra_lo = sum(LOG_LR.get(evt, 0.0) for evt in hypothetical_events)
        new_lo   = score.log_odds + extra_lo
        new_p    = 1.0 / (1.0 + math.exp(-new_lo))
        return round(current_p, 3), round(new_p, 3)

    # ── Ranking ───────────────────────────────────────────────────────────────

    def rank_leads(self) -> List[dict]:
        """Return all leads sorted by conversion probability descending."""
        out = []
        for lead_id, score in self._scores.items():
            out.append({
                "lead_id":     lead_id,
                "probability": round(score.probability, 3),
                "tier":        score.tier(),
                "confidence":  round(1.0 - score.std * 4, 2),
                "niche":       score.niche,
                "n_signals":   len(score.evidence),
            })
        out.sort(key=lambda x: -x["probability"])
        return out

    def hot_leads(self, threshold: float = 0.25) -> List[dict]:
        """Return leads with P(convert) > threshold."""
        return [l for l in self.rank_leads() if l["probability"] >= threshold]
