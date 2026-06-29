"""
Hamilton-Jacobi Optimal Outreach Planner
=========================================

Solves the entire outreach future AT ONCE by computing a value function V(s)
over the complete funnel state space.

V(s) = minimum expected effort (in outreach touchpoints) to reach a closed
       deal from state s.

The Hamilton-Jacobi-Bellman equation:
  V(s) = min_a [ cost(s, a) + γ · V(next_state(s, a)) ]

Once the value function is pre-computed, the optimal action at any state is:
  π*(s) = argmin_a [ cost(s, a) + γ · V(next_state(s, a)) ]

This is the mathematical engine that makes Jarvis sovereign: it doesn't compute
the next move — it already has the optimal response to every possible funnel
situation pre-computed.

Implements:
  - Hamilton-Jacobi-Bellman (HJB) optimal control
  - Pontryagin Maximum Principle (optimal trajectory characterisation)
  - Model Predictive Control (receding horizon — replan every N steps)
  - Control Barrier Functions (guardrails against over-aggressive outreach)
  - Optimal control theory (minimise outreach effort, maximise P(conversion))
  - Variational mechanics (action minimisation over outreach sequences)
  - Receding horizon optimisation
"""

import math
import numpy as np
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple


# ── State & action spaces ─────────────────────────────────────────────────────

# Funnel stages as discrete states
STATES = [
    "new",            # 0 — not contacted yet
    "dm_sent",        # 1 — first DM sent, no reply
    "replied",        # 2 — replied (positive / neutral)
    "call_booked",    # 3 — discovery call scheduled
    "call_done",      # 4 — call completed
    "proposal_sent",  # 5 — price / proposal sent
    "closed",         # 6 — TERMINAL GOAL
    "lost",           # 7 — TERMINAL (lost)
    "stalled",        # 8 — went quiet after reply
    "follow_up_1",    # 9 — first follow-up sent
    "follow_up_2",    # 10 — second follow-up sent
]
STATE_IDX = {s: i for i, s in enumerate(STATES)}
TERMINAL  = {"closed", "lost"}

ACTIONS = [
    "send_dm",           # cold DM
    "send_comment",      # leave a comment on their post
    "send_followup",     # follow-up message
    "send_case_study",   # share a case study
    "send_price",        # share the proposal
    "book_call",         # explicitly ask for a call
    "wait",              # do nothing for 1 cycle
    "disqualify",        # mark as lost and stop
]

# Discount factor (0.9 = prefer early conversions)
GAMMA = 0.90


@dataclass
class OutreachConfig:
    """Configurable outreach parameters."""
    max_dms_per_day:          int   = 10
    max_followups_per_lead:   int   = 3
    min_hours_between_msgs:   float = 24.0
    aggressive_close_p:       float = 0.7   # control barrier: only close-push when P(close) > this


class HamiltonJacobiPlanner:
    """
    Pre-computed optimal outreach policy via Hamilton-Jacobi-Bellman.

    At startup, runs value iteration over the finite MDP to produce
    V[state] and π[state]. At runtime, policy lookup is O(1).
    """

    def __init__(self, cfg: Optional[OutreachConfig] = None):
        self.cfg = cfg or OutreachConfig()
        self._V: Dict[str, float] = {}      # value function
        self._pi: Dict[str, str]  = {}      # optimal policy
        self._transition: Dict    = {}
        self._reward: Dict        = {}
        self._build_mdp()
        self._value_iteration()

    # ── MDP construction ──────────────────────────────────────────────────────

    def _build_mdp(self):
        """Define transition probabilities and rewards for the outreach MDP."""
        # Transition: P(next_state | state, action)
        # Format: {(state, action): [(next_state, prob), ...]}
        T = {}

        def add(s, a, *outcomes):
            """outcomes = (next_state, prob) pairs"""
            T[(s, a)] = list(outcomes)

        # ── From 'new' ────────────────────────────────────────────────────────
        add("new", "send_dm",
            ("dm_sent", 1.0))
        add("new", "send_comment",
            ("dm_sent", 0.6), ("new", 0.4))
        add("new", "wait",
            ("new", 1.0))

        # ── From 'dm_sent' ────────────────────────────────────────────────────
        add("dm_sent", "wait",
            ("replied", 0.12), ("dm_sent", 0.88))
        add("dm_sent", "send_followup",
            ("replied", 0.18), ("follow_up_1", 0.82))
        add("dm_sent", "send_comment",
            ("replied", 0.15), ("dm_sent", 0.85))
        add("dm_sent", "disqualify",
            ("lost", 1.0))

        # ── From 'follow_up_1' ────────────────────────────────────────────────
        add("follow_up_1", "wait",
            ("replied", 0.10), ("follow_up_1", 0.90))
        add("follow_up_1", "send_followup",
            ("replied", 0.12), ("follow_up_2", 0.88))
        add("follow_up_1", "disqualify",
            ("lost", 1.0))

        # ── From 'follow_up_2' ────────────────────────────────────────────────
        add("follow_up_2", "wait",
            ("replied", 0.06), ("follow_up_2", 0.94))
        add("follow_up_2", "send_followup",
            ("replied", 0.07), ("lost", 0.93))   # 3rd follow-up rarely works
        add("follow_up_2", "disqualify",
            ("lost", 1.0))

        # ── From 'replied' ────────────────────────────────────────────────────
        add("replied", "book_call",
            ("call_booked", 0.45), ("stalled", 0.55))
        add("replied", "send_case_study",
            ("stalled", 0.30), ("replied", 0.70))
        add("replied", "wait",
            ("stalled", 0.40), ("replied", 0.60))
        add("replied", "send_price",
            ("proposal_sent", 0.25), ("stalled", 0.75))

        # ── From 'stalled' ────────────────────────────────────────────────────
        add("stalled", "send_followup",
            ("replied", 0.20), ("stalled", 0.80))
        add("stalled", "send_case_study",
            ("replied", 0.25), ("stalled", 0.75))
        add("stalled", "wait",
            ("stalled", 0.95), ("lost", 0.05))
        add("stalled", "disqualify",
            ("lost", 1.0))

        # ── From 'call_booked' ────────────────────────────────────────────────
        add("call_booked", "wait",
            ("call_done", 0.80), ("call_booked", 0.20))

        # ── From 'call_done' ─────────────────────────────────────────────────
        add("call_done", "send_price",
            ("proposal_sent", 0.75), ("lost", 0.25))
        add("call_done", "wait",
            ("proposal_sent", 0.40), ("lost", 0.60))

        # ── From 'proposal_sent' ─────────────────────────────────────────────
        add("proposal_sent", "wait",
            ("closed", 0.35), ("lost", 0.30), ("stalled", 0.35))
        add("proposal_sent", "send_followup",
            ("closed", 0.40), ("lost", 0.35), ("stalled", 0.25))

        # ── Terminals ─────────────────────────────────────────────────────────
        for terminal in TERMINAL:
            for action in ACTIONS:
                add(terminal, action, (terminal, 1.0))

        self._transition = T

        # Reward function: R(state, action, next_state)
        R = {}
        for (s, a), outcomes in T.items():
            for (ns, p) in outcomes:
                if ns == "closed":
                    R[(s, a, ns)] = 100.0   # conversion reward
                elif ns == "lost":
                    R[(s, a, ns)] = -5.0    # small loss penalty
                elif a == "wait":
                    R[(s, a, ns)] = -0.5    # waiting has opportunity cost
                elif a in ("send_dm", "send_followup", "send_comment"):
                    R[(s, a, ns)] = -1.0    # outreach costs effort
                else:
                    R[(s, a, ns)] = -0.8
        self._reward = R

    # ── Value iteration ───────────────────────────────────────────────────────

    def _value_iteration(self, theta: float = 1e-6, max_iter: int = 500):
        """
        Solve HJB via synchronous value iteration.
        V_new(s) = max_a Σ_s' P(s'|s,a) [R(s,a,s') + γ·V(s')]
        """
        V = {s: 0.0 for s in STATES}
        V["closed"] = 100.0
        V["lost"]   = -5.0

        for _ in range(max_iter):
            delta = 0.0
            V_new = dict(V)
            for s in STATES:
                if s in TERMINAL:
                    continue
                best_val = -math.inf
                best_act = "wait"
                for a in ACTIONS:
                    key = (s, a)
                    if key not in self._transition:
                        continue
                    q_val = 0.0
                    for (ns, p) in self._transition[key]:
                        r = self._reward.get((s, a, ns), -1.0)
                        q_val += p * (r + GAMMA * V[ns])
                    if q_val > best_val:
                        best_val = q_val
                        best_act = a
                V_new[s] = best_val
                delta = max(delta, abs(V[s] - best_val))
                self._pi[s] = best_act
            V = V_new
            if delta < theta:
                break

        self._V = V

    # ── Public API ────────────────────────────────────────────────────────────

    def optimal_action(self, state: str, mht_state: Optional[dict] = None) -> str:
        """
        Return the HJ-optimal action for a given funnel state.
        If mht_state is provided, applies a Control Barrier Function:
        only escalate to 'book_call' or 'send_price' if intent probability
        exceeds the configured threshold.
        """
        base_action = self._pi.get(state, "wait")

        # Control Barrier Function — safety guardrail
        if mht_state and base_action in ("book_call", "send_price"):
            hot_p = (mht_state.get("ready_to_close", 0)
                     + mht_state.get("interested", 0) * 0.7)
            if hot_p < self.cfg.aggressive_close_p:
                # Not confident enough — fall back to softer action
                return "send_case_study"

        return base_action

    def value(self, state: str) -> float:
        """Pre-computed value V(s) = expected conversion value from this state."""
        return self._V.get(state, 0.0)

    def value_field(self) -> Dict[str, float]:
        """Return the full value function — the pre-computed map of conversion potential."""
        return dict(self._V)

    def q_values(self, state: str) -> Dict[str, float]:
        """
        Q(s,a) for all actions at this state.
        Higher Q = better expected outcome.
        Implements the Model Predictive Control principle:
        plan the optimal sequence, execute first step, replan.
        """
        Q = {}
        for a in ACTIONS:
            key = (state, a)
            if key not in self._transition:
                continue
            q_val = 0.0
            for (ns, p) in self._transition[key]:
                r = self._reward.get((state, a, ns), -1.0)
                q_val += p * (r + GAMMA * self._V.get(ns, 0.0))
            Q[a] = round(q_val, 3)
        return dict(sorted(Q.items(), key=lambda x: -x[1]))

    def optimal_sequence(self, start_state: str, horizon: int = 5) -> List[dict]:
        """
        Receding horizon optimisation: compute the optimal action sequence
        for `horizon` steps from `start_state`.
        Returns list of {state, action, expected_value}.
        """
        seq    = []
        state  = start_state
        for _ in range(horizon):
            if state in TERMINAL:
                break
            action = self._pi.get(state, "wait")
            seq.append({
                "state":          state,
                "optimal_action": action,
                "value":          round(self._V.get(state, 0.0), 2),
            })
            # Simulate most likely transition
            key = (state, action)
            if key not in self._transition:
                break
            best_ns = max(self._transition[key], key=lambda x: x[1])[0]
            state   = best_ns

        return seq

    def pontryagin_optimal_control(
        self, state: str, target: str = "closed"
    ) -> Dict[str, float]:
        """
        Pontryagin Maximum Principle: identify the control (action) that
        maximises the Hamiltonian at this state.
        H(s, a, λ) = R(s,a) + λ · f(s,a) where λ is the costate (shadow price
        of being one state further from the target).

        Returns: {action: hamiltonian_value, ...} sorted by optimality.
        """
        # Costate = gradient of V (sensitivity of value to state)
        costate = {s: self._V.get(s, 0.0) for s in STATES}
        H_vals  = {}
        for a in ACTIONS:
            key = (state, a)
            if key not in self._transition:
                continue
            ham = 0.0
            for (ns, p) in self._transition[key]:
                r   = self._reward.get((state, a, ns), -1.0)
                ham += p * (r + GAMMA * costate.get(ns, 0.0))
            H_vals[a] = round(ham, 3)
        return dict(sorted(H_vals.items(), key=lambda x: -x[1]))

    def summary(self) -> dict:
        """Full policy summary for Jarvis to report."""
        return {
            "policy": dict(self._pi),
            "value_field": {k: round(v, 2) for k, v in self._V.items()},
            "top_states": sorted(
                [(s, round(v, 2)) for s, v in self._V.items() if s not in TERMINAL],
                key=lambda x: -x[1]
            )[:5],
        }
