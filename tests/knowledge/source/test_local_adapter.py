"""Local file source adapter tests (read + convert, no RAG backend)."""

from pathlib import Path

from app.knowledge.source.errors import KnowledgeSourceNotFoundError
from app.knowledge.source.local import LocalFileSourceAdapter

ROOT = Path(__file__).resolve().parents[3] / "data" / "knowledge" / "sources"


def _adapter():
    return LocalFileSourceAdapter(str(ROOT))


def test_list_documents():
    adapter = _adapter()
    assert len(adapter.list_documents()) == 6


def test_read_pdf_document():
    adapter = _adapter()
    document = adapter.read_document("policies/日本站退换货政策.pdf")
    assert document.tenant_id == "demo"
    assert document.document_type == "policy"
    assert "退货" in document.content
    assert document.access_policy["security_level"] == "public"


def test_read_docx_document():
    adapter = _adapter()
    document = adapter.read_document("products/商品说明书.docx")
    assert "充电器" in document.content
    assert document.access_policy["security_level"] == "public"


def test_read_parts_pdf_pages():
    adapter = _adapter()
    parts = adapter.read_parts("policies/日本站退换货政策.pdf")
    assert len(parts) >= 1
    assert any(p.access_policy.get("page") for p in parts)


def test_read_parts_docx_sections():
    adapter = _adapter()
    parts = adapter.read_parts("products/商品说明书.docx")
    assert len(parts) >= 1
    assert any(p.access_policy.get("section") for p in parts)


def test_read_missing_raises():
    adapter = _adapter()
    try:
        adapter.read_document("not/exist.pdf")
        assert False, "expected KnowledgeSourceNotFoundError"
    except KnowledgeSourceNotFoundError:
        pass


def test_acl_metadata_propagates():
    adapter = _adapter()
    doc = adapter.read_document("management/管理层经营制度.docx")
    assert doc.access_policy["security_level"] == "confidential"
    store = adapter.read_document("stores/JP01内部规则.pdf")
    assert store.access_policy["store_id"] == "JP01"
