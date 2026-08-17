"""PostgreSQL transaction scope shared by the repository and identity map.

A single ``transaction`` context makes every canonical write (repository + the
ExternalIdentityMap) share one connection / unit-of-work: on success it commits,
on any exception it rolls back, so a partially-applied publish never becomes
visible.
"""

from contextlib import contextmanager
from contextvars import ContextVar

_tx_connection: ContextVar = ContextVar("commerce_tx_connection", default=None)


def current_tx_connection():
    return _tx_connection.get()


@contextmanager
def transaction(connection_factory):
    """Open one connection, run all nested writes on it, commit/rollback."""
    existing = _tx_connection.get()
    if existing is not None:
        yield existing
        return
    connection = connection_factory()
    token = _tx_connection.set(connection)
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        _tx_connection.reset(token)
        connection.close()


__all__ = ["transaction", "current_tx_connection"]
