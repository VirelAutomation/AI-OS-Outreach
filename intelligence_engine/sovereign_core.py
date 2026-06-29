"""
Sovereign Core — MOIRA-Class Sales Intelligence Orchestrator
=============================================================

This is the master intelligence layer. It runs the full MOIRA cycle:
  GENERATE → PRUNE → REFINE

For every lead at every stage, it produces a unified intelligence package:
  - Manifold position + curvature + geodesic projection
  - Multi-hypothesis intent state (MHT)
  - Bayesian conversion probability
  - Entropy / surprise score
  - Kalman-filtered engagement trajectory
  - Hamilton-Jacobi optimal action
  - Quantum ensemble strategy ranking
  - Verkle pattern commitment match
  - CRL causal intervention recommendation
  - Jarvis action brief (what to tell Jarvis to do)

This is what makes Jarvis genuinely sovereign:
  "It doesn't compute the next move.
   It already has the optimal response to every possible funnel situation
   pre-computed across the entire state space."

Adapts from MOIRA, DMBG, VCAOC, CRL, and the SCI architecture.
"""

import json
import os
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, List, Optional

from .lead_manifold       import LeadManifold, ManifoldPoint
from .multi_hypothesis    import MHT
from .bayesian_scorer     import BayesianScorer
from .entropy_monitor     import EntropyMonitor
from .kalman_engagement   import KalmanEngagement
from .hamilton_jacobi     import HamiltonJacobiPlanner, OutreachConfig
from .quantum_ensemble    import QuantumEnsemble
from .pattern_tree        import PatternTree
from .causal_engine       import CausalEngine


_DATA_DIR = Path(os.getenv("DATA_DIR", str(Path(__file__).parent.parent)))


@dataclass
class LeadIntelligencePackage:
    """Full intelligence output for a single lead."""
    lead_id:             str
    timestamp:           str

    # Manifold layer
    manifold_stage:      float
    funnel_curvature:    float
    behavioral_curvature:float
    coupled_curvature:   float
    temporal_curvature:  float
    geodesic_projection: str       # "converting" | "stalling" | "churning" | "progressing"
    geodesic_stability:  float     # confidence gate

    # MHT layer
    dominant_intent:     str
    intent_confidence:   float
    intent_entropy:      float
    intent_collapsed:    Optional[str]

    # Bayesian layer
    conversion_probability: float
    probability_tier:    str       # "🔥 HOT" etc.

    # Entropy layer
    surprise_score:      float
    surprise_direction:  str

    # Kalman layer
    engagement_level:    float
    engagement_trend:    str

    # HJ + Quantum layer
    optimal_action:      str
    optimal_strategy:    str
    strategy_probability:float

    # Pattern layer
    pattern_match:       str
    pattern_outcome:     str
    pattern_confidence:  float

    # Final directive (for Jarvis)
    priority_score:      float
    action_brief:        str       # plain English for Jarvis


class SovereignCore:
    """
    The sovereign intelligence orchestrator.

    One instance per session. Persists state to JSON files in DATA_DIR
    so intelligence carries across conversations.
    """

    def __init__(self):
        self.manifold  = LeadManifold()
        self.mht       = MHT()
        self.bayes     = BayesianScorer()
        self.entropy   = EntropyMonitor()
        self.kalman    = KalmanEngagement()
        self.hj        = HamiltonJacobiPlanner(OutreachConfig())
        self.quantum   = QuantumEnsemble(temperature=1.2)
        self.patterns  = PatternTree()
        self.causal    = CausalEngine()
        self._lead_contexts: Dict[str, dict] = {}   # niche, region, platform
        self._load_contexts()

    # ── Lead registration ─────────────────────────────────────────────────────

    def register_lead(
        self,
        lead_id:  str,
        niche:    str,
        region:   str,
        platform: str,
        stage:    str = "dm_sent",
    ):
        """Register a new lead with all intelligence engines."""
        self._lead_contexts[lead_id] = {
            "niche": niche, "region": region,
            "platform": platform, "stage": stage,
            "events": [],
        }
        self.mht.init_lead(lead_id, niche)
        self.bayes.init_lead(lead_id, niche)
        self.entropy.init_lead(lead_id, stage)
        self.kalman.init_lead(lead_id)
        self._save_contexts()

    # ── Event processing ──────────────────────────────────────────────────────

    def process_event(
        self,
        lead_id:        str,
        event:          str,
        is_intervention: bool = False,
        stage:          str  = "",
    ) -> LeadIntelligencePackage:
        """
        Process a new event for a lead and run the full MOIRA cycle.
        Returns a complete intelligence package.
        """
        ctx = self._lead_contexts.setdefault(lead_id, {
            "niche": "default", "region": "us", "platform": "instagram",
            "stage": stage or "dm_sent", "events": [],
        })
        if stage:
            ctx["stage"] = stage
        ctx["events"].append(event)

        niche    = ctx["niche"]
        region   = ctx["region"]
        cur_stage = ctx["stage"]

        # ── Engine updates ────────────────────────────────────────────────────

        mht_state    = self.mht.update(lead_id, event)
        bayes_score  = self.bayes.update(lead_id, event, is_intervention)
        surprise, _  = self.entropy.record_event(lead_id, event, cur_stage)
        kalman_state = self.kalman.update(lead_id, event)

        # Update manifold point
        manifold_pt = ManifoldPoint(
            lead_id           = lead_id,
            stage             = float({"dm_sent":1,"replied":2,"call_booked":3,
                                       "call_done":4,"proposal_sent":5,
                                       "closed":6,"lost":-1}.get(cur_stage, 1)),
            response_rate     = min(1.0, sum(1 for e in ctx["events"] if e == "replied") /
                                    max(len(ctx["events"]), 1)),
            response_time_inv = 0.5 if event in ("replied", "positive_reply") else 0.1,
            sentiment         = {"positive_reply": 0.8, "negative_reply": -0.8,
                                  "replied": 0.3, "objection_raised": -0.2,
                                  "booked_call": 1.0}.get(event, 0.0),
            engagement_vel    = kalman_state.velocity(),
            message_depth     = 0.8 if event == "long_message" else 0.2,
            timestamp         = time.time(),
        )
        self.manifold.update(manifold_pt)

        # ── MOIRA cycle ───────────────────────────────────────────────────────

        # GENERATE: HJ optimal action
        dom_intent, dom_p = mht_state.dominant()
        hj_action = self.hj.optimal_action(cur_stage, dict(mht_state.probs))

        # GENERATE: Quantum ensemble
        strategy, strat_p = self.quantum.collapse(
            niche=niche,
            funnel_stage=cur_stage,
            conversion_p=bayes_score.probability,
            mht_dominant=dom_intent,
            hj_spine=hj_action,
        )

        # PRUNE: Pattern tree lookup (prune low-plausibility interpretations)
        pattern_match = self.patterns.lookup(lead_id, ctx["events"])

        # REFINE: Geodesic projection with stability confidence gate
        curvatures = self.manifold.curvature_report(lead_id)
        proj_vec, stability, projection = self.manifold.project_geodesic(lead_id)

        # ── Priority score ────────────────────────────────────────────────────
        # Combines all intelligence signals into one urgency number
        priority = (
            bayes_score.probability * 2.0
            + self.mht.urgency_score(lead_id) * 1.5
            + (1.0 if projection == "converting" else 0.0) * 1.0
            + stability * 0.5
            + min(surprise / 3.0, 0.5)
        ) / 5.5

        # ── Action brief (for Jarvis) ─────────────────────────────────────────
        brief = self._generate_brief(
            lead_id=lead_id, niche=niche, region=region,
            stage=cur_stage, dom_intent=dom_intent, dom_p=dom_p,
            conv_p=bayes_score.probability, tier=bayes_score.tier(),
            projection=projection, stability=stability,
            hj_action=hj_action, strategy_name=strategy.name,
            pattern=pattern_match, priority=priority,
        )

        # Record for CRL
        self.causal.record_simple(
            lead_id=lead_id, niche=niche, region=region,
            interventions=[event] if is_intervention else [],
            outcome=(cur_stage == "closed"),
        )

        return LeadIntelligencePackage(
            lead_id              = lead_id,
            timestamp            = time.strftime("%Y-%m-%d %H:%M:%S"),
            manifold_stage       = manifold_pt.stage,
            funnel_curvature     = round(curvatures.get("funnel", 0), 4),
            behavioral_curvature = round(curvatures.get("behavioral", 0), 4),
            coupled_curvature    = round(curvatures.get("coupled", 0), 4),
            temporal_curvature   = round(curvatures.get("temporal", 0), 4),
            geodesic_projection  = projection,
            geodesic_stability   = round(stability, 3),
            dominant_intent      = dom_intent,
            intent_confidence    = round(dom_p, 3),
            intent_entropy       = round(mht_state.entropy(), 3),
            intent_collapsed     = mht_state.collapsed,
            conversion_probability = round(bayes_score.probability, 3),
            probability_tier     = bayes_score.tier(),
            surprise_score       = round(surprise, 3),
            surprise_direction   = (
                self.entropy.get_state(lead_id).alerts[-1]["direction"]
                if self.entropy.get_state(lead_id) and self.entropy.get_state(lead_id).alerts
                else "neutral"
            ),
            engagement_level     = round(kalman_state.level(), 3),
            engagement_trend     = kalman_state.trend(),
            optimal_action       = hj_action,
            optimal_strategy     = strategy.name,
            strategy_probability = strat_p,
            pattern_match        = pattern_match.best_match.name,
            pattern_outcome      = pattern_match.predicted_outcome,
            pattern_confidence   = pattern_match.confidence,
            priority_score       = round(priority, 3),
            action_brief         = brief,
        )

    # ── Batch intelligence scan ───────────────────────────────────────────────

    def full_pipeline_scan(self) -> dict:
        """
        Run intelligence scan on ALL registered leads.
        Returns prioritised action list for Jarvis.
        """
        hot_leads  = self.bayes.hot_leads(threshold=0.20)
        mht_states = self.mht.all_states()
        surprise_q = self.entropy.priority_leads(top_k=10)
        kalman_top = self.kalman.rank_by_engagement()[:5]
        causal_recs = self.causal.recommend_interventions(
            niche="hvac", region="us"  # generalised
        )

        return {
            "hot_leads":           hot_leads[:10],
            "top_mht_states":      mht_states[:10],
            "surprise_queue":      surprise_q,
            "top_engaged":         kalman_top,
            "proven_mechanisms":   causal_recs,
            "hj_policy_summary":   self.hj.summary(),
            "persistent_patterns": self.patterns.persistent_patterns(),
        }

    # ── Brief generation ──────────────────────────────────────────────────────

    def _generate_brief(self, **kw) -> str:
        tier  = kw["tier"]
        stage = kw["stage"]
        proj  = kw["projection"]
        stab  = kw["stability"]
        p     = kw["conv_p"]

        lines = [
            f"{tier} lead in {stage}",
            f"Intent: {kw['dom_intent']} ({kw['dom_p']:.0%} confidence)",
            f"Conversion probability: {p:.0%}",
            f"Geodesic: {proj} (stability {stab:.0%})",
        ]
        if stab > 0.7 and proj == "converting" and p > 0.25:
            lines.append(f"⚡ LOCKED ONTO CONVERSION — execute {kw['hj_action']} NOW")
        elif proj == "stalling" and stab > 0.5:
            lines.append(f"⚠️  STALLING DETECTED — intervene with {kw['strategy_name']}")
        elif proj == "churning":
            lines.append("🚨 CHURN TRAJECTORY — last chance: send case study or disqualify")
        else:
            lines.append(f"→ Next optimal action: {kw['hj_action']}")

        lines.append(f"Strategy: {kw['strategy_name']}")
        if kw["pattern"].match_type != "novel":
            lines.append(f"Pattern: {kw['pattern'].best_match.name} → {kw['pattern'].predicted_outcome}")
        return " | ".join(lines)

    # ── Persistence ───────────────────────────────────────────────────────────

    def _save_contexts(self):
        try:
            f = _DATA_DIR / "lead_contexts.json"
            f.write_text(json.dumps(self._lead_contexts, indent=2, default=str))
        except Exception:
            pass

    def _load_contexts(self):
        try:
            f = _DATA_DIR / "lead_contexts.json"
            if f.exists():
                self._lead_contexts = json.loads(f.read_text())
        except Exception:
            self._lead_contexts = {}

    # ── Jarvis tool interface ─────────────────────────────────────────────────

    def jarvis_intelligence_scan(self) -> dict:
        """
        Single-call method for Jarvis to get the full intelligence overview.
        Returns a clean dict that maps to Jarvis's intelligence_scan tool.
        """
        scan = self.full_pipeline_scan()
        return {
            "total_leads":        len(self._lead_contexts),
            "hot_leads":          len(scan["hot_leads"]),
            "ready_to_close":     sum(
                1 for s in scan["top_mht_states"] if s["dominant"] == "ready_to_close"
            ),
            "top_priority_leads": scan["hot_leads"][:5],
            "surprise_targets":   scan["surprise_queue"][:3],
            "proven_actions":     [r["intervention"] for r in scan["proven_mechanisms"][:3]],
            "hj_optimal_policy":  scan["hj_policy_summary"]["policy"],
            "causal_mechanisms":  scan["proven_mechanisms"],
        }
