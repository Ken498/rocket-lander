"""
2D rocket state vector.

This is the canonical interface between the physics and the renderer.
Both partners code against `State`. If this changes, both halves break —
so changes here happen in PRs, not on `main`.

State variables (Phase 1, 2D):
    x, y    : position [m]   (y is up; ground is y=0)
    vx, vy  : velocity [m/s]
    theta   : attitude angle [rad]   (0 = pointing up; +ve = tilted CCW)
    omega   : angular velocity [rad/s]
    m       : current mass [kg]      (decreases as fuel burns)
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class State:
    x: float
    y: float
    vx: float
    vy: float
    theta: float
    omega: float
    m: float

    def to_array(self) -> np.ndarray:
        """Pack state into a 7-element numpy array for the integrator."""
        return np.array([self.x, self.y, self.vx, self.vy, self.theta, self.omega, self.m])

    @classmethod
    def from_array(cls, arr: np.ndarray) -> State:
        """Unpack a 7-element numpy array back into a State."""
        if arr.shape != (7,):
            raise ValueError(f"State array must have shape (7,), got {arr.shape}")
        return cls(*arr.tolist())