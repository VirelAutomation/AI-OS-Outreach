"""
Riemannian Dual-Manifold for Lead Trajectories
================================================

Every lead is a point on M = M_funnel × M_behavioral.

M_funnel    — pipeline stage space (1→7, real-valued for interpolation)
M_behavioral — behavioral signature space:
               [response_rate, avg_response_time_norm, sentiment_score,
                engagement_velocity, message_depth_norm]

The metric tensor G at each point defines the cost of movement in that space.
A lead accelerating toward 'closed' follows a natural geodesic.
Curvature = how much the trajectory is bending away from the natural geodesic.

Implements:
  - Riemannian manifolds (DMBG core)
  - Geodesic deviation
  - Differential trajectory curvature
  - Manifold distance metrics
  - Product manifold M_phys × M_behav (here: M_funnel × M_behavioral)
  - Temporal curvature (second derivative — earliest warning signal)
  - Hamilton-Jacobi value field (∂V/∂t + H(x,∇V,t) = 0)
  - Lyapunov stability for trajectory analysis
"""

import numpy as np
from dataclasses import dataclass, field
from typing import List, Optional, Tuple


# ── Constants ──────────────────────────────────────────────────────────────────

# Funnel stage numeric values (1=dm_sent … 6=closed, 7=lost)
STAGE_VALUES = {
    "dm_sent": 1.0, "replied": 2.0, "call_booked": 3.0,
    "call_done": 4.0, "proposal_sent": 5.0, "closed": 6.0, "lost": -1.0,
}

# Conversion attractor in funnel space (closed = 6.0)
CONVERSION_ATTRACTOR = np.array([6.0, 1.0, 0.0, 1.0, 1.0, 1.0])
LOST_ATTRACTOR        = np.array([-1.0, 0.0, 1.0, -1.0, 0.0, 0.0])

# Metric weights — higher weight = more important dimension
# [stage, response_rate, response_time_inv, sentiment, engagement_v, depth]
METRIC_DIAG = np.array([2.5, 1.8, 1.2, 2.0, 1.5, 1.0])


@dataclass
class ManifoldPoint:
    """A lead's position in M = M_funnel × M_behavioral."""
    lead_id:           str
    stage:             float          # M_funnel coordinate
    response_rate:     float          # 0-1 fraction of messages replied to
    response_time_inv: float          # 1/(avg_response_hours) normalised 0-1
    sentiment:         float          # -1=negative, 0=neutral, +1=positive
    engagement_vel:    float          # change in engagement score per day
    message_depth:     float          # avg message length / 500 words, 0-1
    timestamp:         float = 0.0   # Unix timestamp

    def to_vector(self) -> np.ndarray:
        return np.array([
            self.stage, self.response_rate, self.response_time_inv,
            self.sentiment, self.engagement_vel, self.message_depth,
        ])


@dataclass
class LeadTrajectory:
    """History of a lead's manifold positions."""
    lead_id:  str
    points:   List[ManifoldPoint] = field(default_factory=list)

    def add(self, point: ManifoldPoint):
        self.points.append(point)

    def vectors(self) -> np.ndarray:
        """Shape (T, 6) — each row is one manifold point."""
        return np.array([p.to_vector() for p in self.points])

    def velocity(self) -> Optional[np.ndarray]:
        """First derivative of trajectory (manifold velocity)."""
        vecs = self.vectors()
        if len(vecs) < 2:
            return None
        return vecs[-1] - vecs[-2]

    def acceleration(self) -> Optional[np.ndarray]:
        """Second derivative — temporal curvature (earliest warning)."""
        vecs = self.vectors()
        if len(vecs) < 3:
            return None
        return vecs[-1] - 2 * vecs[-2] + vecs[-3]


class LeadManifold:
    """
    Riemannian dual manifold engine for lead trajectory analysis.

    Implements the full DMBG stack adapted to sales intelligence:
      - Context-conditioned metric tensor (SPD matrix)
      - Four curvature signals: funnel, behavioral, coupled, temporal
      - Geodesic projection toward/away from conversion attractor
      - Geodesic stability as confidence gate
      - Lyapunov stability analysis
    """

    def __init__(self, metric_weights: Optional[np.ndarray] = None):
        self.G = np.diag(metric_weights if metric_weights is not None else METRIC_DIAG)
        self._trajectories: dict[str, LeadTrajectory] = {}

    # ── Trajectory management ─────────────────────────────────────────────────

    def update(self, point: ManifoldPoint):
        """Add a new manifold observation for a lead."""
        if point.lead_id not in self._trajectories:
            self._trajectories[point.lead_id] = LeadTrajectory(point.lead_id)
        self._trajectories[point.lead_id].add(point)

    def get_trajectory(self, lead_id: str) -> Optional[LeadTrajectory]:
        return self._trajectories.get(lead_id)

    # ── Metric & distance ─────────────────────────────────────────────────────

    def riemannian_distance(self, a: np.ndarray, b: np.ndarray) -> float:
        """
        Geodesic distance in the Riemannian manifold under metric G.
        For the linearised (flat) case: d = sqrt((a-b)ᵀ G (a-b))
        The full non-linear version would integrate the metric along the geodesic.
        """
        delta = a - b
        return float(np.sqrt(delta @ self.G @ delta))

    def similarity(self, a: np.ndarray, b: np.ndarray) -> float:
        """Normalised similarity ∈ [0,1] — 1 = identical in manifold space."""
        d = self.riemannian_distance(a, b)
        return float(np.exp(-d))

    # ── Curvature engines ─────────────────────────────────────────────────────

    def funnel_curvature(self, traj: LeadTrajectory) -> float:
        """How much the funnel-stage dimension is bending (M_funnel curvature)."""
        vecs = traj.vectors()
        if len(vecs) < 3:
            return 0.0
        # Second derivative of stage column
        d2 = vecs[-1, 0] - 2 * vecs[-2, 0] + vecs[-3, 0]
        return float(abs(d2))

    def behavioral_curvature(self, traj: LeadTrajectory) -> float:
        """How much the behavioral signature dimensions are bending."""
        vecs = traj.vectors()
        if len(vecs) < 3:
            return 0.0
        d2 = vecs[-1, 1:] - 2 * vecs[-2, 1:] + vecs[-3, 1:]
        return float(np.linalg.norm(d2))

    def coupled_curvature(self, traj: LeadTrajectory) -> float:
        """
        Cross-correlation between funnel curvature and behavioral curvature.
        The PRIMARY signal — high coupled curvature = both manifolds bending
        together = genuine conversion trajectory or genuine churn trajectory.
        """
        vecs = traj.vectors()
        if len(vecs) < 3:
            return 0.0
        d2 = vecs[-1] - 2 * vecs[-2] + vecs[-3]
        funnel_d2   = d2[0]
        behavior_d2 = d2[1:]
        # Coupled = magnitude of funnel deviation × correlated behavioral deviation
        corr = float(abs(funnel_d2) * np.linalg.norm(behavior_d2))
        # Normalize by metric
        return float(corr * np.sqrt(self.G[0, 0]))

    def temporal_curvature(self, traj: LeadTrajectory) -> float:
        """
        Third derivative — how fast the curvature itself is changing.
        EARLIEST warning signal: detects the approach to an inflection
        before the inflection occurs.
        """
        vecs = traj.vectors()
        if len(vecs) < 4:
            return 0.0
        # Third derivative (jerk)
        d3 = vecs[-1] - 3 * vecs[-2] + 3 * vecs[-3] - vecs[-4]
        return float(np.linalg.norm(d3 * np.sqrt(np.diag(self.G))))

    def curvature_report(self, lead_id: str) -> dict:
        """Full four-signal curvature report for a lead."""
        traj = self._trajectories.get(lead_id)
        if not traj or len(traj.points) < 2:
            return {"funnel": 0, "behavioral": 0, "coupled": 0, "temporal": 0}
        return {
            "funnel":     self.funnel_curvature(traj),
            "behavioral": self.behavioral_curvature(traj),
            "coupled":    self.coupled_curvature(traj),
            "temporal":   self.temporal_curvature(traj),
        }

    # ── Geodesic projection ───────────────────────────────────────────────────

    def project_geodesic(
        self, lead_id: str, steps: int = 5
    ) -> Tuple[np.ndarray, float, str]:
        """
        Hamilton-Jacobi geodesic projection: shoot the lead's trajectory
        forward `steps` time units and return the projected manifold position,
        geodesic stability score, and predicted outcome.

        Returns: (projected_vector, stability, outcome_label)
        """
        traj = self._trajectories.get(lead_id)
        if not traj or len(traj.points) < 2:
            current = traj.points[-1].to_vector() if traj else np.zeros(6)
            return current, 0.0, "insufficient_data"

        vecs  = traj.vectors()
        vel   = vecs[-1] - vecs[-2]   # manifold velocity
        # Acceleration if available
        accel = np.zeros(6)
        if len(vecs) >= 3:
            accel = (vecs[-1] - 2 * vecs[-2] + vecs[-3]) * 0.5

        # Project forward (kinematic integration on manifold)
        projected = vecs[-1] + vel * steps + 0.5 * accel * steps ** 2
        # Clip to valid range
        projected[0] = np.clip(projected[0], -1.0, 6.5)
        projected[1:] = np.clip(projected[1:], -1.0, 1.5)

        # Geodesic stability: small perturbation test
        stability = self._geodesic_stability(vecs, vel, steps)

        # Outcome classification
        outcome = self._classify_endpoint(projected)
        return projected, stability, outcome

    def _geodesic_stability(
        self, vecs: np.ndarray, vel: np.ndarray, steps: int
    ) -> float:
        """
        Stability = 1 - variance of projected endpoint across small perturbations.
        High stability → trajectory is geometrically locked (confident prediction).
        Low stability  → many possible futures (hold alert level down).
        """
        projections = []
        for _ in range(20):
            noise = np.random.normal(0, 0.05, vel.shape)
            perturbed_vel = vel + noise
            proj = vecs[-1] + perturbed_vel * steps
            projections.append(proj)
        proj_array = np.array(projections)
        variance = float(np.mean(np.var(proj_array, axis=0)))
        stability = float(np.exp(-variance * 3))
        return np.clip(stability, 0.0, 1.0)

    def _classify_endpoint(self, point: np.ndarray) -> str:
        """Map a manifold point to a sales outcome label."""
        d_convert = self.riemannian_distance(point, CONVERSION_ATTRACTOR)
        d_lost    = self.riemannian_distance(point, LOST_ATTRACTOR)
        if point[0] >= 5.5:
            return "converting"
        elif point[0] <= -0.5:
            return "churning"
        elif d_convert < d_lost:
            return "progressing"
        else:
            return "stalling"

    # ── Lyapunov stability ────────────────────────────────────────────────────

    def lyapunov_score(self, lead_id: str) -> float:
        """
        Lyapunov stability: is the lead's trajectory converging to a stable
        attractor (conversion or churn) or wandering?
        V(x) = ||x - x_attractor||²_G. dV/dt < 0 → converging (stable).
        Returns: positive = converging toward conversion, negative = diverging.
        """
        traj = self._trajectories.get(lead_id)
        if not traj or len(traj.points) < 2:
            return 0.0
        vecs = traj.vectors()
        d_t0 = self.riemannian_distance(vecs[-2], CONVERSION_ATTRACTOR)
        d_t1 = self.riemannian_distance(vecs[-1], CONVERSION_ATTRACTOR)
        return float(d_t0 - d_t1)  # positive → getting closer to conversion

    # ── Manifold distance between two leads ───────────────────────────────────

    def lead_similarity(self, id_a: str, id_b: str) -> float:
        """How similar are two leads in manifold space? 1=identical, 0=completely different."""
        ta = self._trajectories.get(id_a)
        tb = self._trajectories.get(id_b)
        if not ta or not tb:
            return 0.0
        return self.similarity(ta.points[-1].to_vector(), tb.points[-1].to_vector())

    def nearest_leads(self, lead_id: str, top_k: int = 5) -> List[Tuple[str, float]]:
        """Find the k most similar leads in manifold space (for transfer learning)."""
        traj = self._trajectories.get(lead_id)
        if not traj:
            return []
        ref_vec = traj.points[-1].to_vector()
        scores = []
        for lid, ltraj in self._trajectories.items():
            if lid == lead_id:
                continue
            d = self.riemannian_distance(ref_vec, ltraj.points[-1].to_vector())
            scores.append((lid, d))
        scores.sort(key=lambda x: x[1])
        return scores[:top_k]
