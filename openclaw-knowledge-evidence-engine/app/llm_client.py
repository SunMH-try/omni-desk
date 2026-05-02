from __future__ import annotations
import time
import json
import re
from openai import OpenAI, RateLimitError
from app.config import API_KEY, ENDPOINT_ID, ARK_BASE_URL

_client = OpenAI(api_key=API_KEY, base_url=ARK_BASE_URL)

# 每次 LLM 调用后的最小间隔（秒），避免 TPM 超限
_MIN_INTERVAL = 1.5
_last_call_time = 0.0


def chat(messages: list[dict], prompt_name: str = "unnamed", **kwargs) -> tuple[str, dict]:
    """Call LLM with rate limiting and retry. Returns (content, usage_trace)."""
    global _last_call_time

    # 保证调用间隔
    wait = _MIN_INTERVAL - (time.time() - _last_call_time)
    if wait > 0:
        time.sleep(wait)

    retries = 0
    backoff = 5  # 初始退避秒数
    start = time.time()

    while True:
        try:
            _last_call_time = time.time()
            resp = _client.chat.completions.create(
                model=ENDPOINT_ID,
                messages=messages,
                **kwargs,
            )
            elapsed = round(time.time() - start, 2)
            usage = {
                "prompt_name": prompt_name,
                "model": ENDPOINT_ID,
                "prompt_tokens": resp.usage.prompt_tokens,
                "completion_tokens": resp.usage.completion_tokens,
                "total_tokens": resp.usage.total_tokens,
                "elapsed_s": elapsed,
                "retries": retries,
            }
            return resp.choices[0].message.content, usage

        except RateLimitError:
            retries += 1
            if retries > 5:
                raise
            print(f"[llm] 429 rate limit, waiting {backoff}s (retry {retries}) ...")
            time.sleep(backoff)
            backoff = min(backoff * 2, 60)


def chat_json(messages: list[dict], prompt_name: str = "unnamed", **kwargs) -> tuple[dict | list, dict]:
    """Call LLM expecting JSON output. Returns (parsed_json, usage_trace)."""
    content, usage = chat(messages, prompt_name=prompt_name, **kwargs)
    content = re.sub(r"^```(?:json)?\s*", "", content.strip())
    content = re.sub(r"\s*```$", "", content)
    return json.loads(content), usage
