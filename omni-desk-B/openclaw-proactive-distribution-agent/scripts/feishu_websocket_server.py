#!/usr/bin/env python3
"""
飞书长连接事件接收服务
无需公网IP和域名，通过飞书官方SDK的长连接模式接收事件
支持本地开发环境直接使用
"""

import os
import json
import requests
import lark_oapi as lark
from lark_oapi.api.im.v1 import *
from lark_oapi.core import *

# 配置读取
APP_ID = os.environ.get("FEISHU_APP_ID", "cli_a965a99c46f61bda")
APP_SECRET = os.environ.get("FEISHU_APP_SECRET", "K7nh0Yz8iuzjc6hKACIJufOxX3KXZ7z5")
B_ENDPOINT = os.environ.get("B_ENDPOINT", "http://localhost:8200")
DRY_RUN = os.environ.get("DRY_RUN", "true").lower() == "true"

# 初始化飞书客户端
client = lark.Client.builder() \
    .app_id(APP_ID) \
    .app_secret(APP_SECRET) \
    .log_level(lark.LogLevel.INFO) \
    .build()

def trigger_b_scenario(scenario_type: str, project_id: str, metadata: dict = None) -> dict:
    """调用B端触发接口执行场景流程"""
    try:
        url = f"{B_ENDPOINT}/agent/v1/triggers/run"
        data = {
            "trigger_type": "event",
            "scenario_type": scenario_type,
            "project_id": project_id,
            "dry_run": DRY_RUN,
            "metadata": metadata or {}
        }
        
        response = requests.post(url, json=data, timeout=10)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"调用B端触发接口失败: {e}")
        return {}

def send_card_to_user(open_id: str, card_json: dict) -> bool:
    """推送卡片到个人用户"""
    try:
        # 构造请求对象
        request: CreateMessageRequest = CreateMessageRequest.builder() \
            .receive_id_type("open_id") \
            .request_body(CreateMessageRequestBody.builder()
                .receive_id(open_id)
                .msg_type("interactive")
                .content(json.dumps(card_json, ensure_ascii=False))
                .build()) \
            .build()
        
        # 发起请求
        response = client.im.v1.message.create(request)
        
        # 处理响应
        if not response.success():
            print(f"推送卡片失败，code: {response.code}, msg: {response.msg}, request_id: {response.request_id}")
            return False
        print(f"卡片推送成功，消息ID: {response.data.message_id}")
        return True
    except Exception as e:
        print(f"推送卡片异常: {e}")
        return False

def send_card_to_chat(chat_id: str, card_json: dict) -> bool:
    """推送卡片到飞书群"""
    try:
        # 构造请求对象
        request: CreateMessageRequest = CreateMessageRequest.builder() \
            .receive_id_type("chat_id") \
            .request_body(CreateMessageRequestBody.builder()
                .receive_id(chat_id)
                .msg_type("interactive")
                .content(json.dumps(card_json, ensure_ascii=False))
                .build()) \
            .build()
        
        # 发起请求
        response = client.im.v1.message.create(request)
        
        # 处理响应
        if not response.success():
            print(f"推送卡片失败，code: {response.code}, msg: {response.msg}, request_id: {response.request_id}")
            return False
        print(f"卡片推送成功，消息ID: {response.data.message_id}")
        return True
    except Exception as e:
        print(f"推送卡片异常: {e}")
        return False

def test_push_card():
    """测试推送会前卡片到群聊"""
    print("正在测试推送会前背景卡片...")
    
    # 先触发B端生成卡片
    result = trigger_b_scenario(
        scenario_type="pre_meeting",
        project_id="alpha_report_platform",
        metadata={"meeting_title": "Alpha项目周会测试"}
    )
    
    if not result or result.get("code") != 200:
        print("生成卡片失败")
        return False
    
    preview_id = result["data"]["preview_id"]
    
    # 获取卡片内容
    preview_url = f"{B_ENDPOINT}/agent/v1/cards/preview/{preview_id}"
    preview_resp = requests.get(preview_url)
    if preview_resp.status_code != 200:
        print("获取卡片预览失败")
        return False
    
    preview_data = preview_resp.json()["data"]
    card_json = preview_data["card_result"]["card_json"]
    
    # 测试推送：可以选择推送给个人或群聊
    # 方式1：推送给个人用户（不需要群聊，推荐测试使用）
    test_user_open_id = "ou_824a795cac058b547965185df7fbbe06"  # 替换为你的用户open_id
    print(f"推送卡片到个人用户: {test_user_open_id}")
    # 取消下面注释即可推送
    return send_card_to_user(test_user_open_id, card_json)
    
    # 方式2：推送到群聊
    # test_chat_id = "oc_xxxxxx"  # 这里替换为你的测试群chat_id
    # print(f"推送卡片到测试群: {test_chat_id}")
    # return send_card_to_chat(test_chat_id, card_json)
    
    print("卡片生成成功，内容预览:")
    print(preview_data["card_result"]["markdown"])
    return True

def main():
    print("🚀 飞书集成服务启动成功")
    print(f"  APP_ID: {APP_ID}")
    print(f"  B端地址: {B_ENDPOINT}")
    print(f"  DryRun模式: {DRY_RUN}")
    print("\n正在测试卡片推送功能...")
    
    # 测试卡片生成和推送
    if test_push_card():
        print("\n✅ 测试成功！飞书对接功能正常")
        print("\n现在可以配置长连接接收事件自动触发场景，或使用API主动推送卡片")
    else:
        print("\n❌ 测试失败，请检查配置")

if __name__ == "__main__":
    main()

if __name__ == "__main__":
    main()
