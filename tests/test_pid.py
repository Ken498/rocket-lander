"""Unit tests for the PID autopilot."""

import math

import pytest

from physics import ControllerOutput, PIDGains, RocketPID, State
from physics.controller import PIDController


# --- PIDController unit tests ---

def test_proportional_only():
    pid = PIDController(PIDGains(kp=2.0, ki=0.0, kd=0.0))
    assert pid.update(5.0, dt=0.1) == pytest.approx(10.0)


def test_integral_accumulates():
    pid = PIDController(PIDGains(kp=0.0, ki=1.0, kd=0.0))
    pid.update(1.0, dt=0.1)  # integral = 0.1
    out = pid.update(1.0, dt=0.1)  # integral = 0.2
    assert out == pytest.approx(0.2)


def test_derivative_term():
    pid = PIDController(PIDGains(kp=0.0, ki=0.0, kd=1.0))
    pid.update(0.0, dt=0.1)          # first call: derivative = 0 (no spike)
    out = pid.update(1.0, dt=0.1)    # derivative = (1 - 0) / 0.1 = 10
    assert out == pytest.approx(10.0)


def test_no_derivative_spike_on_first_call():
    """First update should not produce a derivative spike regardless of error."""
    pid = PIDController(PIDGains(kp=0.0, ki=0.0, kd=100.0))
    assert pid.update(999.0, dt=0.1) == pytest.approx(0.0)


def test_output_clamped_high():
    pid = PIDController(PIDGains(kp=1.0, ki=0.0, kd=0.0), output_limits=(0.0, 10.0))
    assert pid.update(100.0, dt=0.1) == pytest.approx(10.0)


def test_output_clamped_low():
    pid = PIDController(PIDGains(kp=1.0, ki=0.0, kd=0.0), output_limits=(-10.0, 10.0))
    assert pid.update(-100.0, dt=0.1) == pytest.approx(-10.0)


def test_anti_windup_stops_integral_growth():
    """When saturated, the integral should not keep growing."""
    pid = PIDController(PIDGains(kp=0.0, ki=1.0, kd=0.0), output_limits=(0.0, 5.0))
    for _ in range(100):
        pid.update(10.0, dt=0.1)
    # If anti-windup works, integral is bounded; without it it would be 100.
    assert pid._integral < 10.0


def test_reset_clears_state():
    pid = PIDController(PIDGains(kp=1.0, ki=1.0, kd=1.0))
    pid.update(5.0, dt=0.1)
    pid.reset()
    assert pid._integral == 0.0
    assert pid._prev_error == 0.0
    assert not pid._initialized


# --- RocketPID integration tests ---

def _make_state(**kwargs) -> State:
    defaults = dict(x=0, y=100, vx=0, vy=0, theta=0, omega=0, m=1000)
    return State(**{**defaults, **kwargs})


def test_positive_altitude_error_produces_thrust():
    """Rocket below target → positive thrust."""
    pid = RocketPID(
        altitude_gains=PIDGains(kp=100.0, ki=0.0, kd=0.0),
        attitude_gains=PIDGains(kp=0.0, ki=0.0, kd=0.0),
    )
    out = pid.update(_make_state(y=50.0), target_altitude=100.0, dt=0.1)
    assert out.thrust > 0.0


def test_negative_altitude_error_clamps_to_zero():
    """Thrust can't be negative — rocket above target → zero thrust."""
    pid = RocketPID(
        altitude_gains=PIDGains(kp=100.0, ki=0.0, kd=0.0),
        attitude_gains=PIDGains(kp=0.0, ki=0.0, kd=0.0),
    )
    out = pid.update(_make_state(y=150.0), target_altitude=100.0, dt=0.1)
    assert out.thrust == pytest.approx(0.0)


def test_positive_theta_error_produces_negative_gimbal():
    """Rocket tilted CCW (theta > 0) → negative gimbal to correct."""
    pid = RocketPID(
        altitude_gains=PIDGains(kp=0.0, ki=0.0, kd=0.0),
        attitude_gains=PIDGains(kp=1000.0, ki=0.0, kd=0.0),
    )
    out = pid.update(_make_state(theta=0.1), target_altitude=100.0, target_theta=0.0, dt=0.1)
    assert out.gimbal < 0.0


def test_gimbal_clamped_to_max():
    pid = RocketPID(
        altitude_gains=PIDGains(kp=0.0, ki=0.0, kd=0.0),
        attitude_gains=PIDGains(kp=1e6, ki=0.0, kd=0.0),
        max_gimbal=0.3,
    )
    out = pid.update(_make_state(theta=1.0), target_altitude=100.0, target_theta=0.0, dt=0.1)
    assert out.gimbal == pytest.approx(-0.3)


def test_controller_output_type():
    pid = RocketPID(
        altitude_gains=PIDGains(kp=10.0, ki=0.0, kd=0.0),
        attitude_gains=PIDGains(kp=10.0, ki=0.0, kd=0.0),
    )
    out = pid.update(_make_state(), target_altitude=100.0, dt=0.1)
    assert isinstance(out, ControllerOutput)


def test_at_target_no_proportional_output():
    """At exactly the target (error=0, integral=0), P and I terms are zero."""
    pid = RocketPID(
        altitude_gains=PIDGains(kp=100.0, ki=0.0, kd=0.0),
        attitude_gains=PIDGains(kp=100.0, ki=0.0, kd=0.0),
    )
    out = pid.update(_make_state(y=100.0, theta=0.0), target_altitude=100.0, target_theta=0.0, dt=0.1)
    assert out.thrust == pytest.approx(0.0)
    assert out.gimbal == pytest.approx(0.0)
