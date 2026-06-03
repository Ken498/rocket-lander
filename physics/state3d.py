"""
6-DOF rocket state (14 elements).

State vector layout
-------------------
Index  Symbol    Units   Description
 0     x         m       World-frame position — East
 1     y         m       World-frame position — Up (ground = 0)
 2     z         m       World-frame position — South
 3     vx        m/s     World-frame velocity
 4     vy        m/s     World-frame velocity
 5     vz        m/s     World-frame velocity
 6     q0        —       Quaternion scalar  (q=[1,0,0,0] → upright)
 7     q1        —       Quaternion vector x
 8     q2        —       Quaternion vector y
 9     q3        —       Quaternion vector z
10     omega_x   rad/s   Body-frame angular velocity
11     omega_y   rad/s   Body-frame angular velocity
12     omega_z   rad/s   Body-frame angular velocity
13     m         kg      Total (wet) mass

Quaternion convention
---------------------
Scalar-first: q = [q0, q1, q2, q3].
Unit length: |q| = 1.
q = [1, 0, 0, 0] is the identity rotation (body frame = world frame),
meaning the rocket axis (+y_body) points straight up (+y_world).

Reference: Diebel, "Representing Attitude", Stanford 2006.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class State3D:
    """Full 6-DOF state of the 3D rocket."""

    # ── Position (world frame) ────────────────────────────────────────
    x: float = 0.0  # m — East
    y: float = 0.0  # m — Up  (ground = 0)
    z: float = 0.0  # m — South

    # ── Velocity (world frame) ────────────────────────────────────────
    vx: float = 0.0  # m/s
    vy: float = 0.0  # m/s
    vz: float = 0.0  # m/s

    # ── Attitude quaternion (scalar-first, unit length) ───────────────
    q0: float = 1.0  # scalar  — 1.0 means upright
    q1: float = 0.0
    q2: float = 0.0
    q3: float = 0.0

    # ── Angular velocity (body frame) ─────────────────────────────────
    omega_x: float = 0.0  # rad/s
    omega_y: float = 0.0  # rad/s
    omega_z: float = 0.0  # rad/s

    # ── Mass ──────────────────────────────────────────────────────────
    m: float = 1000.0  # kg — total (wet) mass

    # ------------------------------------------------------------------ #
    # Array conversion                                                     #
    # ------------------------------------------------------------------ #

    def to_array(self) -> np.ndarray:
        """Pack into a length-14 float64 array."""
        return np.array(
            [
                self.x,
                self.y,
                self.z,
                self.vx,
                self.vy,
                self.vz,
                self.q0,
                self.q1,
                self.q2,
                self.q3,
                self.omega_x,
                self.omega_y,
                self.omega_z,
                self.m,
            ],
            dtype=float,
        )

    @classmethod
    def from_array(cls, arr: np.ndarray) -> State3D:
        """Unpack a length-14 array into a State3D."""
        return cls(
            x=float(arr[0]),
            y=float(arr[1]),
            z=float(arr[2]),
            vx=float(arr[3]),
            vy=float(arr[4]),
            vz=float(arr[5]),
            q0=float(arr[6]),
            q1=float(arr[7]),
            q2=float(arr[8]),
            q3=float(arr[9]),
            omega_x=float(arr[10]),
            omega_y=float(arr[11]),
            omega_z=float(arr[12]),
            m=float(arr[13]),
        )

    # ------------------------------------------------------------------ #
    # Convenience properties                                               #
    # ------------------------------------------------------------------ #

    @property
    def pos(self) -> np.ndarray:
        """World-frame position [x, y, z] as (3,) array."""
        return np.array([self.x, self.y, self.z])

    @property
    def vel(self) -> np.ndarray:
        """World-frame velocity [vx, vy, vz] as (3,) array."""
        return np.array([self.vx, self.vy, self.vz])

    @property
    def quat(self) -> np.ndarray:
        """Attitude quaternion [q0, q1, q2, q3] as (4,) array."""
        return np.array([self.q0, self.q1, self.q2, self.q3])

    @property
    def omega(self) -> np.ndarray:
        """Body-frame angular velocity [ωx, ωy, ωz] as (3,) array."""
        return np.array([self.omega_x, self.omega_y, self.omega_z])
