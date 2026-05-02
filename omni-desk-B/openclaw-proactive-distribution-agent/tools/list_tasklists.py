"""查询当前应用可访问的飞书任务清单，找到 GUID 填入 .env"""
import httpx

APP_ID     = "cli_a97a69f02bf8dbdd"
APP_SECRET = "xpubXvVPMDXryNJMmJj0BdZhbIfPk2fF"
FEISHU_API = "https://open.feishu.cn/open-apis"


def get_token():
    r = httpx.post(
        f"{FEISHU_API}/auth/v3/tenant_access_token/internal",
        json={"app_id": APP_ID, "app_secret": APP_SECRET},
    )
    return r.json()["tenant_access_token"]


def main():
    token = get_token()
    headers = {"Authorization": f"Bearer {token}"}

    r = httpx.get(f"{FEISHU_API}/task/v2/tasklists", headers=headers, timeout=10)
    d = r.json()

    if d.get("code") != 0:
        print(f"❌ 查询失败: code={d.get('code')} msg={d.get('msg')}")
        return

    items = d.get("data", {}).get("items", [])
    if not items:
        print("⚠️  没有找到任务清单，需要先创建一个共享清单。")
        print_guide()
        return

    print(f"✅ 找到 {len(items)} 个任务清单：\n")
    for t in items:
        print(f"  名称: {t.get('name', '无名称')}")
        print(f"  GUID: {t.get('guid', '')}")
        print()

    print("👉 把项目共享清单的 GUID 填入 .env 的 FEISHU_TASKLIST_GUID=")


def print_guide():
    print("""
── 如何创建项目共享任务清单 ────────────────────────────────────
1. 飞书 → 任务 → 左侧「+ 创建清单」
2. 命名为「OpenClaw 项目任务」
3. 邀请孙鸣皓、朱嘉骏等成员加入
4. 清单 URL 里可以看到 GUID（xxx.feishu.cn/task/list/{GUID}）
   或重新运行本脚本获取
──────────────────────────────────────────────────────────────
""")


if __name__ == "__main__":
    main()
