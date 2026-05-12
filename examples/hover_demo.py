"""
Hover demo. Starts a rocket at 100 m with a 5° tilt and lets the PID
autopilot stabilize attitude and hold altitude.

Run:
    python examples/hover_demo.py
"""

import math

from physics import PIDGains, Rocket, RocketParams, RocketPID, State
from viz import animate


def main() -> None:
    params = RocketParams(dry_mass=100.0, body_length=20.0, nozzle_arm=10.0, isp=300.0)

    initial = State(
        x=0.0,
        y=100.0,
        vx=0.0,
        vy=0.0,
        theta=math.radians(5),  # 5° tilt — controller must correct this
        omega=0.0,
        m=1000.0,
    )

    pid = RocketPID(
        altitude_gains=PIDGains(kp=50.0, ki=10.0, kd=200.0),
        attitude_gains=PIDGains(kp=5000.0, ki=0.0, kd=500.0),
        max_thrust=30_000.0,
        max_gimbal=0.3,
    )

    dt = 1.0 / 60.0
    duration = 15.0
    n_steps = int(duration / dt)

    rocket = Rocket(initial, params)
    trajectory = [State(*initial.__dict__.values())]

    for _ in range(n_steps):
        cmd = pid.update(rocket.state, target_altitude=100.0, target_theta=0.0, dt=dt)
        rocket.step(dt, thrust=cmd.thrust, gimbal=cmd.gimbal)
        trajectory.append(State(*vars(rocket.state).values()))

    final = trajectory[-1]
    print(f"Simulated {len(trajectory)} frames ({duration:.0f} s)")
    print(f"Final: y={final.y:.2f} m  vy={final.vy:.2f} m/s  θ={math.degrees(final.theta):.2f}°")
    animate(trajectory, dt=dt, ylim=(0, 150))


if __name__ == "__main__":
    main()
