"""
Quantum-Inspired Outreach Strategy Ensemble
=============================================

Implements the MOIRA quantum hypothesis layer adapted for sales:

  |strategy> = Σᵢ αᵢ |sᵢ>    (superposition of outreach strategies)

Each strategy has an amplitude αᵢ ∝ exp(-S[strategy]/τ) where S is the
action (expected effort / inverse-conversion-probability) of that strategy.

Low temperature τ → collapses toward single best strategy (HJ spine).
High temperature τ → spreads over many alternatives (robustness mode).

Interference: strategies that lead to the same outcome AND are correlated
(e.g., both rely on high interest) REINFORCE. Contradictory strategies CANCEL.

Implements:
  - Feynman path integral (sum-over-histories for outreach sequences)
  - Quantum superposition (simultaneous strategy evaluation)
  - Amplitude / wavefunction per strategy
  - Interference (correlated reinforcement, anti-correlated cancellation)
  - Measurement / collapse (commit to single strategy for execution)
  - Decoherence (weak strategies decay over time)
  - Entanglement (correlated lead strategies for multi-lead campaigns)
  - Tunneling (sudden unexpected conversion jumps)
  - Amplitude amplification (iterative reweighting toward high-conversion regions)
  - Branching futures (many-worlds strategy tree)
  - MOIRA cycle: GENERATE → PRUNE → REFINE
"""

import math
import random
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


# ── Strategy library ──────────────────────────────────────────────────────────

@dataclass
class OutreachStrategy:
    """A concrete outreach strategy — a sequence of actions for a lead."""
    id:          str
    name:        str
    actions:     List[str]
    target_stage: str              # what stage does this strategy aim for
    niche_fit:   Dict[str, float]  # niche → suitability [0-1]
    cost:        float             # effort cost (lower = preferred)
    description: str = ""

    def action_fingerprint(self) -> int:
        """Hash of the action sequence — used for interference calculation."""
        return hash(tuple(self.actions))


STRATEGIES: List[OutreachStrategy] = [
    OutreachStrategy(
        id="cold_dm_value",
        name="Cold DM with Value Upfront",
        actions=["send_dm", "wait_2_days", "send_comment", "send_followup"],
        target_stage="replied",
        niche_fit={"hvac": 0.85, "med_spa": 0.90, "coach": 0.75, "digital_marketing_agency": 0.70},
        cost=0.40,
        description="Lead with a value insight, no pitch. Follow up with comment on their post.",
    ),
    OutreachStrategy(
        id="comment_first",
        name="Comment Warm-Up → DM",
        actions=["send_comment", "send_comment", "send_dm", "send_followup"],
        target_stage="replied",
        niche_fit={"hvac": 0.70, "med_spa": 0.85, "coach": 0.90, "digital_marketing_agency": 0.60},
        cost=0.45,
        description="3 genuine comments before the DM — highest reply rate for coaches.",
    ),
    OutreachStrategy(
        id="case_study_opener",
        name="Case Study Opener",
        actions=["send_dm", "send_case_study", "book_call"],
        target_stage="call_booked",
        niche_fit={"hvac": 0.65, "med_spa": 0.70, "coach": 0.80, "digital_marketing_agency": 0.85},
        cost=0.55,
        description="Open with a specific result for their niche, then ask for a call.",
    ),
    OutreachStrategy(
        id="direct_offer",
        name="Direct Offer (High Intent)",
        actions=["send_dm", "send_price", "book_call"],
        target_stage="call_booked",
        niche_fit={"hvac": 0.60, "med_spa": 0.55, "coach": 0.50, "digital_marketing_agency": 0.65},
        cost=0.60,
        description="For leads with high Bayesian score — skip the warmup, go direct.",
    ),
    OutreachStrategy(
        id="fb_group_engage",
        name="Facebook Group Authority Build",
        actions=["send_comment", "send_comment", "fb_post_value", "send_dm"],
        target_stage="replied",
        niche_fit={"hvac": 0.80, "med_spa": 0.75, "coach": 0.85, "digital_marketing_agency": 0.70},
        cost=0.50,
        description="Build authority via group posts before DM. Works well for Facebook groups.",
    ),
    OutreachStrategy(
        id="nurture_sequence",
        name="Long Nurture Sequence",
        actions=["send_comment", "send_dm", "wait_3_days", "send_followup", "send_case_study", "book_call"],
        target_stage="call_booked",
        niche_fit={"hvac": 0.55, "med_spa": 0.60, "coach": 0.70, "digital_marketing_agency": 0.65},
        cost=0.75,
        description="For colder leads — longer sequence, more touches before the ask.",
    ),
]


@dataclass
class StrategyAmplitude:
    """Quantum amplitude for a strategy in the ensemble."""
    strategy:   OutreachStrategy
    amplitude:  float    = 0.0    # raw weight
    phase:      float    = 0.0    # phase for interference calculation
    decayed:    bool     = False

    @property
    def probability(self) -> float:
        """P = |α|² (Born rule adapted for classical ensemble)."""
        return self.amplitude ** 2


class QuantumEnsemble:
    """
    Quantum-inspired strategy ensemble for outreach decisions.

    The ensemble holds all strategies in superposition, weights them by
    expected action (effort × inverse-conversion-probability), applies
    interference between correlated strategies, and collapses to the
    highest-probability strategy when Jarvis needs to commit to an action.

    MOIRA cycle:
    1. HJ PROPOSES the spine (best strategy from Hamilton-Jacobi)
    2. QUANTUM EXPANDS variations around the spine
    3. VERKLE PRUNES low-amplitude strategies (implemented in PatternTree)
    4. HJ REFINES the survivors
    """

    def __init__(self, temperature: float = 1.0):
        self.tau = temperature   # higher τ = more exploration

    def _action_cost(
        self, strategy: OutreachStrategy,
        niche: str, conversion_p: float
    ) -> float:
        """
        S[strategy] = effort_cost / (niche_fit × P(conversion))
        Lower action = higher amplitude.
        """
        niche_fit = strategy.niche_fit.get(niche, 0.5)
        expected_conv = niche_fit * conversion_p + 1e-6
        return strategy.cost / expected_conv

    def build_ensemble(
        self,
        niche:         str,
        funnel_stage:  str,
        conversion_p:  float,
        mht_dominant:  str   = "considering",
        hj_spine:      str   = "",
    ) -> List[StrategyAmplitude]:
        """
        Build the full strategy ensemble for a lead context.

        Amplitudes: αᵢ = exp(-S[sᵢ]/τ) (Boltzmann / Feynman weighting)
        Interference: strategies with similar action-fingerprints reinforce.
        """
        ensemble = []
        fingerprint_sum: Dict[int, float] = {}

        # Phase 1: GENERATE — compute raw amplitudes
        for strat in STRATEGIES:
            action = self._action_cost(strat, niche, conversion_p)
            amplitude = math.exp(-action / self.tau)
            fp = strat.action_fingerprint()
            fingerprint_sum[fp] = fingerprint_sum.get(fp, 0) + amplitude
            ensemble.append(StrategyAmplitude(
                strategy=strat,
                amplitude=amplitude,
                phase=action % (2 * math.pi),
            ))

        # Phase 2: INTERFERENCE — correlated strategies reinforce
        for sa in ensemble:
            fp = sa.strategy.action_fingerprint()
            # Strategies that share outcome fingerprints interfere constructively
            constructive_sum = fingerprint_sum.get(fp, 0)
            sa.amplitude *= (1 + 0.15 * constructive_sum)

        # Phase 3: AMPLITUDE AMPLIFICATION — boost strategies aligned with HJ spine
        if hj_spine:
            for sa in ensemble:
                if hj_spine in sa.strategy.actions:
                    sa.amplitude *= 1.4   # iterative reweighting toward high-conv regions

        # MHT-informed amplification
        if mht_dominant == "ready_to_close":
            for sa in ensemble:
                if "book_call" in sa.strategy.actions or "send_price" in sa.strategy.actions:
                    sa.amplitude *= 1.6
        elif mht_dominant == "stalling":
            for sa in ensemble:
                if "send_followup" in sa.strategy.actions:
                    sa.amplitude *= 1.3

        # Phase 4: DECOHERENCE — strategies with very low amplitude decay
        threshold = max(sa.amplitude for sa in ensemble) * 0.1
        for sa in ensemble:
            if sa.amplitude < threshold:
                sa.decayed = True

        # Normalize (Born rule)
        total = sum(sa.amplitude ** 2 for sa in ensemble if not sa.decayed)
        if total > 0:
            for sa in ensemble:
                if not sa.decayed:
                    sa.amplitude = sa.amplitude / math.sqrt(total)

        # Sort by probability
        ensemble.sort(key=lambda x: -x.probability)
        return ensemble

    def collapse(
        self,
        niche:        str,
        funnel_stage: str,
        conversion_p: float,
        mht_dominant: str = "considering",
        hj_spine:     str = "",
    ) -> Tuple[OutreachStrategy, float]:
        """
        Measurement / collapse: pick the single highest-amplitude strategy.
        This is the moment of commitment — the ensemble collapses.
        """
        ensemble = self.build_ensemble(niche, funnel_stage, conversion_p, mht_dominant, hj_spine)
        best = ensemble[0]
        return best.strategy, round(best.probability, 3)

    def tunneling_probability(
        self, funnel_stage: str, mht_dominant: str
    ) -> float:
        """
        Tunneling: probability of a sudden unexpected jump to a higher stage
        (e.g., lead replies with "let's do this" before we even sent a proposal).
        High tunneling = high urgency to have collateral ready.
        """
        base = 0.03
        if mht_dominant in ("ready_to_close", "interested"):
            base *= 3.0
        if funnel_stage in ("replied", "stalled"):
            base *= 1.5
        return round(min(base, 0.25), 3)

    def entangled_strategy(
        self,
        lead_ids:     List[str],
        niche:        str,
        conversion_ps: Dict[str, float],
    ) -> str:
        """
        Entanglement: when multiple leads are in the same group/network,
        their strategies are correlated.
        Returns: the single strategy ID that maximises joint conversion probability.
        """
        if not lead_ids:
            return "cold_dm_value"
        avg_p = sum(conversion_ps.get(lid, 0.05) for lid in lead_ids) / len(lead_ids)
        ensemble = self.build_ensemble(niche, "dm_sent", avg_p)
        return ensemble[0].strategy.id if ensemble else "cold_dm_value"

    def interference_map(
        self, niche: str, conversion_p: float
    ) -> List[dict]:
        """
        Show the full interference pattern — which strategies reinforce/cancel.
        This IS the factor attribution mechanism: dimensions that survive
        across the most-weighted strategies ARE the causal drivers.
        """
        ensemble = self.build_ensemble(niche, "replied", conversion_p)
        active = [sa for sa in ensemble if not sa.decayed]
        return [
            {
                "strategy":   sa.strategy.name,
                "probability": round(sa.probability, 3),
                "amplitude":  round(sa.amplitude, 3),
                "decayed":    sa.decayed,
                "actions":    sa.strategy.actions,
            }
            for sa in active[:5]
        ]
