"""
PID autopilot for 2D rocket landing.

Two independent PID loops:
  Altitude loop  — error = target_y - y       → thrust command  [N]
  Attitude loop  — error = target_theta - theta → gimbal command [rad]

Both controllers use conditional-integration anti-windup: the integral
stops accumulating whenever the output is saturated, preventing runaway
wind-up during large transients.
"""

from __future__ import annotations

from dataclasses import dataclass

from .state import State


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
    """Single-axis PID controller with output limits and anti-windup."""

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

        self._integral += error * dt

        output = (
            self.gains.kp * error
            + self.gains.ki * self._integral
            + self.gains.kd * derivative
        )

        lo, hi = self.output_limits
        clamped = max(lo, min(hi, output))

        # Anti-windup: undo the integral step that pushed us into saturation.
        if clamped != output:
            self._integral -= error * dt

        self._prev_error = error
        return clamped


class RocketPID:
    """
    Dual-axis PID autopilot.

    Altitude loop  → thrust   (target_y     → state.y)
    Attitude loop  → gimbal   (target_theta → state.theta)

    Typical starting gains for a 1 000 kg rocket:
        altitude : PIDGains(kp=50,   ki=10,  kd=200)
        attitude : PIDGains(kp=5000, ki=0,   kd=500)
    """

    def __init__(
        self,
        altitude_gains: PIDGains,
        attitude_gains: PIDGains,
        max_thrust: float = 30_000.0,  # N
        max_gimbal: float = 0.3,       # rad  (~17°)
    ) -> None:
        self.altitude_pid = PIDController(altitude_gains, output_limits=(0.0, max_thrust))
        self.attitude_pid = PIDController(attitude_gains, output_limits=(-max_gimbal, max_gimbal))

    def reset(self) -> None:
        self.altitude_pid.reset()
        self.attitude_pid.reset()

    def update(
        self,
        state: State,
        target_altitude: float,
        target_theta: float = 0.0,
        dt: float = 1.0 / 60.0,
    ) -> ControllerOutput:
        """Compute thrust and gimbal commands from the current state and targets."""
        thrust = self.altitude_pid.update(target_altitude - state.y, dt)
        gimbal = self.attitude_pid.update(target_theta - state.theta, dt)
        return ControllerOutput(thrust=thrust, gimbal=gimbal)
