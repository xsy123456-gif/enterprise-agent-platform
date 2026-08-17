"""Phase 18.0 guard: production security must fail-closed.

Production must never default to ``AllowAll`` governance or memory
authorization.  ``build_application`` selects the policy by environment via
``app.composition.security``; the security validator (Phase 18.7) fails startup
on any insecure production configuration.
"""

from pathlib import Path

from tests.architecture._scan import scan_imports


def _source_contains(relative_path, token):
    return token in (Path(relative_path)).read_text(encoding="utf-8")


def test_composition_does_not_default_to_allow_all():
    for path in ("app/main.py", "app/composition/production.py",
                 "app/composition/factory.py"):
        assert not _source_contains(
            path, "AllowAllGovernancePolicy"), (
            f"{path} must not reference AllowAllGovernancePolicy"
        )
        assert not _source_contains(
            path, "AllowAllMemoryAuthorizationProvider"), (
            f"{path} must not reference AllowAllMemoryAuthorizationProvider"
        )
