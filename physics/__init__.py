"""Physics package: dynamics, integrators, controllers."""

# Phase 1 — 2D
from .controller import ControllerOutput, PIDController, PIDGains, RocketPID
from .rocket import Rocket, RocketParams, simulate_freefall
from .state import State

# Phase 2 — 6-DOF 3D
from .rocket3d import ControlInput3D, Rocket3D, RocketParams3D
from .state3d import State3D

__all__ = [
    # 2D
    "ControllerOutput",
    "PIDController",
    "PIDGains",
    "Rocket",
    "RocketParams",
    "RocketPID",
    "State",
    "simulate_freefall",
    # 3D
    "ControlInput3D",
    "Rocket3D",
    "RocketParams3D",
    "State3D",
]