# Self-Landing Rocket Simulator — Dynamics Reference

This is the physicist's source of truth for every equation implemented in `physics/`.
All symbols used in code have a corresponding definition here.

---

## 1. Coordinate System

| Symbol | Description |
|--------|-------------|
| x, y | World-frame position. y-axis points **up**; ground is at y = 0. |
| θ (theta) | Attitude angle from vertical. θ = 0 = upright. Positive = CCW. |
| γ (gamma) | Gimbal (nozzle deflection) angle from body axis. Positive = CCW. |
| ω (omega) | Angular velocity [rad/s]. |

---

## 2. State Vector (Phase 1 — 2D)

| Index | Symbol | Units | Description |
|-------|--------|-------|-------------|
| 0 | x | m | Horizontal position |
| 1 | y | m | Vertical position (ground = 0) |
| 2 | vx | m/s | Horizontal velocity |
| 3 | vy | m/s | Vertical velocity |
| 4 | θ | rad | Attitude angle |
| 5 | ω | rad/s | Angular velocity |
| 6 | m | kg | Total mass (decreases as fuel burns) |

---

## 3. Equations of Motion

### 3.1 Translational Dynamics (Newton's 2nd Law)

$$\ddot{x} = \frac{T \cdot (-\sin(\theta + \gamma))}{m}$$

$$\ddot{y} = \frac{T \cdot \cos(\theta + \gamma)}{m} - g$$

where $T$ = engine thrust [N] and $g = 9.81 \text{ m/s}^2$.

### 3.2 Rotational Dynamics

Torque about centre of mass from gimbaled nozzle:

$$\tau = -L \cdot T \cdot \sin(\gamma)$$

$$\dot{\omega} = \frac{\tau}{I} = \frac{-L \cdot T \cdot \sin(\gamma)}{I}$$

Moment of inertia (thin-rod approximation):

$$I = \frac{m \cdot \ell^2}{12}$$

where $\ell$ = body length and $L$ = nozzle arm distance (CoM to nozzle).

### 3.3 Mass Depletion (Tsiolkovsky)

$$\dot{m} = -\frac{T}{I_{sp} \cdot g_0}$$

Integrating a constant-thrust burn from $m_0$ to $m_f$:

$$\boxed{\Delta v = I_{sp} \cdot g_0 \cdot \ln\!\left(\frac{m_0}{m_f}\right)}$$

This is the **Tsiolkovsky rocket equation** — validated in `tests/test_physics.py`.

---

## 4. Numerical Integration — RK4

Fixed-timestep 4th-order Runge-Kutta:

$$k_1 = f(s_n,\, u)$$
$$k_2 = f\!\left(s_n + \tfrac{\Delta t}{2}\,k_1,\; u\right)$$
$$k_3 = f\!\left(s_n + \tfrac{\Delta t}{2}\,k_2,\; u\right)$$
$$k_4 = f(s_n + \Delta t\,k_3,\; u)$$

$$s_{n+1} = s_n + \frac{\Delta t}{6}\!\left(k_1 + 2k_2 + 2k_3 + k_4\right)$$

**Why not Euler?** Forward Euler doesn't conserve energy and causes the simulation to diverge.
RK4 has global error $O(\Delta t^4)$, which is sufficient at $\Delta t = 1/60$ s.

---

## 5. Controllers

### 5.1 PID (`physics/controller.py`) — Phase 1

Two decoupled PID loops:

**Altitude loop** → thrust:

$$e_y = (y_{\text{target}} - y) - \lambda\,\dot{y}$$
$$T = K_p^{(y)}\,e_y + K_i^{(y)}\!\int e_y\,dt + K_d^{(y)}\,\dot{e}_y$$

The $\lambda\,\dot{y}$ term damps vertical velocity to prevent hard landings.

**Attitude loop** → gimbal:

$$e_\theta = \theta_{\text{target}} - \theta$$
$$\gamma = K_p^{(\theta)}\,e_\theta + K_i^{(\theta)}\!\int e_\theta\,dt + K_d^{(\theta)}\,\dot{e}_\theta$$

---

### 5.2 LQR (`physics/lqr.py`) — Phase 2

**Hover equilibrium linearisation:**

$$\dot{\delta z} = A\,\delta z + B\,\delta u$$

$$A = \begin{pmatrix}
0 & 0 & 1 & 0 &  0 & 0 \\
0 & 0 & 0 & 1 &  0 & 0 \\
0 & 0 & 0 & 0 & -g & 0 \\
0 & 0 & 0 & 0 &  0 & 0 \\
0 & 0 & 0 & 0 &  0 & 1 \\
0 & 0 & 0 & 0 &  0 & 0
\end{pmatrix},\qquad
B = \begin{pmatrix}
0     & 0 \\
0     & 0 \\
0     & -g \\
1/m   & 0 \\
0     & 0 \\
0     & -LT_{eq}/I
\end{pmatrix}$$

**Continuous-Time Algebraic Riccati Equation (CARE):**

$$A^T P + P A - P B R^{-1} B^T P + Q = 0$$

**Gain matrix and control law:**

$$K = R^{-1} B^T P \quad \in \mathbb{R}^{2 \times 6}$$

$$\delta u = -K\,\delta z \;\Rightarrow\; T = T_{eq} - K_{0,:}\,\delta z,\quad \gamma = -K_{1,:}\,\delta z$$

**Bryson's rule for Q, R:**

$$Q_{ii} = \frac{1}{(\text{acceptable deviation}_i)^2}, \qquad R_{jj} = \frac{1}{(\text{max control}_j)^2}$$

The gain matrix $K$ is recomputed whenever mass changes by >10 kg (**mass-scheduled LQR**).

---

### 5.3 MPC (`physics/mpc.py`) — Phase 3

**Finite-horizon QP (solved every timestep — receding horizon):**

$$\min_{\delta u_0,\ldots,\delta u_{N-1}}
\sum_{k=0}^{N-1}\!\left[\delta z_k^T Q\,\delta z_k + \delta u_k^T R\,\delta u_k\right]
+ \delta z_N^T P_f\,\delta z_N$$

subject to:

| Constraint | Expression |
|------------|------------|
| Dynamics | $\delta z_{k+1} = A_d\,\delta z_k + B_d\,\delta u_k$ |
| Thrust | $0 \leq T_{eq} + \delta T_k \leq T_{\max}$ |
| Gimbal | $\|\gamma_k\| \leq \gamma_{\max}$ |
| Ground (Week 7) | $y_k \geq 0$ |

$A_d, B_d$ = ZOH discretisation of $(A, B)$.  
$P_f$ = LQR terminal cost (from CARE) — guarantees stability at the horizon.  
Solver: **CVXPY + OSQP**, 30 ms time budget. Fallback: LQR on failure.

---

## 6. Validation Benchmarks

All tests in `tests/test_physics.py`.

| Test | Analytical formula | Tolerance |
|------|--------------------|-----------|
| Free-fall acceleration | $a_y = -g = -9.81\text{ m/s}^2$ | 0.1 % |
| Free-fall trajectory | $y(t) = y_0 - \frac{1}{2}g t^2$ | 0.01 % |
| Tsiolkovsky $\Delta v$ | $\Delta v = I_{sp}\,g_0\,\ln(m_0/m_f)$ | 1 % |
| Hover equilibrium | $T = mg \Rightarrow \ddot{y} = 0$ | $<10^{-3}$ m/s² |
| Angular momentum | $\gamma = 0 \Rightarrow \dot{\omega} = 0$ | machine precision |
| Dry-mass clamp | $m \geq m_{\text{dry}}$ always | exact |

---

## 7. Phase 2 Extensions — Full 3D (Weeks 4–6)

State vector extended to 13 dimensions:

$$s = [x,\, y,\, z,\, v_x,\, v_y,\, v_z,\, q_0,\, q_1,\, q_2,\, q_3,\, \omega_x,\, \omega_y,\, \omega_z,\, m]$$

$(q_0, q_1, q_2, q_3)$ is a **unit quaternion** (avoids gimbal lock).

Quaternion kinematics:

$$\dot{\mathbf{q}} = \frac{1}{2}\,\mathbf{q} \otimes \begin{pmatrix} 0 \\ \boldsymbol{\omega} \end{pmatrix}$$

Euler's rotation equations:

$$I\,\dot{\boldsymbol{\omega}} + \boldsymbol{\omega} \times (I\boldsymbol{\omega}) = \boldsymbol{\tau}_{\text{gimbal}}$$

Key reference: Diebel, *Representing Attitude: Euler Angles, Unit Quaternions, and Rotation Vectors* (free PDF).

---

*Authors: Dendup (physics) × Ken (CS) — Summer 2026*
