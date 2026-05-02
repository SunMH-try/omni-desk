import os
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent

# Load .env from project root if present
try:
    from dotenv import load_dotenv
    load_dotenv(BASE_DIR / ".env", override=False)
except ImportError:
    pass

API_KEY = os.environ.get("ARK_API_KEY", "ark-9c63f23c-39f4-46b7-a299-84226416d11c-4f6f3")
ENDPOINT_ID = os.environ.get("ARK_ENDPOINT_ID", "ep-20260423222827-6lcn6")
ARK_BASE_URL = "https://ark.cn-beijing.volces.com/api/v3"

FIXTURES_DIR = BASE_DIR / "fixtures"
OUTPUTS_DIR = BASE_DIR / "outputs"
CONTRACTS_DIR = BASE_DIR / "contracts"

DEFAULT_TENANT_ID = "demo_tenant"
DEFAULT_PROJECT_ID = "alpha_report_platform"

# In real mode, override defaults so the engine uses the correct tenant/project
if os.environ.get("FEISHU_MODE", "fixture") == "real":
    _ft = os.environ.get("FEISHU_TENANT_ID", "")
    _fp = os.environ.get("FEISHU_PROJECT_ID", "")
    if _ft:
        DEFAULT_TENANT_ID = _ft
    if _fp:
        DEFAULT_PROJECT_ID = _fp

# ── Feishu real-API configuration ─────────────────────────────────────────
# Set FEISHU_MODE=real to fetch live data instead of local fixtures.

FEISHU_MODE = os.environ.get("FEISHU_MODE", "fixture")          # fixture | real
FEISHU_APP_ID = os.environ.get("FEISHU_APP_ID", "")
FEISHU_APP_SECRET = os.environ.get("FEISHU_APP_SECRET", "")

FEISHU_TENANT_ID = os.environ.get("FEISHU_TENANT_ID", DEFAULT_TENANT_ID)
FEISHU_PROJECT_ID = os.environ.get("FEISHU_PROJECT_ID", DEFAULT_PROJECT_ID)

# Comma-separated resource IDs to fetch
FEISHU_CHAT_IDS = [x.strip() for x in os.environ.get("FEISHU_CHAT_IDS", "").split(",") if x.strip()]
FEISHU_DOC_TOKENS = [x.strip() for x in os.environ.get("FEISHU_DOC_TOKENS", "").split(",") if x.strip()]
FEISHU_MINUTES_TOKENS = [x.strip() for x in os.environ.get("FEISHU_MINUTES_TOKENS", "").split(",") if x.strip()]
FEISHU_TASKLIST_GUIDS = [x.strip() for x in os.environ.get("FEISHU_TASKLIST_GUIDS", "").split(",") if x.strip()]
FEISHU_CALENDAR_IDS = [x.strip() for x in os.environ.get("FEISHU_CALENDAR_IDS", "").split(",") if x.strip()]
FEISHU_LOOKBACK_DAYS = int(os.environ.get("FEISHU_LOOKBACK_DAYS", "14"))

# 飞书文档/群链接的域名前缀，测试企业用 https://test-di4wis1yhf55.feishu.cn
FEISHU_WEB_BASE_URL = os.environ.get("FEISHU_WEB_BASE_URL", "https://feishu.cn")
