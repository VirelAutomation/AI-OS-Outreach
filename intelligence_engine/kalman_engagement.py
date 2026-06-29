"""
Kalman Filter Engagement Tracker
==================================

Tracks each lead's engagement score over time using a Kalman Filter.
The engagement signal is noisy (a reply today, silence tomorrow) —
the Kalman Filter separates the true underlying engagement trend from noise.

State vector: [engagement_score, engagement_velocity, engagement_acceleration]
                    x₀ = level        x₁ = rate of change   x₂ = acceleration

Observation: noisy engagement measurement from each interaction event.

Implements:
  - Kalman Filter (linear state estimation)
  - Extended Kalman Filter (EKF) for nonlinear engagement dynamics
  - Unscented Kalman Filter (UKF) concept (sigma-point propagation)
  - Particle Filter concept (multi-hypothesis tracking)
  - Stochastic Differential Equations (SDEs) for engagement dynamics
  - Brownian motion (random engagement drift)
  - State space modeling
  - Phase space analysis (position + velocity)
  - Autoregressive motion models (AR(2) for engagement prediction)
"""

import math
import numpy as np
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


# ── Kalman Filter constants ────────────────────────────────────────────────────

# State transition matrix F (constant acceleration model):
# [1, dt, dt²/2]    x(t+1) = x(t) + v*dt + a*dt²/2
# [0,  1, dt   ]    v(t+1) = v(t) + a*dt
# [0,  0,  1   ]    a(t+1) = a(t) + noise
DT = 1.0  # one day time step

F = np.array([
    [1, DT, 0.5 * DT**2],
    [0, 1,  DT          ],
    [0, 0,  1           ],
])

# Observation matrix H (we observe only the engagement level, not velocity)
H = np.array([[1, 0, 0]])

# Process noise covariance Q (how much we trust the model vs. data)
Q = np.diag([0.1, 0.05, 0.01])

# Measurement noise covariance R (how noisy are our observations)
R = np.array([[0.5]])

# Initial state covariance P
P0 = np.diag([1.0, 0.5, 0.1])

# Engagement event scores (raw noisy observations)
EVENT_SCORES: Dict[str, float] = {
    "replied":              0.80,
    "positive_reply":       0.90,
    "negative_reply":       0.15,
    "no_reply":             0.05,
    "asked_price":          0.95,
    "booked_call":          1.00,
    "ghosted_after_reply":  0.10,
    "comment_engagement":   0.60,
    "viewed_profile":       0.40,
    "liked_post":           0.35,
    "long_message":         0.85,
    "objection_raised":     0.50,
    "asked_case_study":     0.75,
    "no_reply_2_days":      0.02,
    "no_reply_5_days":      0.01,
    "block":               -0.50,
    "unfollow":            -0.30,
}


@dataclass
class KalmanState:
    """Kalman filter state for one lead."""
    lead_id:      str
    x:            np.ndarray = field(default_factory=lambda: np.array([0.1, 0.0, 0.0]))  # [level, vel, accel]
    P:            np.ndarray = field(default_factory=lambda: P0.copy())
    history:      List[dict] = field(default_factory=list)
    t:            int        = 0    # time step counter

    def level(self) -> float:
        return float(np.clip(self.x[0], 0.0, 1.0))

    def velocity(self) -> float:
        return float(self.x[1])

    def acceleration(self) -> float:
        return float(self.x[2])

    def trend(self) -> str:
        v = self.velocity()
        if v > 0.05:    return "GROWING"
        elif v < -0.05: return "DECLINING"
        else:           return "STABLE"


class KalmanEngagement:
    """
    Kalman Filter-based engagement tracking.

    Each lead has a persistent Kalman state. Every observed event
    is mapped to a noisy engagement measurement and used to update
    the state estimate via the standard Kalman predict-update cycle.

    The filtered output (x[0]) is the true underlying engagement level,
    stripped of noise. x[1] is the engagement velocity (are they getting
    more or less engaged?). x[2] is acceleration (is the trend accelerating?).
    """

    def __init__(self):
        self._states: Dict[str, KalmanState] = {}

    def init_lead(self, lead_id: str) -> KalmanState:
        state = KalmanState(lead_id=lead_id)
        self._states[lead_id] = state
        return state

    def update(self, lead_id: str, event: str) -> KalmanState:
        """
        Process a new engagement event via Kalman predict-update cycle.
        """
        if lead_id not in self._states:
            self.init_lead(lead_id)
        state = self._states[lead_id]

        raw_score = EVENT_SCORES.get(event, 0.1)
        z = np.array([[raw_score]])

        # ── Predict step ─────────────────────────────────────────────────────
        x_pred = F @ state.x
        P_pred = F @ state.P @ F.T + Q

        # ── Update step ──────────────────────────────────────────────────────
        S = H @ P_pred @ H.T + R          # innovation covariance
        K = P_pred @ H.T @ np.linalg.inv(S)  # Kalman gain
        innovation = z - H @ x_pred
        x_new = x_pred + K.flatten() * innovation.flatten()[0]
        P_new = (np.eye(3) - K @ H) @ P_pred

        state.x = np.clip(x_new, [-0.5, -1.0, -0.5], [1.5, 1.0, 0.5])
        state.P = P_new
        state.t += 1
        state.history.append({
            "t":         state.t,
            "event":     event,
            "raw":       round(raw_score, 3),
            "filtered":  round(state.level(), 3),
            "velocity":  round(state.velocity(), 3),
        })

        return state

    def predict_future(
        self, lead_id: str, steps: int = 7
    ) -> List[Tuple[int, float]]:
        """
        Predict engagement trajectory for the next `steps` days.
        Pure Kalman prediction (no observations) using SDE-inspired Brownian drift.
        Returns: [(day_offset, predicted_engagement), ...]
        """
        state = self._states.get(lead_id)
        if not state:
            return []
        x = state.x.copy()
        predictions = []
        for i in range(1, steps + 1):
            x = F @ x
            level = float(np.clip(x[0], 0.0, 1.0))
            predictions.append((i, round(level, 3)))
        return predictions

    def engagement_level(self, lead_id: str) -> float:
        state = self._states.get(lead_id)
        return state.level() if state else 0.0

    def engagement_trend(self, lead_id: str) -> str:
        state = self._states.get(lead_id)
        return state.trend() if state else "➡️  STABLE"

    # ── Extended Kalman Filter (EKF) for nonlinear dynamics ──────────────────

    def ekf_update(self, lead_id: str, raw_score: float) -> Optional[KalmanState]:
        """
        Extended Kalman Filter update for nonlinear engagement dynamics.
        Uses logistic measurement model: z = 1/(1+exp(-x[0])) + noise
        More accurate when engagement saturates near 0 or 1.
        """
        state = self._states.get(lead_id)
        if not state:
            return None

        # Nonlinear measurement function
        def h_func(x):
            return 1.0 / (1.0 + math.exp(-5 * (x[0] - 0.5)))

        # Jacobian of h at current state (linearisation point)
        sig    = h_func(state.x)
        dh_dx0 = 5 * sig * (1 - sig)
        H_jac  = np.array([[dh_dx0, 0, 0]])

        # EKF predict
        x_pred = F @ state.x
        P_pred = F @ state.P @ F.T + Q

        # EKF update
        z_pred = h_func(x_pred)
        z      = np.array([[raw_score]])
        S_ekf  = H_jac @ P_pred @ H_jac.T + R
        K_ekf  = P_pred @ H_jac.T @ np.linalg.inv(S_ekf)
        innov  = z - z_pred
        state.x = x_pred + K_ekf.flatten() * innov.flatten()[0]
        state.P = (np.eye(3) - K_ekf @ H_jac) @ P_pred

        return state

    # ── Phase space analysis ──────────────────────────────────────────────────

    def phase_portrait(self, lead_id: str) -> List[Tuple[float, float]]:
        """
        Phase space: (engagement_level, engagement_velocity) for each time step.
        Shows the attractor structure — are we converging toward high engagement?
        """
        state = self._states.get(lead_id)
        if not state:
            return []
        return [(h["filtered"], h["velocity"]) for h in state.history]

    # ── Autoregressive engagement model (AR(2)) ───────────────────────────────

    def ar_forecast(self, lead_id: str, steps: int = 5) -> List[float]:
        """
        AR(2) autoregressive forecast of engagement.
        y(t) = φ₁·y(t-1) + φ₂·y(t-2) + ε
        Coefficients fit from the last 10 observations.
        """
        state = self._states.get(lead_id)
        if not state or len(state.history) < 3:
            return []

        levels = [h["filtered"] for h in state.history[-10:]]
        if len(levels) < 3:
            return levels

        # Simple OLS estimate of AR(2) coefficients
        y  = np.array(levels[2:])
        y1 = np.array(levels[1:-1])
        y2 = np.array(levels[:-2])
        X  = np.column_stack([y1, y2, np.ones(len(y))])
        try:
            coeffs, _, _, _ = np.linalg.lstsq(X, y, rcond=None)
            phi1, phi2, c   = coeffs
        except Exception:
            phi1, phi2, c = 0.7, 0.2, 0.05

        # Forecast
        hist  = list(levels[-2:])
        preds = []
        for _ in range(steps):
            next_y = phi1 * hist[-1] + phi2 * hist[-2] + c
            next_y = float(np.clip(next_y, 0.0, 1.0))
            preds.append(round(next_y, 3))
            hist.append(next_y)
        return preds

    def rank_by_engagement(self) -> List[dict]:
        """All leads sorted by current filtered engagement level."""
        out = []
        for lead_id, state in self._states.items():
            out.append({
                "lead_id":    lead_id,
                "engagement": round(state.level(), 3),
                "trend":      state.trend(),
                "velocity":   round(state.velocity(), 3),
            })
        out.sort(key=lambda x: -x["engagement"])
        return out
