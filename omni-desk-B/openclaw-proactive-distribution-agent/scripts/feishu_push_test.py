#!/usr/bin/env python3
"""
飞书卡片推送测试脚本
用于测试将生成的卡片真实推送到飞书群
"""

import argparse
import requests
import json
import os
from typing import Dict, Any

class FeishuPusher:
    def __init__(self, app_id: str, app_secret: str):
        self.app_id = app_id
        self.app_secret = app_secret
        self.tenant_access_token = None
        self.base_url = "https://open.feishu.cn"
    
    def get_tenant_access_token(self) -> str:
        """获取租户访问凭证"""
        if self.tenant_access_token:
            return self.tenant_access_token
        
        url = f"{self.base_url}/open-apis/auth/v3/tenant_access_token/internal"
        headers = {"Content-Type": "application/json"}
        data = {
            "app_id": self.app_id,
            "app_secret": self.app_secret
        }
        
        response = requests.post(url, headers=headers, json=data)
        response.raise_for_status()
        result = response.json()
        
        if result["code"] != 0:
            raise Exception(f"获取access_token失败: {result['msg']}")
        
        self.tenant_access_token = result["tenant_access_token"]
        return self.tenant_access_token
    
    def push_card_to_chat(self, chat_id: str, card_json: Dict[str, Any], content: str = "") -> Dict[str, Any]:
        """推送卡片到指定群聊"""
        url = f"{self.base_url}/open-apis/im/v1/messages?receive_id_type=chat_id"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.get_tenant_access_token()}"
        }
        
        data = {
            "receive_id": chat_id,
            "msg_type": "interactive",
            "content": json.dumps(card_json, ensure_ascii=False)
        }
        
        if content:
            # 如果是普通文本消息
            data["msg_type"] = "text"
            data["content"] = json.dumps({"text": content}, ensure_ascii=False)
        
        response = requests.post(url, headers=headers, json=data)
        response.raise_for_status()
        return response.json()
    
    def create_task(self, title: str, owner_ids: list, deadline: int = None) -> Dict[str, Any]:
        """创建飞书任务"""
        url = f"{self.base_url}/open-apis/task/v1/tasks"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.get_tenant_access_token()}"
        }
        
        data = {
            "summary": title,
            "members": [{"id": user_id, "role": "assignee"} for user_id in owner_ids]
        }
        
        if deadline:
            data["due"] = {"time": deadline}
        
        response = requests.post(url, headers=headers, json=data)
        response.raise_for_status()
        return response.json()

def get_card_from_local(scenario: str) -> Dict[str, Any]:
    """从本地服务获取生成的卡片"""
    # 先触发场景生成卡片
    trigger_url = "http://localhost:8200/agent/v1/triggers/run"
    trigger_data = {
        "trigger_type": "manual",
        "scenario_type": scenario,
        "project_id": "alpha_report_platform",
        "dry_run": True
    }
    
    response = requests.post(trigger_url, json=trigger_data)
    response.raise_for_status()
    result = response.json()
    preview_id = result["data"]["preview_id"]
    
    # 获取卡片内容
    if scenario in ["pre_meeting", "weekly_insight"]:
        preview_url = f"http://localhost:8200/agent/v1/cards/preview/{preview_id}"
    elif scenario == "risk_alert":
        preview_url = f"http://localhost:8200/agent/v1/alerts/preview/{preview_id}"
    elif scenario == "post_meeting":
        preview_url = f"http://localhost:8200/agent/v1/tasks/preview/{preview_id}"
    else:
        raise ValueError(f"不支持的场景: {scenario}")
    
    response = requests.get(preview_url)
    response.raise_for_status()
    return response.json()["data"]

def main():
    parser = argparse.ArgumentParser(description="飞书卡片推送测试工具")
    parser.add_argument("--chat-id", required=True, help="飞书群chat_id")
    parser.add_argument("--scenario", required=True, 
                        choices=["pre_meeting", "weekly_insight", "risk_alert", "post_meeting"],
                        help="测试场景")
    parser.add_argument("--app-id", help="飞书APP_ID，默认从环境变量FEISHU_APP_ID读取")
    parser.add_argument("--app-secret", help="飞书APP_SECRET，默认从环境变量FEISHU_APP_SECRET读取")
    parser.add_argument("--only-print", action="store_true", help="仅打印卡片内容，不实际推送")
    
    args = parser.parse_args()
    
    # 从环境变量获取凭证
    app_id = args.app_id or os.environ.get("FEISHU_APP_ID")
    app_secret = args.app_secret or os.environ.get("FEISHU_APP_SECRET")
    
    if not args.only_print and (not app_id or not app_secret):
        print("错误：请提供APP_ID和APP_SECRET，或设置FEISHU_APP_ID和FEISHU_APP_SECRET环境变量")
        return
    
    # 获取卡片
    print(f"正在生成【{args.scenario}】场景卡片...")
    card_data = get_card_from_local(args.scenario)
    
    # 打印卡片信息
    print("\n=== 生成的卡片信息 ===")
    if "card_result" in card_data:
        print(f"卡片标题: {card_data['card_result']['card_title']}")
        print(f"预览ID: {card_data['preview_id']}")
        print("\nMarkdown预览:")
        print(card_data['card_result']['markdown'])
        
        if args.only_print:
            print("\n=== 卡片JSON ===")
            print(json.dumps(card_data['card_result']['card_json'], ensure_ascii=False, indent=2))
            return
    elif "preview_card" in card_data:
        print(f"任务预览: 共{len(card_data['processed_items'])}个任务")
        print("\n任务列表:")
        for idx, item in enumerate(card_data['processed_items'], 1):
            print(f"{idx}. {item['title']} - {item['owner_name']} - {item['deadline']}")
    
    # 推送卡片到飞书
    print("\n正在推送到飞书群...")
    pusher = FeishuPusher(app_id, app_secret)
    
    if "card_result" in card_data:
        result = pusher.push_card_to_chat(args.chat_id, card_data['card_result']['card_json'])
    elif "preview_card" in card_data:
        result = pusher.push_card_to_chat(args.chat_id, card_data['preview_card'])
    
    if result["code"] == 0:
        print("✅ 推送成功！请检查飞书群")
        print(f"消息ID: {result['data']['message_id']}")
    else:
        print(f"❌ 推送失败: {result['msg']}")
        print(f"错误码: {result['code']}")

if __name__ == "__main__":
    main()
