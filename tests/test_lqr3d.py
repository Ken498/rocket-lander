"""
3D LQR controller tests (Week 5).

Tests
-----
1.  Gain matrix shape  —  K is (3, 12) for any valid params
2.  Zero-error command  —  at hover equilibrium → T ≈ m·g, γ_p = γ_y = 0
3.  Attitude correction  —  tilted rocket → gimbal commands point back upright
4.  Mass-scheduled recompute  —  K updates when mass drifts > threshold
5.  Landing from ±50 m x-offset  —  3D analog of the 2D PID landing test:
        y0 = 1000 m, x0 = ±50 m, z0 = 0 → lands within 2 m in x, vy > −2 m/s
6.  Landing from ±50 m z-offset  —  same but displaced in z
7.  Landing from combined x-z offset  —  x0 = z0 = ±35 m (~50 m diagonal)
"""

from __future__ import annotations

import numpy as np
import pytest

from physics.lqr3d import LQRController3D, LQRWeights3D, solve_lqr3d
from physics.rocket3d import GRAVITY, Rocket3D, RocketParams3D
from physics.state3d import State3D


# ──────────────────────────────────────────────────────────────────── #
# Shared helpers                                                         #
# ──────────────────────────────────────────────────────────────────── #

DEFAULT_PARAMS = RocketParams3D(
    dry_mass=100.0,
    body_length=20.0,
    body_radius=1.0,
    nozzle_arm=10.0,
    isp=300.0,
)
HOVER_MASS = 1000.0


def make_hover_state(**kwargs: float) -> State3D:
    """Upright rocket at rest with optional field overrides."""
    return State3D(y=1000.0, m=HOVER_MASS, **kwargs)


# ──────────────────────────────────────────────────────────────────── #
# 1 — Gain matrix shape                                                 #
# ──────────────────────────────────────────────────────────────────── #

class TestGainShape:
    def test_K_shape(self) -> None:
        K = solve_lqr3d(DEFAULT_PARAMS, HOVER_MASS)
        assert K.shape == (3, 10), f"K.shape = {K.shape}, expected (3, 10)"

    def test_K_finite(self) -> None:
        K = solve_lqr3d(DEFAULT_PARAMS, HOVER_MASS)
        assert np.all(np.isfinite(K)), "K contains NaN or Inf"


# ──────────────────────────────────────────────────────────────────── #
# 2 — Zero-error command at hover equilibrium                           #
# ──────────────────────────────────────────────────────────────────── #

class TestZeroErrorCommand:
    def test_hover_equilibrium(self) -> None:
        """At hover with zero error, T ≈ m·g and both gimbals ≈ 0."""
        state = make_hover_state()
        lqr = LQRController3D(DEFAULT_PARAMS, hover_mass=HOVER_MASS)
        cmd = lqr.update(state, target_x=0.0, target_y=1000.0, target_z=0.0)

        assert abs(cmd.thrust - HOVER_MASS * GRAVITY) < 1.0, (
            f"Hover thrust = {cmd.thrust:.2f} N, expected {HOVER_MASS * GRAVITY:.2f} N"
        )
        assert abs(cmd.gimbal_pitch) < 1e-6, (
            f"gimbal_pitch = {cmd.gimbal_pitch:.2e} rad at equilibrium"
        )
        assert abs(cmd.gimbal_yaw) < 1e-6, (
            f"gimbal_yaw = {cmd.gimbal_yaw:.2e} rad at equilibrium"
        )


# ──────────────────────────────────────────────────────────────────── #
# 3 — Attitude correction sign                                          #
# ──────────────────────────────────────────────────────────────────── #

class TestAttitudeCorrection:
    """
    A tilted rocket should receive a gimbal command that produces a restoring torque.

    Torque model (from rocket3d.py, sign convention: F_body = T·[-γy, 1, -γp]):
        τ_x = +T·L·γ_pitch  →  α_x = τ_x / I_t
        τ_z = −T·L·γ_yaw   →  α_z = τ_z / I_t

    Tilt around x (δφ = 2·q1 > 0): need α_x < 0 → τ_x < 0 → γ_pitch < 0
    Tilt around z (δθ = 2·q3 > 0): need α_z < 0 → τ_z < 0 → γ_yaw > 0
    """

    def _tilted_state(self, q1: float = 0.0, q3: float = 0.0) -> State3D:
        """
        Small-tilt state: q ≈ [1, q1, 0, q3].  Renormalise for consistency.
        """
        q = np.array([1.0, q1, 0.0, q3])
        q /= np.linalg.norm(q)
        return State3D(y=1000.0, m=HOVER_MASS,
                       q0=q[0], q1=q[1], q2=q[2], q3=q[3])

    def test_pitch_correction_sign(self) -> None:
        """δθ = 2·q3 > 0 → τ_z = -T·L·γ_yaw < 0 requires γ_yaw > 0 to restore."""
        state = self._tilted_state(q3=0.05)  # θ ≈ 0.1 rad tilt
        lqr = LQRController3D(DEFAULT_PARAMS, hover_mass=HOVER_MASS)
        cmd = lqr.update(state, target_x=0.0, target_y=1000.0, target_z=0.0)
        assert cmd.gimbal_yaw > 0.0, (
            f"Expected γ_yaw > 0 for δθ > 0 tilt (restoring torque), got {cmd.gimbal_yaw:.4f}"
        )

    def test_roll_correction_sign(self) -> None:
        """δφ = 2·q1 > 0 → τ_x = +T·L·γ_pitch < 0 requires γ_pitch < 0 to restore."""
        state = self._tilted_state(q1=0.05)  # φ ≈ 0.1 rad tilt
        lqr = LQRController3D(DEFAULT_PARAMS, hover_mass=HOVER_MASS)
        cmd = lqr.update(state, target_x=0.0, target_y=1000.0, target_z=0.0)
        assert cmd.gimbal_pitch < 0.0, (
            f"Expected γ_pitch < 0 for δφ > 0 tilt (restoring torque), got {cmd.gimbal_pitch:.4f}"
        )


# ──────────────────────────────────────────────────────────────────── #
# 4 — Mass-scheduled recompute                                          #
# ──────────────────────────────────────────────────────────────────── #

class TestMassSchedule:
    def test_K_updates_on_mass_change(self) -> None:
        """After enough mass burn, K must change from its initial value."""
        lqr = LQRController3D(
            DEFAULT_PARAMS,
            hover_mass=HOVER_MASS,
            recompute_threshold=10.0,
        )
        K_initial = lqr.K.copy()

        # Feed a state whose mass is 20 kg below hover_mass.
        state = State3D(y=1000.0, m=HOVER_MASS - 20.0)
        lqr.update(state, target_x=0.0, target_y=1000.0, target_z=0.0)

        assert not np.allclose(lqr.K, K_initial), (
            "K was not recomputed after mass changed by > threshold"
        )

    def test_K_unchanged_within_threshold(self) -> None:
        """Small mass change (< threshold) must NOT trigger recompute."""
        lqr = LQRController3D(
            DEFAULT_PARAMS,
            hover_mass=HOVER_MASS,
            recompute_threshold=10.0,
        )
        K_initial = lqr.K.copy()

        state = State3D(y=1000.0, m=HOVER_MASS - 5.0)
        lqr.update(state, target_x=0.0, target_y=1000.0, target_z=0.0)

        np.testing.assert_array_equal(lqr.K, K_initial)


# ──────────────────────────────────────────────────────────────────── #
# 5–7 — Closed-loop landing                                             #
# ──────────────────────────────────────────────────────────────────── #

class TestLanding3D:
    """
    End-to-end LQR landing from offsets in x and/or z at y0 = 1000 m.

    Pass criteria (same as Week 3 PID spec, extended to 3D):
        |x_touchdown| < 2 m
        |z_touchdown| < 2 m
        vy_touchdown  > −2 m/s

    Simulation: dt = 1/60 s, max 300 s.

    Guidance strategy
    -----------------
    The LQR is a hover stabiliser valid only near its linearisation point.
    To keep errors small during a 1 km descent we use reference-trajectory
    tracking (standard in aerospace):

      x_ref(t) = x0 · exp(−λ·t)         — exponential approach to pad
      vy_ref    = −clip(k·y, v_min, v_max)  — velocity descent profile

    The LQR sees small deviations from the reference at every step and
    operates entirely within its linear regime.
    """

    DT = 1.0 / 60.0
    MAX_STEPS = 18_000     # 300 s
    MAX_LANDING_X = 2.0    # m
    MAX_LANDING_Z = 2.0    # m
    MAX_LANDING_VY = -2.0  # m/s

    LAMBDA = 0.03          # horizontal convergence rate [1/s]

    def _land(
        self,
        x0: float = 0.0,
        z0: float = 0.0,
        y0: float = 1000.0,
        m0: float = HOVER_MASS,
    ) -> tuple[float, float, float]:
        """Run reference-trajectory tracking until y ≤ 0; return (x, z, vy)."""
        state = State3D(x=x0, y=y0, z=z0, m=m0)
        rocket = Rocket3D(state, DEFAULT_PARAMS)
        lqr = LQRController3D(DEFAULT_PARAMS, hover_mass=m0)

        t = 0.0
        for _ in range(self.MAX_STEPS):
            s = rocket.state
            t += self.DT

            # Horizontal reference: exponential convergence to the landing pad.
            x_ref = x0 * np.exp(-self.LAMBDA * t)
            z_ref = z0 * np.exp(-self.LAMBDA * t)
            vx_ref = -self.LAMBDA * x_ref
            vz_ref = -self.LAMBDA * z_ref

            # Vertical reference: velocity profile keeps LQR near hover.
            # vy_ref → 0 as y → 0 so touchdown is soft.
            vy_ref = -float(np.clip(0.25 * max(s.y, 0.0), 0.2, 5.0))

            cmd = lqr.update(
                s,
                target_x=x_ref,
                target_y=s.y,       # altitude position error = 0; only vy matters
                target_z=z_ref,
                target_vx=vx_ref,
                target_vy=vy_ref,
                target_vz=vz_ref,
            )
            rocket.step(self.DT, cmd=cmd)
            if rocket.state.y <= 0.0:
                break

        s = rocket.state
        return s.x, s.z, s.vy

    # ── 5 — x-offset ──────────────────────────────────────────────── #

    @pytest.mark.parametrize("x0", [50.0, -50.0])
    def test_landing_x_offset(self, x0: float) -> None:
        """Start ±50 m in x → touch down within 2 m, vy > −2 m/s."""
        x_f, z_f, vy_f = self._land(x0=x0)
        assert abs(x_f) < self.MAX_LANDING_X, (
            f"x0={x0}: x_touchdown={x_f:.2f} m (limit ±{self.MAX_LANDING_X} m)"
        )
        assert abs(z_f) < self.MAX_LANDING_Z, (
            f"x0={x0}: z_touchdown={z_f:.2f} m (limit ±{self.MAX_LANDING_Z} m)"
        )
        assert vy_f > self.MAX_LANDING_VY, (
            f"x0={x0}: vy_touchdown={vy_f:.2f} m/s (limit {self.MAX_LANDING_VY} m/s)"
        )

    # ── 6 — z-offset ──────────────────────────────────────────────── #

    @pytest.mark.parametrize("z0", [50.0, -50.0])
    def test_landing_z_offset(self, z0: float) -> None:
        """Start ±50 m in z → touch down within 2 m, vy > −2 m/s."""
        x_f, z_f, vy_f = self._land(z0=z0)
        assert abs(x_f) < self.MAX_LANDING_X, (
            f"z0={z0}: x_touchdown={x_f:.2f} m"
        )
        assert abs(z_f) < self.MAX_LANDING_Z, (
            f"z0={z0}: z_touchdown={z_f:.2f} m (limit ±{self.MAX_LANDING_Z} m)"
        )
        assert vy_f > self.MAX_LANDING_VY, (
            f"z0={z0}: vy_touchdown={vy_f:.2f} m/s"
        )

    # ── 7 — Combined x-z offset ───────────────────────────────────── #

    @pytest.mark.parametrize("offset", [35.0, -35.0])
    def test_landing_combined_offset(self, offset: float) -> None:
        """Start ±35 m in both x and z (≈50 m diagonal) → land within spec."""
        x_f, z_f, vy_f = self._land(x0=offset, z0=offset)
        assert abs(x_f) < self.MAX_LANDING_X, (
            f"(x0,z0)=({offset},{offset}): x_touchdown={x_f:.2f} m"
        )
        assert abs(z_f) < self.MAX_LANDING_Z, (
            f"(x0,z0)=({offset},{offset}): z_touchdown={z_f:.2f} m"
        )
        assert vy_f > self.MAX_LANDING_VY, (
            f"(x0,z0)=({offset},{offset}): vy={vy_f:.2f} m/s"
        )
