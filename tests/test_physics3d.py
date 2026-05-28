"""
6-DOF physics validation tests  (Week 4).

Every test has a closed-form analytical answer.
If a test fails the bug is in rocket3d.py — not in a gain or a tuning param.

Tests
-----
1.  3D free-fall  —  ay = −g, ax = az = 0, y(t) = y0 − ½g·t²
2.  Quaternion norm  —  |q| = 1 throughout free motion with initial ω
3.  Hover equilibrium  —  T = m·g, upright → ÿ ≈ 0, no horizontal drift
4.  Angular momentum conservation  —  zero torque, zero thrust →
        |L_world| = const  and  quaternion norm = 1
5.  Axial spin stability  —  ω = [0, Ω, 0] (around symmetry axis),
        no torque → ω stays constant (Euler equations, symmetric body)
6.  Tsiolkovsky Δv in 3D  —  vertical burn matches Isp·g₀·ln(m₀/mf)
        within 1 %  (high T/W so gravity losses are negligible)
7.  Dry-mass clamp  —  mass never drops below dry_mass under burn
"""

from __future__ import annotations

import numpy as np
import pytest

from physics.rocket3d import (
    GRAVITY,
    G0,
    ControlInput3D,
    Rocket3D,
    RocketParams3D,
    _quat_to_rot,
)
from physics.state3d import State3D


# ──────────────────────────────────────────────────────────────────── #
# Helpers                                                               #
# ──────────────────────────────────────────────────────────────────── #

def make_rocket(
    y: float = 100.0,
    m: float = 1000.0,
    dry_mass: float = 100.0,
    **kwargs: float,
) -> Rocket3D:
    """Upright rocket at rest, floating in the air."""
    state = State3D(y=y, m=m, **kwargs)
    params = RocketParams3D(dry_mass=dry_mass)
    return Rocket3D(state, params)


def _angular_momentum_world(state: State3D, params: RocketParams3D) -> np.ndarray:
    """
    Angular momentum in world frame:  L = R · (I_body · ω_body)
    For a diagonal inertia tensor I = diag(It, Ia, It).
    """
    m = state.m
    I_t = m * params.body_length**2 / 12.0
    I_a = 0.5 * m * params.body_radius**2
    I_diag = np.array([I_t, I_a, I_t])

    omega_body = state.omega
    R = _quat_to_rot(state.quat)
    return R @ (I_diag * omega_body)


# ──────────────────────────────────────────────────────────────────── #
# 1 — 3D free-fall                                                      #
# ──────────────────────────────────────────────────────────────────── #

class TestFreefall3D:
    DT = 1.0 / 1000.0
    T_FINAL = 3.0
    Y0 = 500.0

    def _run(self) -> list[State3D]:
        rocket = make_rocket(y=self.Y0)
        n = int(self.T_FINAL / self.DT)
        hist = [rocket.state]
        for _ in range(n):
            hist.append(rocket.step(self.DT))
        return hist

    def test_vertical_acceleration(self) -> None:
        """ay = −g within 0.1 % over the first timestep."""
        hist = self._run()
        ay = (hist[1].vy - hist[0].vy) / self.DT
        assert abs(ay - (-GRAVITY)) / GRAVITY < 1e-3, (
            f"ay = {ay:.6f} m/s², expected −{GRAVITY}"
        )

    def test_no_horizontal_acceleration(self) -> None:
        """Free-fall → ax = az = 0 throughout."""
        hist = self._run()
        ax = (hist[1].vx - hist[0].vx) / self.DT
        az = (hist[1].vz - hist[0].vz) / self.DT
        assert abs(ax) < 1e-10
        assert abs(az) < 1e-10

    def test_trajectory_matches_analytical(self) -> None:
        """y(t) = Y0 − ½g·t² within 0.01 % at t = T_FINAL."""
        hist = self._run()
        y_analytical = self.Y0 - 0.5 * GRAVITY * self.T_FINAL**2
        y_sim = hist[-1].y
        rel_err = abs(y_sim - y_analytical) / abs(y_analytical)
        assert rel_err < 1e-4, (
            f"y({self.T_FINAL}s) = {y_sim:.4f} m, analytical = {y_analytical:.4f} m"
        )

    def test_attitude_unchanged(self) -> None:
        """No torque → quaternion stays at [1, 0, 0, 0] throughout."""
        hist = self._run()
        q_final = hist[-1].quat
        np.testing.assert_allclose(q_final, [1, 0, 0, 0], atol=1e-10)


# ──────────────────────────────────────────────────────────────────── #
# 2 — Quaternion norm preservation                                      #
# ──────────────────────────────────────────────────────────────────── #

class TestQuaternionNorm:
    """
    Under free motion with initial angular velocity, |q| must stay = 1.
    The RK4 step re-normalises after each step; this confirms no drift escapes.
    """
    DT = 1.0 / 60.0
    N_STEPS = 3600   # 60 s

    def test_norm_stays_unity(self) -> None:
        # Tilted rocket with non-zero spin on all axes.
        state = State3D(
            y=500.0,
            q0=0.9239, q1=0.3827, q2=0.0, q3=0.0,  # ~45° tilt around x
            omega_x=0.5, omega_y=0.1, omega_z=0.3,
            m=500.0,
        )
        rocket = Rocket3D(state, RocketParams3D(dry_mass=100.0))
        for _ in range(self.N_STEPS):
            s = rocket.step(self.DT)
            norm = np.linalg.norm(s.quat)
            assert abs(norm - 1.0) < 1e-9, f"|q| = {norm:.10f} at step {_+1}"


# ──────────────────────────────────────────────────────────────────── #
# 3 — Hover equilibrium                                                 #
# ──────────────────────────────────────────────────────────────────── #

class TestHover3D:
    """T = m·g, upright rocket → vertical acceleration ≈ 0, no drift."""
    DT = 1.0 / 1000.0

    def test_hover_cancels_gravity(self) -> None:
        m = 1000.0
        rocket = make_rocket(y=100.0, m=m, dry_mass=50.0)
        vy_before = rocket.state.vy
        rocket.step(self.DT, thrust=m * GRAVITY)
        ay = (rocket.state.vy - vy_before) / self.DT
        assert abs(ay) < 1e-3, f"ay at hover = {ay:.6f} m/s², expected ~0"

    def test_hover_no_horizontal_drift(self) -> None:
        """Upright hover → x and z stay at 0 for 10 s."""
        m = 1000.0
        rocket = make_rocket(y=100.0, m=m, dry_mass=50.0)
        n = int(10.0 / self.DT)
        for _ in range(n):
            rocket.step(self.DT, thrust=m * GRAVITY)
        assert abs(rocket.state.x) < 1e-8
        assert abs(rocket.state.z) < 1e-8

    def test_hover_attitude_unchanged(self) -> None:
        """Upright hover with zero gimbal → attitude stays [1,0,0,0]."""
        m = 1000.0
        rocket = make_rocket(y=100.0, m=m, dry_mass=50.0)
        n = int(10.0 / self.DT)
        for _ in range(n):
            rocket.step(self.DT, thrust=m * GRAVITY)
        np.testing.assert_allclose(rocket.state.quat, [1, 0, 0, 0], atol=1e-10)


# ──────────────────────────────────────────────────────────────────── #
# 4 — Angular momentum conservation                                     #
# ──────────────────────────────────────────────────────────────────── #

class TestAngularMomentum3D:
    """
    Zero thrust and zero gimbal → no external torque →
    angular momentum in the world frame is conserved.
    """
    DT = 1.0 / 60.0
    N_STEPS = 600   # 10 s

    def test_angular_momentum_conserved(self) -> None:
        state = State3D(
            y=500.0,
            q0=1.0, q1=0.0, q2=0.0, q3=0.0,
            omega_x=0.3, omega_y=0.1, omega_z=0.2,
            m=500.0,
        )
        params = RocketParams3D(dry_mass=100.0)
        rocket = Rocket3D(state, params)

        L0 = _angular_momentum_world(rocket.state, params)

        for _ in range(self.N_STEPS):
            rocket.step(self.DT)   # zero thrust, zero gimbal

        L_final = _angular_momentum_world(rocket.state, params)

        # Angular momentum magnitude conserved within 0.01 %.
        rel_err = abs(np.linalg.norm(L_final) - np.linalg.norm(L0)) / np.linalg.norm(L0)
        assert rel_err < 1e-4, (
            f"|L0| = {np.linalg.norm(L0):.6f}, |Lf| = {np.linalg.norm(L_final):.6f}, "
            f"rel_err = {rel_err:.2e}"
        )


# ──────────────────────────────────────────────────────────────────── #
# 5 — Axial spin stability                                              #
# ──────────────────────────────────────────────────────────────────── #

class TestAxialSpin:
    """
    Rotation purely around the symmetry axis (ω = [0, Ω, 0] body frame),
    no thrust, no torque → ω must stay constant (Euler's equations).

    For a symmetric body  Ix = Iz:
      ω̇_y = 0                     (τ_y = 0)
      ω̇_x = −(Ia − It)·ωy·ωz / It = 0  (ωz = 0)
      ω̇_z = −(It − Ia)·ωx·ωy / It = 0  (ωx = 0)
    → ω is exactly constant.
    """
    DT = 1.0 / 60.0
    N_STEPS = 600   # 10 s
    OMEGA_Y = 2.0   # rad/s spin around body y (symmetry axis)

    def test_axial_spin_omega_constant(self) -> None:
        state = State3D(y=500.0, omega_y=self.OMEGA_Y, m=500.0)
        rocket = Rocket3D(state, RocketParams3D(dry_mass=100.0))
        omega0 = rocket.state.omega.copy()
        for _ in range(self.N_STEPS):
            rocket.step(self.DT)
        np.testing.assert_allclose(
            rocket.state.omega, omega0, rtol=1e-5,
            err_msg="Axial spin should remain constant with no torque",
        )


# ──────────────────────────────────────────────────────────────────── #
# 6 — Tsiolkovsky Δv in 3D                                             #
# ──────────────────────────────────────────────────────────────────── #

class TestTsiolkovsky3D:
    """
    Vertical burn (upright, zero gimbal), high T/W to minimise gravity losses.
    Δv_sim  = vy at burnout.
    Δv_theory = Isp · g₀ · ln(m₀ / m_dry)
    """
    DT = 1.0 / 1000.0

    def _run_burn(
        self,
        m0: float = 1000.0,
        dry_mass: float = 100.0,
        thrust: float = 981_000.0,   # T/W ≈ 100 → burn ≈ 2.7 s, gravity loss < 0.5 %
        isp: float = 300.0,
    ) -> tuple[float, float]:
        params = RocketParams3D(dry_mass=dry_mass, isp=isp)
        state = State3D(y=1e6, m=m0)        # very high altitude → gravity negligible
        rocket = Rocket3D(state, params)

        vy_start = rocket.state.vy
        while rocket.state.m > dry_mass + 1e-3:
            rocket.step(self.DT, thrust=thrust)

        dv_sim = rocket.state.vy - vy_start
        dv_theory = isp * G0 * np.log(m0 / dry_mass)
        return dv_sim, dv_theory

    def test_tsiolkovsky_within_1_percent(self) -> None:
        dv_sim, dv_theory = self._run_burn()
        rel_err = abs(dv_sim - dv_theory) / abs(dv_theory)
        assert rel_err < 0.01, (
            f"Δv_sim={dv_sim:.2f} m/s, Δv_theory={dv_theory:.2f} m/s, "
            f"rel_err={rel_err:.3%}"
        )

    @pytest.mark.parametrize("mass_ratio", [2.0, 5.0, 10.0])
    def test_tsiolkovsky_various_mass_ratios(self, mass_ratio: float) -> None:
        m0 = 1000.0
        dry_mass = m0 / mass_ratio
        dv_sim, dv_theory = self._run_burn(m0=m0, dry_mass=dry_mass)
        rel_err = abs(dv_sim - dv_theory) / abs(dv_theory)
        assert rel_err < 0.01, f"mass_ratio={mass_ratio}, rel_err={rel_err:.3%}"


# ──────────────────────────────────────────────────────────────────── #
# 7 — Dry-mass clamp                                                    #
# ──────────────────────────────────────────────────────────────────── #

class TestDryMassClamp3D:
    """Mass must never drop below dry_mass, even with sustained burn."""
    DT = 1.0 / 60.0
    N_STEPS = 3600   # 60 s — far exceeds propellant lifetime

    def test_mass_never_below_dry(self) -> None:
        dry = 100.0
        params = RocketParams3D(dry_mass=dry)
        state = State3D(y=1e6, m=200.0)
        rocket = Rocket3D(state, params)
        for i in range(self.N_STEPS):
            rocket.step(self.DT, thrust=5000.0)
            assert rocket.state.m >= dry - 1e-9, (
                f"mass = {rocket.state.m:.6f} kg < dry_mass = {dry} at step {i+1}"
            )
