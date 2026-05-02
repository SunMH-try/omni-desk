"""Tests for A02 Permission guard."""
import pytest
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.security.permission_guard import filter_sources, assert_source_allowed
from app.connectors.feishu_adapter import load_manifest


def _manifest():
    return load_manifest("demo_tenant", "alpha_report_platform")


def test_project_member_can_access():
    manifest = _manifest()
    allowed, blocked, log = filter_sources(manifest, "user_pm", "demo_tenant")
    assert len(allowed) > 0
    assert all(e["result"] == "allowed" for e in log if e["source_id"] in {s["source_id"] for s in allowed})


def test_cross_tenant_blocked():
    manifest = [{"source_id": "s1", "source_type": "docs", "tenant_id": "other_tenant",
                 "title": "", "url": "", "project_id": "x", "permission_scope": [], "updated_at": ""}]
    allowed, blocked, log = filter_sources(manifest, "user_pm", "demo_tenant")
    assert len(allowed) == 0
    assert len(blocked) == 1
    assert log[0]["reason"] == "cross_tenant"


def test_missing_tenant_raises():
    with pytest.raises(PermissionError):
        filter_sources([], "user_pm", "")


def test_external_user_blocked():
    manifest = _manifest()
    allowed, blocked, _ = filter_sources(manifest, "user_external", "demo_tenant")
    assert len(allowed) == 0


def test_assert_source_allowed():
    assert assert_source_allowed("doc_alpha_prd", "user_pm", "demo_tenant") is True


def test_assert_source_denied():
    assert assert_source_allowed("doc_alpha_prd", "user_external", "demo_tenant") is False
