"""
Model Predictive Control (MPC) autopilot — Phase 3 scaffold.

Theory
------
At each timestep we solve a finite-horizon optimal control problem:

    minimise    Σ_{k=0}^{N-1} [ z_k^T Q z_k + u_k^T R u_k ] + z_N^T P_f z_N
    subject to  z_{k+1} = A_d z_k + B_d u_k      (discrete linear dynamics)
                0 ≤ T_eq + δT_k ≤ T_max            (thrust limits)
                |γ_k| ≤ γ_max                       (gimbal limits)
                y_k ≥ 0                             (no-fly-below-ground)

where z_k = [δx, δy, δvx, δvy, δθ, δω],  u_k = [δT, δγ].

A_d, B_d = ZOH discretisation of the hover-linearised (A, B) from lqr.py.
P_f      = LQR terminal cost matrix (ensures stability at horizon end).

Only u_0 is applied; problem re-solved next step (receding horizon principle).

Week 7 TODO list
-----------------
1. Tune horizon N — start with N=20 at dt=0.1 s (2 s lookahead).
2. Complete ground constraint: target_y + δy_k ≥ 0 for all k.
3. Add slack variables for soft constraints (robustness near limits).
4. Set OSQP time_limit = 0.030 s (30 ms budget at 30 Hz).
5. Profile: if too slow, reduce N or switch to C-compiled OSQP.

References
----------
- Borrelli, Bemporad, Morari — Predictive Control for Linear and Hybrid Systems
- CVXPY MPC tutorial: https://www.cvxpy.org/examples/basic/mpc.html
- OSQP docs: https://osqp.org/docs/
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .controller import ControllerOutput
from .lqr import LQRController, LQRWeights, _build_AB
from .rocket import GRAVITY, RocketParams
from .state import State

try:
    import cvxpy as cp
    _CVXPY_AVAILABLE = True
except ImportError:
    _CVXPY_AVAILABLE = False


@dataclass
class MPCParams:
    """Tunable MPC parameters."""
    horizon: int = 20               # prediction steps N
    dt: float = 1.0 / 10.0         # MPC update timestep [s]
    max_thrust: float = 30_000.0   # N
    max_gimbal: float = 0.3        # rad (~17°)
    solver_time_limit: float = 0.030  # 30 ms per solve at 30 Hz


class MPCController:
    """
    MPC controller for 2D rocket landing.

    Falls back to LQR if CVXPY is unavailable or if the QP solver
    exceeds its time budget or returns infeasible.

    Usage
    -----
        mpc = MPCController(rocket_params, hover_mass=500.0)
        output = mpc.update(state, target_x=0.0, target_y=0.0)
    """

    def __init__(
        self,
        rocket_params: RocketParams,
        hover_mass: float,
        mpc_params: MPCParams | None = None,
        lqr_weights: LQRWeights | None = None,
    ) -> None:
        self.rocket_params = rocket_params
        self.mpc_params = mpc_params or MPCParams()
        self.lqr_weights = lqr_weights or LQRWeights()
        self._hover_mass = hover_mass

        # Continuous-time linear system at hover
        self.A, self.B = _build_AB(rocket_params, hover_mass)

        # Terminal cost P_f: solution to the CARE (LQR cost-to-go)
        from scipy.linalg import solve_continuous_are
        Q = self.lqr_weights.Q()
        R = self.lqr_weights.R()
        self.P_terminal = solve_continuous_are(self.A, self.B, Q, R)

        # LQR fallback for solver failures
        self._lqr = LQRController(rocket_params, hover_mass, lqr_weights)

        # CVXPY problem (built once, warm-started each step)
        self._problem: object = None
        self._z0_param: object = None
        self._u_var: object = None
        self._z_var: object = None

        if _CVXPY_AVAILABLE:
            self._build_problem()

    # ------------------------------------------------------------------
    # Problem construction
    # ------------------------------------------------------------------

    def _discretise(self) -> tuple[np.ndarray, np.ndarray]:
        """Zero-order hold (ZOH) discretisation of (A, B) at mpc_params.dt."""
        from scipy.linalg import expm
        dt = self.mpc_params.dt
        n, m = self.A.shape[0], self.B.shape[1]
        M = np.zeros((n + m, n + m))
        M[:n, :n] = self.A
        M[:n, n:] = self.B
        M_exp = expm(M * dt)
        return M_exp[:n, :n], M_exp[:n, n:]

    def _build_problem(self) -> None:
        """Pre-build CVXPY problem for warm-starting at runtime."""
        if not _CVXPY_AVAILABLE:
            return

        import cvxpy as cp

        N = self.mpc_params.horizon
        n_s, n_c = 6, 2
        A_d, B_d = self._discretise()
        Q = self.lqr_weights.Q()
        R = self.lqr_weights.R()
        T_eq = self._hover_mass * GRAVITY

        z = cp.Variable((n_s, N + 1))
        u = cp.Variable((n_c, N))
        z0 = cp.Parameter(n_s)

        # Running + terminal cost
        cost = (
            sum(cp.quad_form(z[:, k], Q) + cp.quad_form(u[:, k], R) for k in range(N))
            + cp.quad_form(z[:, N], self.P_terminal)
        )

        constraints = [z[:, 0] == z0]
        for k in range(N):
            constraints += [
                z[:, k + 1] == A_d @ z[:, k] + B_d @ u[:, k],
                # Thrust: 0 ≤ T_eq + δT ≤ T_max
                u[0, k] >= -T_eq,
                u[0, k] <= self.mpc_params.max_thrust - T_eq,
                # Gimbal limits
                cp.abs(u[1, k]) <= self.mpc_params.max_gimbal,
                # TODO (Week 7): ground constraint — z[1,k] + target_y >= 0
                # TODO (Week 7): slack variables for soft constraints
            ]

        self._problem = cp.Problem(cp.Minimize(cost), constraints)
        self._z0_param = z0
        self._u_var = u
        self._z_var = z

    # ------------------------------------------------------------------
    # Runtime
    # ------------------------------------------------------------------

    def update(
        self,
        state: State,
        target_x: float = 0.0,
        target_y: float = 0.0,
    ) -> ControllerOutput:
        """
        Solve the MPC QP and apply the first control action.
        Falls back to LQR on any solver failure.
        """
        if not _CVXPY_AVAILABLE or self._problem is None:
            return self._lqr.update(state, target_x=target_x, target_y=target_y)

        import cvxpy as cp

        dz = np.array([
            state.x - target_x,
            state.y - target_y,
            state.vx,
            state.vy,
            state.theta,
            state.omega,
        ])
        self._z0_param.value = dz

        try:
            self._problem.solve(
                solver=cp.OSQP,
                warm_start=True,
                max_iter=4000,
                time_limit=self.mpc_params.solver_time_limit,
                verbose=False,
            )
            if self._problem.status not in ("optimal", "optimal_inaccurate"):
                raise RuntimeError(f"OSQP status: {self._problem.status}")

            u0 = self._u_var.value[:, 0]
            T_eq = state.m * GRAVITY
            thrust = float(np.clip(T_eq + u0[0], 0.0, self.mpc_params.max_thrust))
            gimbal = float(np.clip(u0[1], -self.mpc_params.max_gimbal, self.mpc_params.max_gimbal))
            return ControllerOutput(thrust=thrust, gimbal=gimbal)

        except Exception:
            # Silent fallback to LQR
            return self._lqr.update(state, target_x=target_x, target_y=target_y)

    def predicted_trajectory(self) -> np.ndarray | None:
        """
        Return the MPC predicted state trajectory for visualisation.

        Returns shape (N+1, 6), or None if last solve failed.
        Columns: [δx, δy, δvx, δvy, δθ, δω]
        """
        if self._z_var is None or self._z_var.value is None:
            return None
        return self._z_var.value.T  # (N+1, 6)
