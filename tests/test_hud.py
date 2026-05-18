import matplotlib.pyplot as plt
from matplotlib.gridspec import GridSpec

from physics import ControllerOutput, State
from viz.hud import TrulyResponsiveHUD

test_state = State(x=10.0, y=750.5, vx=2.3, vy=-12.4, theta=0.08, omega=0.01, m=14200.0)
test_control = ControllerOutput(thrust=12000.0, gimbal=0.08)

# Create figure with GridSpec layout
fig = plt.figure(figsize=(12, 8))
gs = GridSpec(6, 2, figure=fig, hspace=0.4, wspace=0.3)

# Create HUD
hud = TrulyResponsiveHUD(fig, gs)
hud.update(test_state, test_control, time=45.3)

plt.show()
