# 飞书Bot集成设计

## 目录

1. [整体架构](#整体架构)
2. [消息处理流程](#消息处理流程)
3. [交互卡片设计](#交互卡片设计)
4. [会话管理](#会话管理)

---

## 整体架构

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           Feishu / Lark Platform                            │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌───────────────────────────────────────────────────────────────────────┐ │
│  │                        Feishu App                                      │ │
│  │  - 机器人配置                                                           │ │
│  │  - 权限管理                                                             │ │
│  │  - Webhook/Long Connection                                             │ │
│  └───────────────────────────────┬───────────────────────────────────────┘ │
│                                  │                                         │
│                                  │ WebSocket / Webhook                     │
│                                  ▼                                         │
│  ┌───────────────────────────────────────────────────────────────────────┐ │
│  │                   Feishu Gateway (飞书网关)                            │ │
│  │                                                                        │ │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌────────────┐│ │
│  │  │   Webhook    │  │  WS Client   │  │   Message    │  │   Card     ││ │
│  │  │   Handler    │  │   (Long      │  │ Normalizer   │  │  Handler   ││ │
│  │  │              │  │ Connection)  │  │              │  │            ││ │
│  │  └──────────────┘  └──────────────┘  └──────────────┘  └────────────┘│ │
│  │                                                                        │ │
│  └───────────────────────────────┬───────────────────────────────────────┘ │
└──────────────────────────────────┼────────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           Edge Runtime (本地)                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌───────────────────────────────────────────────────────────────────────┐ │
│  │                   FeishuBotAgent (飞书Agent)                           │ │
│  │                                                                        │ │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌────────────┐│ │
│  │  │   Intent     │  │   Session    │  │  Operation   │  │   Card     ││ │
│  │  │   Router     │  │   Manager    │  │   Tracker    │  │  Renderer  ││ │
│  │  └──────────────┘  └──────────────┘  └──────────────┘  └────────────┘│ │
│  │                                                                        │ │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                  │ │
│  │  │    Brain     │  │ Confirmation │  │   Health     │                  │ │
│  │  │  (LLM Core)  │  │   Manager    │  │   Monitor    │                  │ │
│  │  └──────────────┘  └──────────────┘  └──────────────┘                  │ │
│  │                                                                        │ │
│  └───────────────────────────────┬───────────────────────────────────────┘ │
│                                  │                                         │
│                                  │ Local API Calls                         │
│                                  ▼                                         │
│  ┌───────────────────────────────────────────────────────────────────────┐ │
│  │                   OpenCode Session Manager                             │ │
│  │                                                                        │ │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                  │ │
│  │  │  Workspace   │  │   Process    │  │   Port       │                  │ │
│  │  │   Manager    │  │   Manager    │  │  Allocator   │                  │ │
│  │  └──────────────┘  └──────────────┘  └──────────────┘                  │ │
│  │                                                                        │ │
│  └───────────────────────────────────────────────────────────────────────┘ │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
                                   │
                                   │ HTTP / WebSocket
                                   ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                      Backend Server (SailZen Server)                         │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐          │
│  │  Workflow        │  │  Task            │  │  Agent           │          │
│  │  Engine          │  │  Scheduler       │  │  Registry        │          │
│  └──────────────────┘  └──────────────────┘  └──────────────────┘          │
│                                                                             │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐          │
│  │  PostgreSQL      │  │  Redis           │  │  Object          │          │
│  │  (Primary)       │  │  (Cache/Queue)   │  │  Storage         │          │
│  └──────────────────┘  └──────────────────┘  └──────────────────┘          │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 消息处理流程

### 完整消息流转

```
用户发送消息
    │
    ▼
┌────────────────────────────────────────────────────────────────┐
│  Feishu Platform                                                │
│  - 消息接收                                                     │
│  - 事件封装                                                     │
│  - 签名验证                                                     │
└────────────────────────┬───────────────────────────────────────┘
                         │ im.message.receive_v1
                         ▼
┌────────────────────────────────────────────────────────────────┐
│  Feishu Gateway                                                │
│  - WebSocket长连接 / Webhook接收                                │
│  - 消息去重 (message_id)                                        │
│  - 事件标准化                                                   │
└────────────────────────┬───────────────────────────────────────┘
                         │
                         ▼
┌────────────────────────────────────────────────────────────────┐
│  FeishuBotAgent                                                │
│                                                                │
│  Step 1: 消息预处理                                            │
│  ├── 提取文本内容                                               │
│  ├── 解析卡片回调                                               │
│  └── 验证用户身份                                               │
│                                                                │
└────────────────────────┬───────────────────────────────────────┘
                         │
                         ▼
┌────────────────────────────────────────────────────────────────┐
│  Step 2: 会话管理                                              │
│  ├── 恢复或创建会话                                             │
│  ├── 加载历史上下文                                             │
│  └── 更新最后活动时间                                           │
└────────────────────────┬───────────────────────────────────────┘
                         │
                         ▼
┌────────────────────────────────────────────────────────────────┐
│  Step 3: 意图路由                                              │
│  ├── 检查待确认操作                                             │
│  ├── LLM意图识别 (BotBrain)                                     │
│  ├── 参数提取                                                   │
│  └── Agent匹配                                                  │
└────────────────────────┬───────────────────────────────────────┘
                         │
                         ▼
┌────────────────────────────────────────────────────────────────┐
│  Step 4: 风险评估                                              │
│  ├── 操作风险分级                                               │
│  ├── 需要确认?                                                  │
│  └── 发送确认卡片                                               │
└────────────────────────┬───────────────────────────────────────┘
                         │
                         ▼
┌────────────────────────────────────────────────────────────────┐
│  Step 5: 任务执行                                              │
│  ├── 创建工作流                                                 │
│  ├── 提交到调度器                                               │
│  ├── 实时进度推送                                               │
│  └── 结果收集                                                   │
└────────────────────────┬───────────────────────────────────────┘
                         │
                         ▼
┌────────────────────────────────────────────────────────────────┐
│  Step 6: 响应渲染                                              │
│  ├── 格式化结果                                                 │
│  ├── 选择卡片模板                                               │
│  └── 构建飞书消息                                               │
└────────────────────────┬───────────────────────────────────────┘
                         │
                         ▼
┌────────────────────────────────────────────────────────────────┐
│  Step 7: 消息发送                                              │
│  ├── 调用飞书API                                                │
│  ├── 错误重试                                                   │
│  └── 发送确认                                                   │
└────────────────────────────────────────────────────────────────┘
```

### 代码实现示例

```python
class FeishuBotAgent:
    """飞书Bot Agent - 处理飞书消息并与OpenCode集成"""
    
    def __init__(self, config: BotConfig):
        self.config = config
        self.lark_client = lark.Client(
            app_id=config.app_id,
            app_secret=config.app_secret
        )
        self.session_mgr = SessionManager()
        self.intent_router = IntentRouter()
        self.workflow_client = WorkflowClient()
        self.card_renderer = CardRenderer()
    
    async def handle_message(self, event: lark.im.P2ImMessageReceiveV1):
        """处理飞书消息"""
        
        # 1. 提取消息信息
        message_id = event.event.message.message_id
        chat_id = event.event.message.chat_id
        sender_id = event.event.sender.sender_id.open_id
        content = json.loads(event.event.message.content)
        text = content.get("text", "").strip()
        
        # 2. 消息去重
        if await self._is_duplicate(message_id):
            return
        
        # 3. 获取或创建会话
        session = await self.session_mgr.get_or_create(
            user_id=sender_id,
            chat_id=chat_id,
            platform="feishu"
        )
        
        # 4. 检查待确认操作
        if session.has_pending_confirmation():
            result = await self._handle_confirmation(session, text)
            if result.handled:
                return
        
        # 5. 意图识别
        intent_result = await self.intent_router.route(
            text=text,
            context=session.get_context(),
            session=session
        )
        
        # 6. 风险评估
        if intent_result.risk_level >= RiskLevel.HIGH:
            await self._send_confirmation_card(
                session=session,
                intent=intent_result,
                message=f"⚠️ 该操作风险等级为{intent_result.risk_level.name}，请确认是否继续？"
            )
            return
        
        # 7. 执行工作流
        workflow_id = await self.workflow_client.submit(
            workflow_type=intent_result.workflow_type,
            params=intent_result.params,
            user_id=sender_id,
            session_id=session.id
        )
        
        # 8. 发送确认消息
        await self._send_workflow_started_card(
            session=session,
            workflow_id=workflow_id,
            description=intent_result.description
        )
        
        # 9. 订阅进度更新
        asyncio.create_task(
            self._subscribe_progress(session, workflow_id)
        )
    
    async def _subscribe_progress(self, session: Session, workflow_id: str):
        """订阅工作流进度并推送到飞书"""
        async for progress in self.workflow_client.subscribe_progress(workflow_id):
            # 根据进度更新卡片
            await self._update_progress_card(session, progress)
            
            if progress.status in ["completed", "failed", "cancelled"]:
                # 发送最终结果
                await self._send_result_card(session, progress)
                break
```

---

## 交互卡片设计

### 卡片类型体系

```
Card Types
│
├── 1. 会话卡片 (Session Cards)
│   ├── WelcomeCard          # 欢迎卡片
│   ├── HelpCard             # 帮助卡片
│   ├── StatusCard           # 状态卡片
│   └── QuickActionsCard     # 快捷操作
│
├── 2. 工作流卡片 (Workflow Cards)
│   ├── WorkflowStartedCard  # 工作流开始
│   ├── ProgressCard         # 进度卡片
│   ├── StepCompleteCard     # 步骤完成
│   └── ResultCard           # 结果卡片
│
├── 3. 确认卡片 (Confirmation Cards)
│   ├── SimpleConfirmCard    # 简单确认
│   ├── RiskConfirmCard      # 风险确认
│   ├── OptionsCard          # 选项选择
│   └── FormCard             # 表单输入
│
├── 4. 错误卡片 (Error Cards)
│   ├── ErrorCard            # 错误提示
│   ├── WarningCard          # 警告提示
│   └── RetryCard            # 重试选项
│
└── 5. 工作区卡片 (Workspace Cards)
    ├── WorkspaceListCard    # 工作区列表
    ├── WorkspaceHomeCard    # 工作区主页
    └── FileBrowserCard      # 文件浏览器
```

### 工作流进度卡片示例

```json
{
  "config": {
    "wide_screen_mode": true
  },
  "header": {
    "template": "blue",
    "title": {
      "content": "🚀 工作流执行中",
      "tag": "plain_text"
    }
  },
  "elements": [
    {
      "tag": "div",
      "fields": [
        {
          "is_short": true,
          "text": {
            "content": "**工作流:** 新功能开发",
            "tag": "lark_md"
          }
        },
        {
          "is_short": true,
          "text": {
            "content": "**ID:** wf-123456",
            "tag": "lark_md"
          }
        }
      ]
    },
    {
      "tag": "div",
      "text": {
        "content": "当前步骤: **代码审查** (3/8)",
        "tag": "lark_md"
      }
    },
    {
      "tag": "progress",
      "value": 37.5
    },
    {
      "tag": "div",
      "text": {
        "content": "⏱️ 已用时: 5分32秒 | 预计剩余: 12分钟",
        "tag": "lark_md"
      }
    },
    {
      "tag": "hr"
    },
    {
      "tag": "div",
      "text": {
        "content": "**最近日志:**\n✅ 需求分析完成\n✅ 技术方案设计完成\n🔄 代码实现中...",
        "tag": "lark_md"
      }
    },
    {
      "tag": "action",
      "actions": [
        {
          "tag": "button",
          "text": {
            "content": "查看详情",
            "tag": "plain_text"
          },
          "type": "primary",
          "value": {
            "action": "view_details",
            "workflow_id": "wf-123456"
          }
        },
        {
          "tag": "button",
          "text": {
            "content": "暂停",
            "tag": "plain_text"
          },
          "type": "default",
          "value": {
            "action": "pause_workflow",
            "workflow_id": "wf-123456"
          }
        },
        {
          "tag": "button",
          "text": {
            "content": "取消",
            "tag": "plain_text"
          },
          "type": "danger",
          "value": {
            "action": "cancel_workflow",
            "workflow_id": "wf-123456"
          }
        }
      ]
    }
  ]
}
```

### 确认卡片示例

```json
{
  "config": {
    "wide_screen_mode": true
  },
  "header": {
    "template": "red",
    "title": {
      "content": "⚠️ 高风险操作确认",
      "tag": "plain_text"
    }
  },
  "elements": [
    {
      "tag": "div",
      "text": {
        "content": "**操作:** 部署到生产环境",
        "tag": "lark_md"
      }
    },
    {
      "tag": "div",
      "text": {
        "content": "**项目:** SailZen",
        "tag": "lark_md"
      }
    },
    {
      "tag": "div",
      "text": {
        "content": "**版本:** v1.2.3",
        "tag": "lark_md"
      }
    },
    {
      "tag": "div",
      "text": {
        "content": "**影响:** 将影响线上用户",
        "tag": "lark_md"
      }
    },
    {
      "tag": "hr"
    },
    {
      "tag": "div",
      "text": {
        "content": "📝 **变更摘要:**\n- 新增用户认证模块\n- 优化数据库查询\n- 修复支付Bug",
        "tag": "lark_md"
      }
    },
    {
      "tag": "action",
      "actions": [
        {
          "tag": "button",
          "text": {
            "content": "✅ 确认执行",
            "tag": "plain_text"
          },
          "type": "primary",
          "value": {
            "action": "confirm",
            "confirmation_id": "conf-123",
            "choice": "yes"
          }
        },
        {
          "tag": "button",
          "text": {
            "content": "❌ 取消",
            "tag": "plain_text"
          },
          "type": "default",
          "value": {
            "action": "confirm",
            "confirmation_id": "conf-123",
            "choice": "no"
          }
        },
        {
          "tag": "button",
          "text": {
            "content": "🔍 查看更多详情",
            "tag": "plain_text"
          },
          "type": "default",
          "value": {
            "action": "view_details",
            "confirmation_id": "conf-123"
          }
        }
      ]
    }
  ]
}
```

### 工作区列表卡片

```json
{
  "config": {
    "wide_screen_mode": true
  },
  "header": {
    "template": "blue",
    "title": {
      "content": "📁 工作区管理",
      "tag": "plain_text"
    }
  },
  "elements": [
    {
      "tag": "div",
      "text": {
        "content": "你有 **3** 个活跃工作区",
        "tag": "lark_md"
      }
    },
    {
      "tag": "hr"
    },
    {
      "tag": "div",
      "text": {
        "content": "**🟢 SailZen**\n路径: D:/ws/repos/SailZen\n状态: 运行中 | 端口: 4096",
        "tag": "lark_md"
      }
    },
    {
      "tag": "action",
      "actions": [
        {
          "tag": "button",
          "text": {
            "content": "进入",
            "tag": "plain_text"
          },
          "type": "primary",
          "value": {
            "action": "enter_workspace",
            "workspace_id": "ws-1"
          }
        },
        {
          "tag": "button",
          "text": {
            "content": "停止",
            "tag": "plain_text"
          },
          "type": "default",
          "value": {
            "action": "stop_workspace",
            "workspace_id": "ws-1"
          }
        }
      ]
    },
    {
      "tag": "hr"
    },
    {
      "tag": "div",
      "text": {
        "content": "**⚪ ProjectX**\n路径: D:/ws/repos/ProjectX\n状态: 已停止",
        "tag": "lark_md"
      }
    },
    {
      "tag": "action",
      "actions": [
        {
          "tag": "button",
          "text": {
            "content": "启动",
            "tag": "plain_text"
          },
          "type": "primary",
          "value": {
            "action": "start_workspace",
            "workspace_id": "ws-2"
          }
        },
        {
          "tag": "button",
          "text": {
            "content": "删除",
            "tag": "plain_text"
          },
          "type": "danger",
          "value": {
            "action": "delete_workspace",
            "workspace_id": "ws-2"
          }
        }
      ]
    },
    {
      "tag": "hr"
    },
    {
      "tag": "action",
      "actions": [
        {
          "tag": "button",
          "text": {
            "content": "➕ 新建工作区",
            "tag": "plain_text"
          },
          "type": "primary",
          "value": {
            "action": "create_workspace"
          }
        }
      ]
    }
  ]
}
```

---

## 会话管理

### 会话状态机

```
┌──────────┐
│  CREATED │
└────┬─────┘
     │
     │ 用户开始交互
     ▼
┌──────────┐
│  ACTIVE  │◀──────────────────────────┐
└────┬─────┘                           │
     │                                 │
     │ 选择工作区/开始工作流            │
     ▼                                 │
┌──────────┐      工作流完成/返回      │
│ WORKING  │───────────────────────────┘
└────┬─────┘
     │
     │ 长时间无活动 (30分钟)
     ▼
┌──────────┐
│   IDLE   │
└────┬─────┘
     │
     │ 超时 (2小时)
     ▼
┌──────────┐
│ EXPIRED  │
└──────────┘
```

### 会话上下文

```python
@dataclass
class SessionContext:
    """会话上下文"""
    
    # 基础信息
    session_id: str
    user_id: str
    platform: str  # feishu, web, cli
    
    # 飞书特定
    feishu_user_id: Optional[str]
    feishu_chat_id: Optional[str]
    feishu_open_id: Optional[str]
    
    # 当前状态
    current_workspace_id: Optional[str]
    current_workflow_id: Optional[str]
    current_agent_type: Optional[str]
    
    # 对话历史 (最近10轮)
    conversation_history: List[ConversationTurn]
    
    # 用户偏好
    preferences: Dict[str, Any]
    
    # 临时变量
    temp_variables: Dict[str, Any]
    
    # 待确认操作
    pending_confirmation: Optional[PendingConfirmation]
    
    # 时间戳
    created_at: datetime
    last_activity_at: datetime
    expires_at: datetime


class SessionManager:
    """会话管理器"""
    
    def __init__(
        self,
        redis: Redis,
        db: AsyncSession,
        session_timeout: int = 7200  # 2小时
    ):
        self.redis = redis
        self.db = db
        self.session_timeout = session_timeout
    
    async def get_or_create(
        self,
        user_id: str,
        platform: str,
        **kwargs
    ) -> SessionContext:
        """获取或创建会话"""
        
        # 1. 尝试从Redis获取活跃会话
        session_key = f"session:{platform}:{user_id}"
        session_data = await self.redis.get(session_key)
        
        if session_data:
            session = SessionContext.deserialize(session_data)
            
            # 检查是否过期
            if session.expires_at > datetime.utcnow():
                # 更新活动时间
                session.last_activity_at = datetime.utcnow()
                session.expires_at = datetime.utcnow() + timedelta(seconds=self.session_timeout)
                await self._save_to_redis(session)
                return session
        
        # 2. 创建新会话
        session = await self._create_session(user_id, platform, **kwargs)
        return session
    
    async def _create_session(
        self,
        user_id: str,
        platform: str,
        **kwargs
    ) -> SessionContext:
        """创建新会话"""
        
        now = datetime.utcnow()
        session = SessionContext(
            session_id=generate_uuid(),
            user_id=user_id,
            platform=platform,
            feishu_user_id=kwargs.get("feishu_user_id"),
            feishu_chat_id=kwargs.get("feishu_chat_id"),
            feishu_open_id=kwargs.get("feishu_open_id"),
            current_workspace_id=None,
            current_workflow_id=None,
            current_agent_type=None,
            conversation_history=[],
            preferences={},
            temp_variables={},
            pending_confirmation=None,
            created_at=now,
            last_activity_at=now,
            expires_at=now + timedelta(seconds=self.session_timeout)
        )
        
        # 保存到Redis
        await self._save_to_redis(session)
        
        # 持久化到数据库
        await self._persist_session(session)
        
        return session
    
    async def update_context(
        self,
        session_id: str,
        updates: Dict[str, Any]
    ):
        """更新会话上下文"""
        session = await self.get_by_id(session_id)
        
        for key, value in updates.items():
            if hasattr(session, key):
                setattr(session, key, value)
        
        session.last_activity_at = datetime.utcnow()
        await self._save_to_redis(session)
    
    async def add_conversation_turn(
        self,
        session_id: str,
        user_message: str,
        agent_response: str
    ):
        """添加对话轮次"""
        session = await self.get_by_id(session_id)
        
        turn = ConversationTurn(
            timestamp=datetime.utcnow(),
            user_message=user_message,
            agent_response=agent_response
        )
        
        session.conversation_history.append(turn)
        
        # 只保留最近10轮
        if len(session.conversation_history) > 10:
            session.conversation_history = session.conversation_history[-10:]
        
        await self._save_to_redis(session)
```

### 多工作区切换

```python
class WorkspaceSwitcher:
    """工作区切换器"""
    
    async def switch_workspace(
        self,
        session: SessionContext,
        workspace_id: str
    ) -> SwitchResult:
        """切换工作区"""
        
        # 1. 获取目标工作区
        workspace = await self.workspace_mgr.get(workspace_id)
        if not workspace:
            return SwitchResult(
                success=False,
                error="工作区不存在"
            )
        
        # 2. 保存当前工作区状态 (如果有)
        if session.current_workspace_id:
            await self._save_current_workspace_state(session)
        
        # 3. 检查目标工作区状态
        if workspace.status == "inactive":
            # 需要启动工作区
            await self._start_workspace(workspace)
        
        # 4. 更新会话
        await self.session_mgr.update_context(
            session.session_id,
            {
                "current_workspace_id": workspace_id,
                "current_workflow_id": None
            }
        )
        
        # 5. 恢复工作区上下文
        context = await self._load_workspace_context(workspace_id)
        
        return SwitchResult(
            success=True,
            workspace=workspace,
            context=context,
            message=f"已切换到工作区: {workspace.name}"
        )
    
    async def list_available_workspaces(
        self,
        user_id: str
    ) -> List[WorkspaceInfo]:
        """列出用户可用工作区"""
        workspaces = await self.workspace_mgr.list_by_user(user_id)
        
        return [
            WorkspaceInfo(
                id=ws.id,
                name=ws.name,
                project_id=ws.project_id,
                status=ws.status,
                is_active=ws.status == "active",
                last_accessed=ws.last_accessed_at
            )
            for ws in workspaces
        ]
```

---

## 离线消息处理

```python
class OfflineMessageQueue:
    """离线消息队列"""
    
    def __init__(self, redis: Redis):
        self.redis = redis
    
    async def enqueue(
        self,
        user_id: str,
        message: Dict[str, Any]
    ):
        """将消息加入离线队列"""
        queue_key = f"offline_queue:{user_id}"
        
        await self.redis.lpush(
            queue_key,
            json.dumps({
                **message,
                "enqueued_at": datetime.utcnow().isoformat()
            })
        )
        
        # 设置队列过期时间 (7天)
        await self.redis.expire(queue_key, 7 * 24 * 3600)
    
    async def dequeue_all(
        self,
        user_id: str
    ) -> List[Dict[str, Any]]:
        """取出所有离线消息"""
        queue_key = f"offline_queue:{user_id}"
        
        messages = []
        while True:
            message = await self.redis.rpop(queue_key)
            if not message:
                break
            messages.append(json.loads(message))
        
        return messages
    
    async def process_offline_messages(
        self,
        session: SessionContext
    ):
        """处理用户上线时的离线消息"""
        messages = await self.dequeue_all(session.user_id)
        
        if messages:
            # 合并相似消息
            grouped = self._group_messages(messages)
            
            # 发送汇总卡片
            await self._send_offline_summary(session, grouped)
```

---

*文档版本: 1.0*
*最后更新: 2026-03-25*
