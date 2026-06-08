"""Run the 3D LQR simulation and save the trajectory to JSON.

Run from project root:
    python -m viz.export_trajectory
    python -m viz.export_trajectory --x0 80 --y0 1200 --output my_traj.json
"""

from __future__ import annotations

import argparse
import json

from viz.sim_runner3d import run_simulation


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--x0", type=float, default=50.0)
    parser.add_argument("--y0", type=float, default=1000.0)
    parser.add_argument("--z0", type=float, default=0.0)
    parser.add_argument("--output", type=str, default="trajectory.json")
    args = parser.parse_args()

    print(f"[export_trajectory] Simulating x0={args.x0} y0={args.y0} z0={args.z0} ...")
    traj = run_simulation(x0=args.x0, y0=args.y0, z0=args.z0)
    with open(args.output, "w") as f:
        json.dump(traj, f)
    print(f"[export_trajectory] Saved {len(traj)} frames → {args.output}")


main()
