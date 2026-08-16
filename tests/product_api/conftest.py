"""Shared fixtures for Product API tests (Phase 18.12)."""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.api.server import build_http_application
from app.commerce.domain import MetricSeries, Store
from tests.memory.repository import TestEmbeddingService, TestMemoryRepository


class _StubLLM:
    def chat(self, messages, **kwargs):
        return '{"goal":"g","steps":[]}'


def seed_commerce(application):
    repository = application.commerce.repository
    repository.upsert_store("company_A", Store(
        store_id="JP01", tenant_id="company_A", platform="amazon",
        marketplace="JP", external_store_id="ext-JP01", name="Japan Store",
        currency="JPY", timezone="Asia/Tokyo"))
    for name, value in [("GMV", 1000.0), ("GMV_B", 2000.0),
                        ("ORDERS", 20.0), ("ORDERS_B", 40.0),
                        ("SESSIONS", 1000.0), ("SESSIONS_B", 1000.0)]:
        repository.upsert_metric("company_A", MetricSeries(
            metric_record_id=name, tenant_id="company_A", subject_type="STORE",
            subject_id="JP01", metric_name=name, metric_class="AGGREGATED",
            granularity="DAILY", period_start="2026-08-01",
            period_end="2026-08-02", value=value))
    return application


@pytest.fixture()
def http_app():
    with patch("app.main.create_llm", return_value=_StubLLM()):
        app = build_http_application(
            "testing",
            memory_repository=TestMemoryRepository(),
            memory_embedding_service=TestEmbeddingService(),
        )
    seed_commerce(app.state.application)
    return app


@pytest.fixture()
def client(http_app):
    return TestClient(http_app)


@pytest.fixture()
def application(http_app):
    return http_app.state.application


AUTH = {"Authorization": "Bearer test-user-U001"}
