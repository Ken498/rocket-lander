"""
Landing demo. Drops a rocket from 200 m and uses a PID autopilot with
gravity feedforward to execute a smooth, propulsive landing.

Control strategy
----------------
Altitude (thrust):
  A gravity feedforward (m·g) handles the weight; the PID only corrects
  the error dynamics. The gain ratio kp/kd defines the guidance profile:

    vy*(y) = -(kp/kd) · y

  so descent rate is proportional to altitude — the rocket slows
  automatically as it approaches the ground.

  kp=200, kd=1000 → vy*(200) ≈ -40 m/s, vy*(5) ≈ -1 m/s.
  Damping ratio ζ ≈ 1.12 (overdamped, no oscillation).

Attitude (gimbal):
  Standard PD to null the tilt angle.

Run:
    python examples/landing_demo.py
"""

import math

from physics import PIDController, PIDGains, Rocket, RocketParams, State
from viz import animate

GRAVITY = 9.81     # m/s²
MAX_THRUST = 30_000.0  # N
MAX_GIMBAL = 0.3       # rad  (~17°)


def main() -> None:
    params = RocketParams(dry_mass=100.0, body_length=20.0, nozzle_arm=10.0, isp=300.0)

    initial = State(
        x=0.0,
        y=200.0,
        vx=0.0,
        vy=0.0,
        theta=math.radians(3),  # 3° tilt
        omega=0.0,
        m=1000.0,
    )

    # Allow negative output so feedforward can reduce thrust below m·g.
    altitude_pid = PIDController(
        PIDGains(kp=200.0, ki=0.0, kd=1000.0),
        output_limits=(-MAX_THRUST, MAX_THRUST),
    )
    attitude_pid = PIDController(
        PIDGains(kp=5000.0, ki=0.0, kd=500.0),
        output_limits=(-MAX_GIMBAL, MAX_GIMBAL),
    )

    dt = 1.0 / 60.0
    rocket = Rocket(initial, params)
    trajectory = [State.from_array(rocket.state.to_array())]

    for _ in range(int(40.0 / dt)):
        s = rocket.state
        pid_correction = altitude_pid.update(0.0 - s.y, dt)
        thrust = min(MAX_THRUST, max(0.0, pid_correction + s.m * GRAVITY))
        gimbal = attitude_pid.update(0.0 - s.theta, dt)
        rocket.step(dt, thrust=thrust, gimbal=gimbal)
        trajectory.append(State.from_array(rocket.state.to_array()))
        if rocket.state.y <= 0.0:
            break

    final = trajectory[-1]
    t_land = len(trajectory) * dt
    print(f"Landed after {t_land:.1f} s  ({len(trajectory)} frames)")
    print(f"Touchdown: y={final.y:.2f} m  vy={final.vy:.2f} m/s  θ={math.degrees(final.theta):.2f}°")
    animate(trajectory, dt=dt, ylim=(0, 220))


if __name__ == "__main__":
    main()
