"""
Mathematics & Physics Toolkit Registry
=======================================

Central registry of all 110 mathematical and physics techniques used
across the Sovereign Intelligence Engine.

Each technique is registered with:
  - Name
  - Domain
  - Sales intelligence application
  - Status: "active" (implemented), "partial" (partially implemented), "registered" (planned)
  - Module where it lives

Based on the complete technique set from the MOIRA/VCAOC/DMBG architecture:
40 Classical/Advanced Power Engines + 15 Speed Engines + 55 Extended Techniques
"""

from dataclasses import dataclass
from typing import Callable, Dict, List, Optional


@dataclass
class MathTechnique:
    """A registered mathematical technique."""
    id:          str
    name:        str
    domain:      str
    application: str    # How it applies to sales intelligence
    status:      str    # "active" | "partial" | "registered"
    module:      str
    compute_fn:  Optional[Callable] = None


# ── Registry ───────────────────────────────────────────────────────────────────

TECHNIQUES: List[MathTechnique] = [

    # ── CLASSICAL MECHANICS ────────────────────────────────────────────────────
    MathTechnique("kinematics", "Kinematics", "Classical Mechanics",
        "Lead stage velocity: how fast a lead moves through pipeline stages",
        "active", "lead_manifold"),
    MathTechnique("newtonian", "Newtonian Dynamics", "Classical Mechanics",
        "Force = mass × acceleration applied to engagement pressure",
        "partial", "kalman_engagement"),
    MathTechnique("momentum_conservation", "Momentum Conservation", "Classical Mechanics",
        "Outreach momentum: a sequence of touches builds and carries forward",
        "registered", "lead_manifold"),
    MathTechnique("impulse", "Impulse Mechanics", "Classical Mechanics",
        "Short-duration high-value messages: impulse = force × time",
        "registered", "quantum_ensemble"),
    MathTechnique("collision_dynamics", "Collision Dynamics", "Classical Mechanics",
        "What happens when two outreach touches 'collide' (too close together)",
        "registered", "quantum_ensemble"),
    MathTechnique("energy_transfer", "Energy Transfer Analysis", "Classical Mechanics",
        "Engagement energy transferred between outreach actions",
        "partial", "kalman_engagement"),
    MathTechnique("hamiltonian", "Hamiltonian Mechanics", "Classical Mechanics",
        "Total system energy (engagement + pipeline progress) conservation",
        "active", "hamilton_jacobi"),
    MathTechnique("lagrangian", "Lagrangian Mechanics", "Classical Mechanics",
        "Action minimisation: find the outreach path of least resistance",
        "active", "hamilton_jacobi"),

    # ── MOTION MODELING ────────────────────────────────────────────────────────
    MathTechnique("sde", "Stochastic Differential Equations", "Motion Modeling",
        "Model random drift in lead engagement over time",
        "partial", "kalman_engagement"),
    MathTechnique("brownian", "Brownian Motion", "Motion Modeling",
        "Random walk model for lead interest fluctuation",
        "partial", "kalman_engagement"),
    MathTechnique("kalman", "Kalman Filter", "Motion Modeling",
        "Optimal state estimation for engagement signal filtering",
        "active", "kalman_engagement"),
    MathTechnique("ekf", "Extended Kalman Filter", "Motion Modeling",
        "Nonlinear engagement dynamics (saturation near 0 and 1)",
        "active", "kalman_engagement"),
    MathTechnique("ukf", "Unscented Kalman Filter", "Motion Modeling",
        "Sigma-point propagation for better nonlinear estimates",
        "partial", "kalman_engagement"),
    MathTechnique("particle_filter", "Particle Filter", "Motion Modeling",
        "Multi-hypothesis engagement tracking via weighted particles",
        "registered", "multi_hypothesis"),

    # ── GEOMETRY ──────────────────────────────────────────────────────────────
    MathTechnique("riemannian", "Riemannian Manifolds", "Geometry",
        "Curved lead-behavior space where distance encodes conversion likelihood",
        "active", "lead_manifold"),
    MathTechnique("geodesic", "Geodesic Deviation", "Geometry",
        "How much a lead's path deviates from the natural conversion trajectory",
        "active", "lead_manifold"),
    MathTechnique("curvature", "Differential Trajectory Curvature", "Geometry",
        "Four curvature signals: funnel, behavioral, coupled, temporal",
        "active", "lead_manifold"),
    MathTechnique("manifold_distance", "Manifold Distance Metrics", "Geometry",
        "Riemannian distance between leads in behavioral space",
        "active", "lead_manifold"),

    # ── TOPOLOGY ──────────────────────────────────────────────────────────────
    MathTechnique("persistent_homology", "Persistent Homology", "Topology",
        "Structural conversion patterns that persist across different lead types",
        "partial", "pattern_tree"),
    MathTechnique("tda", "Topological Data Analysis", "Topology",
        "Shape of lead conversion patterns in behavioral space",
        "partial", "pattern_tree"),
    MathTechnique("betti", "Betti Numbers", "Topology",
        "Count connected components of lead behavioral clusters",
        "registered", "pattern_tree"),
    MathTechnique("persistence_diagrams", "Persistence Diagrams", "Topology",
        "Long-term stability of conversion pattern families",
        "partial", "pattern_tree"),

    # ── INFORMATION THEORY ────────────────────────────────────────────────────
    MathTechnique("fisher_info", "Fisher Information Metric", "Information Theory",
        "How informative is each new signal about conversion probability",
        "active", "bayesian_scorer"),
    MathTechnique("entropy", "Entropy Analysis", "Information Theory",
        "Lead state uncertainty — high entropy = highly uncertain intent",
        "active", "entropy_monitor"),
    MathTechnique("kl_divergence", "KL Divergence", "Information Theory",
        "Surprise score: how much lead behavior deviates from expected",
        "active", "entropy_monitor"),
    MathTechnique("surprise", "Surprise Scoring", "Information Theory",
        "Flag leads whose behavior is anomalously different from baseline",
        "active", "entropy_monitor"),

    # ── CONTROL THEORY ────────────────────────────────────────────────────────
    MathTechnique("mpc", "Model Predictive Control", "Control Theory",
        "Compute optimal outreach sequence for next N steps",
        "active", "hamilton_jacobi"),
    MathTechnique("rho", "Receding Horizon Optimisation", "Control Theory",
        "Re-plan the outreach sequence after each new event",
        "active", "hamilton_jacobi"),
    MathTechnique("cbf", "Control Barrier Functions", "Control Theory",
        "Safety guardrail: don't escalate if intent probability is below threshold",
        "active", "hamilton_jacobi"),
    MathTechnique("optimal_control", "Optimal Control Theory", "Control Theory",
        "Minimise outreach effort while maximising conversion probability",
        "active", "hamilton_jacobi"),

    # ── GRAPH THEORY ─────────────────────────────────────────────────────────
    MathTechnique("interaction_graph", "Interaction Graph Analysis", "Graph Theory",
        "Map relationships between leads, referrers, and groups",
        "registered", "causal_engine"),
    MathTechnique("centrality", "Graph Centrality", "Graph Theory",
        "Which leads are hubs — high-centrality = likely to refer others",
        "partial", "pattern_tree"),
    MathTechnique("relational_anomaly", "Relational Anomaly Detection", "Graph Theory",
        "Detect unusual interaction patterns in lead networks",
        "registered", "entropy_monitor"),

    # ── PROBABILITY ──────────────────────────────────────────────────────────
    MathTechnique("bayesian", "Bayesian Inference", "Probability",
        "Update conversion probability as new evidence arrives",
        "active", "bayesian_scorer"),
    MathTechnique("causal_inference", "Causal Inference (Do-Calculus)", "Probability",
        "Distinguish what causes conversions from what correlates with them",
        "active", "causal_engine"),
    MathTechnique("monte_carlo", "Monte Carlo Simulation", "Probability",
        "Simulate 1000 possible lead futures to estimate conversion probability",
        "active", "bayesian_scorer"),

    # ── OPTIMISATION ─────────────────────────────────────────────────────────
    MathTechnique("gradient_descent", "Gradient Descent", "Optimisation",
        "Tune outreach parameters (timing, message length) to maximise reply rate",
        "registered", "causal_engine"),
    MathTechnique("sparse_matrix", "Sparse Matrix Optimisation", "Optimisation",
        "Efficient computation over large lead × feature matrices",
        "registered", "lead_manifold"),

    # ── COMPUTATIONAL PHYSICS ─────────────────────────────────────────────────
    MathTechnique("hj", "Hamilton-Jacobi Field Modeling", "Computational Physics",
        "Pre-computed value field V(s) over entire funnel state space",
        "active", "hamilton_jacobi"),
    MathTechnique("tfo", "Trajectory Field Optimisation", "Computational Physics",
        "Optimal outreach trajectory that minimises expected touchpoints to close",
        "active", "hamilton_jacobi"),

    # ── ADVANCED MECHANICS ────────────────────────────────────────────────────
    MathTechnique("variational", "Variational Mechanics", "Advanced Mechanics",
        "Outreach path derived from minimising the action functional",
        "active", "hamilton_jacobi"),
    MathTechnique("pontryagin", "Pontryagin Maximum Principle", "Advanced Mechanics",
        "Optimal control characterisation: maximise conversion Hamiltonian",
        "active", "hamilton_jacobi"),
    MathTechnique("nonlinear_dynamics", "Nonlinear Dynamical Systems", "Advanced Mechanics",
        "Detect chaotic or unstable lead behavior trajectories",
        "partial", "lead_manifold"),
    MathTechnique("lyapunov", "Lyapunov Stability Analysis", "Advanced Mechanics",
        "Is this lead's trajectory converging to conversion or diverging?",
        "active", "lead_manifold"),
    MathTechnique("phase_space", "Phase Space Analysis", "Advanced Mechanics",
        "Lead in (engagement_level, engagement_velocity) phase space",
        "active", "kalman_engagement"),
    MathTechnique("lagrange_mult", "Lagrange Multiplier Optimisation", "Advanced Mechanics",
        "Constrained outreach: maximise conversion subject to daily DM limits",
        "registered", "hamilton_jacobi"),
    MathTechnique("energy_landscape", "Energy Landscape Modeling", "Advanced Mechanics",
        "Conversion funnel as an energy landscape with basins of attraction",
        "partial", "lead_manifold"),
    MathTechnique("contact_mechanics", "Contact Mechanics", "Advanced Mechanics",
        "Physical model of outreach 'contact events' and their force",
        "registered", "quantum_ensemble"),

    # ── SIGNAL PROCESSING ────────────────────────────────────────────────────
    MathTechnique("fourier", "Fourier Transform Analysis", "Signal Processing",
        "Detect periodic patterns in reply timing (e.g., leads who reply every Monday)",
        "registered", "kalman_engagement"),
    MathTechnique("wavelet", "Wavelet Transform Analysis", "Signal Processing",
        "Multi-scale engagement pattern detection across different time horizons",
        "registered", "kalman_engagement"),
    MathTechnique("spectral", "Spectral Motion Analysis", "Signal Processing",
        "Detect oscillatory engagement patterns (interest spikes)",
        "registered", "kalman_engagement"),

    # ── BEHAVIORAL MODELING ───────────────────────────────────────────────────
    MathTechnique("hmm", "Hidden Markov Models", "Behavioral Modeling",
        "Lead intent as hidden state transitions observed through events",
        "partial", "multi_hypothesis"),
    MathTechnique("switching_ds", "Switching Dynamical Systems", "Behavioral Modeling",
        "Multiple engagement modes (active / dormant / considering / converting)",
        "partial", "multi_hypothesis"),
    MathTechnique("dtw", "Dynamic Time Warping", "Behavioral Modeling",
        "Compare lead engagement sequences despite timing differences",
        "registered", "pattern_tree"),
    MathTechnique("ar_models", "Autoregressive Models", "Behavioral Modeling",
        "AR(2) forecast of future engagement from past signal history",
        "active", "kalman_engagement"),
    MathTechnique("state_space", "State Space Models", "Behavioral Modeling",
        "Unified state representation: [stage, engagement, intent, time]",
        "active", "kalman_engagement"),

    # ── ADVANCED GEOMETRY ────────────────────────────────────────────────────
    MathTechnique("projective_geom", "Projective Geometry", "Advanced Geometry",
        "Project lead features into lower-dimensional decision space",
        "registered", "lead_manifold"),
    MathTechnique("epipolar", "Epipolar Geometry", "Advanced Geometry",
        "Cross-platform lead triangulation (same person on IG and FB)",
        "registered", "pattern_tree"),
    MathTechnique("convex_geom", "Convex Geometry", "Advanced Geometry",
        "Convex hull of convertible lead region in feature space",
        "registered", "lead_manifold"),
    MathTechnique("voronoi", "Voronoi Diagrams", "Advanced Geometry",
        "Territory decomposition: which outreach approach 'owns' which lead region",
        "registered", "pattern_tree"),
    MathTechnique("delaunay", "Delaunay Triangulation", "Advanced Geometry",
        "Reconstruct the structural network between leads in manifold space",
        "registered", "pattern_tree"),

    # ── QUANTUM ENGINE ────────────────────────────────────────────────────────
    MathTechnique("superposition", "Quantum Superposition", "Quantum Engine",
        "Hold multiple outreach strategies simultaneously before committing",
        "active", "quantum_ensemble"),
    MathTechnique("path_integral", "Feynman Path Integral", "Quantum Engine",
        "Sum over all possible outreach histories weighted by action",
        "active", "quantum_ensemble"),
    MathTechnique("interference", "Quantum Interference", "Quantum Engine",
        "Correlated strategies reinforce; contradictory strategies cancel",
        "active", "quantum_ensemble"),
    MathTechnique("amplitude_amp", "Amplitude Amplification (Grover-inspired)", "Quantum Engine",
        "Iteratively boost high-conversion strategy weights",
        "active", "quantum_ensemble"),
    MathTechnique("decoherence", "Decoherence", "Quantum Engine",
        "Low-amplitude strategies decay and drop from the ensemble",
        "active", "quantum_ensemble"),
    MathTechnique("collapse", "Measurement / Collapse", "Quantum Engine",
        "Commit to the dominant strategy for execution",
        "active", "quantum_ensemble"),
    MathTechnique("entanglement", "Quantum Entanglement", "Quantum Engine",
        "Correlated strategies across leads in the same group/network",
        "active", "quantum_ensemble"),
    MathTechnique("tunneling", "Quantum Tunneling", "Quantum Engine",
        "Probability of sudden unexpected conversion jump",
        "active", "quantum_ensemble"),
    MathTechnique("phase_locking", "Phase / Phase-Locking", "Quantum Engine",
        "Detect coordinated buying signals from multiple leads in same network",
        "registered", "quantum_ensemble"),
    MathTechnique("branching_futures", "Branching Futures (Many-Worlds)", "Quantum Engine",
        "Maintain parallel future branches; prune as evidence arrives",
        "active", "quantum_ensemble"),

    # ── CRYPTOGRAPHIC LAYER ───────────────────────────────────────────────────
    MathTechnique("verkle_tree", "Verkle Trees", "Cryptographic",
        "Fast O(log n) fuzzy pattern matching for conversion signatures",
        "active", "pattern_tree"),
    MathTechnique("kzg", "KZG Polynomial Commitments", "Cryptographic",
        "Prove a lead pattern satisfies conversion criteria without revealing raw data",
        "registered", "pattern_tree"),
    MathTechnique("zk_snark", "ZK-SNARKs", "Cryptographic",
        "Compact proof that entire intelligence pipeline ran correctly",
        "registered", "pattern_tree"),
    MathTechnique("hash_chaining", "Cryptographic Hash Chaining", "Cryptographic",
        "Tamper-proof audit trail of all lead interactions",
        "registered", "sovereign_core"),
    MathTechnique("merkle_hash", "Merkle Pattern Hashing", "Cryptographic",
        "Hash behavioral patterns into a searchable tree structure",
        "partial", "pattern_tree"),
    MathTechnique("faiss_hnsw", "FAISS + HNSW Vector Search", "Cryptographic",
        "O(log n) similarity search across all historical lead patterns",
        "registered", "pattern_tree"),

    # ── ASI / CAUSAL CONCEPTS ─────────────────────────────────────────────────
    MathTechnique("causal_world_model", "Causal World Model", "ASI Concepts",
        "Maintain a posterior distribution over causal graphs of outreach",
        "active", "causal_engine"),
    MathTechnique("meta_causal", "Meta-Causal Reasoning", "ASI Concepts",
        "Watch which causal mechanisms are failing; structured self-distrust",
        "partial", "causal_engine"),
    MathTechnique("crl", "Causal Representation Learning (CRL)", "ASI Concepts",
        "Learn what causes conversions (mechanisms), not what correlates with them",
        "active", "causal_engine"),
    MathTechnique("irm", "Invariant Risk Minimization (IRM)", "ASI Concepts",
        "Identify outreach principles that work across ALL niches",
        "active", "causal_engine"),
    MathTechnique("counterfactual", "Counterfactual Simulation", "ASI Concepts",
        "What would have happened if we had sent X instead of Y?",
        "active", "causal_engine"),
    MathTechnique("surprise_max", "Causal Surprise Maximisation", "ASI Concepts",
        "Actively hunt for leads with high epistemic uncertainty",
        "active", "entropy_monitor"),
    MathTechnique("causal_abstraction", "Causal Abstraction Hierarchy", "ASI Concepts",
        "Three levels: signal → behavioral → market-level causal reasoning",
        "partial", "causal_engine"),
    MathTechnique("episodic_memory", "Episodic Memory with Causal Indexing", "ASI Concepts",
        "Store past leads indexed by causal signature, not timestamp",
        "registered", "sovereign_core"),
    MathTechnique("icm", "Independent Causal Mechanisms", "ASI Concepts",
        "Each causal mechanism is independent — partial environment shift patches only broken mechanisms",
        "partial", "causal_engine"),
    MathTechnique("sovereign_execution", "Sovereign Execution Layer", "ASI Concepts",
        "Jarvis operates autonomously without external dependencies",
        "active", "sovereign_core"),
    MathTechnique("ssv_gate", "Structural Sanity Verification (SSV) Gate", "ASI Concepts",
        "Hard gate: only act on evidence that passes structural coherence checks",
        "active", "causal_engine"),

    # ── SPEED ENGINES ────────────────────────────────────────────────────────
    MathTechnique("event_gating", "Event Gating Engine", "Speed Engines",
        "Ignore irrelevant events to reduce computation",
        "partial", "entropy_monitor"),
    MathTechnique("spatial_hash", "Spatial Hash Grid", "Speed Engines",
        "Fast lookup of leads by manifold region",
        "registered", "lead_manifold"),
    MathTechnique("temporal_cache", "Temporal Coherence Cache", "Speed Engines",
        "Reuse previous computation when state hasn't changed significantly",
        "registered", "sovereign_core"),
    MathTechnique("ring_buffer", "Ring Buffer Memory", "Speed Engines",
        "Efficient fixed-size history window for trajectory computation",
        "active", "kalman_engagement"),
    MathTechnique("kd_tree", "KD-Tree Spatial Indexing", "Speed Engines",
        "O(log n) nearest-neighbor queries in lead manifold space",
        "registered", "lead_manifold"),
    MathTechnique("octree", "Octree Spatial Partitioning", "Speed Engines",
        "Hierarchical spatial decomposition of lead feature space",
        "registered", "pattern_tree"),
    MathTechnique("parallel_sched", "Parallel Task Scheduling", "Speed Engines",
        "Concurrent outreach processing across multiple leads",
        "registered", "sovereign_core"),
    MathTechnique("sparse_matrix_speed", "Sparse Matrix Computation", "Speed Engines",
        "Efficient operations on sparse lead × feature matrices",
        "registered", "lead_manifold"),
    MathTechnique("incremental_topo", "Incremental Topology Updates", "Speed Engines",
        "Update pattern tree incrementally instead of full recomputation",
        "registered", "pattern_tree"),
    MathTechnique("bvh", "Bounding Volume Hierarchies (BVH)", "Speed Engines",
        "Fast pruning of strategy space by bounding expected conversion value",
        "partial", "pattern_tree"),
    MathTechnique("ann_search", "Approximate Nearest Neighbor Search", "Speed Engines",
        "Fast similarity search with bounded approximation error",
        "registered", "pattern_tree"),
    MathTechnique("low_rank", "Low-Rank Matrix Approximation", "Speed Engines",
        "Compress large lead × feature correlation matrices",
        "registered", "lead_manifold"),
    MathTechnique("incremental_svd", "Incremental SVD Updates", "Speed Engines",
        "Fast decomposition updates as new leads are added",
        "registered", "lead_manifold"),
    MathTechnique("simd", "SIMD Vectorization", "Speed Engines",
        "CPU vector acceleration for manifold distance computations",
        "registered", "lead_manifold"),
    MathTechnique("gpu_pipeline", "GPU Stream Processing", "Speed Engines",
        "Parallel computation for large ensemble processing",
        "registered", "quantum_ensemble"),
]


class MathToolkitRegistry:
    """Central registry for all 110 mathematical techniques."""

    def __init__(self):
        self._registry: Dict[str, MathTechnique] = {t.id: t for t in TECHNIQUES}

    def get(self, technique_id: str) -> Optional[MathTechnique]:
        return self._registry.get(technique_id)

    def by_domain(self, domain: str) -> List[MathTechnique]:
        return [t for t in self._registry.values() if t.domain == domain]

    def active_techniques(self) -> List[MathTechnique]:
        return [t for t in self._registry.values() if t.status == "active"]

    def by_module(self, module: str) -> List[MathTechnique]:
        return [t for t in self._registry.values() if t.module == module]

    def summary(self) -> dict:
        all_t = list(self._registry.values())
        return {
            "total":      len(all_t),
            "active":     sum(1 for t in all_t if t.status == "active"),
            "partial":    sum(1 for t in all_t if t.status == "partial"),
            "registered": sum(1 for t in all_t if t.status == "registered"),
            "domains":    list({t.domain for t in all_t}),
        }

    def print_summary(self):
        s = self.summary()
        print(f"\n{'='*60}")
        print(f"  Virel Intelligence Engine — Math Toolkit Registry")
        print(f"{'='*60}")
        print(f"  Total techniques: {s['total']}")
        print(f"  Active (implemented): {s['active']}")
        print(f"  Partial:             {s['partial']}")
        print(f"  Registered (planned):{s['registered']}")
        print(f"\n  Domains covered:")
        for d in sorted(s['domains']):
            count = len(self.by_domain(d))
            active = sum(1 for t in self.by_domain(d) if t.status == "active")
            print(f"    {d:35s} {active}/{count} active")
        print(f"{'='*60}\n")


# Singleton registry
registry = MathToolkitRegistry()
