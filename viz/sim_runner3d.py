"""
3D LQR simulation runner — Week 6.

Three usage modes
-----------------
1. **Run** – simulate a landing and return trajectory as a list of state dicts.
2. **Export** – embed the trajectory in a self-contained HTML file that can be
   opened directly in any browser without a server.
3. **Serve** – stream live state JSON over a WebSocket at ~60 Hz while the
   simulation runs (used by viz/server3d.py).

Quick start
-----------
    from viz.sim_runner3d import run_simulation, export_html

    traj = run_simulation(x0=50.0, z0=0.0)
    export_html(traj, "landing.html")
"""

from __future__ import annotations

import json
import math
import pathlib
import time
from typing import Any

import numpy as np

from physics.lqr3d import LQRController3D, LQRWeights3D
from physics.rocket3d import GRAVITY, ControlInput3D, Rocket3D, RocketParams3D
from physics.state3d import State3D

# ── Simulation constants ──────────────────────────────────────────────── #

DT: float = 1.0 / 60.0  # timestep [s]
MAX_STEPS: int = 18_000  # 300 s hard cap
LAMBDA: float = 0.03  # horizontal convergence rate [1/s]
DEFAULT_MASS: float = 1_000.0  # kg  initial total mass
DEFAULT_PARAMS = RocketParams3D(
    dry_mass=100.0,
    body_length=20.0,
    body_radius=1.0,
    nozzle_arm=10.0,
    isp=300.0,
)


# ══════════════════════════════════════════════════════════════════════ #
# Core simulator                                                         #
# ══════════════════════════════════════════════════════════════════════ #


def _state_to_dict(s: State3D, t: float, cmd: ControlInput3D) -> dict[str, Any]:
    """Convert a State3D snapshot + command into a JSON-serialisable dict."""
    return {
        "t": round(t, 4),
        # position
        "x": round(float(s.x), 4),
        "y": round(float(s.y), 4),
        "z": round(float(s.z), 4),
        # velocity
        "vx": round(float(s.vx), 4),
        "vy": round(float(s.vy), 4),
        "vz": round(float(s.vz), 4),
        # attitude quaternion
        "q0": round(float(s.q0), 6),
        "q1": round(float(s.q1), 6),
        "q2": round(float(s.q2), 6),
        "q3": round(float(s.q3), 6),
        # angular velocity
        "omega_x": round(float(s.omega_x), 6),
        "omega_y": round(float(s.omega_y), 6),
        "omega_z": round(float(s.omega_z), 6),
        # mass
        "m": round(float(s.m), 3),
        # control
        "thrust": round(float(cmd.thrust), 2),
        "gimbal_pitch": round(float(cmd.gimbal_pitch), 6),
        "gimbal_yaw": round(float(cmd.gimbal_yaw), 6),
        # derived
        "speed": round(float(math.sqrt(s.vx**2 + s.vy**2 + s.vz**2)), 4),
        "altitude": round(float(max(s.y, 0.0)), 4),
    }


def run_simulation(
    x0: float = 0.0,
    y0: float = 1_000.0,
    z0: float = 0.0,
    m0: float = DEFAULT_MASS,
    params: RocketParams3D | None = None,
    weights: LQRWeights3D | None = None,
    record_every: int = 1,
    on_step: Any = None,
) -> list[dict[str, Any]]:
    """
    Run a 3D LQR landing simulation and return the trajectory.

    Parameters
    ----------
    x0, y0, z0     : initial position [m]
    m0             : initial mass [kg]
    params         : rocket physical parameters (uses defaults if None)
    weights        : LQR cost weights (uses defaults if None)
    record_every   : save every N-th frame (1 = every frame at 60 Hz)
    on_step        : optional callback ``fn(frame_dict)`` called every recorded step
                     (used by the WebSocket server for live streaming)

    Returns
    -------
    trajectory : list of dicts, one per recorded step
    """
    if params is None:
        params = DEFAULT_PARAMS

    state = State3D(x=x0, y=y0, z=z0, m=m0)
    rocket = Rocket3D(state, params)
    lqr = LQRController3D(params, hover_mass=m0, weights=weights)

    trajectory: list[dict[str, Any]] = []
    t = 0.0
    hover_thrust = m0 * GRAVITY
    # Initial command for frame 0
    cmd0 = ControlInput3D(thrust=hover_thrust)
    trajectory.append(_state_to_dict(rocket.state, t, cmd0))
    if on_step is not None:
        on_step(trajectory[-1])

    for step in range(MAX_STEPS):
        s = rocket.state
        t += DT

        # ── Reference trajectory ──────────────────────────────────────── #
        x_ref = x0 * math.exp(-LAMBDA * t)
        z_ref = z0 * math.exp(-LAMBDA * t)
        vx_ref = -LAMBDA * x_ref
        vz_ref = -LAMBDA * z_ref

        # Soft descent profile: vy → 0 as y → 0
        vy_ref = -float(np.clip(0.25 * max(float(s.y), 0.0), 0.2, 5.0))

        cmd = lqr.update(
            s,
            target_x=x_ref,
            target_y=float(s.y),  # δy = 0 always; vy error drives altitude
            target_z=z_ref,
            target_vx=vx_ref,
            target_vy=vy_ref,
            target_vz=vz_ref,
        )
        rocket.step(DT, cmd=cmd)

        if (step + 1) % record_every == 0:
            frame = _state_to_dict(rocket.state, t, cmd)
            trajectory.append(frame)
            if on_step is not None:
                on_step(frame)

        if rocket.state.y <= 0.0:
            break

    return trajectory


# ══════════════════════════════════════════════════════════════════════ #
# HTML export                                                            #
# ══════════════════════════════════════════════════════════════════════ #


def export_html(
    trajectory: list[dict[str, Any]],
    output_path: str | pathlib.Path,
    title: str = "Rocket Lander 3D",
) -> pathlib.Path:
    """
    Embed *trajectory* into a self-contained HTML file.

    The viewer (viewer3d.html) is loaded from the same directory; its
    ``TRAJECTORY_DATA`` placeholder is replaced with the JSON payload.

    Parameters
    ----------
    trajectory  : list of frame dicts from run_simulation()
    output_path : where to write the HTML file
    title       : page <title>

    Returns
    -------
    Path to the written file.
    """
    output_path = pathlib.Path(output_path)

    viewer_path = pathlib.Path(__file__).parent / "viewer3d.html"
    if not viewer_path.exists():
        raise FileNotFoundError(
            f"viewer3d.html not found at {viewer_path}. "
            "Make sure viz/viewer3d.html exists alongside sim_runner3d.py."
        )

    template = viewer_path.read_text(encoding="utf-8")

    traj_json = json.dumps(trajectory, separators=(",", ":"))
    # Embed in a <script> block that the viewer reads from window.TRAJECTORY
    injection = f"<script>window.TRAJECTORY={traj_json};window.VIZ_MODE='replay';</script>"

    # Insert right before </head>
    if "</head>" in template:
        html = template.replace("</head>", injection + "\n</head>", 1)
    else:
        html = injection + template

    html = html.replace("<title>Rocket Lander 3D</title>", f"<title>{title}</title>")

    output_path.write_text(html, encoding="utf-8")
    return output_path


# ══════════════════════════════════════════════════════════════════════ #
# CLI entry point                                                        #
# ══════════════════════════════════════════════════════════════════════ #

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Run 3D LQR landing and export HTML.")
    parser.add_argument("--x0", type=float, default=50.0, help="Initial x offset [m]")
    parser.add_argument("--z0", type=float, default=0.0, help="Initial z offset [m]")
    parser.add_argument("--y0", type=float, default=1000.0, help="Initial altitude [m]")
    parser.add_argument(
        "--record-every",
        type=int,
        default=1,
        help="Save every Nth frame (1=60Hz, 2=30Hz, 3=20Hz). Larger N → smaller file.",
    )
    parser.add_argument("--out", default="landing3d.html", help="Output HTML path")
    args = parser.parse_args()

    print(f"Simulating: x0={args.x0}m  y0={args.y0}m  z0={args.z0}m …")
    t0 = time.perf_counter()
    traj = run_simulation(x0=args.x0, y0=args.y0, z0=args.z0, record_every=args.record_every)
    elapsed = time.perf_counter() - t0

    final = traj[-1]
    print(
        f"Done in {elapsed:.2f}s — {len(traj)} frames  "
        f"touchdown x={final['x']:.2f}m  z={final['z']:.2f}m  vy={final['vy']:.2f}m/s"
    )

    out = export_html(traj, args.out)
    print(f"Exported → {out}")
