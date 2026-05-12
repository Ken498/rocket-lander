"""
Matplotlib animation utility for 2D rocket states.

API:
    animate(states, dt=1/60)              # play live
    animate(states, dt=1/60, save="x.gif") # render to file

`states` is any iterable of State objects (see physics/state.py). The
animation draws the rocket as a rotated rectangle plus a thrust-vector
arrow placeholder, with a ground line at y=0 and a small landing pad
at the origin.

This is intentionally minimal. Phase 2 swaps the whole thing for Three.js.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.animation import FuncAnimation
from matplotlib.patches import Rectangle

from physics.state import State

# Visual constants — purely cosmetic, tweak freely.
ROCKET_HEIGHT = 8.0  # m, for rendering only
ROCKET_WIDTH = 1.2  # m, for rendering only
PAD_WIDTH = 6.0  # m
GROUND_COLOR = "#3a3a3a"
ROCKET_COLOR = "#dddddd"
PAD_COLOR = "#888888"
SKY_TOP = "#0a1628"
SKY_BOTTOM = "#1a3550"


def _rocket_corners(state: State) -> np.ndarray:
    """Return the 4 corners of the rocket rectangle, rotated by theta about its base."""
    w, h = ROCKET_WIDTH, ROCKET_HEIGHT
    # Rocket coords with origin at the base (between the legs)
    local = np.array(
        [
            [-w / 2, 0],
            [w / 2, 0],
            [w / 2, h],
            [-w / 2, h],
        ]
    )
    c, s = np.cos(state.theta), np.sin(state.theta)
    rot = np.array([[c, -s], [s, c]])
    world = (rot @ local.T).T + np.array([state.x, state.y])
    return world


def animate(
    states: Sequence[State],
    dt: float = 1.0 / 60.0,
    save: str | Path | None = None,
    figsize: tuple[float, float] = (6, 8),
    xlim: tuple[float, float] = (-50, 50),
    ylim: tuple[float, float] = (0, 120),
) -> FuncAnimation:
    """
    Animate a sequence of rocket states.

    Parameters
    ----------
    states : sequence of State
        Trajectory to play back. One frame per state.
    dt : float
        Wall-clock seconds between frames. 1/60 → 60 fps.
    save : str or Path, optional
        If given, save to this path (`.gif` or `.mp4`). If None, show interactively.
    figsize, xlim, ylim
        Plot configuration; defaults work for a 100 m drop.

    Returns
    -------
    FuncAnimation
        The animation object. Keep a reference to it or it'll get GC'd.
    """
    fig, ax = plt.subplots(figsize=figsize)
    ax.set_xlim(*xlim)
    ax.set_ylim(*ylim)
    ax.set_aspect("equal")
    ax.set_facecolor(SKY_BOTTOM)
    fig.patch.set_facecolor(SKY_TOP)
    ax.set_xlabel("x [m]", color="white")
    ax.set_ylabel("y [m]", color="white")
    ax.tick_params(colors="white")
    for spine in ax.spines.values():
        spine.set_color("white")

    # Ground
    ax.axhline(0, color=GROUND_COLOR, linewidth=2, zorder=1)
    # Landing pad
    pad = Rectangle(
        (-PAD_WIDTH / 2, -0.5),
        PAD_WIDTH,
        0.6,
        facecolor=PAD_COLOR,
        edgecolor="white",
        zorder=2,
    )
    ax.add_patch(pad)

    # Rocket polygon (we'll update its xy each frame)
    rocket_poly = plt.Polygon(
        _rocket_corners(states[0]),
        closed=True,
        facecolor=ROCKET_COLOR,
        edgecolor="black",
        zorder=3,
    )
    ax.add_patch(rocket_poly)

    # HUD text
    hud = ax.text(
        0.02,
        0.97,
        "",
        transform=ax.transAxes,
        color="white",
        family="monospace",
        verticalalignment="top",
        fontsize=10,
    )

    def update(frame: int):
        s = states[frame]
        rocket_poly.set_xy(_rocket_corners(s))
        speed = np.hypot(s.vx, s.vy)
        hud.set_text(
            f"t = {frame * dt:5.2f} s\n"
            f"alt = {s.y:6.1f} m\n"
            f"v   = {speed:5.1f} m/s\n"
            f"θ   = {np.degrees(s.theta):+5.1f}°\n"
            f"m   = {s.m:6.1f} kg"
        )
        return rocket_poly, hud

    anim = FuncAnimation(
        fig,
        update,
        frames=len(states),
        interval=dt * 1000,
        blit=True,
        repeat=False,
    )

    if save is not None:
        save_path = Path(save)
        if save_path.suffix == ".gif":
            anim.save(save_path, writer="pillow", fps=int(1 / dt))
        else:
            anim.save(save_path, fps=int(1 / dt))
        plt.close(fig)
    else:
        plt.show()

    return anim
