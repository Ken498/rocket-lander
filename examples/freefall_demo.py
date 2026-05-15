"""Week 1 deliverable: rocket falls under gravity in a Matplotlib window.

Wires the physicist's `simulate_freefall` into the CS-side animator.
Run with:  python examples/freefall_demo.py
"""

from __future__ import annotations

import matplotlib.pyplot as plt

from physics import State, simulate_freefall
from viz import animate_rocket


def main() -> None:
    dt = 1.0 / 60.0
    duration = 20.0  # plenty long; simulate_freefall stops at ground

    initial_state = State(
        x=0.0,
        y=1000.0,
        vx=0.0,
        vy=0.0,
        theta=0.0,
        omega=0.0,
        m=550.0,
    )

    trajectory = simulate_freefall(initial_state, duration=duration, dt=dt)

    # Sanity check against analytical free fall: vy(t) = -g * t.
    final_t = (len(trajectory) - 1) * dt
    expected_vy = -9.81 * final_t
    print(f"Sim ended after {final_t:.2f} s")
    print(f"Final y  = {trajectory[-1].y:7.2f} m")
    print(f"Final vy = {trajectory[-1].vy:7.2f} m/s  (analytical: {expected_vy:.2f})")

    anim = animate_rocket(  # noqa: F841  (keeps animation alive for plt.show)
        trajectory,
        dt,
        xlim=(-50, 50),
        ylim=(0, 1100),
        rocket_height=30.0,
        title="Rocket free-fall demo",
        equal_aspect=False,
    )
    plt.show()


if __name__ == "__main__":
    main()
