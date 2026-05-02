from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    # 子系统A配置
    a_base_url: str = "http://localhost:8100"
    a_mock_mode: bool = True

    # 飞书配置
    feishu_app_id: Optional[str] = None
    feishu_app_secret: Optional[str] = None
    feishu_verification_token: Optional[str] = None
    feishu_encrypt_key: Optional[str] = None

    # 服务配置
    server_host: str = "0.0.0.0"
    server_port: int = 8200
    debug: bool = True

    # 任务配置
    default_task_group_id: Optional[str] = None
    feishu_bitable_app_token: Optional[str] = None
    feishu_bitable_table_id: Optional[str] = None
    feishu_tasklist_guid: Optional[str] = None  # Action Items 同步到此清单

    # 群聊目标（定时主动推送用）
    feishu_target_chat_id: Optional[str] = None

    # Demo配置
    demo_project_id: str = "openclaw_project"

    class Config:
        env_file = ".env"
        case_sensitive = False

settings = Settings()
