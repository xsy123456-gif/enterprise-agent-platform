"""Simulation launcher (Phase 18.13).

Starts all simulation services on localhost.  Usage::

    python -m simulation.launcher

Each service is a separate FastAPI app served by uvicorn on its own port.  The
platform talks to them over HTTP only — it never imports this package.
"""

import threading
import time

import uvicorn


def _providers():
    from simulation.amazon.app import build_app as amazon

    return [("amazon", amazon())]


def _run(app, host, port):
    config = uvicorn.Config(app, host=host, port=port, log_level="warning")
    server = uvicorn.Server(config)
    server.run()


def main():
    providers = _providers()
    threads = []
    for name, app in providers:
        port = app.state.provider and _port_for(name)
        thread = threading.Thread(target=_run, args=(app, "127.0.0.1", port),
                                  daemon=True)
        thread.start()
        threads.append(thread)
        print(f"started {name} simulation on http://127.0.0.1:{port}")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass


def _port_for(name):
    from simulation.common.config import DEFAULT_PORTS
    return DEFAULT_PORTS.get(name, 9100)


if __name__ == "__main__":
    main()
