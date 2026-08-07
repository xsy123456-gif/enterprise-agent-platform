"""Memory — independent enterprise memory subsystem.

Public API (supported, stable):
  write(request) → MemoryWriteReceipt
  read(request)  → MemoryReadResult

Composition:
  system = build_memory_system(...)
  system.runtime.start()
  system.client.write(...)

Everything else under app.memory is internal implementation.
"""

from app.memory.api.models import (
    MemoryObservation,
    MemoryPrincipal,
    MemorySource,
)
from app.memory.api.public_models import (
    MemoryReadRequest,
    MemoryReadResult,
    MemoryRecord,
    MemoryWriteReceipt,
    MemoryWriteRequest,
)
from app.memory.api.type_registry import MemoryType
from app.memory.errors import (
    MemoryAccessDenied,
    MemoryError,
    MemoryValidationError,
)
from app.memory.factory import (
    MemoryClient,
    MemoryRuntime,
    MemorySystem,
    build_memory_system,
)
from app.memory.models.scope import MemoryScope
from app.memory.ports.authorization import (
    AllowAllMemoryAuthorizationProvider,
    DenyByDefaultMemoryAuthorizationProvider,
    MemoryAuthorizationProvider,
)

Memory = MemoryClient

__all__ = [
    "Memory",
    "MemoryClient",
    "MemorySystem",
    "MemoryRuntime",
    "build_memory_system",
    "MemoryWriteRequest",
    "MemoryWriteReceipt",
    "MemoryReadRequest",
    "MemoryReadResult",
    "MemoryRecord",
    "MemoryObservation",
    "MemoryPrincipal",
    "MemorySource",
    "MemoryScope",
    "MemoryType",
    "MemoryError",
    "MemoryValidationError",
    "MemoryAccessDenied",
    "MemoryAuthorizationProvider",
    "AllowAllMemoryAuthorizationProvider",
    "DenyByDefaultMemoryAuthorizationProvider",
]
