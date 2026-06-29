"""
Virel Automation — Sovereign Intelligence Engine
================================================

MOIRA-class sales intelligence adapted from DMBG / VCAOC / CRL / quantum-ensemble
architecture. Every lead is a point on a Riemannian product manifold.
The system predicts where each lead is heading and computes the optimal
outreach action to deflect stalling leads back toward conversion.

Architecture (MOIRA cycle — Generate → Prune → Refine):
  1. Lead Manifold     — M_funnel × M_behavioral product space
  2. Hamilton-Jacobi   — optimal action pre-computed over entire funnel state space
  3. Quantum Ensemble  — superposition of strategies, interference-based ranking
  4. Pattern Tree      — Verkle-inspired fuzzy pattern commitment for conversion signatures
  5. Multi-Hypothesis  — MHT for parallel lead intent hypotheses
  6. Bayesian Scorer   — posterior conversion probability per evidence
  7. Entropy Monitor   — KL-divergence surprise scoring for hot-lead detection
  8. Kalman Engagement — smooth noisy engagement signals
  9. Causal Engine     — CRL invariant mechanism learning
 10. Sovereign Core    — orchestrates all engines, exposes unified API
"""

from .sovereign_core import SovereignCore
from .lead_manifold   import LeadManifold
from .multi_hypothesis import MHT
from .bayesian_scorer  import BayesianScorer
from .entropy_monitor  import EntropyMonitor
from .kalman_engagement import KalmanEngagement
from .hamilton_jacobi  import HamiltonJacobiPlanner
from .quantum_ensemble import QuantumEnsemble
from .pattern_tree     import PatternTree
from .causal_engine    import CausalEngine

__all__ = [
    "SovereignCore", "LeadManifold", "MHT", "BayesianScorer",
    "EntropyMonitor", "KalmanEngagement", "HamiltonJacobiPlanner",
    "QuantumEnsemble", "PatternTree", "CausalEngine",
]
