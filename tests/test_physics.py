"""
Physics validation tests.

Every test here has a closed-form analytical answer.
If any test fails, the bug is in the dynamics — not in a gain or a tuning parameter.

Tests
-----
1. Free-fall acceleration matches g = 9.81 m/s² within 0.1 %
2. Free-fall trajectory matches y(t) = y0 - ½g·t²
3. Tsiolkovsky Δv: vertical burn matches Isp·g0·ln(m0/mf) within 1 %
4. Hover equilibrium: T = m·g → ay ≈ 0
5. Angular momentum conserved when gimbal = 0 (no torque → ω constant)
6. Dry-mass clamp: mass never drops below dry_mass
"""

from __future__ import annotations

import numpy as np
import pytest

from physics.rocket import GRAVITY, G0, Rocket, RocketParams
from physics.state import State


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def make_rocket(
    y: float = 100.0,
    vy: float = 0.0,
    m: float = 1000.0,
    dry_mass: float = 100.0,
) -> Rocket:
    state = State(x=0.0, y=y, vx=0.0, vy=vy, theta=0.0, omega=0.0, m=m)
    params = RocketParams(dry_mass=dry_mass)
    return Rocket(state, params)


def run(
    rocket: Rocket,
    dt: float,
    n_steps: int,
    thrust: float = 0.0,
    gimbal: float = 0.0,
) -> list[State]:
    history = [State.from_array(rocket.state.to_array())]
    for _ in range(n_steps):
        history.append(rocket.step(dt, thrust=thrust, gimbal=gimbal))
    return history


# ---------------------------------------------------------------------------
# 1 & 2 — free-fall
# ---------------------------------------------------------------------------

class TestFreefall:
    DT = 1.0 / 1000.0   # 1 ms — tight dt to isolate integrator error
    T_FINAL = 3.0        # s
    Y0 = 500.0           # m

    def _run(self) -> list[State]:
        rocket = make_rocket(y=self.Y0)
        n = int(self.T_FINAL / self.DT)
        return run(rocket, self.DT, n)

    def test_acceleration_magnitude(self) -> None:
        """Numerically measured ay ≈ -g within 0.1 %."""
        hist = self._run()
        ay_numerical = (hist[1].vy - hist[0].vy) / self.DT
        assert abs(ay_numerical - (-GRAVITY)) / GRAVITY < 1e-3, (
            f"ay = {ay_numerical:.6f} m/s², expected -{GRAVITY}"
        )

    def test_trajectory_matches_analytical(self) -> None:
        """y(t) = Y0 − ½g·t² within 0.01 % at t = T_FINAL."""
        hist = self._run()
        y_analytical = self.Y0 - 0.5 * GRAVITY * self.T_FINAL**2
        y_numerical = hist[-1].y
        rel_err = abs(y_numerical - y_analytical) / abs(y_analytical)
        assert rel_err < 1e-4, (
            f"y({self.T_FINAL}s) = {y_numerical:.4f} m, "
            f"analytical = {y_analytical:.4f} m, rel_err = {rel_err:.2e}"
        )

    def test_horizontal_position_unchanged(self) -> None:
        """No horizontal force → x stays at 0."""
        hist = self._run()
        assert abs(hist[-1].x) < 1e-12

    def test_mass_unchanged_no_thrust(self) -> None:
        """No engine → mass is conserved."""
        hist = self._run()
        assert hist[-1].m == pytest.approx(hist[0].m, rel=1e-12)


# ---------------------------------------------------------------------------
# 3 — Tsiolkovsky Δv
# ---------------------------------------------------------------------------

class TestTsiolkovsky:
    """
    Vertical burn (theta=0, gimbal=0) starting from rest.
    Δv_sim   = vy at burnout.
    Δv_theory = Isp * g0 * ln(m0 / mf)
    """

    DT = 1.0 / 1000.0

    def _run_burn(
        self,
        m0: float = 1000.0,
        dry_mass: float = 100.0,
        thrust: float = 981_000.0,  # T/W = 100 → burn ~2.7 s → gravity loss < 0.5 %
        isp: float = 300.0,
    ) -> tuple[float, float]:
        params = RocketParams(dry_mass=dry_mass, isp=isp)
        # High T/W ratio makes the burn short (~2.7 s), so gravity losses are
        # negligible (<0.5 %) and Δv_sim ≈ Isp·g0·ln(m0/mf) within 1 %.
        state = State(x=0, y=1e6, vx=0, vy=0, theta=0, omega=0, m=m0)
        rocket = Rocket(state, params)

        vy_start = rocket.state.vy
        while rocket.state.m > dry_mass + 1e-3:
            rocket.step(self.DT, thrust=thrust, gimbal=0.0)

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


# ---------------------------------------------------------------------------
# 4 — Hover equilibrium
# ---------------------------------------------------------------------------

class TestHover:
    """T = m·g with gimbal=0 should produce ay ≈ 0."""

    DT = 1.0 / 1000.0

    def test_hover_cancels_gravity(self) -> None:
        m = 1000.0
        rocket = make_rocket(y=100.0, m=m, dry_mass=50.0)
        vy_before = rocket.state.vy
        rocket.step(self.DT, thrust=m * GRAVITY, gimbal=0.0)
        ay = (rocket.state.vy - vy_before) / self.DT
        assert abs(ay) < 1e-3, f"ay at hover = {ay:.6f} m/s², expected ~0"

    def test_hover_no_horizontal_drift(self) -> None:
        """Upright hover (theta=0, gimbal=0) → no horizontal force."""
        m = 1000.0
        rocket = make_rocket(y=100.0, m=m, dry_mass=50.0)
        x0 = rocket.state.x
        n = int(10.0 / self.DT)
        for _ in range(n):
            rocket.step(self.DT, thrust=m * GRAVITY, gimbal=0.0)
        assert abs(rocket.state.x - x0) < 1e-9


# ---------------------------------------------------------------------------
# 5 — Angular momentum conservation
# ---------------------------------------------------------------------------

class TestAngularMomentum:
    """gimbal=0, thrust=0 → no torque → ω must remain constant."""

    DT = 1.0 / 60.0
    N_STEPS = 600   # 10 s

    def test_omega_constant_no_torque(self) -> None:
        state = State(x=0, y=500, vx=0, vy=0, theta=0.1, omega=0.5, m=500.0)
        rocket = Rocket(state, RocketParams(dry_mass=100.0))
        omega0 = rocket.state.omega
        for _ in range(self.N_STEPS):
            rocket.step(self.DT, thrust=0.0, gimbal=0.0)
        assert rocket.state.omega == pytest.approx(omega0, rel=1e-6)


# ---------------------------------------------------------------------------
# 6 — Dry-mass clamp
# ---------------------------------------------------------------------------

class TestDryMassClamp:
    """Mass must never drop below dry_mass, even with sustained burn."""

    DT = 1.0 / 60.0
    N_STEPS = 3600  # 60 s — far exceeds propellant lifetime

    def test_mass_never_below_dry(self) -> None:
        dry = 100.0
        rocket = make_rocket(y=1e6, m=200.0, dry_mass=dry)
        for _ in range(self.N_STEPS):
            rocket.step(self.DT, thrust=5000.0, gimbal=0.0)
            assert rocket.state.m >= dry - 1e-9, (
                f"mass dropped to {rocket.state.m:.6f} kg, below dry_mass={dry}"
            )
