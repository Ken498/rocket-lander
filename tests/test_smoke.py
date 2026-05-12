"""Smoke tests so CI is green from commit one.

The physicist will replace these with real validation: free-fall vs g,
Tsiolkovsky Δv, energy conservation, Kepler's third law. For now we
just verify the State <-> array round-trip and that the stub doesn't
crash.
"""

import numpy as np
import pytest

from physics import Rocket, RocketParams, State, simulate_freefall


def test_state_roundtrip():
    s = State(x=1.0, y=2.0, vx=3.0, vy=4.0, theta=0.5, omega=0.1, m=1000.0)
    arr = s.to_array()
    assert arr.shape == (7,)
    s2 = State.from_array(arr)
    assert s == s2


def test_state_from_array_rejects_wrong_shape():
    with pytest.raises(ValueError):
        State.from_array(np.zeros(6))


def test_freefall_falls():
    """A dropped rocket should end up lower than it started."""
    initial = State(x=0, y=100, vx=0, vy=0, theta=0, omega=0, m=1000)
    traj = simulate_freefall(initial, duration=2.0, dt=0.01)
    assert traj[-1].y < traj[0].y
    assert traj[-1].vy < 0  # moving down


def test_freefall_horizontal_motion_is_zero():
    """No horizontal force, so x and vx should stay at zero."""
    initial = State(x=0, y=100, vx=0, vy=0, theta=0, omega=0, m=1000)
    traj = simulate_freefall(initial, duration=1.0, dt=0.01)
    for s in traj:
        assert s.x == 0.0
        assert s.vx == 0.0


def test_rocket_step_returns_state():
    rocket = Rocket(State(x=0, y=10, vx=0, vy=0, theta=0, omega=0, m=100))
    result = rocket.step(0.01)
    assert isinstance(result, State)


# --- RK4 physics validation ---

def test_freefall_matches_analytic():
    """RK4 free-fall should match y(t) = y0 - ½g*t² to within 1 cm."""
    g, y0, t, dt = 9.81, 100.0, 2.0, 0.001
    initial = State(x=0, y=y0, vx=0, vy=0, theta=0, omega=0, m=1000)
    traj = simulate_freefall(initial, duration=t, dt=dt)
    assert abs(traj[-1].y - (y0 - 0.5 * g * t ** 2)) < 0.01


def test_vertical_thrust_accelerates_upward():
    """Upward thrust on an upright rocket should produce net upward acceleration."""
    params = RocketParams(dry_mass=0.0, isp=300.0)
    rocket = Rocket(State(x=0, y=0, vx=0, vy=0, theta=0, omega=0, m=1000.0), params)
    state = rocket.step(dt=1.0, thrust=20_000.0, gimbal=0.0)
    assert state.vy > 0


def test_gimbal_creates_clockwise_torque():
    """Positive gimbal on an upright, thrusting rocket should produce CW (negative) angular velocity."""
    params = RocketParams(dry_mass=0.0, isp=300.0)
    rocket = Rocket(State(x=0, y=100, vx=0, vy=0, theta=0, omega=0, m=1000.0), params)
    state = rocket.step(dt=0.1, thrust=10_000.0, gimbal=0.1)
    assert state.omega < 0


def test_thrust_depletes_mass():
    """Firing the engine should reduce the rocket's mass."""
    params = RocketParams(dry_mass=0.0, isp=300.0)
    rocket = Rocket(State(x=0, y=100, vx=0, vy=0, theta=0, omega=0, m=1000.0), params)
    state = rocket.step(dt=1.0, thrust=10_000.0, gimbal=0.0)
    assert state.m < 1000.0


def test_no_thrust_no_mass_change():
    """With zero thrust, mass should stay constant."""
    initial = State(x=0, y=100, vx=0, vy=0, theta=0, omega=0, m=1000.0)
    traj = simulate_freefall(initial, duration=2.0, dt=0.01)
    for s in traj:
        assert s.m == 1000.0
