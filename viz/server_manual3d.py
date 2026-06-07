"""Week 4 — 3D manual-flight WebSocket server.
Run:  python -m viz.server_manual3d
"""

from __future__ import annotations

import asyncio
import json

import websockets
import websockets.exceptions

from physics.rocket3d import ControlInput3D, Rocket3D, RocketParams3D
from physics.state3d import State3D

DT, HOST, PORT = 1 / 60, "localhost", 8765


def _start_state() -> State3D:
    return State3D(
        x=0.0,
        y=500.0,
        z=0.0,
        vx=0.0,
        vy=0.0,
        vz=0.0,
        q0=1.0,
        q1=0.0,
        q2=0.0,
        q3=0.0,  # identity = upright
        omega_x=0.0,
        omega_y=0.0,
        omega_z=0.0,
        m=1000.0,
    )


async def handler(websocket) -> None:
    rocket = Rocket3D(state=_start_state(), params=RocketParams3D())
    cmd: ControlInput3D = ControlInput3D()

    async def receive() -> None:
        nonlocal cmd
        async for raw in websocket:
            try:
                d = json.loads(raw)
                cmd = ControlInput3D(
                    thrust=float(d.get("thrust", 0.0)),
                    gimbal_pitch=float(d.get("gimbal_pitch", 0.0)),
                    gimbal_yaw=float(d.get("gimbal_yaw", 0.0)),
                )
            except Exception:
                pass

    async def loop() -> None:
        try:
            while True:
                s = rocket.state
                if s.y > 19:
                    rocket.step(DT, cmd)
                    s = rocket.state
                await websocket.send(
                    json.dumps(
                        {
                            "x": s.x,
                            "y": s.y,
                            "z": s.z,
                            "vx": s.vx,
                            "vy": s.vy,
                            "vz": s.vz,
                            "q0": s.q0,
                            "q1": s.q1,
                            "q2": s.q2,
                            "q3": s.q3,
                            "m": s.m,
                            "thrust": float(cmd.thrust),
                        }
                    )
                )
                await asyncio.sleep(DT)
        except websockets.exceptions.ConnectionClosed:
            pass

    recv_task = asyncio.create_task(receive())
    await loop()
    recv_task.cancel()


async def _main() -> None:
    print(f"[server_manual3d] ws://{HOST}:{PORT}")
    print("  Controls: ↑ thrust   ← → steer   W/S pitch")
    async with websockets.serve(handler, HOST, PORT):
        await asyncio.Future()


if __name__ == "__main__":
    asyncio.run(_main())
