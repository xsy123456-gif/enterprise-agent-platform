"""Knowledge retrieval performance benchmark.

Run manually::

    python -m tests.knowledge.evaluation.run_performance

Measures P50/P95/P99 latency and concurrent throughput (10/50/100) on the real
Qdrant + Ollama stack.
"""

import concurrent.futures
import json
import statistics
import time

from .run_evaluation import (
    _build_store,
    _ingest,
    _retrieve_hybrid,
    QUERIES,
)


def _latency_percentiles(samples):
    ordered = sorted(samples)
    n = len(ordered)
    if n == 0:
        return {}
    return {
        "p50": ordered[int(n * 0.50)],
        "p95": ordered[min(int(n * 0.95), n - 1)],
        "p99": ordered[min(int(n * 0.99), n - 1)],
    }


def _measure_single_latency(store, iterations=3):
    samples = []
    for _ in range(iterations):
        for query, _ in QUERIES:
            start = time.perf_counter()
            _retrieve_hybrid(store, query)
            samples.append(time.perf_counter() - start)
    return samples


def _measure_concurrent(store, concurrency):
    queries = [q for q, _ in QUERIES]

    def work(index):
        start = time.perf_counter()
        _retrieve_hybrid(store, queries[index % len(queries)])
        return time.perf_counter() - start

    start = time.perf_counter()
    with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as pool:
        latencies = list(pool.map(work, range(concurrency)))
    total = time.perf_counter() - start
    return {
        "concurrency": concurrency,
        "total_seconds": round(total, 3),
        "throughput_qps": round(concurrency / total, 2),
        "avg_latency": round(statistics.mean(latencies), 3),
    }


def main():
    store = _build_store()
    _ingest(store)

    single = _measure_single_latency(store, iterations=2)
    report = {
        "single_retrieval_latency_seconds": _latency_percentiles(single),
        "concurrent": [
            _measure_concurrent(store, 10),
            _measure_concurrent(store, 50),
            _measure_concurrent(store, 100),
        ],
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
