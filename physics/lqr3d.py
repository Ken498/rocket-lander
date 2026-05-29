"""
3D LQR autopilot for 6-DOF rocket landing (Phase 2 — Week 5).

Theory
------
We linearise the 6-DOF dynamics around the hover equilibrium:

    pos_eq  = [x_tgt, y_tgt, z_tgt]
    vel_eq  = [0, 0, 0]
    att_eq  = [1, 0, 0, 0]   (upright, q = identity)
    ω_eq    = [0, 0, 0]
    T_eq    = m · g

Yaw note
--------
A gimballed rocket with a single nozzle cannot generate a yaw torque around
its symmetry axis (+y body).  Yaw angle ψ and spin rate ωy are therefore
uncontrollable and are excluded from the LQR state.

10-element deviation state (small-angle, hovering reference):

    δz = [δx, δy, δz,       (indices 0-2)  position
          δvx, δvy, δvz,     (indices 3-5)  velocity
          δφ, δθ,            (indices 6-7)  controlled tilt angles
          δωx, δωz]          (indices 8-9)  controlled angular rates

3-element deviation control:

    δu = [δT, δγ_pitch, δγ_yaw]   (indices 0-2)

Small-angle attitude extraction (quaternion scalar-first, upright = [1,0,0,0]):

    δφ ≈ 2·q1   (tilt around world x → thrust has +z component)
    δθ ≈ 2·q3   (tilt around world z → thrust has -x component)
    (ψ ≈ 2·q2 — yaw, excluded)

Continuous-time linear system  δż = A·δz + B·δu
-------------------------------------------------

A (10×10) — non-zero entries:
    A[0,3]=1, A[1,4]=1, A[2,5]=1   position kinematics
    A[3,7]=-g                        θ-tilt → x-acceleration
    A[5,6]=g                         φ-tilt → z-acceleration
    A[6,8]=1                         φ̇ = ωx
    A[7,9]=1                         θ̇ = ωz

B (10×3) — non-zero entries:
    B[4,0]= 1/m                      thrust → vertical acceleration
    B[3,2]= g                        γ_yaw   → x-acceleration (F_body x = T·γy)
    B[5,1]= g                        γ_pitch → z-acceleration (F_body z = T·γp)
    B[8,1]=-T_eq·L/I_t              γ_pitch → α_x (pitch torque)
    B[9,2]= T_eq·L/I_t              γ_yaw   → α_z (yaw torque)

where I_t = m·ℓ²/12 is the transverse moment of inertia.

Control law
-----------
    δu = −K · δz    (K is 3×10 from CARE: A^T P + PA − PBR⁻¹B^T P + Q = 0)
    T      = m·g + δT       (clamped to [0, max_thrust])
    γ_p    = δγ_pitch        (clamped to ±max_gimbal)
    γ_y    = δγ_yaw          (clamped to ±max_gimbal)

Usage
-----
    lqr = LQRController3D(params, hover_mass=500.0)
    cmd = lqr.update(state, target_x=0.0, target_y=100.0, target_z=0.0)
    # cmd is a ControlInput3D(thrust, gimbal_pitch, gimbal_yaw)
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.linalg import solve_continuous_are

from .rocket3d import GRAVITY, ControlInput3D, RocketParams3D
from .state3d import State3D


@dataclass
class LQRWeights3D:
    """
    Diagonal Q (state cost) and R (control cost) for the 10-state 3D LQR.

    State order: [δx, δy, δz, δvx, δvy, δvz, δφ, δθ, δωx, δωz]
    Control order: [δT, δγ_pitch, δγ_yaw]

    Bryson's rule:
        Q[i,i] = 1 / (acceptable_deviation_i)²
        R[j,j] = 1 / (max_control_j)²
    """

    # Position errors
    q_x: float = 1.0          # x  [1/m²]
    q_y: float = 10.0         # y  [1/m²]   — altitude more critical
    q_z: float = 1.0          # z  [1/m²]

    # Velocity errors
    q_vx: float = 1.0         # vx [1/(m/s)²]
    q_vy: float = 5.0         # vy [1/(m/s)²]  — vertical speed more critical
    q_vz: float = 1.0         # vz [1/(m/s)²]

    # Attitude (tilt angles, rad)
    q_phi: float   = 50.0     # φ (tilt around x)  [1/rad²]
    q_theta: float = 50.0     # θ (tilt around z)  [1/rad²]

    # Angular rates (rad/s)
    q_omx: float = 10.0       # ωx  [1/(rad/s)²]
    q_omz: float = 10.0       # ωz  [1/(rad/s)²]

    # Control effort
    r_thrust: float = 0.01    # δT  — tuned for K[0,4]≈450 (strong braking) while K[0,1]≈32 (>300 m headroom)
    r_gimbal_pitch: float = 1.0
    r_gimbal_yaw: float = 1.0

    def Q(self) -> np.ndarray:  # noqa: N802
        """10×10 diagonal state cost matrix."""
        return np.diag([
            self.q_x, self.q_y, self.q_z,
            self.q_vx, self.q_vy, self.q_vz,
            self.q_phi, self.q_theta,
            self.q_omx, self.q_omz,
        ])

    def R(self) -> np.ndarray:  # noqa: N802
        """3×3 diagonal control cost matrix."""
        return np.diag([self.r_thrust, self.r_gimbal_pitch, self.r_gimbal_yaw])


def _build_AB3d(
    params: RocketParams3D,
    hover_mass: float,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Return (A, B) of the 10-state linearised hover dynamics.

    State: [δx, δy, δz, δvx, δvy, δvz, δφ, δθ, δωx, δωz]
    Control: [δT, δγ_pitch, δγ_yaw]
    """
    g = GRAVITY
    m = hover_mass
    L = params.nozzle_arm
    I_t = m * params.body_length**2 / 12.0   # transverse moment of inertia
    T_eq = m * g

    A = np.zeros((10, 10))

    # Position kinematics
    A[0, 3] = 1.0    # ẋ  = vx
    A[1, 4] = 1.0    # ẏ  = vy
    A[2, 5] = 1.0    # ż  = vz

    # Gravity-coupling through tilt
    A[3, 7] = -g     # v̇x ≈ -g·δθ  (θ-tilt tilts thrust in -x)
    A[5, 6] =  g     # v̇z ≈ +g·δφ  (φ-tilt tilts thrust in +z)

    # Attitude kinematics
    A[6, 8] = 1.0    # δφ̇ = δωx
    A[7, 9] = 1.0    # δθ̇ = δωz

    B = np.zeros((10, 3))

    # Thrust → vertical acceleration
    B[4, 0] = 1.0 / m

    # Gimbal → translational force (small-angle, upright rocket)
    # Convention: positive gimbal → negative horizontal force (matches 2D)
    # F_body = T·[-γy, 1, -γp] → F_world ≈ T·[-γy, 1, -γp] when upright
    B[3, 2] = -g         # γ_yaw   → ẍ = -g·γy
    B[5, 1] = -g         # γ_pitch → z̈ = -g·γp

    # Gimbal → angular acceleration via torque
    # τ = T·[L·γp, 0, -L·γy]  (from cross product with new F_body)
    # α_x = τ_x / I_t = T_eq·L·γ_pitch / I_t
    B[8, 1] = T_eq * L / I_t
    # α_z = τ_z / I_t = -T_eq·L·γ_yaw / I_t
    B[9, 2] = -T_eq * L / I_t

    return A, B


def solve_lqr3d(
    params: RocketParams3D,
    hover_mass: float,
    weights: LQRWeights3D | None = None,
) -> np.ndarray:
    """
    Solve the CARE and return the 3×10 gain matrix K.

    Parameters
    ----------
    params      : rocket physical parameters
    hover_mass  : linearisation mass [kg]
    weights     : Q and R cost matrices (uses defaults if None)

    Returns
    -------
    K : np.ndarray, shape (3, 10)  —  δu = -K @ δz
    """
    if weights is None:
        weights = LQRWeights3D()

    A, B = _build_AB3d(params, hover_mass)
    Q = weights.Q()
    R = weights.R()

    P = solve_continuous_are(A, B, Q, R)
    K = np.linalg.solve(R, B.T @ P)   # K = R⁻¹ B^T P   (3×10)
    return K


class LQRController3D:
    """
    3D LQR autopilot with mass-scheduled gain recomputation.

    Re-solves the CARE whenever mass drifts more than `recompute_threshold` kg
    from the last linearisation point, keeping K accurate as propellant burns.

    Usage
    -----
        params = RocketParams3D()
        lqr    = LQRController3D(params, hover_mass=1000.0)

        cmd = lqr.update(state, target_x=0.0, target_y=0.0, target_z=0.0)
        # cmd is a ControlInput3D(thrust, gimbal_pitch, gimbal_yaw)
    """

    def __init__(
        self,
        params: RocketParams3D,
        hover_mass: float,
        weights: LQRWeights3D | None = None,
        max_thrust: float = 50_000.0,
        max_gimbal: float = 0.3,            # rad
        recompute_threshold: float = 10.0,  # kg
    ) -> None:
        self.params = params
        self.weights = weights or LQRWeights3D()
        self.max_thrust = max_thrust
        self.max_gimbal = max_gimbal
        self.recompute_threshold = recompute_threshold

        self._hover_mass = hover_mass
        self.K = solve_lqr3d(params, hover_mass, self.weights)

    def _maybe_recompute(self, current_mass: float) -> None:
        """Re-solve CARE if mass has drifted significantly from linearisation point."""
        if abs(current_mass - self._hover_mass) > self.recompute_threshold:
            self._hover_mass = current_mass
            self.K = solve_lqr3d(self.params, current_mass, self.weights)

    def update(
        self,
        state: State3D,
        target_x: float = 0.0,
        target_y: float = 0.0,
        target_z: float = 0.0,
        target_vx: float = 0.0,
        target_vy: float = 0.0,
        target_vz: float = 0.0,
    ) -> ControlInput3D:
        """
        Compute thrust and gimbal commands for one timestep.

        Parameters
        ----------
        state     : current 6-DOF rocket state
        target_x  : reference position x [m]
        target_y  : reference altitude  y [m]  (set to state.y to use velocity-only control)
        target_z  : reference position z [m]
        target_vx : reference velocity vx [m/s]  (feedforward for trajectory tracking)
        target_vy : reference velocity vy [m/s]  (use negative value for controlled descent)
        target_vz : reference velocity vz [m/s]

        Returns
        -------
        ControlInput3D with thrust [N], gimbal_pitch [rad], gimbal_yaw [rad].

        Trajectory tracking
        -------------------
        For a full landing from altitude, pass a reference trajectory rather than
        the static landing-pad position.  The LQR is linearised around hover and is
        valid only for small deviations; tracking a smooth reference keeps errors small:

            x_ref(t)  = x0 · exp(-λ·t)     # horizontal approach
            vy_ref(t) = -clip(k·y, v_min, v_max)  # velocity descent profile

        Example::

            x_ref = x0 * np.exp(-0.03 * t)
            vy_ref = -np.clip(0.25 * state.y, 0.2, 5.0)
            cmd = lqr.update(state,
                             target_x=x_ref, target_y=state.y, target_z=z_ref,
                             target_vx=-0.03*x_ref, target_vy=vy_ref, target_vz=-0.03*z_ref)
        """
        self._maybe_recompute(state.m)

        # Extract small-angle tilt angles from quaternion (yaw excluded)
        d_phi   = 2.0 * state.q1   # tilt around world x
        d_theta = 2.0 * state.q3   # tilt around world z

        # 10-element deviation state (ψ and ωy are excluded)
        dz = np.array([
            state.x  - target_x,
            state.y  - target_y,
            state.z  - target_z,
            state.vx - target_vx,
            state.vy - target_vy,
            state.vz - target_vz,
            d_phi,
            d_theta,
            state.omega_x,
            state.omega_z,
        ])

        T_eq = state.m * GRAVITY
        du = -self.K @ dz   # [δT, δγ_pitch, δγ_yaw]

        thrust       = float(np.clip(T_eq + du[0], 0.0, self.max_thrust))
        gimbal_pitch = float(np.clip(du[1], -self.max_gimbal, self.max_gimbal))
        gimbal_yaw   = float(np.clip(du[2], -self.max_gimbal, self.max_gimbal))

        return ControlInput3D(
            thrust=thrust,
            gimbal_pitch=gimbal_pitch,
            gimbal_yaw=gimbal_yaw,
        )
