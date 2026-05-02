"""查询当前应用（bot）可访问的飞书日历列表，找到 calendar_id 填入 .env"""
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

    r = httpx.get(f"{FEISHU_API}/calendar/v4/calendars", headers=headers, timeout=10)
    d = r.json()

    if d.get("code") != 0:
        print(f"❌ 查询失败: code={d.get('code')} msg={d.get('msg')}")
        print("   可能原因：日历未共享给 bot，或权限未生效")
        return

    items = d.get("data", {}).get("calendar_list", [])
    if not items:
        print("⚠️  没有找到可访问的日历。需要先把日历共享给 bot。")
        print_share_guide()
        return

    print(f"✅ 找到 {len(items)} 个日历：\n")
    for c in items:
        print(f"  名称: {c.get('summary', '无名称')}")
        print(f"  ID  : {c.get('calendar_id', '')}")
        print(f"  类型: {c.get('type', '')}")
        print()

    print("👉 把上面的 calendar_id 填入 .env 的 FEISHU_CALENDAR_ID=")


def print_share_guide():
    print("""
── 如何把日历共享给 bot ──────────────────────────────────────
1. 打开飞书 → 日历
2. 在左侧找到目标日历 → 右键 → 「设置」→「共享」
3. 搜索你的 bot 名称（OpenClaw MeetingOps Agent）并添加，权限选「可查看」
4. 重新运行本脚本
─────────────────────────────────────────────────────────────
""")


if __name__ == "__main__":
    main()
