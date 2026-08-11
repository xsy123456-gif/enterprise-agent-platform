"""Group 3 Contract Tests — Public API only.

Imports ONLY from app.memory and app.memory.api.testing.
"""

import time
import unittest

from app.memory import (
    MemoryObservation,
    MemoryPrincipal,
    MemoryReadRequest,
    MemoryReadResult,
    MemoryRecord,
    MemoryRuntime,
    MemorySource,
    MemoryType,
    MemoryValidationError,
    MemoryWriteReceipt,
    MemoryWriteRequest,
)
from app.memory import MemoryScope
from tests.memory.testing import (
    build_test_memory,
    build_test_memory_with_spies,
    SpyCounters,
)


# ── Public Imports ─────────────────────────────────────────────────

class PublicImportsTest(unittest.TestCase):
    def test_system_has_client_and_runtime(self):
        s = build_test_memory()
        self.assertTrue(hasattr(s, "client"))
        self.assertTrue(hasattr(s, "runtime"))


# ── Write Contract ────────────────────────────────────────────────

class WriteContractTest(unittest.TestCase):
    def setUp(self):
        self.system = build_test_memory()

    def test_write_returns_receipt(self):
        req = _make_write_request("wc-1")
        receipt = self.system.client.write(req)
        self.assertIsInstance(receipt, MemoryWriteReceipt)
        self.assertTrue(receipt.accepted)
        self.assertIsNotNone(receipt.event_id)

    def test_duplicate_idempotency_returns_same_event_id(self):
        req = _make_write_request("wc-2")
        r1 = self.system.client.write(req)
        r2 = self.system.client.write(req)
        self.assertEqual(r1.event_id, r2.event_id)


# ── Read Contract (Public Seal) ────────────────────────────────────

class PublicSealTest(unittest.TestCase):
    def test_write_and_read_engineer(self):
        system = build_test_memory()
        system.runtime.start()
        try:
            req = _make_write_request("seal-1", entity_id="张三",
                                       attribute="职业", content="工程师",
                                       type_id="person")
            receipt = system.client.write(req)
            self.assertTrue(receipt.accepted)

            found = _poll_read_until(
                system,
                query="张三的职业是什么？",
                types=["person"],
                predicate=lambda rec: rec.entity_id == "张三"
                    and (rec.attribute == "职业" or rec.attribute == "occupation")
                    and rec.content == "工程师",
                timeout=5,
            )
            self.assertTrue(found, "seal: read must find 工程师")
        finally:
            system.runtime.stop()


# ── Read Contract ─────────────────────────────────────────────────

class ReadContractTest(unittest.TestCase):
    def setUp(self):
        self.system = build_test_memory()

    def test_empty_query_results_empty(self):
        result = self.system.client.read(_make_read_request("天马座", []))
        self.assertEqual(0, len(result.records))


# ── Validation ─────────────────────────────────────────────────────

class ValidationTest(unittest.TestCase):
    def test_empty_query_rejected(self):
        with self.assertRaises(MemoryValidationError):
            _make_read_request("")

    def test_query_too_long(self):
        with self.assertRaises(MemoryValidationError):
            _make_read_request("x" * 4097)

    def test_limit_zero(self):
        with self.assertRaises(MemoryValidationError):
            MemoryReadRequest(
                principal=MemoryPrincipal("u", "tn", "u", "ag"),
                scope=MemoryScope("tn", "u", "ag"),
                query="x", limit=0,
            )

    def test_limit_101(self):
        with self.assertRaises(MemoryValidationError):
            MemoryReadRequest(
                principal=MemoryPrincipal("u", "tn", "u", "ag"),
                scope=MemoryScope("tn", "u", "ag"),
                query="x", limit=101,
            )

    def test_invalid_type_rejected(self):
        with self.assertRaises(MemoryValidationError):
            _make_read_request("x", ["hacked_type"])

    def test_empty_observations_rejected(self):
        with self.assertRaises(MemoryValidationError):
            MemoryWriteRequest(
                principal=MemoryPrincipal("u", "tn", "u", "ag"),
                scope=MemoryScope("tn", "u", "ag"),
                idempotency_key="k",
                source=MemorySource("t", "s"),
                observations=[],
            )

    def test_content_none_rejected(self):
        with self.assertRaises(MemoryValidationError):
            MemoryWriteRequest(
                principal=MemoryPrincipal("u", "tn", "u", "ag"),
                scope=MemoryScope("tn", "u", "ag"),
                idempotency_key="k",
                source=MemorySource("t", "s"),
                observations=[MemoryObservation("f", None)],
            )

    def test_invalid_source_rejected(self):
        with self.assertRaises(MemoryValidationError):
            MemoryWriteRequest(
                principal=MemoryPrincipal("u", "tn", "u", "ag"),
                scope=MemoryScope("tn", "u", "ag"),
                idempotency_key="k",
                source=MemorySource("", "s"),
                observations=[MemoryObservation("f", "x")],
            )

    def test_empty_idempotency_key_rejected(self):
        with self.assertRaises(MemoryValidationError):
            MemoryWriteRequest(
                principal=MemoryPrincipal("u", "tn", "u", "ag"),
                scope=MemoryScope("tn", "u", "ag"),
                idempotency_key="",
                source=MemorySource("t", "s"),
                observations=[MemoryObservation("f", "x")],
            )

    # ── spy boundary tests ──────────────────────────────────────────

    def test_invalid_write_never_calls_save_event(self):
        system, counters = build_test_memory_with_spies()
        with self.assertRaises(MemoryValidationError):
            MemoryWriteRequest(
                principal=MemoryPrincipal("u", "tn", "u", "ag"),
                scope=MemoryScope("tn", "u", "ag"),
                idempotency_key="",
                source=MemorySource("t", "s"),
                observations=[MemoryObservation("f", "x")],
            )
        self.assertEqual(0, counters.save_event_calls,
                         "save_event must not be called for invalid write")

    def test_invalid_read_never_calls_embedding(self):
        system, counters = build_test_memory_with_spies()
        with self.assertRaises(MemoryValidationError):
            _make_read_request("")
        self.assertEqual(0, counters.embed_calls,
                         "embed must not be called for invalid read")


# ── MemoryScope ────────────────────────────────────────────────────

class MemoryScopeTest(unittest.TestCase):
    def test_empty_tenant_id(self):
        with self.assertRaises(MemoryValidationError):
            MemoryScope("", "u", "a")

    def test_empty_user_id(self):
        with self.assertRaises(MemoryValidationError):
            MemoryScope("tn", "", "a")

    def test_empty_agent_id(self):
        with self.assertRaises(MemoryValidationError):
            MemoryScope("tn", "u", "")

    def test_invalid_department_id(self):
        with self.assertRaises(MemoryValidationError):
            MemoryScope("tn", "u", "a", department_id="")


# ── Lifecycle ──────────────────────────────────────────────────────

class LifecycleTest(unittest.TestCase):
    def setUp(self):
        self.system = build_test_memory()

    def test_build_does_not_auto_start(self):
        self.assertFalse(self.system.runtime.running)

    def test_start_stop(self):
        self.system.runtime.start()
        self.assertTrue(self.system.runtime.running)
        self.system.runtime.stop()
        self.assertFalse(self.system.runtime.running)

    def test_start_idempotent(self):
        self.system.runtime.start()
        self.system.runtime.start()
        self.assertTrue(self.system.runtime.running)

    def test_stop_idempotent(self):
        self.system.runtime.start()
        self.system.runtime.stop()
        self.system.runtime.stop()
        self.assertFalse(self.system.runtime.running)

    def test_client_has_no_lifecycle(self):
        c = self.system.client
        self.assertFalse(hasattr(c, "start"))
        self.assertFalse(hasattr(c, "stop"))
        self.assertFalse(hasattr(c, "health"))

    def test_runtime_has_no_business(self):
        r = self.system.runtime
        self.assertFalse(hasattr(r, "read"))
        self.assertFalse(hasattr(r, "write"))


# ── Helpers ────────────────────────────────────────────────────────

def _poll_read_until(system, query, types, predicate, timeout):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        result = system.client.read(_make_read_request(query, types))
        for rec in result.records:
            try:
                if predicate(rec):
                    return True
            except Exception:
                continue
        time.sleep(0.05)
    return False


def _make_write_request(key, content="工程师",
                        entity_id="张三", attribute="职业", type_id="person"):
    principal = MemoryPrincipal("u", "tn", "u", "ag")
    scope = MemoryScope("tn", "u", "ag")
    return MemoryWriteRequest(
        principal=principal, scope=scope,
        idempotency_key=key,
        source=MemorySource("test", key),
        observations=[MemoryObservation("fact", content)],
        metadata={"memory_candidates": [{
            "type": type_id, "entity_id": entity_id,
            "attribute": attribute, "content": content,
            "confidence": 0.9, "business_value": 0.9,
            "stability": 0.9, "explicitness": 1.0,
            "future_usefulness": 0.9,
        }]},
    )


def _make_read_request(query="工程师", types=None):
    principal = MemoryPrincipal("u", "tn", "u", "ag")
    scope = MemoryScope("tn", "u", "ag")
    return MemoryReadRequest(
        principal=principal, scope=scope,
        query=query, types=types or [],
    )


if __name__ == "__main__":
    unittest.main()
