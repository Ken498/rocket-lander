"""
Rocket dynamics — STUB.

The physicist owns this file. This stub exists only so the CS-side
animation, repo plumbing, and demos can be developed in parallel during
Week 1. It implements gravity-only Euler integration, which is wrong
on purpose: it's a placeholder that should be replaced with a proper
RK4 integrator that supports thrust and gimbaled torque.

DO NOT BUILD ON TOP OF THIS. Replace it.
"""

from __future__ import annotations

import numpy as np

from .state import State

GRAVITY = 9.81  # m/s^2


class Rocket:
    """Placeholder rocket. Physicist will replace this in Week 1."""

    def __init__(self, state: State) -> None:
        self.state = state

    def step(self, dt: float, thrust: float = 0.0, gimbal: float = 0.0) -> State:
        """
        Advance the state by `dt` seconds.

        STUB: ignores thrust and gimbal, applies gravity only via forward Euler.
        Real version (physicist): RK4 integrator, force balance with thrust,
        torque about COM from gimbal, mass depletion via Tsiolkovsky.
        """
        s = self.state
        s.vy -= GRAVITY * dt
        s.x += s.vx * dt
        s.y += s.vy * dt
        s.theta += s.omega * dt
        return s


def simulate_freefall(
    initial_state: State,
    duration: float = 5.0,
    dt: float = 1.0 / 60.0,
) -> list[State]:
    """
    Run the stub rocket forward and return the trajectory as a list of States.

    Used by examples/freefall_demo.py to exercise the animator without
    needing the real physics implementation.
    """
    rocket = Rocket(initial_state)
    n_steps = int(np.ceil(duration / dt))
    trajectory: list[State] = [State.from_array(rocket.state.to_array())]
    for _ in range(n_steps):
        rocket.step(dt)
        trajectory.append(State.from_array(rocket.state.to_array()))
        if rocket.state.y <= 0:
            break
    return trajectory
