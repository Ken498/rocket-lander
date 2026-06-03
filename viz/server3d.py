"""
Live 3D simulation WebSocket server — Week 6.

Streams State3D JSON frames to any connected browser client at ~60 Hz
while the LQR landing simulation runs in real time.

Usage
-----
    python viz/server3d.py                    # default: x0=50, z0=0, port=8765
    python viz/server3d.py --x0 50 --z0 50   # combined offset
    python viz/server3d.py --port 8888

Then open viz/viewer3d.html in a browser (or a self-contained export generated
with sim_runner3d.py --out landing.html) and set window.VIZ_MODE = 'live'.
For convenience the server also serves viewer3d.html over HTTP on port+1 so you
can navigate to http://localhost:8766 directly.

Protocol
--------
Each message is a single JSON object matching the frame dicts produced by
sim_runner3d._state_to_dict().  Clients should parse with JSON.parse().

A final {"event": "done", ...} message is sent after the rocket lands.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import pathlib
import time

import websockets

from viz.sim_runner3d import run_simulation

# ── Default config ─────────────────────────────────────────────────── #
DEFAULT_HOST = "localhost"
DEFAULT_PORT = 8765
TARGET_DT = 1.0 / 60.0  # target frame interval [s]


# ══════════════════════════════════════════════════════════════════════ #
# WebSocket handler
# ══════════════════════════════════════════════════════════════════════ #


async def _stream_sim(
    websocket,
    x0: float,
    y0: float,
    z0: float,
) -> None:
    """
    Run the simulation in a thread and stream each frame to the client.

    We use run_in_executor so the CPU-bound RK4 loop doesn't block the
    asyncio event loop; the on_step callback puts frames into a queue
    that the sender coroutine drains.
    """
    queue: asyncio.Queue = asyncio.Queue(maxsize=300)
    loop = asyncio.get_event_loop()

    def on_step(frame: dict) -> None:
        """Called from the worker thread — safe to put into the queue."""
        loop.call_soon_threadsafe(queue.put_nowait, frame)

    # Run the heavy simulation in a thread pool executor
    sim_future = loop.run_in_executor(
        None,
        lambda: run_simulation(x0=x0, y0=y0, z0=z0, on_step=on_step),
    )

    # Drain the queue and send frames to the browser
    frame_start = time.perf_counter()
    frames_sent = 0

    while True:
        try:
            frame = queue.get_nowait()
        except asyncio.QueueEmpty:
            # If simulation finished and queue is empty, we're done
            if sim_future.done():
                break
            await asyncio.sleep(0.001)
            continue

        try:
            await websocket.send(json.dumps(frame, separators=(",", ":")))
        except websockets.exceptions.ConnectionClosed:
            return

        frames_sent += 1

        # Throttle to ~60 Hz so the browser doesn't get flooded
        elapsed = time.perf_counter() - frame_start
        expected = frames_sent * TARGET_DT
        sleep_s = expected - elapsed
        if sleep_s > 0:
            await asyncio.sleep(sleep_s)

    # Drain any remaining frames
    while not queue.empty():
        frame = queue.get_nowait()
        try:
            await websocket.send(json.dumps(frame, separators=(",", ":")))
        except websockets.exceptions.ConnectionClosed:
            return

    # Send completion event
    final = await sim_future  # should already be done
    last = final[-1] if final else {}
    done_msg = json.dumps(
        {
            "event": "done",
            "total_frames": len(final),
            "touchdown_x": last.get("x", 0),
            "touchdown_z": last.get("z", 0),
            "touchdown_vy": last.get("vy", 0),
        }
    )
    try:
        await websocket.send(done_msg)
    except websockets.exceptions.ConnectionClosed:
        pass

    print(
        f"[server3d] Stream complete — {len(final)} frames, "
        f"x={last.get('x', 0):.2f}m z={last.get('z', 0):.2f}m "
        f"vy={last.get('vy', 0):.2f}m/s"
    )


async def _handler(websocket, x0: float, y0: float, z0: float) -> None:
    remote = websocket.remote_address
    print(f"[server3d] Client connected: {remote}  sim x0={x0} y0={y0} z0={z0}")
    try:
        await _stream_sim(websocket, x0=x0, y0=y0, z0=z0)
    except websockets.exceptions.ConnectionClosed:
        print(f"[server3d] Client disconnected: {remote}")
    except Exception as exc:
        print(f"[server3d] Error: {exc}")


# ══════════════════════════════════════════════════════════════════════ #
# Optional HTTP server for viewer3d.html
# ══════════════════════════════════════════════════════════════════════ #


async def _serve_viewer(port: int) -> None:
    """Minimal HTTP server to serve viewer3d.html on port+1."""
    import http.server
    import threading

    viewer_dir = pathlib.Path(__file__).parent

    class Handler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(viewer_dir), **kwargs)

        def log_message(self, fmt, *args):
            pass  # silence noisy logs

    def _run():
        with http.server.HTTPServer(("localhost", port), Handler) as srv:
            print(f"[server3d] viewer3d.html → http://localhost:{port}/viewer3d.html")
            srv.serve_forever()

    threading.Thread(target=_run, daemon=True).start()


# ══════════════════════════════════════════════════════════════════════ #
# Entry point
# ══════════════════════════════════════════════════════════════════════ #


async def _main(args: argparse.Namespace) -> None:
    await _serve_viewer(args.port + 1)

    async def handler(ws):
        await _handler(ws, args.x0, args.y0, args.z0)

    async with websockets.serve(handler, args.host, args.port):
        print(
            f"[server3d] WebSocket server running at ws://{args.host}:{args.port}\n"
            f"           Open http://localhost:{args.port + 1}/viewer3d.html  "
            f"(set VIZ_MODE='live' in browser console if needed)\n"
            f"           Ctrl-C to quit."
        )
        await asyncio.Future()  # run forever


def main() -> None:
    parser = argparse.ArgumentParser(description="3D LQR landing WebSocket server")
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--x0", type=float, default=50.0)
    parser.add_argument("--y0", type=float, default=1000.0)
    parser.add_argument("--z0", type=float, default=0.0)
    args = parser.parse_args()

    asyncio.run(_main(args))


if __name__ == "__main__":
    main()
