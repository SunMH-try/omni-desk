"""A02 — Permission & tenant isolation guard."""
from __future__ import annotations
import yaml
from pathlib import Path
from app.config import FIXTURES_DIR


def _load_policy(tenant_id: str) -> dict:
    policy_file = FIXTURES_DIR / "permissions" / "permission_policy.yaml"
    if not policy_file.exists():
        return {}
    policy = yaml.safe_load(policy_file.read_text(encoding="utf-8"))
    if policy.get("tenant_id") != tenant_id:
        return {}
    return policy


def filter_sources(
    source_manifest: list[dict],
    user_id: str,
    tenant_id: str,
) -> tuple[list[dict], list[dict], list[dict]]:
    """Filter sources by permission.

    Returns (allowed_sources, blocked_sources, audit_log).
    Raises PermissionError if tenant_id is missing.
    """
    if not tenant_id:
        raise PermissionError("tenant_id is required")

    policy = _load_policy(tenant_id)
    user_groups = set(policy.get("users", {}).get(user_id, {}).get("groups", []))
    source_policies = policy.get("sources", {})

    allowed, blocked, audit_log = [], [], []

    for src in source_manifest:
        if src.get("tenant_id") != tenant_id:
            blocked.append(src)
            audit_log.append({"source_id": src["source_id"], "result": "blocked", "reason": "cross_tenant"})
            continue

        src_id = src["source_id"]
        allowed_groups = set(source_policies.get(src_id, {}).get("allowed_groups", src.get("permission_scope", [])))

        if user_groups & allowed_groups:
            allowed.append(src)
            audit_log.append({"source_id": src_id, "result": "allowed"})
        else:
            blocked.append(src)
            audit_log.append({"source_id": src_id, "result": "blocked", "reason": "no_permission"})

    return allowed, blocked, audit_log


def assert_source_allowed(source_id: str, user_id: str, tenant_id: str) -> bool:
    """Quick single-source permission check."""
    if not tenant_id:
        raise PermissionError("tenant_id is required")
    policy = _load_policy(tenant_id)
    user_groups = set(policy.get("users", {}).get(user_id, {}).get("groups", []))
    source_policies = policy.get("sources", {})
    allowed_groups = set(source_policies.get(source_id, {}).get("allowed_groups", []))
    return bool(user_groups & allowed_groups)
