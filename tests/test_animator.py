"""Tests for the animator's geometry and State integration."""

import numpy as np
import pytest

from physics import State
from viz.animator import _rocket_corners, animate_rocket


def test_rocket_corners_shape():
    corners = _rocket_corners(0.0, 0.0, 0.0)
    assert corners.shape == (4, 2)


def test_rocket_corners_at_origin_no_rotation():
    corners = _rocket_corners(0.0, 0.0, 0.0, width=2.0, height=10.0)
    expected = np.array([[-1.0, -5.0], [1.0, -5.0], [1.0, 5.0], [-1.0, 5.0]])
    np.testing.assert_allclose(corners, expected, atol=1e-10)


def test_rocket_corners_translation():
    corners = _rocket_corners(10.0, 20.0, 0.0, width=2.0, height=10.0)
    expected = np.array([[9.0, 15.0], [11.0, 15.0], [11.0, 25.0], [9.0, 25.0]])
    np.testing.assert_allclose(corners, expected, atol=1e-10)


def test_rocket_corners_90deg_rotation():
    # 90° CCW: a vertical rocket becomes horizontal.
    corners = _rocket_corners(0.0, 0.0, np.pi / 2, width=2.0, height=10.0)
    expected = np.array([[5.0, -1.0], [5.0, 1.0], [-5.0, 1.0], [-5.0, -1.0]])
    np.testing.assert_allclose(corners, expected, atol=1e-10)


def test_animate_rocket_accepts_state_list():
    """Smoke test: animator constructs without error from a list[State]."""
    states = [
        State(x=0.0, y=100.0, vx=0.0, vy=0.0, theta=0.0, omega=0.0, m=500.0),
        State(x=0.0, y=95.0, vx=0.0, vy=-10.0, theta=0.0, omega=0.0, m=500.0),
    ]
    anim = animate_rocket(states, dt=0.01)
    assert anim is not None


def test_animate_rocket_rejects_empty():
    with pytest.raises(ValueError):
        animate_rocket([], dt=0.01)
