"""Persistent storage for confirmed tasks — enables the meeting closed loop.

After post_meeting task confirmation, tasks are appended here.
Pre-meeting workflow reads recent tasks to show completion status.
"""
from __future__ import annotations
import json
import logging
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

_HISTORY_PATH = Path(__file__).parent.parent.parent / "outputs" / "confirmed_tasks.jsonl"
_HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)


def append_confirmed_tasks(tasks: list) -> None:
    """Append newly confirmed tasks to the persistent history file."""
    ts = datetime.now().isoformat()
    try:
        with open(_HISTORY_PATH, "a", encoding="utf-8") as f:
            for t in tasks:
                f.write(json.dumps({**t, "confirmed_at": ts}, ensure_ascii=False) + "\n")
    except Exception as e:
        logger.warning(f"[task_history] 写入失败: {e}")


def load_recent_confirmed_tasks(limit: int = 20) -> list:
    """Load the most recent confirmed tasks from history."""
    tasks = []
    try:
        if _HISTORY_PATH.exists():
            lines = _HISTORY_PATH.read_text(encoding="utf-8").strip().splitlines()
            for line in lines[-limit:]:
                try:
                    tasks.append(json.loads(line))
                except Exception:
                    pass
    except Exception as e:
        logger.warning(f"[task_history] 读取失败: {e}")
    return tasks
