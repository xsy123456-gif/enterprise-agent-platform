"""ContributionEngine tests: change attribution, ranking, coverage."""

import pytest

from app.commerce.diagnostics import ContributionEngine


def test_basic_attribution_and_rank():
    engine = ContributionEngine()
    # parent GMV dropped 100; product A dropped 60, product B dropped 40, C rose 10.
    analysis = engine.attribute_change(
        parent_current=900, parent_baseline=1000,
        children=[("product_A", 440, 500), ("product_B", 460, 500), ("product_C", 110, 100)],
    )
    by_id = {item.subject_id: item for item in analysis.items}
    assert by_id["product_A"].relative_contribution == pytest.approx(0.6)
    assert by_id["product_B"].relative_contribution == pytest.approx(0.4)
    assert by_id["product_A"].rank == 1
    assert by_id["product_B"].rank == 2
    assert by_id["product_C"].rank == 3


def test_net_coverage_and_explained_change():
    engine = ContributionEngine()
    analysis = engine.attribute_change(
        parent_current=900, parent_baseline=1000,
        children=[("a", 400, 500), ("b", 500, 500)],
    )
    # explained_change = -100 + 0 = -100 == parent change -> full coverage.
    assert analysis.explained_change == pytest.approx(-100.0)
    assert analysis.unexplained_change == pytest.approx(0.0)
    assert analysis.coverage == pytest.approx(1.0)


def test_unexplained_change():
    engine = ContributionEngine()
    analysis = engine.attribute_change(
        parent_current=900, parent_baseline=1000,
        children=[("a", 450, 500)],  # only explains half the -100 drop
    )
    assert analysis.explained_change == pytest.approx(-50.0)
    assert analysis.unexplained_change == pytest.approx(-50.0)
    assert analysis.coverage == pytest.approx(0.5)


def test_gross_movement_ratio_when_parent_changes():
    engine = ContributionEngine()
    # parent dropped 100; a dropped 150, b rose 50 -> gross movement 200 / 100 = 2.
    analysis = engine.attribute_change(
        parent_current=900, parent_baseline=1000,
        children=[("a", 400, 550), ("b", 500, 450)],
    )
    assert analysis.explained_change == pytest.approx(-100.0)
    assert analysis.gross_movement_ratio == pytest.approx(2.0)
    assert analysis.coverage == pytest.approx(1.0)


def test_zero_parent_change_relative_none():
    engine = ContributionEngine()
    analysis = engine.attribute_change(
        parent_current=1000, parent_baseline=1000,
        children=[("a", 500, 500), ("b", 500, 500)],
    )
    assert all(item.relative_contribution is None for item in analysis.items)
    assert analysis.coverage is None
    assert analysis.gross_movement_ratio is None


def test_algorithm_version_recorded():
    engine = ContributionEngine()
    analysis = engine.attribute_change(900, 1000, [("a", 900, 1000)])
    assert analysis.algorithm_version == "share_of_change_v1"
