"""Visualization utilities for the rocket simulator."""

try:
    from viz.animator import animate_rocket

    __all__ = ["animate_rocket"]
except ImportError:
    __all__ = []
