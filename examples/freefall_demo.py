"""
Free-fall demo. Drops a rocket from 100 m and animates it.

Run:
    python examples/freefall_demo.py

This is intentionally trivial — it exists to prove that the State + stub
Rocket + animator pipeline works end-to-end on day one. Real physics
(thrust, gimbal, RK4, fuel) replaces the stub later this week.
"""

from physics import State, simulate_freefall
from viz import animate


def main() -> None:
    initial = State(
        x=0.0,
        y=100.0,
        vx=0.0,
        vy=0.0,
        theta=0.0,
        omega=0.0,
        m=1000.0,
    )
    trajectory = simulate_freefall(initial, duration=10.0, dt=1.0 / 60.0)
    print(f"Simulated {len(trajectory)} frames")
    print(f"Final state: y={trajectory[-1].y:.2f} m, vy={trajectory[-1].vy:.2f} m/s")
    animate(trajectory, dt=1.0 / 60.0)


if __name__ == "__main__":
    main()
