# 飞书Bot单聊问题解决指南

## 问题：单聊没有发送消息按钮

这说明Bot没有获得发送消息的权限。

## 解决方案

### 步骤1：检查Bot能力是否启用

1. 打开 https://open.feishu.cn/app
2. 进入你的应用
3. 左侧菜单 → **应用能力** → **机器人**
4. 确认显示 **"已启用"**
   - 如果没有启用，点击 **"启用机器人"**

### 步骤2：检查权限（最关键！）

1. 左侧菜单 → **权限管理**
2. 在搜索框中搜索以下权限，**必须全部添加**：

```
✅ im:message.group_at_msg:readonly  (接收群聊@消息)
✅ im:message.p2p_msg:readonly       (接收私聊消息)  
✅ im:message:send                   (发送消息) ⬅️ 这个必须有！
```

**注意**：如果没有 `im:message:send`，Bot就无法在单聊中显示发送按钮！

### 步骤3：检查应用发布状态

1. 左侧菜单 → **版本管理与发布**
2. 确认状态是 **"已发布"**
3. 如果显示 **"待审批"**，需要联系企业管理员审批

### 步骤4：重新添加Bot到群组

有时候权限更新后需要重新添加：

1. 在飞书群组中 → 设置 → 群机器人
2. 删除现有的Bot
3. 重新添加Bot

## 测试方法

配置完成后，测试单聊：

1. 在飞书搜索框搜索你的Bot名称
2. 进入与Bot的私聊
3. 查看底部是否有输入框
4. 发送消息测试

## 如果还是不行

检查 **事件订阅** 是否订阅了私聊事件：

1. 事件与回调 → 事件订阅
2. 确认订阅了：`im.message.receive_v1`
3. 订阅方式：**使用长连接接收事件**

## 常见错误

❌ **错误1**：只添加了 `im:message.group_at_msg:readonly`，没添加 `im:message:send`
✅ **解决**：必须添加 `im:message:send`

❌ **错误2**：权限添加了但应用未重新发布
✅ **解决**：修改权限后必须创建新版本并发布

❌ **错误3**：应用已发布但审批未通过
✅ **解决**：联系企业管理员在「工作台」→「应用管理」中审批

## 快速检查清单

- [ ] Bot能力已启用
- [ ] 权限包含 `im:message:send`
- [ ] 权限包含 `im:message.p2p_msg:readonly`
- [ ] 应用已发布
- [ ] 审批已通过
- [ ] 事件订阅选择了长连接模式
- [ ] 订阅了 `im.message.receive_v1`

## 验证权限代码

运行这个检查权限：

```python
# 检查config中的app_id和app_secret
import yaml
config_path = Path.home() / ".config" / "feishu-agent" / "config.yaml"
with open(config_path) as f:
    data = yaml.safe_load(f)
    print(f"App ID: {data.get('app_id', 'NOT SET')[:20]}...")
    print(f"App Secret: {'*' * 10}...")
```

如果以上都确认无误但还不行，请告诉我你的应用ID，我可以帮你进一步排查！
