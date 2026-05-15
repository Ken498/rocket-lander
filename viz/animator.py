"""Matplotlib animation for the 2D rocket simulator.

Consumes a sequence of `physics.State` objects and renders the rocket as a
rotating rectangle with a HUD panel beside the plot.
"""

from __future__ import annotations

from collections.abc import Sequence

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.animation import FuncAnimation
from matplotlib.patches import Polygon

from physics import State


def _rocket_corners(
    x: float,
    y: float,
    theta: float,
    width: float = 2.0,
    height: float = 20.0,
) -> np.ndarray:
    """4 world-frame corners of the rocket rectangle.

    Rocket points up along +y in its body frame; theta > 0 is CCW.
    """
    half_w, half_h = width / 2.0, height / 2.0
    local = np.array(
        [
            [-half_w, -half_h],
            [half_w, -half_h],
            [half_w, half_h],
            [-half_w, half_h],
        ]
    )
    c, s = np.cos(theta), np.sin(theta)
    rot = np.array([[c, -s], [s, c]])
    return (local @ rot.T) + np.array([x, y])


def animate_rocket(
    states: Sequence[State],
    dt: float,
    xlim: tuple[float, float] = (-50.0, 50.0),
    ylim: tuple[float, float] = (0.0, 1100.0),
    rocket_width: float = 2.0,
    rocket_height: float = 20.0,
    title: str = "Rocket — Week 1 free-fall",
    equal_aspect: bool = False,
) -> FuncAnimation:
    """Animate a trajectory of `State` objects.

    Args:
        states: One State per timestep, in order.
        dt: Physics timestep in seconds; sets playback speed.
        xlim, ylim: Plot axis limits in meters.
        rocket_width, rocket_height: Body dimensions in meters.
        title: Plot title.
        equal_aspect: If True, force 1 m of x to equal 1 m of y on screen
            (physically accurate but tall scenes look narrow). Defaults to
            False for Week 1 freefall; flip to True when the rocket starts
            actually tilting in later phases.

    Returns:
        The FuncAnimation. Caller should call plt.show().
    """
    if len(states) == 0:
        raise ValueError("states cannot be empty")

    # Two-pane layout: rocket plot on left, HUD panel on right.
    fig = plt.figure(figsize=(9, 8))
    gs = fig.add_gridspec(1, 2, width_ratios=[2, 1], wspace=0.15)
    ax = fig.add_subplot(gs[0, 0])
    hud_ax = fig.add_subplot(gs[0, 1])
    hud_ax.axis("off")

    ax.set_xlim(*xlim)
    ax.set_ylim(*ylim)
    if equal_aspect:
        ax.set_aspect("equal")
    ax.set_xlabel("x (m)")
    ax.set_ylabel("y (m)")
    ax.set_title(title)
    ax.grid(True, alpha=0.3)
    ax.axhline(0, color="brown", linewidth=2)  # ground

    s0 = states[0]
    rocket_patch = Polygon(
        _rocket_corners(s0.x, s0.y, s0.theta, rocket_width, rocket_height),
        closed=True,
        facecolor="gray",
        edgecolor="black",
    )
    ax.add_patch(rocket_patch)

    hud = hud_ax.text(
        0.0,
        0.95,
        "",
        transform=hud_ax.transAxes,
        va="top",
        ha="left",
        family="monospace",
        fontsize=11,
    )

    def update(frame: int):
        s = states[frame]
        rocket_patch.set_xy(_rocket_corners(s.x, s.y, s.theta, rocket_width, rocket_height))
        t = frame * dt
        hud.set_text(
            f"t     = {t:6.2f} s\n"
            f"y     = {s.y:8.2f} m\n"
            f"vy    = {s.vy:8.2f} m/s\n"
            f"theta = {np.degrees(s.theta):6.1f} deg\n"
            f"mass  = {s.m:8.1f} kg"
        )
        return rocket_patch, hud

    interval_ms = max(1, int(dt * 1000))
    return FuncAnimation(fig, update, frames=len(states), interval=interval_ms, blit=False)
