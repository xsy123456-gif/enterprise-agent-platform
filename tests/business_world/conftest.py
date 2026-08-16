"""Business world seed test fixtures (Phase 18.14)."""

from pathlib import Path

import pytest

SEED_ROOT = str(Path(__file__).resolve().parents[2] / "data" / "seed"
                / "enterprise-commerce-v1")


@pytest.fixture(scope="module")
def seed_root():
    return SEED_ROOT
