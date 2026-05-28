"""
LQR (Linear Quadratic Regulator) autopilot for 2D rocket landing.

Theory
------
We linearise the dynamics around the hover equilibrium:

    state_eq   = [x_eq, y_eq, 0, 0, 0, 0]   (zero velocities, upright)
    control_eq = [m·g, 0]                     (thrust cancels gravity, no gimbal)

Deviation state:   δz = [δx, δy, δvx, δvy, δθ, δω]
Deviation control: δu = [δT, δγ]

Continuous-time linear system:  δż = A δz + B δu

    A = [[0, 0, 1, 0,  0, 0],
         [0, 0, 0, 1,  0, 0],
         [0, 0, 0, 0, -g, 0],
         [0, 0, 0, 0,  0, 0],
         [0, 0, 0, 0,  0, 1],
         [0, 0, 0, 0,  0, 0]]

    B = [[0,       0         ],
         [0,       0         ],
         [0,      -g         ],
         [1/m,     0         ],
         [0,       0         ],
         [0,  -L·T_eq / I    ]]

where L = nozzle_arm, T_eq = m·g, I = m·L²/12.

We solve the continuous-time algebraic Riccati equation (CARE):

    A^T P + P A - P B R^{-1} B^T P + Q = 0

and compute: K = R^{-1} B^T P
Control law: δu = -K δz  →  T = T_eq - K[0,:]·δz,  γ = -K[1,:]·δz

Usage
-----
    lqr = LQRController(params, hover_mass=500.0)
    output = lqr.update(state, target_x=0.0, target_y=100.0)
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.linalg import solve_continuous_are

from .controller import ControllerOutput
from .rocket import GRAVITY, RocketParams
from .state import State


@dataclass
class LQRWeights:
    """
    Diagonal Q (state cost) and R (control cost) matrices.

    Penalises deviations of [δx, δy, δvx, δvy, δθ, δω] and control [δT, δγ].

    Bryson's rule:
        Q[i,i] = 1 / (acceptable_deviation_i)²
        R[j,j] = 1 / (max_control_j)²
    """

    q_x: float = 1.0        # position x       [1/m²]
    q_y: float = 10.0       # position y        [1/m²]   — landing precision critical
    q_vx: float = 1.0       # horizontal speed  [1/(m/s)²]
    q_vy: float = 5.0       # vertical speed    [1/(m/s)²]
    q_theta: float = 50.0   # attitude          [1/rad²]
    q_omega: float = 10.0   # angular velocity  [1/(rad/s)²]
    r_thrust: float = 1e-7  # thrust effort     (small → large thrust allowed)
    r_gimbal: float = 1.0   # gimbal effort

    def Q(self) -> np.ndarray:  # noqa: N802
        return np.diag([
            self.q_x, self.q_y, self.q_vx, self.q_vy, self.q_theta, self.q_omega,
        ])

    def R(self) -> np.ndarray:  # noqa: N802
        return np.diag([self.r_thrust, self.r_gimbal])


def _build_AB(
    params: RocketParams,
    hover_mass: float,
) -> tuple[np.ndarray, np.ndarray]:
    """Return (A, B) of the linearised hover dynamics."""
    g = GRAVITY
    m = hover_mass
    L = params.nozzle_arm
    I = m * params.body_length**2 / 12.0
    T_eq = m * g

    A = np.array([
        [0, 0, 1, 0,  0, 0],
        [0, 0, 0, 1,  0, 0],
        [0, 0, 0, 0, -g, 0],
        [0, 0, 0, 0,  0, 0],
        [0, 0, 0, 0,  0, 1],
        [0, 0, 0, 0,  0, 0],
    ], dtype=float)

    B = np.array([
        [0,          0            ],
        [0,          0            ],
        [0,         -g            ],
        [1.0 / m,    0            ],
        [0,          0            ],
        [0,         -L * T_eq / I ],
    ], dtype=float)

    return A, B


def solve_lqr(
    params: RocketParams,
    hover_mass: float,
    weights: LQRWeights | None = None,
) -> np.ndarray:
    """
    Solve the CARE and return the 2×6 gain matrix K.

    Parameters
    ----------
    params      : rocket physical parameters
    hover_mass  : linearisation mass [kg]
    weights     : Q and R cost matrices

    Returns
    -------
    K : np.ndarray, shape (2, 6)  —  δu = -K @ δz
    """
    if weights is None:
        weights = LQRWeights()

    A, B = _build_AB(params, hover_mass)
    Q = weights.Q()
    R = weights.R()

    P = solve_continuous_are(A, B, Q, R)
    K = np.linalg.solve(R, B.T @ P)  # K = R^{-1} B^T P
    return K


class LQRController:
    """
    LQR autopilot with mass-scheduled gain recomputation.

    Re-solves the CARE whenever mass drifts more than `recompute_threshold` kg
    from the last linearisation point, handling the time-varying mass.
    """

    def __init__(
        self,
        params: RocketParams,
        hover_mass: float,
        weights: LQRWeights | None = None,
        max_thrust: float = 30_000.0,
        max_gimbal: float = 0.3,
        recompute_threshold: float = 10.0,
    ) -> None:
        self.params = params
        self.weights = weights or LQRWeights()
        self.max_thrust = max_thrust
        self.max_gimbal = max_gimbal
        self.recompute_threshold = recompute_threshold

        self._hover_mass = hover_mass
        self.K = solve_lqr(params, hover_mass, self.weights)

    def _maybe_recompute(self, current_mass: float) -> None:
        """Re-solve CARE if mass has drifted significantly."""
        if abs(current_mass - self._hover_mass) > self.recompute_threshold:
            self._hover_mass = current_mass
            self.K = solve_lqr(self.params, current_mass, self.weights)

    def update(
        self,
        state: State,
        target_x: float = 0.0,
        target_y: float = 0.0,
    ) -> ControllerOutput:
        """
        Compute thrust and gimbal commands.

        Parameters
        ----------
        state    : current rocket state
        target_x : landing pad x [m]
        target_y : landing pad y [m]
        """
        self._maybe_recompute(state.m)

        dz = np.array([
            state.x   - target_x,
            state.y   - target_y,
            state.vx,
            state.vy,
            state.theta,
            state.omega,
        ])

        T_eq = state.m * GRAVITY
        du = -self.K @ dz  # [δT, δγ]

        thrust = float(np.clip(T_eq + du[0], 0.0, self.max_thrust))
        gimbal = float(np.clip(du[1], -self.max_gimbal, self.max_gimbal))
        return ControllerOutput(thrust=thrust, gimbal=gimbal)
