"""Reference dataset consistency tests.

The platform-level enums (``ProfessionalLevel``, ``SecurityClearance``) are the
runtime authority for value domains; the YAML files are the human-readable
enterprise dataset.  These tests guarantee the two never drift apart.
"""

from pathlib import Path

import yaml

from app.identity import ProfessionalLevel, SecurityClearance

ROOT = Path(__file__).resolve().parents[2] / "data" / "identity"


def test_levels_yaml_matches_enum():
    data = yaml.safe_load((ROOT / "levels.yaml").read_text(encoding="utf-8"))
    ids = [item["id"] for item in data["levels"]]
    assert ids == ProfessionalLevel.values()


def test_security_clearances_yaml_matches_enum():
    data = yaml.safe_load(
        (ROOT / "security_clearances.yaml").read_text(encoding="utf-8")
    )
    ids = [item["id"] for item in data["security_clearances"]]
    assert ids == SecurityClearance.values()
