"""Evaluation metrics unit tests."""

import unittest

from app.knowledge.evaluation.metrics import evaluate_queries


class MetricsTest(unittest.TestCase):
    def test_perfect_retrieval(self):
        results = {"q1": {"retrieved": ["a", "b"], "relevant": ["a"]}}
        metrics = evaluate_queries(results, k=3)
        self.assertAlmostEqual(1.0, metrics.recall_at_k)
        self.assertAlmostEqual(1.0, metrics.mrr)
        self.assertAlmostEqual(1.0, metrics.hit_rate)

    def test_miss(self):
        results = {"q1": {"retrieved": ["x", "y"], "relevant": ["a"]}}
        metrics = evaluate_queries(results, k=3)
        self.assertAlmostEqual(0.0, metrics.recall_at_k)
        self.assertAlmostEqual(0.0, metrics.hit_rate)
        self.assertAlmostEqual(0.0, metrics.mrr)

    def test_rank_affects_mrr(self):
        results = {
            "q1": {"retrieved": ["b", "a"], "relevant": ["a"]},
            "q2": {"retrieved": ["a"], "relevant": ["a"]},
        }
        metrics = evaluate_queries(results, k=3)
        self.assertAlmostEqual((0.5 + 1.0) / 2, metrics.mrr)

    def test_recall_partial(self):
        results = {"q1": {"retrieved": ["a"], "relevant": ["a", "b"]}}
        metrics = evaluate_queries(results, k=3)
        self.assertAlmostEqual(0.5, metrics.recall_at_k)


if __name__ == "__main__":
    unittest.main()
