"""Week 2 — Manual flight simulator (keyboard controlled).
Up = thrust  |  Left / Right = gimbal tilt
"""

from __future__ import annotations

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.animation import FuncAnimation

from physics.rocket import Rocket, RocketParams
from physics.state import State

# ── simulation constants ──────────────────────────────────────────────────────
DT = 1 / 30  # fixed physics timestep (s)
MAX_THRUST = 20_000  # N   (T/W ≈ 2 at 1 000 kg starting mass)
MAX_GIMBAL = 0.26  # rad (≈ 15°)

# ── keyboard state ────────────────────────────────────────────────────────────
keys_held: set[str] = set()


def on_key_press(event) -> None:
    keys_held.add(event.key)


def on_key_release(event) -> None:
    keys_held.discard(event.key)


# ── figure + event wiring ─────────────────────────────────────────────────────
fig, ax = plt.subplots(figsize=(6, 9))
fig.canvas.mpl_connect("key_press_event", on_key_press)
fig.canvas.mpl_connect("key_release_event", on_key_release)

# ── rocket ────────────────────────────────────────────────────────────────────
rocket = Rocket(
    state=State(x=0.0, y=150.0, vx=0.0, vy=0.0, theta=0.0, omega=0.0, m=1000.0),
    params=RocketParams(),
)


# ── main animation loop ───────────────────────────────────────────────────────
def update(frame: int) -> None:
    s = rocket.state

    # ── 1. keyboard → commands ────────────────────────────────────────────────
    thrust = MAX_THRUST if "up" in keys_held else 0.0
    if "left" in keys_held and "right" not in keys_held:
        gimbal = -MAX_GIMBAL
    elif "right" in keys_held and "left" not in keys_held:
        gimbal = MAX_GIMBAL
    else:
        gimbal = 0.0

    # ── 2. physics step ───────────────────────────────────────────────────────
    if s.y > 0:
        rocket.step(DT, thrust, gimbal)
        s = rocket.state  # refresh — step() replaces rocket.state

    # ── 3. draw ───────────────────────────────────────────────────────────────
    ax.cla()
    ax.set_facecolor("#0d0d1a")
    ax.set_xlim(s.x - 60, s.x + 60)
    ax.set_ylim(max(-5, s.y - 40), s.y + 80)
    ax.set_aspect("equal")

    # ground + landing pad
    ax.axhline(0, color="#555", lw=1)
    ax.plot([-5, 5], [0, 0], color="gold", lw=4, solid_capstyle="round", zorder=5)

    # body-frame → world-frame helper
    ct, st = np.cos(s.theta), np.sin(s.theta)

    def w(bx, by):
        return ct * bx - st * by + s.x, st * bx + ct * by + s.y

    # rocket body (rectangle)
    hw, hh = 1.5, 10.0
    bpts = [(-hw, -hh), (hw, -hh), (hw, hh), (-hw, hh)]
    xs, ys = zip(*[w(bx, by) for bx, by in bpts], strict=True)
    ax.fill(xs, ys, color="#4a90d9", zorder=3)

    # nose cone (triangle)
    nl, nr, nt = w(-hw, hh), w(hw, hh), w(0, hh + 4)
    ax.fill([nl[0], nr[0], nt[0]], [nl[1], nr[1], nt[1]], color="#e05252", zorder=3)

    # thrust arrow — only when engine is firing
    if thrust > 0:
        nx, ny = w(0, -hh)
        ta = s.theta + gimbal
        alen = (thrust / MAX_THRUST) * 22
        ax.annotate(
            "",
            xy=(nx - np.sin(ta) * alen, ny + np.cos(ta) * alen),
            xytext=(nx, ny),
            arrowprops=dict(arrowstyle="->", color="#ff6600", lw=2.5),
            zorder=4,
        )

    # ── 4. HUD overlay ────────────────────────────────────────────────────────
    fuel = max(0.0, s.m - rocket.params.dry_mass)
    ax.text(
        0.02,
        0.98,
        f"ALT  {s.y:8.1f} m\n"
        f"VX   {s.vx:8.1f} m/s\n"
        f"VY   {s.vy:8.1f} m/s\n"
        f"θ    {np.degrees(s.theta):8.1f} °\n"
        f"FUEL {fuel:8.1f} kg\n"
        f"THR  {int(thrust):8d} N",
        transform=ax.transAxes,
        color="#00ff88",
        fontsize=8,
        family="monospace",
        va="top",
        bbox=dict(boxstyle="round", fc="#000010", alpha=0.7),
    )
    print(keys_held)  # ← remove once keys are confirmed working


ani = FuncAnimation(fig, update, interval=int(DT * 1000), cache_frame_data=False)
plt.show()
