# Self-Landing Rocket Simulator

A Falcon 9-style rocket that lands itself, simulated with full 6-DOF rigid-body
dynamics and a model-predictive control autopilot.

🚧 **Work in progress** — Phase 2: 6-DOF dynamics + LQR autopilot, Three.js viewer.

## Setup

```bash
# Windows
python -m venv .venv
.venv\Scripts\activate

# macOS / Linux
python3.11 -m venv .venv
source .venv/bin/activate

# Then on any OS:
pip install -e ".[dev]"
pre-commit install
pytest
```

## Project structure

- `physics/` — equations of motion, integrators, force models
- `viz/` — Three.js viewer (current), with a 2D Matplotlib animator kept as a Phase 1 milestone
- `tests/` — unit tests for dynamics and controllers
- `notebooks/` — validation plots and exploratory analysis
- `docs/` — physics derivations and design notes

## Try it

```bash
# Replay export — produces a self-contained landing HTML
python -m viz.sim_runner3d --x0 50 --z0 30 --record-every 3 --out landing.html
open landing.html   # or just double-click

# Live mode — physics streams over WebSocket to the browser
python -m viz.server3d
# then open http://localhost:8766/viewer3d.html and set window.VIZ_MODE='live'
```

## Roadmap

| Phase | Weeks | Goal |
|-------|-------|------|
| 1 | 1–3 | 2D MVP with PID controller, Matplotlib |
| 2 | 4–6 | Full 6-DOF dynamics, LQR controller, Three.js |
| 3 | 7–9 | Model Predictive Control |
| 4 | 10  | Deploy + writeup |

## Team

- **Kencho Namgyel** ([@Ken498](https://github.com/Ken498)) — simulation engine, visualization, deployment
- **[Dendup Wangchuk]**  ([@366dendup](https://github.com/366dendup))— dynamics, integrators, control theory

## License

MIT
