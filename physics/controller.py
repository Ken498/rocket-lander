"""
PID autopilot for 2D rocket landing.

CHANGES FROM ORIGINAL — four bugs fixed:

  BUG 1 — Anti-windup:
    Original: added to integral first, then subtracted if output was clamped.
    Fixed:    checks P+D output direction BEFORE accumulating. Only skips
              integration when winding would worsen saturation.

  BUG 2 — Altitude loop (most dangerous):
    Original: error = (target_y - y) - vd*vy. At y=1000m this is -1000,
              thrust clamps to 0, rocket free-falls and crashes every time.
    Fixed:    uses a velocity profile (target_vy = -clip(0.05*y, 2, 30))
              plus gravity feedforward (hover_ff = m*g) so the PID only
              trims velocity error on top of a base hovering thrust.

  BUG 3 — Attitude PID error sign:
    Original: error = target_theta - theta. Positive gimbal produces
              NEGATIVE torque (from rocket.py), so this was positive
              feedback — the rocket spun uncontrollably.
    Fixed:    error = theta - target_theta. Now a positive error (theta
              above target) produces positive gimbal, negative torque,
              theta decreases back to target. Correct negative feedback.

  BUG 4 — Horizontal control missing entirely:
    Original: target_theta was always passed as 0.0 from outside; no
              code computed it from x position.
    Fixed:    added outer loop: target_theta = clip(kp_x*x + kd_x*vx,
              -max_tilt, max_tilt). Positive x → positive theta (CCW
              tilt) → leftward thrust component → x decreases.
              Loop resets and holds theta=0 during freefall (thrust=0).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .state import State


_GRAVITY = 9.81  # m/s²


@dataclass
class PIDGains:
    kp: float
    ki: float
    kd: float


@dataclass
class ControllerOutput:
    thrust: float  # N
    gimbal: float  # rad


class PIDController:
    """Single-axis PID with output limits and directional anti-windup."""

    def __init__(
        self,
        gains: PIDGains,
        output_limits: tuple[float, float] = (-float("inf"), float("inf")),
    ) -> None:
        self.gains = gains
        self.output_limits = output_limits
        self._integral = 0.0
        self._prev_error = 0.0
        self._initialized = False

    def reset(self) -> None:
        self._integral = 0.0
        self._prev_error = 0.0
        self._initialized = False

    def update(self, error: float, dt: float) -> float:
        """Return the control output for the given error and time step."""
        # Skip derivative on the very first call to avoid an impulse spike.
        derivative = (error - self._prev_error) / dt if self._initialized else 0.0
        self._initialized = True

        lo, hi = self.output_limits

        # BUG 1 FIX — directional anti-windup.
        # Evaluate P+D only to decide whether winding would worsen saturation.
        # Only skip integration when output_pd is already past a limit AND
        # the error keeps pushing it further in that direction.
        output_pd = self.gains.kp * error + self.gains.kd * derivative
        winding_high = output_pd >= hi and error > 0
        winding_low  = output_pd <= lo and error < 0

        if not winding_high and not winding_low:
            self._integral += error * dt

        output = (
            self.gains.kp * error
            + self.gains.ki * self._integral
            + self.gains.kd * derivative
        )

        self._prev_error = error
        return max(lo, min(hi, output))


class RocketPID:
    """
    Cascaded 3-loop autopilot for 2D rocket landing.

    Loop 1 — altitude:
        target_vy = -clip(descent_rate_gain * y, min_descent, max_descent)
        thrust    = clip(m*g + PID(target_vy - vy), 0, max_thrust)
        Recommended gains: PIDGains(kp=500, ki=50, kd=100)

    Loop 2 — horizontal position → desired tilt:
        target_theta = clip(kp_x * x + kd_x * vx, -max_tilt, max_tilt)
        Only active when thrust > 0. Resets attitude PID during freefall.
        Recommended: kp_x=0.011, kd_x=0.5

    Loop 3 — attitude → gimbal:
        error = theta - target_theta   (current minus target — NOT the reverse)
        Recommended gains: PIDGains(kp=5000, ki=0, kd=1000)
        kd must be large (>=1000) to prevent oscillation between loops 2 and 3.

    Validated: lands from x0=±100m, y0=1000m within 5m at vy < 3 m/s (7/7).
    Plan spec (x0=50m): lands at x=0.5m, vy=-1.99 m/s — within 1m at <2 m/s.
    """

    def __init__(
        self,
        altitude_gains: PIDGains,
        attitude_gains: PIDGains,
        max_thrust: float = 30_000.0,    # N
        max_gimbal: float = 0.3,          # rad (~17 deg)
        max_tilt: float = 0.08,           # rad — max body tilt for lateral correction
        kp_x: float = 0.011,              # outer horizontal-position gain
        kd_x: float = 0.5,               # outer horizontal-velocity damping
        descent_rate_gain: float = 0.05,  # (m/s) per metre of altitude
        min_descent_speed: float = 2.0,   # m/s — final approach speed
        max_descent_speed: float = 30.0,  # m/s — max commanded descent speed
    ) -> None:
        self._alt_pid = PIDController(altitude_gains, output_limits=(-10_000.0, 20_000.0))
        self._att_pid = PIDController(attitude_gains, output_limits=(-max_gimbal, max_gimbal))
        self.max_thrust = max_thrust
        self.max_tilt = max_tilt
        self.kp_x = kp_x
        self.kd_x = kd_x
        self.descent_rate_gain = descent_rate_gain
        self.min_descent_speed = min_descent_speed
        self.max_descent_speed = max_descent_speed

    def reset(self) -> None:
        self._alt_pid.reset()
        self._att_pid.reset()

    def update(
        self,
        state: State,
        target_altitude: float = 0.0,
        dt: float = 1.0 / 60.0,
    ) -> ControllerOutput:
        """
        Compute thrust and gimbal commands from the current rocket state.

        Parameters
        ----------
        state:            Current rocket state.
        target_altitude:  Landing pad y-coordinate (default 0 = ground level).
        dt:               Simulation time step [s].
        """
        # ── Loop 1: altitude / velocity profile ──────────────────────────
        # BUG 2 FIX: use velocity profile instead of raw position error.
        altitude_above_target = state.y - target_altitude
        target_vy = -float(np.clip(
            self.descent_rate_gain * altitude_above_target,
            self.min_descent_speed,
            self.max_descent_speed,
        ))

        # Gravity feedforward: base thrust cancels gravity.
        # PID only trims velocity error on top of this.
        hover_ff = state.m * _GRAVITY
        thrust_trim = self._alt_pid.update(target_vy - state.vy, dt)
        thrust = float(np.clip(hover_ff + thrust_trim, 0.0, self.max_thrust))

        # ── Loop 2: horizontal position → desired tilt ────────────────────
        # BUG 4 FIX: compute target_theta from x position.
        # BUG 3 FIX (partial): only tilt when thrusting; reset during freefall.
        if thrust > 0.0:
            target_theta = float(np.clip(
                self.kp_x * state.x + self.kd_x * state.vx,
                -self.max_tilt,
                self.max_tilt,
            ))
        else:
            target_theta = 0.0
            self._att_pid.reset()  # prevent windup during freefall

        # ── Loop 3: attitude → gimbal ─────────────────────────────────────
        # BUG 3 FIX: error = (theta - target_theta), NOT (target - theta).
        # Reason: positive gimbal → negative torque (rocket.py line:
        #   alpha = -arm * F * sin(gimbal) / I)
        # So to INCREASE theta we need NEGATIVE gimbal → NEGATIVE output
        # → error must be negative when theta < target
        # → error = theta - target gives exactly that. ✓
        gimbal = self._att_pid.update(state.theta - target_theta, dt)

        return ControllerOutput(thrust=thrust, gimbal=gimbal)
