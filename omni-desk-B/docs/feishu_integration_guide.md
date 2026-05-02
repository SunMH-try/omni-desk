# 飞书应用集成配置指南

本指南详细说明如何将OpenClaw主动分发Agent对接真实飞书生态，实现产品级运行。

---

## 一、飞书开放平台应用创建

### 1. 创建企业自建应用
1. 访问 [飞书开放平台](https://open.feishu.cn/)，登录企业管理员账号
2. 进入「开发者后台」→「创建应用」→「企业自建应用」
3. 填写应用信息：
   - 应用名称：项目知识脉冲助手
   - 应用描述：主动推送会议背景、行动项、周报和风险预警
   - 上传应用图标和头像
4. 点击「创建」完成应用创建

### 2. 获取应用凭证
创建完成后，在「凭证与基础信息」页面获取以下信息：
```
APP_ID: cli_xxxxxx (以cli_开头)
APP_SECRET: xxxxxx (随机字符串)
VERIFICATION_TOKEN: xxxxxx (事件订阅校验token)
ENCRYPT_KEY: xxxxxx (事件加密密钥，可选)
```

---

## 二、权限配置

在「权限管理」页面开启以下权限，点击「申请权限」后提交企业管理员审核：

| 权限名称 | 权限描述 | 权限等级 |
|---------|---------|---------|
| 获取与发送群组消息 | 用于推送卡片到项目群 | 普通权限 |
| 读取用户通讯录 | 用于匹配任务负责人 | 普通权限 |
| 读取与修改任务 | 用于自动创建飞书任务 | 高级权限 |
| 读取与编辑云文档 | 用于读取会议纪要和写入报告 | 高级权限 |
| 读取会议纪要 | 用于会后自动提取行动项 | 高级权限 |
| 读取与编辑多维表格 | 用于同步任务和风险数据 | 高级权限 |
| 订阅日程事件 | 用于会前自动触发背景推送 | 高级权限 |

---

## 三、事件订阅配置

飞书支持两种事件接收方式，**推荐使用长连接模式**，无需公网IP和域名，本地开发环境即可使用：

### 🚀 方式一：长连接模式（推荐）
无需配置公网域名、HTTPS证书、加密解密，5分钟即可完成对接，适合开发和生产环境。

#### 配置步骤：
1. 在飞书开放平台「事件订阅」页面，选择**使用长连接接收事件**
2. 在「事件列表」中添加需要订阅的事件，无需配置回调地址
3. 运行我们提供的长连接服务脚本即可接收事件

#### 优势：
- ✅ 无需公网IP和域名，本地开发环境直接使用
- ✅ 无需处理加密解密、签名验证，SDK自动处理
- ✅ 无需配置IP白名单和防火墙
- ✅ 自动维护access_token生命周期

---

### 📡 方式二：Webhook模式（需要公网域名）
适合有公网服务器的生产环境：
1. **请求网址**：`https://你的服务域名/webhook/feishu/event`
2. **加密策略**：可以选择启用加密，使用前面获取的ENCRYPT_KEY
3. **添加订阅事件**：
   - 日程事件：`v1.calendar.event.before_created`（会议开始前）
   - 会议纪要事件：`v1.meeting.minutes.created`（会议纪要生成后）
   - 群聊@事件：`im.message.receive_v1`（用户@机器人时触发）

---

### 📋 需要订阅的事件列表：
| 事件名称 | 事件标识 | 用途 |
|---------|---------|------|
| 接收消息 | `im.message.receive_v1` | 处理用户@机器人的指令 |
| 日程事件变更 | `calendar.event.changed_v1` | 会议开始前自动推送会前背景 |
| 文档变更 | `drive.file.bitable_record.changed_v1` | 会议纪要生成后自动提取行动项 |
| 卡片交互回调 | `card.action.trigger` | 处理用户点击卡片按钮的操作 |

---

## 四、长连接服务部署（推荐）

### 1. 安装飞书SDK
```bash
pip install lark-oapi -U
```

### 2. 配置环境变量
```bash
export FEISHU_APP_ID=cli_xxxxxx
export FEISHU_APP_SECRET=xxxxxx
export B_ENDPOINT=http://localhost:8200  # B端服务地址
export DRY_RUN=true  # 测试环境保持true，不真实写入数据
```

### 3. 启动长连接服务
```bash
cd openclaw-proactive-distribution-agent
python scripts/feishu_websocket_server.py
```

### 4. 服务启动成功后会显示：
```
🚀 飞书长连接服务启动中...
  APP_ID: cli_xxxxxx
  B端地址: http://localhost:8200
  DryRun模式: true
connected to wss://ws.feishu.cn/
```

### 5. 自动触发的场景
长连接服务会自动监听事件并触发对应流程：
- ✅ 会议开始前1小时 → 自动推送会前背景卡片到会议群
- ✅ 会议纪要生成后 → 自动提取行动项，推送任务确认卡片
- ✅ 用户@机器人查询风险 → 自动生成风险预警卡片
- ✅ 用户点击卡片"确认创建任务"按钮 → 自动创建飞书任务并同步到多维表格

---

## 五、服务端配置

### 1. 环境变量配置
在部署环境中设置以下环境变量，或直接修改`app/config.py`：
```bash
# 飞书应用配置
export FEISHU_APP_ID=cli_xxxxxx
export FEISHU_APP_SECRET=xxxxxx
export FEISHU_VERIFICATION_TOKEN=xxxxxx
export FEISHU_ENCRYPT_KEY=xxxxxx

# 功能开关
export FEISHU_ENABLED=true  # 启用飞书真实能力
export DRY_RUN_DEFAULT=false  # 关闭dry-run模式，执行真实写入

# 子系统配置
export A_BASE_URL=http://localhost:8100
export A_MOCK_MODE=false
```

### 2. 启动服务
```bash
# 启动子系统A
cd openclaw-knowledge-evidence-engine
python -m uvicorn app.main:app --host 0.0.0.0 --port 8100

# 启动子系统B
cd openclaw-proactive-distribution-agent
python -m uvicorn app.main:app --host 0.0.0.0 --port 8200
```

---

## 六、测试对接

### 1. 测试卡片推送
使用提供的测试脚本推送卡片到飞书群：
```bash
cd openclaw-proactive-distribution-agent
python scripts/feishu_push_test.py --chat-id "oc_xxxxxx" --scenario pre_meeting
```

参数说明：
- `--chat-id`：飞书群的chat_id，可以通过飞书群设置->群信息->群ID获取
- `--scenario`：测试场景，可选`pre_meeting`/`weekly_insight`/`risk_alert`

### 2. 验证功能
1. 检查飞书群是否收到推送的卡片
2. 点击卡片上的按钮，验证回调是否正常
3. 确认任务是否真实创建到飞书任务中心
4. 确认数据是否同步到多维表格

---

## 七、真实场景配置

### 1. 会前自动推送
- 无需额外配置，系统会自动监听会议开始前事件，自动推送会前背景卡片
- 支持配置提前推送时间（默认提前60分钟）

### 2. 会后自动创建任务
- 无需额外配置，会议纪要生成后自动触发行动项提取
- 推送任务预览卡片到会议群，用户确认后自动创建飞书任务

### 3. 周报自动推送
- 配置定时任务，每周五18:00触发：
```bash
0 18 * * 5 curl -X POST http://localhost:8200/agent/v1/triggers/run \
  -H "Content-Type: application/json" \
  -d '{"trigger_type":"scheduled","scenario_type":"weekly_insight","project_id":"alpha_report_platform","dry_run":false}'
```

### 4. 风险预警
- 配置定时任务，每天上午10:00触发：
```bash
0 10 * * * curl -X POST http://localhost:8200/agent/v1/triggers/run \
  -H "Content-Type: application/json" \
  -d '{"trigger_type":"scheduled","scenario_type":"risk_alert","project_id":"alpha_report_platform","dry_run":false}'
```

---

## 八、多维表格配置

1. 在飞书中创建多维表格，包含以下字段：
   - 任务ID：单行文本
   - 任务标题：多行文本
   - 负责人：成员
   - 截止时间：日期
   - 状态：单选（待开始/进行中/已完成/已延期）
   - 来源：单选（会议/周报/风险预警）
   - evidence_id：单行文本
   - 创建时间：日期

2. 在`app/config.py`中配置多维表格app_token和table_id：
```python
FEISHU_BITABLE_APP_TOKEN = "bascnxxxxxx"
FEISHU_BITABLE_TABLE_ID = "tblxxxxxx"
```

---

## 九、常见问题

### Q: 推送卡片提示无权限？
A: 请确认：
1. 机器人已经被添加到目标群
2. 已经申请了「获取与发送群组消息」权限并审核通过
3. 应用已经发布上线

### Q: 任务创建失败？
A: 请确认：
1. 已经申请了「读取与修改任务」权限
2. 任务负责人的user_id正确
3. 飞书开放平台的IP白名单配置正确

### Q: 事件订阅回调失败？
A: 请确认：
1. 服务有公网IP和HTTPS证书
2. 回调地址正确，没有重定向
3. VERIFICATION_TOKEN配置正确

---

## 十、官方文档参考
- [飞书开放平台文档](https://open.feishu.cn/document/home)
- [消息卡片开发指南](https://open.feishu.cn/document/uAjLw4CM/ukTMukTMukTM/reference/card-overview)
- [任务API文档](https://open.feishu.cn/document/uAjLw4CM/ukTMukTMukTM/reference/task-v1/task/list)
