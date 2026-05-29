"""
6-DOF Rocket dynamics with RK4 integrator (Phase 2 — Week 4).

See docs/dynamics.md §3 (EOM) and §7 (3D extensions) for the derivations.

Coordinate conventions
----------------------
World frame (inertial, right-hand):
  +x  East  (or any fixed horizontal)
  +y  Up    (against gravity; ground = y = 0)
  +z  South

Body frame (attached to rocket, right-hand):
  +y_body  Rocket symmetry axis (points "up" when upright)
  Nozzle located at  r_nozzle = [0, -L, 0]_body
  where L = nozzle_arm (CoM to nozzle distance)

Attitude quaternion
-------------------
q = [q0, q1, q2, q3]  scalar-first, |q| = 1
q = [1, 0, 0, 0]  →  identity (body frame = world frame, rocket upright)
Rotation body → world:  v_world = R(q) · v_body

Quaternion kinematics:
  q̇ = ½ · q ⊗ [0, ω_body]

Gimbal model  (small-angle, max gimbal ≈ 0.3 rad → < 1.5 % linearisation error)
---------------------------------------------------------------------------
Two deflection angles in body frame:
  γ_pitch:  nozzle deflects in the y-z body plane
  γ_yaw:    nozzle deflects in the x-y body plane

Thrust direction in body frame:  F_body = T · [γ_yaw,  1,  γ_pitch]
Torque about CoM in body frame:
  τ = r_nozzle × F_body = [0, -L, 0] × T·[γy, 1, γp]
    = T · [−L·γ_pitch,  0,  L·γ_yaw]

Inertia tensor  (diagonal, body frame, uniform-cylinder model)
--------------------------------------------------------------
  Ix = Iz = m · ℓ² / 12      (transverse — thin-rod approximation)
  Iy = ½ · m · r²             (axial     — solid-cylinder)
  where ℓ = body_length, r = body_radius

Equations of motion
-------------------
Translation (world frame):
  a = R · F_body / m  +  [0, -g, 0]

Rotation (body frame — Euler's equations):
  I · ω̇ = τ − ω × (I · ω)

Mass depletion (Tsiolkovsky):
  ṁ = −T / (Isp · g₀)     when m > m_dry, else 0
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .state3d import State3D

GRAVITY: float = 9.81   # m/s²
G0: float = 9.81        # standard gravity for Isp → mass-flow conversion [m/s²]


# ══════════════════════════════════════════════════════════════════════ #
# Data classes                                                           #
# ══════════════════════════════════════════════════════════════════════ #

@dataclass
class RocketParams3D:
    """Physical constants that define the 3D rocket."""
    dry_mass: float = 100.0      # kg — mass when propellant is exhausted
    body_length: float = 20.0    # m  — used for transverse moment of inertia
    body_radius: float = 1.0     # m  — used for axial moment of inertia
    nozzle_arm: float = 10.0     # m  — CoM to nozzle distance
    isp: float = 300.0           # s  — specific impulse


@dataclass
class ControlInput3D:
    """
    Control commands for one timestep.

    thrust       : engine thrust magnitude [N]
    gimbal_pitch : nozzle deflection in pitch (y-z body plane) [rad]
    gimbal_yaw   : nozzle deflection in yaw   (x-y body plane) [rad]
    """
    thrust: float = 0.0
    gimbal_pitch: float = 0.0
    gimbal_yaw: float = 0.0


# ══════════════════════════════════════════════════════════════════════ #
# Quaternion helpers                                                     #
# ══════════════════════════════════════════════════════════════════════ #

def _quat_to_rot(q: np.ndarray) -> np.ndarray:
    """
    3×3 rotation matrix R that maps body → world for unit quaternion q.

    v_world = R @ v_body

    Input q = [q0, q1, q2, q3] (scalar first).  The array is normalised
    internally so minor drift during integration does not corrupt R.
    """
    q = q / np.linalg.norm(q)   # guard against accumulated drift
    q0, q1, q2, q3 = q
    return np.array([
        [1 - 2*(q2**2 + q3**2),   2*(q1*q2 - q0*q3),   2*(q1*q3 + q0*q2)],
        [  2*(q1*q2 + q0*q3), 1 - 2*(q1**2 + q3**2),   2*(q2*q3 - q0*q1)],
        [  2*(q1*q3 - q0*q2),   2*(q2*q3 + q0*q1), 1 - 2*(q1**2 + q2**2)],
    ])


# ══════════════════════════════════════════════════════════════════════ #
# Equations of motion                                                    #
# ══════════════════════════════════════════════════════════════════════ #

def _derivatives3d(
    s: np.ndarray,
    params: RocketParams3D,
    thrust: float,
    gimbal_pitch: float,
    gimbal_yaw: float,
) -> np.ndarray:
    """
    Time derivative ṡ of the 14-element state vector.

    Parameters
    ----------
    s            : current state [x,y,z, vx,vy,vz, q0..q3, ωx,ωy,ωz, m]
    params       : rocket physical constants
    thrust       : commanded engine thrust [N]
    gimbal_pitch : nozzle pitch deflection [rad]
    gimbal_yaw   : nozzle yaw deflection [rad]
    """
    # ── Unpack ────────────────────────────────────────────────────────
    _x, _y, _z, vx, vy, vz, q0, q1, q2, q3, wx, wy, wz, m = s

    # Zero thrust and mass-flow when propellant is exhausted.
    T = 0.0 if m <= params.dry_mass else thrust

    # ── Translational dynamics ────────────────────────────────────────
    q_arr = np.array([q0, q1, q2, q3])
    R = _quat_to_rot(q_arr)

    # Thrust vector in body frame (small-angle gimbal).
    # Sign convention: positive gimbal deflects nozzle, creating a NEGATIVE
    # horizontal force in that plane — matching the 2D convention where
    # ax = -T·sin(γ)/m ≈ -g·γ.  This ensures the LQR gain signs are consistent.
    F_body = np.array([-T * gimbal_yaw, T, -T * gimbal_pitch])

    # Rotate to world frame, add gravity on y.
    F_world = R @ F_body
    inv_m = 1.0 / m
    ax = F_world[0] * inv_m
    ay = F_world[1] * inv_m - GRAVITY
    az = F_world[2] * inv_m

    # ── Rotational dynamics (Euler's equations in body frame) ─────────
    L = params.nozzle_arm
    # τ = r_nozzle × F_body  with  r_nozzle = [0, -L, 0]
    # F_body = T·[-γy, 1, -γp]
    # Cross product gives: τ = T · [L·γp, 0, -L·γy]
    tau = np.array([
         L * T * gimbal_pitch,
         0.0,
        -L * T * gimbal_yaw,
    ])

    # Diagonal inertia tensor (body frame).
    I_t = m * params.body_length**2 / 12.0   # transverse (Ix = Iz)
    I_a = 0.5 * m * params.body_radius**2    # axial (Iy)
    I_diag = np.array([I_t, I_a, I_t])       # [Ix, Iy, Iz]

    # Euler: I·ω̇ = τ − ω × (I·ω)
    omega = np.array([wx, wy, wz])
    I_omega = I_diag * omega                  # diagonal → element-wise
    omega_dot = (tau - np.cross(omega, I_omega)) / I_diag

    # ── Quaternion kinematics:  q̇ = ½ · q ⊗ [0, ω_body] ─────────────
    # Expanding the Hamilton product with pure-quaternion ω = [0, wx, wy, wz]:
    q0d = 0.5 * (-q1*wx - q2*wy - q3*wz)
    q1d = 0.5 * ( q0*wx + q2*wz - q3*wy)
    q2d = 0.5 * ( q0*wy - q1*wz + q3*wx)
    q3d = 0.5 * ( q0*wz + q1*wy - q2*wx)

    # ── Mass depletion ────────────────────────────────────────────────
    mdot = 0.0 if m <= params.dry_mass else -thrust / (params.isp * G0)

    return np.array([
        vx, vy, vz,
        ax, ay, az,
        q0d, q1d, q2d, q3d,
        omega_dot[0], omega_dot[1], omega_dot[2],
        mdot,
    ])


def _rk4_step3d(
    s: np.ndarray,
    params: RocketParams3D,
    dt: float,
    thrust: float,
    gimbal_pitch: float,
    gimbal_yaw: float,
) -> np.ndarray:
    """
    Fourth-order Runge-Kutta step for the 6-DOF state.

    The quaternion (indices 6-9) is re-normalised after integration
    to prevent norm drift from accumulating over many steps.
    """
    def f(sv: np.ndarray) -> np.ndarray:
        return _derivatives3d(sv, params, thrust, gimbal_pitch, gimbal_yaw)

    k1 = f(s)
    k2 = f(s + 0.5 * dt * k1)
    k3 = f(s + 0.5 * dt * k2)
    k4 = f(s + dt * k3)

    s_new = s + (dt / 6.0) * (k1 + 2*k2 + 2*k3 + k4)

    # Re-normalise quaternion to stay on the unit 3-sphere.
    s_new[6:10] /= np.linalg.norm(s_new[6:10])

    return s_new


# ══════════════════════════════════════════════════════════════════════ #
# Public API                                                             #
# ══════════════════════════════════════════════════════════════════════ #

class Rocket3D:
    """
    6-DOF rigid-body rocket with RK4 integration.

    Usage
    -----
        params = RocketParams3D()
        state  = State3D(y=1000.0, m=1000.0)
        rocket = Rocket3D(state, params)

        cmd = ControlInput3D(thrust=9810.0)        # hover
        new_state = rocket.step(dt=1/60, cmd=cmd)
    """

    def __init__(self, state: State3D, params: RocketParams3D) -> None:
        self.params = params
        self._s = state.to_array().copy()

    @property
    def state(self) -> State3D:
        """Current rocket state (read-only snapshot)."""
        return State3D.from_array(self._s)

    def step(
        self,
        dt: float,
        cmd: ControlInput3D | None = None,
        *,
        thrust: float = 0.0,
        gimbal_pitch: float = 0.0,
        gimbal_yaw: float = 0.0,
    ) -> State3D:
        """
        Advance the simulation by one RK4 timestep.

        Accepts either a ControlInput3D dataclass *or* keyword arguments
        for convenience in tests.

        Parameters
        ----------
        dt           : timestep [s]
        cmd          : ControlInput3D (takes priority over kwargs)
        thrust       : engine thrust [N]         (used if cmd is None)
        gimbal_pitch : nozzle pitch deflection [rad]
        gimbal_yaw   : nozzle yaw deflection [rad]
        """
        if cmd is not None:
            thrust = cmd.thrust
            gimbal_pitch = cmd.gimbal_pitch
            gimbal_yaw = cmd.gimbal_yaw

        self._s = _rk4_step3d(
            self._s, self.params, dt, thrust, gimbal_pitch, gimbal_yaw,
        )

        # Clamp mass to dry-mass floor.
        if self._s[13] < self.params.dry_mass:
            self._s[13] = self.params.dry_mass

        return State3D.from_array(self._s)
