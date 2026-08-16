"""Phase 18.0 guard: Platform dependency direction.

The Platform layer must depend on Platform Foundation, not on Commerce generic
utilities.  The three generic abstractions (utc_now, error base, versioned
registry) live in ``app/core`` (Phase 18.6); Commerce depends on them — never
the reverse.
"""

from tests.architecture._scan import all_imports

_COMMERCE_GENERIC_UTILITIES = (
    "app.commerce.domain.base",              # utc_now
    "app.commerce.contracts.errors",         # CommerceError base
    "app.commerce.diagnostics.registry.base",  # VersionedRegistry
    "app.commerce.diagnostics.errors",       # UnknownDefinition*Error
)


def test_platform_does_not_import_commerce_generic_utilities():
    imports = all_imports("app/platform")
    offending = [m for m in _COMMERCE_GENERIC_UTILITIES if m in imports]
    assert not offending, (
        f"platform imports commerce generic utilities: {offending}"
    )
