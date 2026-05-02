"""Contract tests: API request/response validation using frozen contracts."""
import json
import pytest
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pathlib import Path
CONTRACTS = Path(__file__).parent.parent / "contracts"


def load_contract(name):
    return json.loads((CONTRACTS / name).read_text(encoding="utf-8"))


def test_query_contract_fields():
    req = load_contract("b_to_a_query_request.json")
    assert "trace_id" in req
    assert "query" in req
    assert "project_id" in req
    assert isinstance(req.get("top_k", 8), int)


def test_premeeting_contract_fields():
    req = load_contract("premeeting_context_request.json")
    assert "meeting_id" in req
    assert "lookback_days" in req
    assert isinstance(req["include_unfinished_tasks"], bool)


def test_action_items_contract_fields():
    req = load_contract("minutes_action_items_request.json")
    assert "minutes_id" in req
    assert req["minutes_id"] == "minutes_alpha_review"


def test_weekly_window_contract_fields():
    req = load_contract("weekly_window_request.json")
    assert "project_id" in req
    assert "week_start" in req
    assert "week_end" in req
    # Dates valid
    from datetime import datetime
    datetime.strptime(req["week_start"], "%Y-%m-%d")
    datetime.strptime(req["week_end"], "%Y-%m-%d")
