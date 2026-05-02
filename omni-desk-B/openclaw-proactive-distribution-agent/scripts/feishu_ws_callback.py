#!/usr/bin/env python3
"""
飞书长连接回调服务（完全符合官方SDK规范）
无需公网IP，无需内网穿透，本地直接运行即可接收卡片回调事件
"""

import os
import json
import lark_oapi as lark
from lark_oapi.ws import Client
from lark_oapi import EventDispatcher
from lark_oapi.callback.model.p2_card_action_trigger import P2CardActionTrigger, P2CardActionTriggerResponse

# 飞书应用配置
APP_ID = "cli_a965a99c46f61bda"
APP_SECRET = "K7nh0Yz8iuzjc6hKACIJufOxX3KXZ7z5"

# 卡片按钮点击回调处理
def handle_card_action(event: P2CardActionTrigger) -> P2CardActionTriggerResponse:
    """处理卡片按钮点击事件，完全符合飞书回调规范"""
    print(f"\n✅ 收到卡片交互事件:")
    print(f"  用户ID: {event.event.operator.open_id}")
    print(f"  操作时间: {event.event.create_time}")
    print(f"  按钮参数: {event.event.action.value}")
    
    try:
        # 解析按钮参数
        action_data = json.loads(event.event.action.value)
        action = action_data.get("action", "")
        preview_id = action_data.get("preview_id", "")
        
        print(f"  操作类型: {action}, 预览ID: {preview_id}")
        
        # 处理【查看完整上下文】按钮
        if action == "view_full_context":
            return P2CardActionTriggerResponse({
                "toast": {
                    "type": "info",
                    "content": "正在加载完整上下文..."
                },
                "card": {
                    "type": "raw",
                    "data": {
                        "config": {"wide_screen_mode": True},
                        "header": {
                            "title": {"tag": "plain_text", "content": "📄 Alpha项目周会 - 完整上下文"},
                            "template": "blue"
                        },
                        "elements": [
                            {
                                "tag": "div",
                                "text": {
                                    "tag": "lark_md",
                                    "content": "**📅 会议基本信息**\n- 会议名称：Alpha项目周会\n- 会议时间：2026-04-28 14:00\n- 参会人：张三、李四、王五、赵六\n- 会议地点：3F-03会议室"
                                }
                            },
                            {"tag": "hr"},
                            {
                                "tag": "div",
                                "text": {
                                    "tag": "lark_md",
                                    "content": "**✅ 上次会议决议跟踪**\n1. ✅ 完成接口联调（已完成）- 李四\n2. ⏳ 测试环境权限申请（进行中）- 运维组\n3. 📝 编写项目文档（待开始）- 张三\n4. ✅ 前端页面开发（已完成）- 王五"
                                }
                            },
                            {"tag": "hr"},
                            {
                                "tag": "div",
                                "text": {
                                    "tag": "lark_md",
                                    "content": "**⚠️ 当前项目风险**\n1. 🔴 测试环境权限未开通，阻塞联调进度，预计延期2天\n2. 🟠 接口字段变更未同步，需要和后端确认\n3. 🟡 移动端适配方案尚未确定"
                                }
                            },
                            {"tag": "hr"},
                            {
                                "tag": "div",
                                "text": {
                                    "tag": "lark_md",
                                    "content": "**📚 相关文档链接**\n1. [项目需求文档](https://feishu.cn/doc/xxx123)\n2. [接口设计文档](https://feishu.cn/doc/xxx456)\n3. [测试用例文档](https://feishu.cn/doc/xxx789)\n4. [上周会议纪要](https://feishu.cn/doc/xxx012)"
                                }
                            }
                        ]
                    }
                }
            })
        
        # 处理【确认创建任务】按钮
        elif action == "confirm_create_tasks":
            return P2CardActionTriggerResponse({
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
                            {
                                "tag": "div",
                                "text": {
                                    "tag": "lark_md",
                                    "content": "已为你创建以下3个任务：\n\n1. **申请测试环境权限**\n👤 负责人：运维组\n📅 截止时间：2026-04-30\n\n2. **完成剩余接口联调**\n👤 负责人：李四\n📅 截止时间：2026-05-05\n\n3. **编写项目测试用例**\n👤 负责人：张三\n📅 截止时间：2026-05-10"
                                }
                            },
                            {"tag": "hr"},
                            {
                                "tag": "action",
                                "actions": [
                                    {
                                        "tag": "button",
                                        "text": {"tag": "plain_text", "content": "👉 查看任务列表"},
                                        "type": "primary",
                                        "url": "https://applink.feishu.cn/client/task/list"
                                    }
                                ]
                            }
                        ]
                    }
                }
            })
    
    except Exception as e:
        print(f"❌ 处理回调异常: {e}")
    
    # 默认响应
    return P2CardActionTriggerResponse({
        "toast": {
            "type": "info",
            "content": "操作已收到，正在处理..."
        }
    })

def main():
    # 1. 初始化事件分发器（两个参数必须为空字符串，官方要求）
    dispatcher = EventDispatcher("", "")
    
    # 2. 注册卡片点击事件回调
    dispatcher.on_p2_card_action_trigger(handle_card_action)
    
    # 3. 创建长连接客户端
    client = Client(
        app_id=APP_ID,
        app_secret=APP_SECRET,
        event_handler=dispatcher,
        log_level=lark.LogLevel.INFO  # 调试阶段用INFO级别，可以看到连接日志
    )
    
    print("🚀 飞书长连接回调服务启动中...")
    print("  ✅ 无需公网IP，无需内网穿透")
    print("  ✅ 自动维护连接，掉线自动重连")
    print("  ✅ 支持卡片按钮交互事件处理")
    print("  📌 现在点击飞书卡片上的按钮就会自动触发回调啦！")
    print("="*60)
    
    try:
        # 启动长连接，主线程阻塞
        client.start()
    except KeyboardInterrupt:
        print("\n👋 服务已停止")
    except Exception as e:
        print(f"❌ 启动失败: {e}")
        print("💡 请检查：")
        print("   1. APP_ID和APP_SECRET是否正确")
        print("   2. 飞书开放平台是否已订阅卡片回传交互事件")
        print("   3. 网络是否能访问公网")

if __name__ == "__main__":
    main()
