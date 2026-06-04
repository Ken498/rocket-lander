"""Week 3 — PID autopilot landing with replay and randomise.

Run:
    python -m viz.pid_landing
"""

from __future__ import annotations

import matplotlib.pyplot as plt
import matplotlib.widgets as mwidgets
import numpy as np
from matplotlib.animation import FuncAnimation

from physics.controller import ControllerOutput, PIDGains, RocketPID
from physics.rocket import Rocket, RocketParams
from physics.state import State

# ── constants ─────────────────────────────────────────────────────────────────
DT = 1 / 60
MAX_STEPS = 7_000
HW, HH = 1.5, 10.0
PARAMS = RocketParams()

_ALT_GAINS = PIDGains(kp=500, ki=50, kd=100)
_ATT_GAINS = PIDGains(kp=5000, ki=0, kd=1000)


def run_landing(initial_state: State) -> list[tuple[State, ControllerOutput]]:
    pid = RocketPID(altitude_gains=_ALT_GAINS, attitude_gains=_ATT_GAINS)
    rocket = Rocket(state=initial_state, params=PARAMS)
    traj: list[tuple[State, ControllerOutput]] = []
    for _ in range(MAX_STEPS):
        s = rocket.state
        ctrl = pid.update(s, dt=DT)
        traj.append((s, ctrl))
        if s.y <= 0:
            break
        rocket.step(DT, ctrl.thrust, ctrl.gimbal)
    return traj


def _default_state() -> State:
    return State(x=50.0, y=1000.0, vx=0.0, vy=0.0, theta=0.0, omega=0.0, m=1000.0)


sim = {"trajectory": run_landing(_default_state()), "frame": 0}


fig, ax = plt.subplots(figsize=(6, 9))
plt.subplots_adjust(left=0.1, bottom=0.18, right=0.95, top=0.97)
fig.patch.set_facecolor("#0d0d1a")

ax_slider = fig.add_axes([0.10, 0.10, 0.75, 0.03])
ax_slider.set_facecolor("#1a1a2e")
ax_btn = fig.add_axes([0.87, 0.08, 0.10, 0.05])

slider = mwidgets.Slider(
    ax_slider, "Frame", 0, len(sim["trajectory"]) - 1, valinit=0, valstep=1, color="#4a90d9"
)
btn = mwidgets.Button(ax_btn, "Rnd", color="#1a1a2e", hovercolor="#2a3a5e")
btn.label.set_color("white")


def draw(s: State, ctrl: ControllerOutput, is_final: bool = False) -> None:
    ax.cla()
    ax.set_facecolor("#0d0d1a")
    ax.set_xlim(s.x - 60, s.x + 60)
    ax.set_ylim(max(-5, s.y - 40), s.y + 80)
    ax.set_aspect("equal")
    ax.tick_params(colors="#444")
    for spine in ax.spines.values():
        spine.set_edgecolor("#333")

    ax.axhline(0, color="#555", lw=1)
    ax.plot([-5, 5], [0, 0], color="gold", lw=4, solid_capstyle="round", zorder=5)

    # trajectory trail
    if sim["frame"] > 0:
        past = sim["trajectory"][: sim["frame"] : 5]
        ax.plot(
            [st.x for st, _ in past],
            [st.y for st, _ in past],
            color="#4a90d9",
            alpha=0.25,
            lw=1,
            zorder=1,
        )

    ct, st = np.cos(s.theta), np.sin(s.theta)

    def w(bx: float, by: float) -> tuple[float, float]:
        return ct * bx - st * by + s.x, st * bx + ct * by + s.y

    bpts = [(-HW, -HH), (HW, -HH), (HW, HH), (-HW, HH)]
    xs, ys = zip(*[w(bx, by) for bx, by in bpts], strict=True)
    ax.fill(xs, ys, color="#4a90d9", zorder=3)

    nl, nr, nt = w(-HW, HH), w(HW, HH), w(0, HH + 4)
    ax.fill([nl[0], nr[0], nt[0]], [nl[1], nr[1], nt[1]], color="#e05252", zorder=3)

    if ctrl.thrust > 100:
        nx, ny = w(0, -HH)
        ta = s.theta + ctrl.gimbal
        alen = (ctrl.thrust / PARAMS.dry_mass / 300) * 22
        ax.annotate(
            "",
            xy=(nx - np.sin(ta) * alen, ny + np.cos(ta) * alen),
            xytext=(nx, ny),
            arrowprops=dict(arrowstyle="->", color="#ff6600", lw=2.5),
            zorder=4,
        )

    fuel = max(0.0, s.m - PARAMS.dry_mass)
    ax.text(
        0.02,
        0.98,
        f"ALT  {s.y:8.1f} m\n"
        f"VX   {s.vx:8.1f} m/s\n"
        f"VY   {s.vy:8.1f} m/s\n"
        f"θ    {np.degrees(s.theta):8.1f} °\n"
        f"FUEL {fuel:8.1f} kg\n"
        f"THR  {ctrl.thrust:8.0f} N",
        transform=ax.transAxes,
        color="#00ff88",
        fontsize=8,
        family="monospace",
        va="top",
        bbox=dict(boxstyle="round", fc="#000010", alpha=0.7),
    )

    if is_final:
        miss = abs(s.x)
        ax.text(
            0.5,
            0.5,
            f"TOUCHDOWN\nmiss  {miss:.2f} m\nvy   {s.vy:.2f} m/s",
            transform=ax.transAxes,
            color="#00ff00" if miss < 1.0 else "#ff8800",
            fontsize=11,
            family="monospace",
            ha="center",
            va="center",
            bbox=dict(boxstyle="round", fc="#000020", alpha=0.85),
        )


def update(frame: int) -> None:
    traj = sim["trajectory"]
    if sim["frame"] < len(traj) - 1:
        sim["frame"] += 1
    is_final = sim["frame"] >= len(traj) - 1
    slider.eventson = False
    slider.set_val(sim["frame"])
    slider.eventson = True
    draw(*traj[sim["frame"]], is_final=is_final)


def on_slider_change(val: float) -> None:
    sim["frame"] = int(val)
    traj = sim["trajectory"]
    draw(*traj[sim["frame"]], is_final=sim["frame"] >= len(traj) - 1)


def on_randomize(event) -> None:  # noqa: ANN001
    rng = np.random.default_rng()
    x0 = float(rng.uniform(-80, 80))
    y0 = float(rng.uniform(600, 1200))
    vx0 = float(rng.uniform(-8, 8))
    sim["trajectory"] = run_landing(
        State(x=x0, y=y0, vx=vx0, vy=0.0, theta=0.0, omega=0.0, m=1000.0)
    )
    sim["frame"] = 0
    n = len(sim["trajectory"])
    slider.valmax = n - 1
    slider.ax.set_xlim(0, n - 1)
    slider.set_val(0)


slider.on_changed(on_slider_change)
btn.on_clicked(on_randomize)

ani = FuncAnimation(fig, update, interval=int(DT * 1000), cache_frame_data=False)
plt.show()
