"""Truly responsive HUD with GridSpec layout and dynamic sizing."""

import numpy as np
from matplotlib.patches import Circle, FancyBboxPatch

from physics import ControllerOutput, State


class TrulyResponsiveHUD:
    """HUD that genuinely adapts to window size using GridSpec."""

    def __init__(self, fig, gs):
        """Initialize with matplotlib figure and GridSpec."""
        self.fig = fig
        self.gs = gs

        # Create axes using GridSpec
        self.ax_title = fig.add_subplot(gs[0, :])
        self.ax_metrics = fig.add_subplot(gs[1, :])
        self.ax_secondary = fig.add_subplot(gs[2, :])
        self.ax_bars = fig.add_subplot(gs[3, :])
        self.ax_gimbal = fig.add_subplot(gs[4, 0])
        self.ax_status = fig.add_subplot(gs[4, 1:])
        self.ax_controls = fig.add_subplot(gs[5, :])

        # Style all axes
        for ax in [
            self.ax_title,
            self.ax_metrics,
            self.ax_secondary,
            self.ax_bars,
            self.ax_gimbal,
            self.ax_status,
            self.ax_controls,
        ]:
            ax.set_facecolor("#0a0e1a")
            ax.set_xlim(0, 10)
            ax.set_ylim(0, 10)
            ax.axis("off")

        # ===== TITLE =====
        self.ax_title.text(
            5,
            5,
            "◆ MISSION CONTROL ◆",
            ha="center",
            va="center",
            fontsize=14,
            fontweight="bold",
            color="#00ffff",
        )
        title_box = FancyBboxPatch(
            (0.2, 2),
            9.6,
            6,
            boxstyle="round,pad=0.4",
            edgecolor="#00ffff",
            facecolor="#001a33",
            linewidth=2,
            alpha=0.9,
        )
        self.ax_title.add_patch(title_box)

        # ===== METRICS CARDS =====
        self._create_metric_card(self.ax_metrics, 2, 5, "ALT", "#00d4ff", "alt_value")
        self._create_metric_card(self.ax_metrics, 5, 5, "VEL", "#ff6b9d", "vel_value")
        self._create_metric_card(self.ax_metrics, 8, 5, "ATT", "#ffd700", "att_value")

        # ===== SECONDARY INFO =====
        self.time_text = self.ax_secondary.text(
            1.5, 8, "T+0.00s", fontsize=7, color="#88ccff", fontweight="bold"
        )
        self.fuel_text = self.ax_secondary.text(
            3.5, 8, "FUEL: 15000 kg", fontsize=7, color="#88ff88", fontweight="bold"
        )
        self.omega_text = self.ax_secondary.text(
            6, 8, "ω: 0.000 rad/s", fontsize=7, color="#ffaa88", fontweight="bold"
        )
        self.control_text = self.ax_secondary.text(
            1.5, 4, "Thrust: 0 N | Gimbal: 0.0°", fontsize=6, color="#cccccc", family="monospace"
        )

        secondary_box = FancyBboxPatch(
            (0.1, 1),
            9.8,
            8.5,
            boxstyle="round,pad=0.3",
            edgecolor="#333333",
            facecolor="none",
            linewidth=0.5,
            alpha=0.5,
        )
        self.ax_secondary.add_patch(secondary_box)

        # ===== POWER BARS =====
        # Fuel bar
        self.ax_bars.text(0.5, 7, "FUEL", fontsize=7, color="#888888", fontweight="bold")
        self.fuel_bar_fill = FancyBboxPatch(
            (1.5, 5.5),
            0.5,
            3,
            boxstyle="round,pad=0.1",
            edgecolor="none",
            facecolor="#00d4ff",
            linewidth=0,
            alpha=0.9,
        )
        self.ax_bars.add_patch(self.fuel_bar_fill)
        fuel_bg = FancyBboxPatch(
            (1.5, 5.5),
            5,
            3,
            boxstyle="round,pad=0.1",
            edgecolor="#333333",
            facecolor="none",
            linewidth=0.5,
            alpha=0.5,
        )
        self.ax_bars.add_patch(fuel_bg)
        self.fuel_percent = self.ax_bars.text(
            7, 7, "0%", fontsize=7, color="#00d4ff", fontweight="bold"
        )

        # Thrust bar
        self.ax_bars.text(0.5, 2, "THRUST", fontsize=7, color="#888888", fontweight="bold")
        self.thrust_bar_fill = FancyBboxPatch(
            (1.5, 0.5),
            0.5,
            3,
            boxstyle="round,pad=0.1",
            edgecolor="none",
            facecolor="#ff6b9d",
            linewidth=0,
            alpha=0.9,
        )
        self.ax_bars.add_patch(self.thrust_bar_fill)
        thrust_bg = FancyBboxPatch(
            (1.5, 0.5),
            5,
            3,
            boxstyle="round,pad=0.1",
            edgecolor="#333333",
            facecolor="none",
            linewidth=0.5,
            alpha=0.5,
        )
        self.ax_bars.add_patch(thrust_bg)
        self.thrust_percent = self.ax_bars.text(
            7, 2, "0%", fontsize=7, color="#ff6b9d", fontweight="bold"
        )

        # ===== GIMBAL =====
        gimbal_box = FancyBboxPatch(
            (0.2, 1),
            9.6,
            8,
            boxstyle="round,pad=0.3",
            edgecolor="#333333",
            facecolor="none",
            linewidth=0.5,
            alpha=0.5,
        )
        self.ax_gimbal.add_patch(gimbal_box)

        self.ax_gimbal.text(
            5, 8, "GIMBAL", ha="center", fontsize=8, color="#888888", fontweight="bold"
        )

        gimbal_dial = Circle((5, 5), 2.5, facecolor="#1a2a3a", edgecolor="#ffd700", linewidth=2)
        self.ax_gimbal.add_patch(gimbal_dial)

        self.gimbal_needle = self.ax_gimbal.plot([5, 5], [5, 7.5], color="#ffd700", linewidth=2)[0]
        self.gimbal_value = self.ax_gimbal.text(
            5, 1.5, "0.0°", ha="center", fontsize=7, color="#ffd700", fontweight="bold"
        )

        # ===== STATUS =====
        status_box = FancyBboxPatch(
            (0.2, 1),
            9.6,
            8,
            boxstyle="round,pad=0.3",
            edgecolor="#333333",
            facecolor="none",
            linewidth=0.5,
            alpha=0.5,
        )
        self.ax_status.add_patch(status_box)

        self.status_indicator = self.ax_status.text(
            5, 6, "● NOMINAL", ha="center", fontsize=10, fontweight="bold", color="#00ff00"
        )

        # ===== CONTROLS =====
        self.ax_controls.text(
            5, 8, "CONTROLS", ha="center", fontsize=9, fontweight="bold", color="#ffffff"
        )

        self.ax_controls.text(
            5,
            4,
            "⬆️ / ⬇️ THRUST  │  ⬅️ / ➡️ GIMBAL  │  A AUTO  │  SPACE PAUSE  │  R RESET  │  Q QUIT",
            ha="center",
            fontsize=6,
            color="#cccccc",
        )

        self.ax_controls.text(
            5, 1, "🟢 Safe  •  🟡 Warning  •  🔴 Critical", ha="center", fontsize=6, color="#888888"
        )

        # Connect to resize event
        self.fig.canvas.mpl_connect("resize_event", self._on_resize)

    def _create_metric_card(self, ax, x, y, label, color, attr_name):
        """Create a single metric card."""
        card = FancyBboxPatch(
            (x - 1.3, y - 2),
            2.6,
            4,
            boxstyle="round,pad=0.2",
            edgecolor="#333333",
            facecolor="none",
            linewidth=0.5,
            alpha=0.5,
        )
        ax.add_patch(card)

        value_text = ax.text(
            x, y + 0.5, "0.0", ha="center", va="center", fontsize=10, fontweight="bold", color=color
        )
        setattr(self, f"{attr_name}_text", value_text)

        ax.text(x, y - 1.2, label, ha="center", va="center", fontsize=6, color="#888888")

    def _on_resize(self, event):
        """Handle window resize events."""
        self.fig.tight_layout()

    def update(self, state: State, control: ControllerOutput, time: float):
        """Update all display elements."""
        # Metrics
        alt_color = self._get_altitude_color(state.y)
        vel_color = self._get_velocity_color(state.vy)

        self.alt_value_text.set_text(f"{state.y:.0f}")
        self.alt_value_text.set_color(alt_color)

        self.vel_value_text.set_text(f"{state.vy:.1f}")
        self.vel_value_text.set_color(vel_color)

        self.att_value_text.set_text(f"{np.degrees(state.theta):.1f}°")

        # Secondary
        self.time_text.set_text(f"T+{time:.2f}s")
        self.fuel_text.set_text(f"FUEL: {state.m:,.0f} kg")
        self.omega_text.set_text(f"ω: {state.omega:.3f} rad/s")
        self.control_text.set_text(
            f"Thrust: {control.thrust:,.0f} N  |  Gimbal: {np.degrees(control.gimbal):.1f}°"
        )

        # Fuel bar
        fuel_percent = ((state.m - 100) / (15000 - 100)) * 100
        fuel_percent = max(0, min(100, fuel_percent))
        fuel_width = (fuel_percent / 100) * 5
        self.fuel_bar_fill.set_width(fuel_width)
        fuel_color = self._get_fuel_color(fuel_percent)
        self.fuel_bar_fill.set_facecolor(fuel_color)
        self.fuel_percent.set_text(f"{fuel_percent:.0f}%")
        self.fuel_percent.set_color(fuel_color)

        # Thrust bar
        thrust_percent = (control.thrust / 30000) * 100
        thrust_width = (thrust_percent / 100) * 5
        self.thrust_bar_fill.set_width(thrust_width)
        thrust_color = self._get_thrust_color(control.thrust)
        self.thrust_bar_fill.set_facecolor(thrust_color)
        self.thrust_percent.set_text(f"{thrust_percent:.0f}%")
        self.thrust_percent.set_color(thrust_color)

        # Gimbal
        gimbal_angle = np.degrees(control.gimbal)
        self.gimbal_value.set_text(f"{gimbal_angle:.1f}°")
        angle_rad = control.gimbal
        x_end = 5 + 2.5 * np.sin(angle_rad)
        y_end = 5 + 2.5 * np.cos(angle_rad)
        self.gimbal_needle.set_data([5, x_end], [5, y_end])

        # Status
        warnings = []
        if state.y <= 0:
            warnings.append("LANDED")
            status_color = "#00ff00"
        elif state.y < 50:
            warnings.append("CRIT ALT")
            status_color = "#ff3333"
        elif abs(state.vy) > 25:
            warnings.append("HIGH DESCENT")
            status_color = "#ffaa00"
        elif state.m < 200:
            warnings.append("LOW FUEL")
            status_color = "#ffaa00"
        else:
            status_color = "#00ff00"

        status_text = "● " + " / ".join(warnings) if warnings else "● NOMINAL"
        self.status_indicator.set_text(status_text)
        self.status_indicator.set_color(status_color)

        self.fig.canvas.draw_idle()

    def _get_altitude_color(self, alt: float) -> str:
        if alt > 500:
            return "#00ffff"
        if alt > 200:
            return "#ffaa00"
        return "#ff6b9d"

    def _get_velocity_color(self, vel: float) -> str:
        descent = abs(vel)
        if descent < 5:
            return "#00ff00"
        if descent < 15:
            return "#ffaa00"
        return "#ff6b9d"

    def _get_fuel_color(self, percent: float) -> str:
        if percent > 50:
            return "#00d4ff"
        if percent > 20:
            return "#ffaa00"
        return "#ff6b9d"

    def _get_thrust_color(self, thrust: float) -> str:
        if thrust < 5000:
            return "#666666"
        if thrust < 20000:
            return "#ffaa00"
        return "#ff6b9d"
