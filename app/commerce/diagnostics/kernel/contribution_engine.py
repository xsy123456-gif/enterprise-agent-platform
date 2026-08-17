"""ContributionEngine — versioned change attribution.

Algorithm ``share_of_change_v1``: for a parent metric and its children, each
child's contribution to the parent's change is its own absolute change; the
relative contribution is that change divided by the parent's change.  Children
are ranked by |relative contribution| (falling back to |absolute| when the
parent change is zero).

- ``explained_change`` = sum of signed child changes (net explanation);
- ``unexplained_change`` = parent change - explained change;
- ``coverage`` = net explanation coverage in [0, 1];
- ``gross_movement_ratio`` = sum(|child change|) / |parent change| (may be > 1).
"""

from app.commerce.diagnostics.models import ContributionAnalysis, ContributionResult

ALGORITHM_VERSION = "share_of_change_v1"


class ContributionEngine:
    ALGORITHM_VERSION = ALGORITHM_VERSION

    def attribute_change(self, parent_current, parent_baseline, children):
        """Attribute the parent's change to its children.

        ``children`` is an iterable of ``(subject_id, current, baseline)``.
        Returns a ``ContributionAnalysis`` with ranked items.
        """
        parent_change = parent_current - parent_baseline
        items = []
        for subject_id, current, baseline in children:
            child_change = current - baseline
            relative = child_change / parent_change if parent_change else None
            items.append(ContributionResult(
                subject_id=subject_id,
                absolute_contribution=child_change,
                relative_contribution=relative,
                rank=0,
            ))
        ranked = sorted(
            items,
            key=lambda item: (
                abs(item.relative_contribution) if item.relative_contribution is not None
                else abs(item.absolute_contribution)
            ),
            reverse=True,
        )
        ranked = [
            ContributionResult(
                subject_id=item.subject_id,
                absolute_contribution=item.absolute_contribution,
                relative_contribution=item.relative_contribution,
                rank=index + 1,
            )
            for index, item in enumerate(ranked)
        ]
        explained_change = sum(item.absolute_contribution for item in ranked)
        if parent_change:
            coverage = max(0.0, min(1.0, explained_change / parent_change))
            gross_movement_ratio = (
                sum(abs(item.absolute_contribution) for item in ranked) / abs(parent_change)
            )
        else:
            coverage = None
            gross_movement_ratio = None
        return ContributionAnalysis(
            items=tuple(ranked),
            explained_change=explained_change,
            unexplained_change=parent_change - explained_change,
            coverage=coverage,
            gross_movement_ratio=gross_movement_ratio,
            algorithm_version=self.ALGORITHM_VERSION,
        )


__all__ = ["ContributionEngine", "ALGORITHM_VERSION"]
