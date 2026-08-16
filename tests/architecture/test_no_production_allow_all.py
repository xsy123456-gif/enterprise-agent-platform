"""Phase 18.0 guard: production security must fail-closed.

Production must never default to ``AllowAll`` governance or memory
authorization, nor fall back to a local principal source.  Startup with an
insecure production configuration must fail.

Currently ``app/main.py``'s composition uses ``AllowAllGovernancePolicy`` and
imports ``AllowAllMemoryAuthorizationProvider``; this guard is ``xfail`` until
Phase 18.7 wires the Permission-backed adapters + startup validation.
"""

import pytest

from tests.architecture._scan import scan_imports


def _source_contains(path, token):
    return token in (path).read_text(encoding="utf-8")


@pytest.mark.xfail(
    reason="Phase 18.7 replaces AllowAll with permission-backed adapters",
    strict=False,
)
def test_composition_does_not_default_to_allow_all():
    for path in ("app/main.py", "app/composition/production.py",
                 "app/composition/factory.py"):
        assert not _source_contains(
            __import__("pathlib").Path(path), "AllowAllGovernancePolicy"), (
            f"{path} must not reference AllowAllGovernancePolicy"
        )
        assert not _source_contains(
            __import__("pathlib").Path(path), "AllowAllMemoryAuthorizationProvider"), (
            f"{path} must not reference AllowAllMemoryAuthorizationProvider"
        )
