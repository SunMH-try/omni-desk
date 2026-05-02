"""飞书文档内容读取器 — 支持 docx / wiki / docs 三种文档类型。"""
from __future__ import annotations
import re
import logging
from typing import Callable, Tuple, Optional

import httpx

logger = logging.getLogger(__name__)
FEISHU_API = "https://open.feishu.cn/open-apis"

_DOC_URL_RE = re.compile(
    r'https?://[a-zA-Z0-9\-]+\.feishu\.cn/(docx|wiki|docs)/([A-Za-z0-9]+)'
)


def extract_doc_token(url: str) -> Tuple[Optional[str], Optional[str]]:
    """从飞书文档 URL 提取 (doc_type, token)，失败返回 (None, None)。"""
    m = _DOC_URL_RE.search(url)
    if not m:
        return None, None
    return m.group(1), m.group(2)


def fetch_doc_content(doc_type: str, token: str, get_token_fn: Callable[[], str]) -> str:
    """
    根据文档类型和 token 调飞书 API 获取文档纯文本内容。
    get_token_fn: 无参函数，返回有效的 tenant_access_token。
    """
    try:
        headers = {"Authorization": f"Bearer {get_token_fn()}"}

        if doc_type == "wiki":
            # Step 1: 通过 wiki node token 获取实际文档信息
            resp = httpx.get(
                f"{FEISHU_API}/wiki/v2/spaces/get_node",
                params={"token": token},
                headers=headers,
                timeout=15,
            )
            d = resp.json()
            if d.get("code") != 0:
                logger.warning(f"Wiki get_node 失败: code={d.get('code')} msg={d.get('msg')}")
                return ""
            node = d.get("data", {}).get("node", {})
            obj_type = node.get("obj_type", "docx")
            obj_token = node.get("obj_token", "")
            if not obj_token:
                return ""
            actual_type = "docx" if obj_type == "docx" else "docs"
            return fetch_doc_content(actual_type, obj_token, get_token_fn)

        elif doc_type == "docx":
            resp = httpx.get(
                f"{FEISHU_API}/docx/v1/documents/{token}/raw_content",
                headers=headers,
                timeout=15,
            )
            d = resp.json()
            if d.get("code") != 0:
                logger.warning(f"Docx raw_content 失败: code={d.get('code')} msg={d.get('msg')}")
                return ""
            return d.get("data", {}).get("content", "")

        elif doc_type == "docs":
            # 旧版 doc API
            resp = httpx.get(
                f"{FEISHU_API}/doc/v2/{token}/content",
                headers=headers,
                timeout=15,
            )
            d = resp.json()
            if d.get("code") != 0:
                logger.warning(f"Doc content 失败: code={d.get('code')} msg={d.get('msg')}")
                return ""
            content_body = d.get("data", {}).get("document", {}).get("body", {})
            return _extract_text_from_doc_body(content_body)

        else:
            logger.warning(f"未知文档类型: {doc_type}")
            return ""

    except Exception as e:
        logger.error(f"读取飞书文档失败 ({doc_type}/{token}): {e}")
        return ""


def _extract_text_from_doc_body(body: dict) -> str:
    """从旧版 doc body JSON 递归提取纯文本。"""
    texts: list[str] = []

    def _traverse(node):
        if isinstance(node, dict):
            if node.get("type") == "text":
                texts.append(node.get("text", ""))
            for v in node.values():
                _traverse(v)
        elif isinstance(node, list):
            for item in node:
                _traverse(item)

    _traverse(body)
    return "\n".join(t for t in texts if t)
