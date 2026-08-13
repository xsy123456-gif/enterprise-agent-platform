"""Knowledge source discovery tests."""

from pathlib import Path

from app.knowledge.source import KnowledgeSourceScanner

ROOT = Path(__file__).resolve().parents[3] / "data" / "knowledge" / "sources"


def test_scanner_discovers_six_files():
    scanner = KnowledgeSourceScanner(str(ROOT))
    documents = scanner.scan()
    assert len(documents) == 6
    ids = {d.source_id for d in documents}
    assert "products/商品说明书.docx" in ids
    assert "faq/客服FAQ.pdf" in ids
    assert "policies/日本站退换货政策.pdf" in ids
    assert "operations/广告投放SOP.docx" in ids
    assert "stores/JP01内部规则.pdf" in ids
    assert "management/管理层经营制度.docx" in ids


def test_document_type_mapped_from_directory():
    scanner = KnowledgeSourceScanner(str(ROOT))
    by_id = {d.source_id: d for d in scanner.scan()}
    assert by_id["products/商品说明书.docx"].document_type == "product"
    assert by_id["faq/客服FAQ.pdf"].document_type == "faq"
    assert by_id["policies/日本站退换货政策.pdf"].document_type == "policy"
    assert by_id["operations/广告投放SOP.docx"].document_type == "sop"
    assert by_id["stores/JP01内部规则.pdf"].document_type == "store_rule"
    assert by_id["management/管理层经营制度.docx"].document_type == "management"


def test_acl_metadata_from_sidecar():
    scanner = KnowledgeSourceScanner(str(ROOT))
    by_id = {d.source_id: d for d in scanner.scan()}
    product = by_id["products/商品说明书.docx"]
    assert product.tenant_id == "demo"
    assert product.metadata["security_level"] == "public"
    assert product.metadata["knowledge_scope"] == "product"

    store = by_id["stores/JP01内部规则.pdf"]
    assert store.metadata["security_level"] == "internal"
    assert store.metadata["store_id"] == "JP01"

    mgmt = by_id["management/管理层经营制度.docx"]
    assert mgmt.metadata["security_level"] == "confidential"


def test_checksum_is_stable():
    scanner = KnowledgeSourceScanner(str(ROOT))
    first = {d.source_id: d.checksum for d in scanner.scan()}
    second = {d.source_id: d.checksum for d in scanner.scan()}
    assert first == second
    assert all(checksum for checksum in first.values())
