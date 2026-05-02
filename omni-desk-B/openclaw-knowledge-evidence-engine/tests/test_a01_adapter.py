"""Tests for A01 Feishu data adapter."""
import pytest
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.connectors.feishu_adapter import load_source, load_manifest


def test_load_docs():
    sources = load_source("docs", tenant_id="demo_tenant", project_id="alpha_report_platform")
    assert len(sources) >= 1
    src = sources[0]
    assert src["source_type"] == "docs"
    assert "updated_at" in src
    assert "permission_scope" in src


def test_load_minutes():
    sources = load_source("minutes", tenant_id="demo_tenant")
    assert len(sources) >= 1
    assert sources[0]["source_type"] == "minutes"


def test_load_by_source_id():
    sources = load_source("docs", source_id="doc_alpha_prd", tenant_id="demo_tenant")
    assert len(sources) == 1
    assert sources[0]["source_id"] == "doc_alpha_prd"


def test_cross_tenant_blocked():
    sources = load_source("docs", source_id="doc_alpha_prd", tenant_id="other_tenant")
    assert len(sources) == 0


def test_manifest_source_count():
    manifest = load_manifest("demo_tenant", "alpha_report_platform")
    assert len(manifest) >= 3
    types = {s["source_type"] for s in manifest}
    assert "docs" in types
    assert "minutes" in types


def test_manifest_fields():
    manifest = load_manifest("demo_tenant")
    for s in manifest:
        assert "source_id" in s
        assert "source_type" in s
        assert "updated_at" in s
        assert "permission_scope" in s
