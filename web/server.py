"""
FastAPI server: computes a landing trajectory and serves the Three.js frontend.

Run:
    pip install -e ".[web]"
    python -m web.server          # or: rocket-server
"""

from __future__ import annotations

import math
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from physics import PIDController, PIDGains, Rocket, RocketParams, State

GRAVITY = 9.81
MAX_THRUST = 30_000.0
MAX_GIMBAL = 0.3
STATIC_DIR = Path(__file__).parent / "static"

app = FastAPI(title="Rocket Lander")


@app.get("/api/trajectory")
def get_trajectory(
    y0: float = 200.0,
    theta0_deg: float = 3.0,
    duration: float = 40.0,
    dt: float = 1.0 / 60.0,
) -> JSONResponse:
    """Simulate a PID-guided landing and return the trajectory as a JSON array."""
    params = RocketParams(dry_mass=100.0, body_length=20.0, nozzle_arm=10.0, isp=300.0)
    initial = State(
        x=0.0, y=y0, vx=0.0, vy=0.0,
        theta=math.radians(theta0_deg), omega=0.0, m=1000.0,
    )

    altitude_pid = PIDController(
        PIDGains(kp=200.0, ki=0.0, kd=1000.0),
        output_limits=(-MAX_THRUST, MAX_THRUST),
    )
    attitude_pid = PIDController(
        PIDGains(kp=5000.0, ki=0.0, kd=500.0),
        output_limits=(-MAX_GIMBAL, MAX_GIMBAL),
    )

    rocket = Rocket(initial, params)
    records = []
    t = 0.0

    while t <= duration and rocket.state.y > 0.0:
        s = rocket.state
        correction = altitude_pid.update(-s.y, dt)
        thrust = min(MAX_THRUST, max(0.0, correction + s.m * GRAVITY))
        gimbal = attitude_pid.update(-s.theta, dt)

        records.append({
            "t":      round(t, 4),
            "x":      round(s.x, 3),
            "y":      round(s.y, 3),
            "vx":     round(s.vx, 4),
            "vy":     round(s.vy, 4),
            "theta":  round(s.theta, 5),
            "omega":  round(s.omega, 5),
            "m":      round(s.m, 2),
            "thrust": round(thrust, 1),
            "gimbal": round(gimbal, 5),
        })

        rocket.step(dt, thrust=thrust, gimbal=gimbal)
        t += dt

    return JSONResponse(records)


# Static files must be mounted AFTER API routes so /api/* is matched first.
app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")


def main() -> None:
    uvicorn.run("web.server:app", host="127.0.0.1", port=8000, reload=False)


if __name__ == "__main__":
    main()
