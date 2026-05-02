import os
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent

API_KEY = os.environ.get("ARK_API_KEY", "ark-9c63f23c-39f4-46b7-a299-84226416d11c-4f6f3")
ENDPOINT_ID = os.environ.get("ARK_ENDPOINT_ID", "doubao-2.0-latest")
ARK_BASE_URL = "https://ark.cn-beijing.volces.com/api/v3"

FIXTURES_DIR = BASE_DIR / "fixtures"
OUTPUTS_DIR = BASE_DIR / "outputs"
CONTRACTS_DIR = BASE_DIR / "contracts"

DEFAULT_TENANT_ID = "demo_tenant"
DEFAULT_PROJECT_ID = "alpha_report_platform"
