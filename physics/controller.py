"""
PID autopilot for 2D rocket landing.
 
Two independent PID loops:
  Altitude loop  — error = target_y - y       → thrust command  [N]
  Attitude loop  — error = target_theta - theta → gimbal command [rad]
 
Anti-windup: the integral is only updated when the error and the
saturation are on opposite sides (i.e. the integral is helping, not
hurting). This prevents runaway wind-up during large transients.
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
 
        lo, hi = self.output_limits
 
        # FIX 1: Only accumulate integral when it won't worsen saturation.
        # Compute output without integral contribution first to check saturation.
        output_no_integral = self.gains.kp * error + self.gains.kd * derivative
        saturated_high = output_no_integral >= hi and error > 0
        saturated_low  = output_no_integral <= lo and error < 0
 
        if not saturated_high and not saturated_low:
            self._integral += error * dt
 
        output = (
            self.gains.kp * error
            + self.gains.ki * self._integral
            + self.gains.kd * derivative
        )
 
        clamped = max(lo, min(hi, output))
 
        self._prev_error = error
        return clamped
 
 
class RocketPID:
    """
    Dual-axis PID autopilot.
 
    Altitude loop  → thrust   (target_y     → state.y, also damps vy)
    Attitude loop  → gimbal   (target_theta → state.theta)
 
    The altitude loop uses a composite error:
        error = (target_y - y) - velocity_damping * vy
 
    This damps the vertical velocity so the rocket slows down as it
    approaches the target altitude, preventing overshoot and hard landings.
 
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
        velocity_damping: float = 2.0, # s    — how aggressively to damp vy
    ) -> None:
        self.altitude_pid = PIDController(altitude_gains, output_limits=(0.0, max_thrust))
        self.attitude_pid = PIDController(attitude_gains, output_limits=(-max_gimbal, max_gimbal))
        self.velocity_damping = velocity_damping
 
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
 
        # FIX 2: Composite altitude error that includes velocity damping.
        # Without this, a rocket descending from 1000 m sees a large negative
        # error that clamps thrust to 0 until it's nearly at the ground.
        altitude_error = (target_altitude - state.y) - self.velocity_damping * state.vy
 
        thrust = self.altitude_pid.update(altitude_error, dt)
        gimbal = self.attitude_pid.update(target_theta - state.theta, dt)
        return ControllerOutput(thrust=thrust, gimbal=gimbal)
