"""Tests for A03 Document parser."""
import pytest
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.connectors.feishu_adapter import load_source
from app.ingestion.document_parser import parse, full_text, ParsedDocument, ParsedMinutes, ParsedTasks


def test_parse_doc():
    raws = load_source("docs", source_id="doc_alpha_prd", tenant_id="demo_tenant")
    assert raws
    parsed = parse(raws[0])
    assert isinstance(parsed, ParsedDocument)
    assert parsed.title != ""
    assert len(parsed.sections) >= 3
    # Heading levels preserved
    levels = [s["level"] for s in parsed.sections]
    assert 1 in levels


def test_parse_minutes():
    raws = load_source("minutes", source_id="minutes_alpha_review", tenant_id="demo_tenant")
    assert raws
    parsed = parse(raws[0])
    assert isinstance(parsed, ParsedMinutes)
    assert len(parsed.attendees) > 0
    assert len(parsed.decisions) > 0
    assert len(parsed.action_items_raw) > 0
    # Agenda not empty
    assert len(parsed.agenda) > 0


def test_parse_tasks():
    raws = load_source("tasks", source_id="tasks_alpha", tenant_id="demo_tenant")
    assert raws
    parsed = parse(raws[0])
    assert isinstance(parsed, ParsedTasks)
    assert len(parsed.tasks) >= 3


def test_full_text_doc():
    raws = load_source("docs", source_id="doc_alpha_prd", tenant_id="demo_tenant")
    parsed = parse(raws[0])
    text = full_text(parsed)
    assert "权限" in text
    assert len(text) > 100


def test_full_text_minutes():
    raws = load_source("minutes", source_id="minutes_alpha_review", tenant_id="demo_tenant")
    parsed = parse(raws[0])
    text = full_text(parsed)
    assert "决议" in text or "联调" in text
