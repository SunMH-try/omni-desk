#!/usr/bin/env python3
"""
飞书卡片回调简易服务
使用FastAPI提供HTTP回调接口，配合内网穿透使用
"""

import os
import json
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
import uvicorn

# 配置
APP_ID = os.environ.get("FEISHU_APP_ID", "cli_a965a99c46f61bda")
APP_SECRET = os.environ.get("FEISHU_APP_SECRET", "K7nh0Yz8iuzjc6hKACIJufOxX3KXZ7z5")
VERIFICATION_TOKEN = os.environ.get("FEISHU_VERIFICATION_TOKEN", "")

app = FastAPI(title="Feishu Callback Service")

@app.post("/webhook/feishu/callback")
async def feishu_callback(request: Request):
    """飞书回调入口"""
    try:
        # 解析请求
        body = await request.json()
        print(f"\n收到回调请求: {json.dumps(body, ensure_ascii=False, indent=2)}")
        
        # 处理URL校验请求
        if body.get("type") == "url_verification":
            return JSONResponse({
                "challenge": body.get("challenge")
            })
        
        # 处理卡片交互事件
        if body.get("header", {}).get("event_type") == "card.action.trigger":
            event = body.get("event", {})
            action_value = json.loads(event.get("action", {}).get("value", "{}"))
            action = action_value.get("action")
            preview_id = action_value.get("preview_id")
            
            print(f"卡片交互: action={action}, preview_id={preview_id}")
            
            if action == "view_full_context":
                # 返回完整上下文
                return JSONResponse({
                    "toast": {
                        "type": "info",
                        "content": "正在加载完整上下文..."
                    },
                    "card": {
                        "type": "raw",
                        "data": {
                            "config": {"wide_screen_mode": True},
                            "header": {
                                "title": {"tag": "plain_text", "content": "📄 会议完整上下文"},
                                "template": "blue"
                            },
                            "elements": [
                                {"tag": "div", "text": {"tag": "lark_md", "content": "**会议基本信息**\n- 会议名称：Alpha项目周会\n- 会议时间：2026-04-28 14:00\n- 参会人：张三、李四、王五"}},
                                {"tag": "hr"},
                                {"tag": "div", "text": {"tag": "lark_md", "content": "**上次会议决议**\n1. ✅ 完成接口联调（已完成）\n2. ⏳ 测试环境权限申请（进行中）\n3. 📝 编写项目文档（待开始）"}},
                                {"tag": "hr"},
                                {"tag": "div", "text": {"tag": "lark_md", "content": "**相关文档**\n1. [项目需求文档](https://feishu.cn/doc/xxx)\n2. [接口设计文档](https://feishu.cn/doc/xxx)\n3. [测试用例文档](https://feishu.cn/doc/xxx)"}}
                            ]
                        }
                    }
                })
            
            elif action == "confirm_create_tasks":
                # 确认创建任务
                return JSONResponse({
                    "toast": {
                        "type": "success",
                        "content": "✅ 任务创建成功！已同步到飞书任务中心"
                    },
                    "card": {
                        "type": "raw",
                        "data": {
                            "config": {"wide_screen_mode": True},
                            "header": {
                                "title": {"tag": "plain_text", "content": "✅ 任务创建成功"},
                                "template": "green"
                            },
                            "elements": [
                                {"tag": "div", "text": {"tag": "lark_md", "content": "已为你创建以下任务：\n1. 申请测试环境权限 - 张三 - 2026-04-30\n2. 完成接口联调 - 李四 - 2026-05-05\n3. 编写测试用例 - 王五 - 2026-05-10"}},
                                {"tag": "hr"},
                                {"tag": "div", "text": {"tag": "lark_md", "content": "👉 [点击查看任务列表](https://applink.feishu.cn/client/task/list)"}}
                            ]
                        }
                    }
                })
        
        # 默认响应
        return JSONResponse({
            "toast": {
                "type": "info",
                "content": "操作已收到~"
            }
        })
    
    except Exception as e:
        print(f"处理回调异常: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")

def main():
    print("🚀 飞书回调服务启动中...")
    print("  服务端口: 8888")
    print("  回调地址: http://localhost:8888/webhook/feishu/callback")
    print("  使用内网穿透将地址暴露到公网，填写到飞书开放平台回调地址即可")
    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8888
    )

if __name__ == "__main__":
    main()
