"""Simulation integration test helpers (Phase 18.13.5).

Starts a real simulation service over a localhost TCP socket (uvicorn) so tests
cross the actual network boundary — not just ASGI in-process.
"""

import socket
import threading
import time
from contextlib import contextmanager

import httpx
import uvicorn


def _free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


class RunningServer:
    def __init__(self, app, port):
        self.app = app
        self.port = port
        self.base_url = f"http://127.0.0.1:{port}"
        self._server = uvicorn.Server(uvicorn.Config(
            app, host="127.0.0.1", port=port, log_level="error"))
        self._thread = threading.Thread(target=self._server.run, daemon=True)

    def start(self):
        self._thread.start()
        self._wait_ready()

    def _wait_ready(self):
        deadline = time.time() + 15
        while time.time() < deadline:
            try:
                response = httpx.get(self.base_url + "/health", timeout=1.0)
                if response.status_code == 200:
                    return
            except Exception:
                pass
            time.sleep(0.05)
        raise RuntimeError("simulation server did not become ready")

    def stop(self):
        self._server.should_exit = True
        self._thread.join(timeout=5)


@contextmanager
def run_simulation(app):
    server = RunningServer(app, _free_port())
    server.start()
    try:
        yield server
    finally:
        server.stop()


__all__ = ["run_simulation", "RunningServer"]
