# 持久化层设计

## 目录

1. [整体架构](#整体架构)
2. [数据库设计](#数据库设计)
3. [状态快照机制](#状态快照机制)
4. [数据备份与恢复](#数据备份与恢复)

---

## 整体架构

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           持久化层 (Persistence Layer)                        │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌───────────────────────────────────────────────────────────────────────┐ │
│  │                     PostgreSQL (Primary Storage)                       │ │
│  │                                                                        │ │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌────────────┐ │ │
│  │  │  Workflows   │  │    Steps     │  │  Checkpoints │  │   Events   │ │ │
│  │  │   (工作流)    │  │   (步骤)      │  │   (检查点)    │  │   (事件)    │ │
│  │  └──────────────┘  └──────────────┘  └──────────────┘  └────────────┘ │ │
│  │                                                                        │ │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                  │ │
│  │  │    Agents    │  │  Workspaces  │  │   Sessions   │                  │ │
│  │  │   (Agent)    │  │   (工作区)    │  │   (会话)      │                  │ │
│  │  └──────────────┘  └──────────────┘  └──────────────┘                  │ │
│  │                                                                        │ │
│  └───────────────────────────────────────────────────────────────────────┘ │
│                                                                             │
│  ┌───────────────────────────────────────────────────────────────────────┐ │
│  │                      Redis (Cache & Queue)                             │ │
│  │                                                                        │ │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌────────────┐ │ │
│  │  │  Session     │  │   Message    │  │ Distributed  │  │  Real-time │ │ │
│  │  │   Cache      │  │    Queue     │  │     Lock     │  │   Pub/Sub  │ │ │
│  │  └──────────────┘  └──────────────┘  └──────────────┘  └────────────┘ │ │
│  │                                                                        │ │
│  └───────────────────────────────────────────────────────────────────────┘ │
│                                                                             │
│  ┌───────────────────────────────────────────────────────────────────────┐ │
│  │                      File System (Artifacts)                           │ │
│  │                                                                        │ │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                  │ │
│  │  │  Workspace   │  │   Build      │  │    Logs      │                  │ │
│  │  │    Files     │  │  Artifacts   │  │   (日志)      │                  │ │
│  │  └──────────────┘  └──────────────┘  └──────────────┘                  │ │
│  │                                                                        │ │
│  └───────────────────────────────────────────────────────────────────────┘ │
│                                                                             │
│  ┌───────────────────────────────────────────────────────────────────────┐ │
│  │                      Object Storage (MinIO/S3)                         │ │
│  │                                                                        │ │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                  │ │
│  │  │  Snapshots   │  │  Archives    │  │  Backups     │                  │ │
│  │  │  (状态快照)   │  │   (归档)      │  │   (备份)      │                  │ │
│  │  └──────────────┘  └──────────────┘  └──────────────┘                  │ │
│  │                                                                        │ │
│  └───────────────────────────────────────────────────────────────────────┘ │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 数据库设计

### 核心表结构

#### 1. workflows (工作流表)

```sql
CREATE TABLE workflows (
    -- 主键
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- 基本信息
    name VARCHAR(255) NOT NULL,
    description TEXT,
    version VARCHAR(50) NOT NULL DEFAULT '1.0',
    
    -- 工作流定义 (JSONB存储完整DAG定义)
    definition JSONB NOT NULL,
    
    -- 状态
    status VARCHAR(50) NOT NULL DEFAULT 'created',
    -- created, pending, running, paused, completed, failed, cancelled
    
    -- 当前执行位置
    current_step_id VARCHAR(100),
    current_step_index INTEGER DEFAULT 0,
    
    -- 上下文变量
    context JSONB DEFAULT '{}',
    
    -- 执行统计
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    execution_time_seconds FLOAT,
    
    -- 关联信息
    project_id VARCHAR(100),
    workspace_id UUID,
    created_by VARCHAR(100),
    
    -- 优先级和调度
    priority INTEGER DEFAULT 5 CHECK (priority >= 1 AND priority <= 10),
    scheduled_at TIMESTAMP WITH TIME ZONE,
    
    -- 错误信息
    error_message TEXT,
    error_stack_trace TEXT,
    
    -- 检查点
    latest_checkpoint_id UUID,
    checkpoint_count INTEGER DEFAULT 0,
    
    -- 元数据
    metadata JSONB DEFAULT '{}',
    
    -- 时间戳
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 索引
CREATE INDEX idx_workflows_status ON workflows(status);
CREATE INDEX idx_workflows_project_id ON workflows(project_id);
CREATE INDEX idx_workflows_created_by ON workflows(created_by);
CREATE INDEX idx_workflows_priority ON workflows(priority DESC, created_at);
CREATE INDEX idx_workflows_status_created ON workflows(status, created_at);

-- GIN索引用于JSONB查询
CREATE INDEX idx_workflows_context_gin ON workflows USING GIN(context);
CREATE INDEX idx_workflows_definition_gin ON workflows USING GIN(definition);
```

#### 2. workflow_steps (工作流步骤表)

```sql
CREATE TABLE workflow_steps (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- 关联
    workflow_id UUID NOT NULL REFERENCES workflows(id) ON DELETE CASCADE,
    step_id VARCHAR(100) NOT NULL,
    
    -- Agent信息
    agent_type VARCHAR(100) NOT NULL,
    agent_instance_id VARCHAR(100),
    
    -- 步骤配置
    step_config JSONB NOT NULL DEFAULT '{}',
    
    -- 状态
    status VARCHAR(50) NOT NULL DEFAULT 'pending',
    -- pending, scheduled, running, waiting, completed, failed, skipped, cancelled
    
    -- 输入输出
    input_data JSONB,
    output_data JSONB,
    
    -- 错误信息
    error_message TEXT,
    error_code VARCHAR(100),
    retry_count INTEGER DEFAULT 0,
    max_retries INTEGER DEFAULT 3,
    
    -- 执行时间
    scheduled_at TIMESTAMP WITH TIME ZONE,
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    execution_time_seconds FLOAT,
    
    -- 依赖关系
    depends_on UUID[],  -- 依赖的步骤ID数组
    
    -- 元数据
    metadata JSONB DEFAULT '{}',
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- 唯一约束: 同一个工作流中步骤ID唯一
    UNIQUE(workflow_id, step_id)
);

-- 索引
CREATE INDEX idx_steps_workflow_id ON workflow_steps(workflow_id);
CREATE INDEX idx_steps_status ON workflow_steps(status);
CREATE INDEX idx_steps_agent_type ON workflow_steps(agent_type);
CREATE INDEX idx_steps_workflow_status ON workflow_steps(workflow_id, status);
```

#### 3. workflow_checkpoints (检查点表)

```sql
CREATE TABLE workflow_checkpoints (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- 关联
    workflow_id UUID NOT NULL REFERENCES workflows(id) ON DELETE CASCADE,
    step_id VARCHAR(100),
    
    -- 检查点类型
    checkpoint_type VARCHAR(50) NOT NULL,
    -- manual, pre_step, post_step, periodic, emergency, progress
    
    -- 完整状态快照 (压缩存储)
    workflow_state BYTEA NOT NULL,  -- 使用msgpack + zlib压缩
    step_states BYTEA,              -- 所有步骤的状态
    context_variables BYTEA,        -- 上下文变量
    
    -- 恢复信息
    recoverable BOOLEAN DEFAULT TRUE,
    recovery_instructions TEXT,
    
    -- 资源使用
    memory_usage_mb FLOAT,
    disk_usage_mb FLOAT,
    
    -- 执行统计
    execution_time_seconds FLOAT,
    step_completed_count INTEGER,
    
    -- 元数据
    metadata JSONB DEFAULT '{}',
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- 过期时间 (用于自动清理)
    expires_at TIMESTAMP WITH TIME ZONE
);

-- 索引
CREATE INDEX idx_checkpoints_workflow_id ON workflow_checkpoints(workflow_id);
CREATE INDEX idx_checkpoints_workflow_type ON workflow_checkpoints(workflow_id, checkpoint_type);
CREATE INDEX idx_checkpoints_created_at ON workflow_checkpoints(created_at);
CREATE INDEX idx_checkpoints_expires_at ON workflow_checkpoints(expires_at) 
    WHERE expires_at IS NOT NULL;
```

#### 4. workflow_events (事件日志表)

```sql
CREATE TABLE workflow_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- 关联
    workflow_id UUID NOT NULL REFERENCES workflows(id) ON DELETE CASCADE,
    step_id VARCHAR(100),
    
    -- 事件信息
    event_type VARCHAR(100) NOT NULL,
    event_version INTEGER DEFAULT 1,
    
    -- 事件数据
    payload JSONB NOT NULL,
    
    -- 上下文
    session_id VARCHAR(100),
    user_id VARCHAR(100),
    
    -- 追踪
    correlation_id VARCHAR(100),
    parent_event_id UUID REFERENCES workflow_events(id),
    
    -- 来源
    source VARCHAR(100),
    source_ip INET,
    
    -- 元数据
    metadata JSONB DEFAULT '{}',
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 索引
CREATE INDEX idx_events_workflow_id ON workflow_events(workflow_id);
CREATE INDEX idx_events_type ON workflow_events(event_type);
CREATE INDEX idx_events_created_at ON workflow_events(created_at);
CREATE INDEX idx_events_correlation ON workflow_events(correlation_id);
CREATE INDEX idx_events_workflow_type_time ON workflow_events(workflow_id, event_type, created_at);

-- 分区: 按月分区处理大量事件
-- CREATE TABLE workflow_events_y2026m03 PARTITION OF workflow_events
--     FOR VALUES FROM ('2026-03-01') TO ('2026-04-01');
```

#### 5. agent_registrations (Agent注册表)

```sql
CREATE TABLE agent_registrations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Agent信息
    agent_type VARCHAR(100) NOT NULL UNIQUE,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    version VARCHAR(50) DEFAULT '1.0',
    
    -- 能力定义
    capabilities JSONB NOT NULL DEFAULT '[]',
    supported_languages JSONB DEFAULT '[]',
    required_tools JSONB DEFAULT '[]',
    
    -- 配置模板
    config_schema JSONB,  -- JSON Schema
    default_config JSONB DEFAULT '{}',
    
    -- 资源限制
    max_concurrent_tasks INTEGER DEFAULT 5,
    timeout_seconds INTEGER DEFAULT 300,
    
    -- 状态
    enabled BOOLEAN DEFAULT TRUE,
    status VARCHAR(50) DEFAULT 'healthy',
    -- healthy, degraded, unavailable
    
    -- 统计
    total_tasks_completed INTEGER DEFAULT 0,
    total_tasks_failed INTEGER DEFAULT 0,
    average_execution_time_seconds FLOAT,
    
    -- 元数据
    metadata JSONB DEFAULT '{}',
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 索引
CREATE INDEX idx_agents_type ON agent_registrations(agent_type);
CREATE INDEX idx_agents_status ON agent_registrations(status);
CREATE INDEX idx_agents_enabled ON agent_registrations(enabled) WHERE enabled = TRUE;
```

#### 6. workspaces (工作区表)

```sql
CREATE TABLE workspaces (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- 基本信息
    name VARCHAR(255) NOT NULL,
    description TEXT,
    
    -- 项目关联
    project_id VARCHAR(100) NOT NULL,
    project_path VARCHAR(500) NOT NULL,
    
    -- 工作区路径
    workspace_path VARCHAR(500) NOT NULL,
    
    -- 状态
    status VARCHAR(50) DEFAULT 'inactive',
    -- inactive, active, locked, archived
    
    -- 资源使用
    disk_usage_mb FLOAT DEFAULT 0,
    memory_usage_mb FLOAT DEFAULT 0,
    
    -- 关联的工作流
    active_workflow_id UUID REFERENCES workflows(id),
    
    -- 配置
    config JSONB DEFAULT '{}',
    
    -- 元数据
    metadata JSONB DEFAULT '{}',
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_accessed_at TIMESTAMP WITH TIME ZONE,
    
    -- 清理策略
    auto_cleanup BOOLEAN DEFAULT TRUE,
    expires_at TIMESTAMP WITH TIME ZONE
);

-- 索引
CREATE INDEX idx_workspaces_project ON workspaces(project_id);
CREATE INDEX idx_workspaces_status ON workspaces(status);
CREATE INDEX idx_workspaces_expires ON workspaces(expires_at) WHERE expires_at IS NOT NULL;
```

#### 7. sessions (会话表)

```sql
CREATE TABLE sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- 用户信息
    user_id VARCHAR(100) NOT NULL,
    user_name VARCHAR(255),
    
    -- 会话信息
    session_type VARCHAR(50) NOT NULL,  -- feishu, web, cli
    platform VARCHAR(50),  -- feishu, web, mobile
    
    -- 飞书特定字段
    feishu_user_id VARCHAR(100),
    feishu_chat_id VARCHAR(100),
    feishu_open_id VARCHAR(100),
    
    -- 当前上下文
    current_workspace_id UUID REFERENCES workspaces(id),
    current_workflow_id UUID REFERENCES workflows(id),
    
    -- 会话状态
    status VARCHAR(50) DEFAULT 'active',
    -- active, idle, expired
    
    -- 最后活动
    last_activity_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_message_at TIMESTAMP WITH TIME ZONE,
    
    -- 统计
    message_count INTEGER DEFAULT 0,
    workflow_count INTEGER DEFAULT 0,
    
    -- 配置
    preferences JSONB DEFAULT '{}',
    
    -- 时间戳
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    expires_at TIMESTAMP WITH TIME ZONE,
    
    -- 唯一约束: 飞书用户同一时间只有一个活跃会话
    UNIQUE(feishu_user_id, status) WHERE status = 'active'
);

-- 索引
CREATE INDEX idx_sessions_user ON sessions(user_id);
CREATE INDEX idx_sessions_feishu ON sessions(feishu_user_id);
CREATE INDEX idx_sessions_status ON sessions(status);
CREATE INDEX idx_sessions_activity ON sessions(last_activity_at);
```

### 数据访问层 (DAO)

```python
# sail_server/data/dao/workflow_dao.py

class WorkflowDAO:
    """工作流数据访问对象"""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def create(
        self,
        name: str,
        definition: Dict[str, Any],
        created_by: str,
        project_id: str = None,
        priority: int = 5,
        context: Dict[str, Any] = None
    ) -> Workflow:
        """创建工作流"""
        workflow = Workflow(
            name=name,
            definition=definition,
            created_by=created_by,
            project_id=project_id,
            priority=priority,
            context=context or {},
            status=WorkflowStatus.CREATED
        )
        self.session.add(workflow)
        await self.session.commit()
        await self.session.refresh(workflow)
        return workflow
    
    async def get_by_id(self, workflow_id: UUID) -> Optional[Workflow]:
        """根据ID获取工作流"""
        result = await self.session.execute(
            select(Workflow).where(Workflow.id == workflow_id)
        )
        return result.scalar_one_or_none()
    
    async def update_status(
        self,
        workflow_id: UUID,
        status: WorkflowStatus,
        error_message: str = None
    ) -> bool:
        """更新工作流状态"""
        update_data = {
            "status": status,
            "updated_at": datetime.utcnow()
        }
        
        if status == WorkflowStatus.RUNNING:
            update_data["started_at"] = datetime.utcnow()
        elif status in [WorkflowStatus.COMPLETED, WorkflowStatus.FAILED, WorkflowStatus.CANCELLED]:
            update_data["completed_at"] = datetime.utcnow()
        
        if error_message:
            update_data["error_message"] = error_message
        
        result = await self.session.execute(
            update(Workflow)
            .where(Workflow.id == workflow_id)
            .values(**update_data)
        )
        await self.session.commit()
        return result.rowcount > 0
    
    async def list_workflows(
        self,
        status: WorkflowStatus = None,
        project_id: str = None,
        created_by: str = None,
        limit: int = 20,
        offset: int = 0
    ) -> List[Workflow]:
        """列取工作流列表"""
        query = select(Workflow)
        
        if status:
            query = query.where(Workflow.status == status)
        if project_id:
            query = query.where(Workflow.project_id == project_id)
        if created_by:
            query = query.where(Workflow.created_by == created_by)
        
        query = query.order_by(Workflow.created_at.desc())
        query = query.limit(limit).offset(offset)
        
        result = await self.session.execute(query)
        return result.scalars().all()
    
    async def save_checkpoint(
        self,
        workflow_id: UUID,
        checkpoint_data: Dict[str, Any]
    ) -> UUID:
        """保存检查点"""
        checkpoint = WorkflowCheckpoint(
            workflow_id=workflow_id,
            **checkpoint_data
        )
        self.session.add(checkpoint)
        
        # 更新工作流的最新检查点
        await self.session.execute(
            update(Workflow)
            .where(Workflow.id == workflow_id)
            .values(
                latest_checkpoint_id=checkpoint.id,
                checkpoint_count=Workflow.checkpoint_count + 1
            )
        )
        
        await self.session.commit()
        await self.session.refresh(checkpoint)
        return checkpoint.id
```

---

## 状态快照机制

### 序列化策略

```python
import msgpack
import zlib
from typing import Any, Dict

class StateSerializer:
    """状态序列化器"""
    
    @staticmethod
    def serialize(state: Dict[str, Any]) -> bytes:
        """序列化状态为压缩字节"""
        # 使用msgpack序列化
        packed = msgpack.packb(state, use_bin_type=True)
        # 使用zlib压缩
        compressed = zlib.compress(packed, level=6)
        return compressed
    
    @staticmethod
    def deserialize(data: bytes) -> Dict[str, Any]:
        """反序列化字节为状态"""
        # 解压缩
        decompressed = zlib.decompress(data)
        # msgpack反序列化
        state = msgpack.unpackb(decompressed, raw=False)
        return state
    
    @staticmethod
    def get_size_mb(data: bytes) -> float:
        """获取数据大小(MB)"""
        return len(data) / (1024 * 1024)


class WorkflowStateSnapshot:
    """工作流状态快照"""
    
    def __init__(self, workflow: Workflow):
        self.workflow = workflow
    
    def capture(self) -> Dict[str, Any]:
        """捕获当前状态"""
        return {
            "id": str(self.workflow.id),
            "name": self.workflow.name,
            "status": self.workflow.status.value,
            "current_step_id": self.workflow.current_step_id,
            "current_step_index": self.workflow.current_step_index,
            "context": self.workflow.context,
            "started_at": self.workflow.started_at.isoformat() if self.workflow.started_at else None,
            "execution_time_seconds": self.workflow.execution_time_seconds,
            "metadata": self.workflow.metadata
        }
    
    @classmethod
    def restore(cls, snapshot: Dict[str, Any]) -> Workflow:
        """从快照恢复工作流"""
        # 注意: 这里只恢复状态，不创建新实例
        # 实际恢复逻辑在Workflow类中实现
        pass
```

### 增量检查点

```python
class IncrementalCheckpoint:
    """增量检查点管理"""
    
    def __init__(self):
        self.base_checkpoint_id: Optional[str] = None
        self.changes: List[StateChange] = []
    
    def record_change(
        self,
        path: str,
        old_value: Any,
        new_value: Any,
        change_type: str  # add, update, delete
    ):
        """记录状态变更"""
        self.changes.append(StateChange(
            path=path,
            old_value=old_value,
            new_value=new_value,
            change_type=change_type,
            timestamp=datetime.utcnow()
        ))
    
    def apply_to_base(
        self,
        base_state: Dict[str, Any]
    ) -> Dict[str, Any]:
        """将增量变更应用到基础状态"""
        state = deepcopy(base_state)
        
        for change in self.changes:
            if change.change_type == "delete":
                self._delete_at_path(state, change.path)
            else:
                self._set_at_path(state, change.path, change.new_value)
        
        return state
```

---

## 数据备份与恢复

### 备份策略

```python
class BackupManager:
    """备份管理器"""
    
    def __init__(
        self,
        db_engine: AsyncEngine,
        storage: ObjectStorage,
        retention_days: int = 30
    ):
        self.db_engine = db_engine
        self.storage = storage
        self.retention_days = retention_days
    
    async def create_backup(
        self,
        backup_type: str = "full",  # full, incremental
        include_files: bool = True
    ) -> BackupInfo:
        """创建备份"""
        backup_id = generate_uuid()
        backup_time = datetime.utcnow()
        
        # 1. 备份数据库
        db_backup_path = await self._backup_database(backup_id)
        
        # 2. 备份文件 (如果需要)
        files_backup_path = None
        if include_files:
            files_backup_path = await self._backup_files(backup_id)
        
        # 3. 创建备份元数据
        backup_info = BackupInfo(
            id=backup_id,
            type=backup_type,
            created_at=backup_time,
            db_size_mb=os.path.getsize(db_backup_path) / (1024 * 1024),
            files_size_mb=os.path.getsize(files_backup_path) / (1024 * 1024) if files_backup_path else 0,
            db_path=db_backup_path,
            files_path=files_backup_path
        )
        
        # 4. 上传到对象存储
        await self._upload_to_storage(backup_info)
        
        return backup_info
    
    async def restore_backup(
        self,
        backup_id: str,
        target_timestamp: datetime = None
    ) -> bool:
        """从备份恢复"""
        # 1. 下载备份文件
        backup_info = await self._download_from_storage(backup_id)
        
        # 2. 恢复数据库
        await self._restore_database(backup_info.db_path)
        
        # 3. 恢复文件
        if backup_info.files_path:
            await self._restore_files(backup_info.files_path)
        
        return True
    
    async def cleanup_old_backups(self):
        """清理过期备份"""
        cutoff_date = datetime.utcnow() - timedelta(days=self.retention_days)
        
        # 删除过期备份
        old_backups = await self._list_backups_before(cutoff_date)
        for backup in old_backups:
            await self._delete_backup(backup.id)
```

### 自动清理策略

```sql
-- 自动清理过期检查点
CREATE OR REPLACE FUNCTION cleanup_expired_checkpoints()
RETURNS void AS $$
BEGIN
    DELETE FROM workflow_checkpoints
    WHERE expires_at IS NOT NULL
      AND expires_at < NOW();
END;
$$ LANGUAGE plpgsql;

-- 创建定时任务 (使用pg_cron扩展)
SELECT cron.schedule('cleanup-checkpoints', '0 2 * * *', 'SELECT cleanup_expired_checkpoints()');

-- 自动归档已完成工作流
CREATE OR REPLACE FUNCTION archive_completed_workflows()
RETURNS void AS $$
BEGIN
    INSERT INTO workflow_archives (
        SELECT * FROM workflows
        WHERE status IN ('completed', 'failed', 'cancelled')
          AND completed_at < NOW() - INTERVAL '30 days'
    );
    
    DELETE FROM workflows
    WHERE status IN ('completed', 'failed', 'cancelled')
      AND completed_at < NOW() - INTERVAL '30 days';
END;
$$ LANGUAGE plpgsql;
```

---

*文档版本: 1.0*
*最后更新: 2026-03-25*
