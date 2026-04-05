# Feishu Doc Demo Bot

飞书文档API验证Demo Bot，用于测试飞书开放平台文档相关功能。

## 功能特性

1. **创建文档**: 发送"置顶"消息时，自动创建飞书文档并发送链接
2. **文档评论响应**: 在文档中@机器人时，在对话中发送通知

## 快速开始

### 1. 配置飞书应用

在 [飞书开放平台](https://open.feishu.cn/app) 创建应用并获取：

- **App ID**
- **App Secret**

### 2. 添加权限

在应用管理后台，添加以下权限：

- `drive:drive` - 访问云文档
- `drive:file:read` - 读取文件
- `drive:file:write` - 创建文件
- `im:message` - 发送消息
- `im:message:receive` - 接收消息

### 3. 配置事件订阅

在"事件与回调"中，启用长连接模式，并订阅以下事件：

- `im.message.receive_v1` - 接收消息
- `drive.file.comment.created_v1` - 文档评论创建

### 4. 初始化配置

```bash
# 创建默认配置文件
uv run bot/doc_demo_bot.py --init

# 编辑配置文件
notepad bot/doc_demo_bot.yaml
```

配置文件示例：
```yaml
app_id: "cli_xxxxxxxxxx"
app_secret: "xxxxxxxxxxxxxxxx"
admin_chat_id: "oc_xxxxxxxxxx"  # 可选，用于接收文档@通知
folder_token: ""  # 可选，指定创建文档的文件夹
```

### 5. 测试API

在启动Bot之前，先测试文档API是否正常：

```bash
# 确保已设置环境变量
$env:FEISHU_APP_ID="cli_xxxxxxxxxx"
$env:FEISHU_APP_SECRET="xxxxxxxxxxxxxxxx"

# 运行测试
uv run bot/test_doc_api.py
```

### 6. 启动Bot

```bash
# 方式1: 使用配置文件
uv run bot/doc_demo_bot.py -c bot/doc_demo_bot.yaml

# 方式2: 使用环境变量
$env:FEISHU_APP_ID="cli_xxxxxxxxxx"
$env:FEISHU_APP_SECRET="xxxxxxxxxxxxxxxx"
uv run bot/doc_demo_bot.py
```

## 使用指南

### 创建文档

在飞书中给机器人发送：
```
置顶
```

Bot会创建一个新的飞书文档并发送链接。

### 测试文档评论

1. 打开Bot创建的文档
2. 在文档中添加评论，@机器人
3. Bot会在对话中发送通知

## 项目结构

```
bot/
├── doc_demo_bot.py      # 主Bot程序
├── doc_demo_bot.yaml    # 配置文件
└── test_doc_api.py      # API测试脚本
```

## 技术实现

### 创建文档API

```python
POST https://open.feishu.cn/open-apis/drive/v1/files
{
    "name": "文档标题",
    "type": "docx"
}
```

### 事件订阅

使用飞书长连接SDK实时接收事件：

```python
event_handler = (
    lark.EventDispatcherHandler.builder("", "")
    .register_p2_im_message_receive_v1(handle_message)
    .register_p2_drive_file_comment_created_v1(handle_comment)
    .build()
)
```

## 故障排除

### 权限不足

如果出现权限错误，请检查：

1. 应用是否已发布
2. 权限是否已添加并生效
3. Token是否过期（有效期2小时）

### 文档创建失败

常见错误及解决方案：

- `1061004 forbidden`: 检查应用是否有 `drive:drive` 和 `drive:file:write` 权限
- `1061002 params error`: 检查请求参数是否正确
- `1062507 parent node out of sibling num`: 目标文件夹已满（限制1500个文件）

### 收不到消息

1. 检查事件订阅是否已启用
2. 确认机器人在对话中
3. 查看日志中的事件数据

## 扩展开发

基于这个Demo，你可以扩展更多功能：

- [ ] 支持在指定文件夹创建文档
- [ ] 支持文档模板
- [ ] 支持读取文档内容并解析任务
- [ ] 支持将执行结果写入文档
- [ ] 支持文档权限管理

## 参考文档

- [飞书开放平台 - 云文档](https://open.feishu.cn/document/uAjLw4CM/ukTMukTMukTM/reference/drive-v1/file/introduction)
- [飞书开放平台 - 创建文件](https://open.feishu.cn/document/uAjLw4CM/ukTMukTMukTM/reference/drive-v1/file/create)
- [飞书开放平台 - 消息事件](https://open.feishu.cn/document/uAjLw4CM/ukTMukTMukTM/reference/im-v1/message/events/receive)

## License

MIT
