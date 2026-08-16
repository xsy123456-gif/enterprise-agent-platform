"""Phase 18.0 guard: Platform dependency direction.

The Platform layer must depend on Platform Foundation, not on Commerce generic
utilities.  The three generic abstractions (utc_now, error base, versioned
registry) must live in platform/core (Phase 18.6), with Commerce depending on
them — never the reverse.

Currently ``app/platform/**`` imports these from ``app.commerce``; this guard is
marked ``xfail`` until Phase 18.6 extracts them.
"""

import pytest

from tests.architecture._scan import all_imports

_COMMERCE_GENERIC_UTILITIES = (
    "app.commerce.domain.base",              # utc_now
    "app.commerce.contracts.errors",         # CommerceError base
    "app.commerce.diagnostics.registry.base",  # VersionedRegistry
    "app.commerce.diagnostics.errors",       # UnknownDefinition*Error
)


@pytest.mark.xfail(
    reason="Phase 18.6 extracts utc_now/errors/versioning into platform/core",
    strict=False,
)
def test_platform_does_not_import_commerce_generic_utilities():
    imports = all_imports("app/platform")
    offending = [m for m in _COMMERCE_GENERIC_UTILITIES if m in imports]
    assert not offending, (
        f"platform imports commerce generic utilities: {offending}"
    )
