"""
Rocket dynamics with RK4 integrator.

Equations of motion (2D, Phase 1):
  - Force balance: gimbaled thrust + gravity
  - Torque about COM from gimbaled engine
  - Mass depletion via Tsiolkovsky rocket equation

Coordinate conventions:
  - theta = 0: rocket pointing straight up; positive = CCW
  - gimbal: nozzle deflection angle from body axis, CCW positive
  - Positive gimbal creates a leftward thrust force and CW (negative) torque

State: [x, y, vx, vy, theta, omega, m]  (see state.py)

NO CHANGES from original — this file was correct.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .state import State

GRAVITY = 9.81  # m/s²
G0 = 9.81  # standard gravity used in Isp → mass-flow conversion


@dataclass
class RocketParams:
    """Physical constants that define the rocket."""

    dry_mass: float = 100.0  # kg  — mass when tank is empty
    body_length: float = 20.0  # m   — used for thin-rod moment of inertia
    nozzle_arm: float = 10.0  # m   — distance from COM to nozzle
    isp: float = 300.0  # s   — specific impulse


def _inertia(m: float, params: RocketParams) -> float:
    """Moment of inertia: thin-rod approximation, I = m * L² / 12."""
    return m * params.body_length**2 / 12.0


def _derivatives(
    state: np.ndarray,
    params: RocketParams,
    thrust: float,
    gimbal: float,
) -> np.ndarray:
    """Return d(state)/dt for the 2D rocket EOM."""
    _, _, vx, vy, theta, omega, m = state

    effective_thrust = 0.0 if m <= params.dry_mass else thrust

    # Thrust force: body axis rotated by gimbal angle, in world frame.
    # body_up at angle theta from vertical = R_CCW(theta) * [0,1] = (-sin θ, cos θ)
    # Gimbaled: direction = R_CCW(theta + gimbal) * [0,1]
    thrust_angle = theta + gimbal
    ax = effective_thrust * (-np.sin(thrust_angle)) / m
    ay = effective_thrust * np.cos(thrust_angle) / m - GRAVITY

    # Torque about COM from gimbaled engine.
    # tau = -arm * F * sin(gimbal)  (derived from r_nozzle × F_thrust)
    inertia = _inertia(m, params)
    alpha = -params.nozzle_arm * effective_thrust * np.sin(gimbal) / inertia

    # Tsiolkovsky mass flow: ṁ = -F / (Isp * g0)
    mdot = -effective_thrust / (params.isp * G0)

    return np.array([vx, vy, ax, ay, omega, alpha, mdot])


def _rk4_step(
    state: np.ndarray,
    params: RocketParams,
    dt: float,
    thrust: float,
    gimbal: float,
) -> np.ndarray:
    """Advance state by dt using 4th-order Runge-Kutta."""
    k1 = _derivatives(state, params, thrust, gimbal)
    k2 = _derivatives(state + 0.5 * dt * k1, params, thrust, gimbal)
    k3 = _derivatives(state + 0.5 * dt * k2, params, thrust, gimbal)
    k4 = _derivatives(state + dt * k3, params, thrust, gimbal)
    return state + (dt / 6.0) * (k1 + 2.0 * k2 + 2.0 * k3 + k4)


class Rocket:
    """2D rocket with RK4 integration."""

    def __init__(self, state: State, params: RocketParams | None = None) -> None:
        self.state = state
        self.params = params if params is not None else RocketParams()

    def step(self, dt: float, thrust: float = 0.0, gimbal: float = 0.0) -> State:
        """Advance the simulation by dt seconds."""
        arr = _rk4_step(self.state.to_array(), self.params, dt, thrust, gimbal)
        arr[6] = max(arr[6], self.params.dry_mass)  # clamp mass at dry_mass
        self.state = State.from_array(arr)
        return self.state


def simulate_freefall(
    initial_state: State,
    duration: float = 5.0,
    dt: float = 1.0 / 60.0,
    params: RocketParams | None = None,
) -> list[State]:
    """
    Run a gravity-only (thrust=0) simulation.

    Used by examples/freefall_demo.py and for validating against
    the analytical solution y(t) = y0 + vy0*t - ½g*t².
    """
    rocket = Rocket(initial_state, params)
    n_steps = int(np.ceil(duration / dt))
    trajectory: list[State] = [State.from_array(rocket.state.to_array())]
    for _ in range(n_steps):
        rocket.step(dt)
        trajectory.append(State.from_array(rocket.state.to_array()))
        if rocket.state.y <= 0:
            break
    return trajectory
