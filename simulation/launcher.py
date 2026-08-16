"""Simulation launcher (Phase 18.13 / 18.14).

Starts all simulation services on localhost.  Usage::

    python -m simulation.launcher [--seed data/seed/enterprise-commerce-v1]

Each service is a separate FastAPI app served by uvicorn on its own port.  The
platform talks to them over HTTP only — it never imports this package.
"""

import argparse
import threading
import time

import uvicorn


def _providers(seed_path=None):
    from simulation.amazon.app import build_app as amazon
    from simulation.netsuite.app import build_app as netsuite
    from simulation.salesforce.app import build_app as salesforce
    from simulation.sap.app import build_app as sap
    from simulation.tiktok.app import build_app as tiktok

    return [
        ("amazon", amazon(seed_path)),
        ("tiktok", tiktok(seed_path)),
        ("sap", sap(seed_path)),
        ("salesforce", salesforce(seed_path)),
        ("netsuite", netsuite(seed_path)),
    ]


def _run(app, host, port):
    config = uvicorn.Config(app, host=host, port=port, log_level="warning")
    server = uvicorn.Server(config)
    server.run()


def main():
    parser = argparse.ArgumentParser(description="Start simulation services")
    parser.add_argument("--seed", default=None,
                        help="path to a data/seed/<dataset> directory")
    args = parser.parse_args()
    providers = _providers(seed_path=args.seed)
    threads = []
    for name, app in providers:
        port = _port_for(name)
        thread = threading.Thread(target=_run, args=(app, "127.0.0.1", port),
                                  daemon=True)
        thread.start()
        threads.append(thread)
        dataset = getattr(app.state, "dataset_id", "") or "contract-fixtures"
        print(f"started {name} simulation on http://127.0.0.1:{port} "
              f"(dataset={dataset})")
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
