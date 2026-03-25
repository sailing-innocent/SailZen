# 工作区管理设计

## 目录

1. [工作区模型](#工作区模型)
2. [隔离策略](#隔离策略)
3. [生命周期管理](#生命周期管理)
4. [资源调度](#资源调度)

---

## 工作区模型

### 工作区概念

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                            Workspace (工作区)                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌───────────────────────────────────────────────────────────────────────┐ │
│  │                      Workspace Manifest                                │ │
│  │                                                                        │ │
│  │  {                                                                     │ │
│  │    "id": "ws-uuid",                                                   │ │
│  │    "name": "SailZen Dev",                                             │ │
│  │    "project_id": "sailzen",                                           │ │
│  │    "project_path": "D:/ws/repos/SailZen",                             │ │
│  │    "workspace_path": "~/.sailzen/workspaces/ws-uuid",                 │ │
│  │                                                                        │ │
│  │    "resources": {                                                      │ │
│  │      "port_range": [4096, 4100],                                      │ │
│  │      "memory_limit_mb": 4096,                                         │ │
│  │      "disk_limit_gb": 50,                                             │ │
│  │      "cpu_limit": 2.0                                                 │ │
│  │    },                                                                  │ │
│  │                                                                        │ │
│  │    "opencode": {                                                       │ │
│  │      "version": "latest",                                             │ │
│  │      "config": {                                                       │ │
│  │        "port": 4096,                                                  │ │
│  │        "api_key": "***"                                               │ │
│  │      }                                                                 │ │
│  │    },                                                                  │ │
│  │                                                                        │ │
│  │    "environment": {                                                    │ │
│  │      "variables": {                                                    │ │
│  │        "NODE_ENV": "development",                                     │ │
│  │        "PYTHONPATH": "/workspace/src"                                 │ │
│  │      },                                                                │ │
│  │      "python_version": "3.13",                                        │ │
│  │      "node_version": "20"                                             │ │
│  │    }                                                                   │ │
│  │  }                                                                     │ │
│  │                                                                        │ │
│  └───────────────────────────────────────────────────────────────────────┘ │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 工作区目录结构

```
~/.sailzen/workspaces/
│
├── ws-uuid-1/                          # 工作区1
│   ├── manifest.json                   # 工作区配置
│   ├── state.json                      # 运行时状态
│   ├── logs/                           # 日志目录
│   │   ├── opencode.log
│   │   ├── agent.log
│   │   └── error.log
│   ├── cache/                          # 缓存目录
│   │   ├── build/
│   │   ├── dependencies/
│   │   └── temp/
│   ├── sessions/                       # OpenCode会话
│   │   ├── session-1/
│   │   └── session-2/
│   └── workspace/                      # 工作目录 (挂载项目)
│       └── (project files)
│
├── ws-uuid-2/                          # 工作区2
│   └── ...
│
└── shared/                             # 共享资源
    ├── templates/                      # 模板文件
    ├── tools/                          # 工具链
    └── cache/                          # 全局缓存
```

---

## 隔离策略

### 1. 进程隔离

```python
class ProcessIsolation:
    """进程隔离管理"""
    
    async def create_isolated_process(
        self,
        workspace: Workspace,
        command: List[str],
        **kwargs
    ) -> subprocess.Process:
        """创建隔离进程"""
        
        # 1. 设置资源限制 (Linux)
        def preexec_fn():
            if sys.platform != "win32":
                import resource
                # 限制内存
                resource.setrlimit(
                    resource.RLIMIT_AS,
                    (workspace.memory_limit_mb * 1024 * 1024, -1)
                )
                # 限制CPU时间
                resource.setrlimit(
                    resource.RLIMIT_CPU,
                    (3600, -1)  # 1小时
                )
        
        # 2. 设置环境变量
        env = os.environ.copy()
        env.update(workspace.environment_variables)
        env["SAILZEN_WORKSPACE_ID"] = str(workspace.id)
        env["SAILZEN_WORKSPACE_PATH"] = workspace.workspace_path
        
        # 3. 创建工作目录
        work_dir = workspace.workspace_path
        os.makedirs(work_dir, exist_ok=True)
        
        # 4. 启动进程
        process = await asyncio.create_subprocess_exec(
            *command,
            cwd=work_dir,
            env=env,
            preexec_fn=preexec_fn if sys.platform != "win32" else None,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            **kwargs
        )
        
        return process
```

### 2. 端口隔离

```python
class PortAllocator:
    """端口分配器"""
    
    def __init__(
        self,
        base_port: int = 4096,
        max_port: int = 8192,
        ports_per_workspace: int = 5
    ):
        self.base_port = base_port
        self.max_port = max_port
        self.ports_per_workspace = ports_per_workspace
        self.allocated_ranges: Dict[str, PortRange] = {}
        self.lock = asyncio.Lock()
    
    async def allocate_range(self, workspace_id: str) -> PortRange:
        """为工作区分配端口范围"""
        async with self.lock:
            # 检查是否已分配
            if workspace_id in self.allocated_ranges:
                return self.allocated_ranges[workspace_id]
            
            # 查找可用范围
            for start in range(
                self.base_port,
                self.max_port,
                self.ports_per_workspace
            ):
                end = start + self.ports_per_workspace - 1
                
                if self._is_range_available(start, end):
                    port_range = PortRange(
                        workspace_id=workspace_id,
                        start=start,
                        end=end,
                        ports=list(range(start, end + 1))
                    )
                    self.allocated_ranges[workspace_id] = port_range
                    return port_range
            
            raise PortAllocationError("No available port range")
    
    def _is_range_available(self, start: int, end: int) -> bool:
        """检查端口范围是否可用"""
        for allocated in self.allocated_ranges.values():
            if not (end < allocated.start or start > allocated.end):
                return False
        
        # 检查端口是否被占用
        for port in range(start, end + 1):
            if self._is_port_in_use(port):
                return False
        
        return True
    
    async def release_range(self, workspace_id: str):
        """释放端口范围"""
        async with self.lock:
            if workspace_id in self.allocated_ranges:
                del self.allocated_ranges[workspace_id]
```

### 3. 文件系统隔离

```python
class FileSystemIsolation:
    """文件系统隔离"""
    
    async def setup_workspace_fs(self, workspace: Workspace):
        """设置工作区文件系统"""
        
        # 1. 创建工作区目录结构
        dirs = [
            workspace.workspace_path,
            workspace.logs_path,
            workspace.cache_path,
            workspace.sessions_path,
        ]
        
        for dir_path in dirs:
            os.makedirs(dir_path, exist_ok=True)
        
        # 2. 创建符号链接到项目目录
        project_link = os.path.join(workspace.workspace_path, "project")
        if os.path.exists(project_link):
            os.remove(project_link)
        
        if sys.platform == "win32":
            # Windows使用junction
            import subprocess
            subprocess.run(
                ["mklink", "/J", project_link, workspace.project_path],
                check=True,
                shell=True
            )
        else:
            # Unix使用symlink
            os.symlink(workspace.project_path, project_link)
        
        # 3. 设置只读挂载 (可选，Linux only)
        if sys.platform != "win32" and workspace.read_only:
            await self._mount_readonly(workspace)
    
    async def cleanup_workspace_fs(self, workspace: Workspace):
        """清理工作区文件系统"""
        
        # 1. 卸载挂载点
        if sys.platform != "win32":
            await self._unmount(workspace)
        
        # 2. 删除工作区目录 (保留日志)
        if os.path.exists(workspace.workspace_path):
            shutil.rmtree(workspace.workspace_path)
```

### 4. 网络隔离 (Docker模式)

```python
class DockerIsolation:
    """Docker容器隔离"""
    
    def __init__(self):
        self.docker = aiodocker.Docker()
    
    async def create_workspace_container(
        self,
        workspace: Workspace
    ) -> Container:
        """为工作区创建隔离容器"""
        
        container_config = {
            "Image": "sailzen-workspace:latest",
            "Cmd": ["tail", "-f", "/dev/null"],  # 保持运行
            "HostConfig": {
                "Binds": [
                    f"{workspace.project_path}:/workspace/project:ro",
                    f"{workspace.workspace_path}:/workspace/data",
                ],
                "PortBindings": {
                    f"{port}/tcp": [{"HostPort": str(port)}]
                    for port in workspace.ports
                },
                "Memory": workspace.memory_limit_mb * 1024 * 1024,
                "CpuQuota": int(workspace.cpu_limit * 100000),
                "NetworkMode": f"workspace-{workspace.id}",
            },
            "Env": [
                f"SAILZEN_WORKSPACE_ID={workspace.id}",
                f"WORKSPACE_PORT={workspace.main_port}",
            ],
            "Labels": {
                "sailzen.workspace.id": str(workspace.id),
                "sailzen.workspace.name": workspace.name,
            }
        }
        
        container = await self.docker.containers.create(
            config=container_config,
            name=f"sailzen-workspace-{workspace.id}"
        )
        
        await container.start()
        
        return container
```

---

## 生命周期管理

### 工作区状态机

```
┌──────────┐
│  CREATED │
└────┬─────┘
     │
     │ 初始化资源
     ▼
┌──────────┐     启动失败      ┌──────────┐
│READY/    │──────────────────▶│  ERROR   │
│INACTIVE   │                   └──────────┘
└────┬─────┘
     │
     │ 用户启动 / 自动启动
     ▼
┌──────────┐
│ STARTING │
└────┬─────┘
     │
     ▼
┌──────────┐     异常           ┌──────────┐
│  ACTIVE  │──────────────────▶│ DEGRADED │
└────┬─────┘                   └────┬─────┘
     │                              │
     │ 健康检查失败                    │ 恢复
     │                              ▼
     │                         ┌──────────┐
     │                         │  ACTIVE  │
     │                         └──────────┘
     │
     │ 用户停止 / 超时
     ▼
┌──────────┐
│STOPPING  │
└────┬─────┘
     │
     ▼
┌──────────┐
│  LOCKED  │◀────────────────────────┐
└────┬─────┘                          │
     │                                │
     │ 解锁                           │ 手动锁定
     ▼                                │
┌──────────┐                         │
│READY/    │─────────────────────────┘
│INACTIVE   │
└──────────┘
     │
     │ 归档
     ▼
┌──────────┐
│ARCHIVED  │
└──────────┘
```

### 生命周期管理器

```python
class WorkspaceLifecycleManager:
    """工作区生命周期管理器"""
    
    def __init__(
        self,
        workspace_mgr: WorkspaceManager,
        process_mgr: ProcessManager,
        port_allocator: PortAllocator
    ):
        self.workspace_mgr = workspace_mgr
        self.process_mgr = process_mgr
        self.port_allocator = port_allocator
        self.health_checker = HealthChecker()
    
    async def create_workspace(
        self,
        project_id: str,
        project_path: str,
        name: str = None,
        config: Dict[str, Any] = None
    ) -> Workspace:
        """创建新工作区"""
        
        # 1. 生成工作区ID
        workspace_id = generate_uuid()
        
        # 2. 分配端口
        port_range = await self.port_allocator.allocate_range(workspace_id)
        
        # 3. 创建工作区对象
        workspace = Workspace(
            id=workspace_id,
            name=name or f"{project_id}-{datetime.now().strftime('%Y%m%d')}",
            project_id=project_id,
            project_path=project_path,
            workspace_path=os.path.expanduser(f"~/.sailzen/workspaces/{workspace_id}"),
            status=WorkspaceStatus.CREATED,
            ports=port_range.ports,
            main_port=port_range.start,
            resources=config.get("resources", {}),
            created_at=datetime.utcnow()
        )
        
        # 4. 设置文件系统
        await FileSystemIsolation().setup_workspace_fs(workspace)
        
        # 5. 保存到数据库
        await self.workspace_mgr.save(workspace)
        
        # 6. 更新状态
        await self._transition_state(workspace, WorkspaceStatus.INACTIVE)
        
        return workspace
    
    async def start_workspace(self, workspace_id: str) -> Workspace:
        """启动工作区"""
        workspace = await self.workspace_mgr.get(workspace_id)
        
        if workspace.status not in [WorkspaceStatus.INACTIVE, WorkspaceStatus.ERROR]:
            raise WorkspaceStateError(
                f"Cannot start workspace in {workspace.status} state"
            )
        
        # 1. 更新状态
        await self._transition_state(workspace, WorkspaceStatus.STARTING)
        
        try:
            # 2. 启动OpenCode进程
            opencode_process = await self.process_mgr.start_opencode(
                workspace=workspace,
                port=workspace.main_port,
                project_path=workspace.project_path
            )
            
            workspace.opencode_pid = opencode_process.pid
            
            # 3. 等待健康检查
            healthy = await self.health_checker.wait_for_healthy(
                workspace.main_port,
                timeout=60
            )
            
            if not healthy:
                raise WorkspaceStartError("OpenCode health check failed")
            
            # 4. 更新状态
            await self._transition_state(workspace, WorkspaceStatus.ACTIVE)
            workspace.started_at = datetime.utcnow()
            await self.workspace_mgr.save(workspace)
            
            # 5. 启动健康检查循环
            asyncio.create_task(self._health_check_loop(workspace))
            
            return workspace
            
        except Exception as e:
            await self._transition_state(workspace, WorkspaceStatus.ERROR)
            workspace.error_message = str(e)
            await self.workspace_mgr.save(workspace)
            raise
    
    async def stop_workspace(
        self,
        workspace_id: str,
        force: bool = False
    ):
        """停止工作区"""
        workspace = await self.workspace_mgr.get(workspace_id)
        
        if workspace.status != WorkspaceStatus.ACTIVE:
            return
        
        await self._transition_state(workspace, WorkspaceStatus.STOPPING)
        
        try:
            # 1. 停止OpenCode进程
            if workspace.opencode_pid:
                await self.process_mgr.stop_process(
                    workspace.opencode_pid,
                    force=force
                )
            
            # 2. 清理端口占用
            for port in workspace.ports:
                await self._kill_port_processes(port)
            
            # 3. 更新状态
            await self._transition_state(workspace, WorkspaceStatus.INACTIVE)
            workspace.stopped_at = datetime.utcnow()
            workspace.opencode_pid = None
            await self.workspace_mgr.save(workspace)
            
        except Exception as e:
            logger.error(f"Error stopping workspace {workspace_id}: {e}")
            raise
    
    async def archive_workspace(self, workspace_id: str):
        """归档工作区"""
        workspace = await self.workspace_mgr.get(workspace_id)
        
        # 1. 确保已停止
        if workspace.status == WorkspaceStatus.ACTIVE:
            await self.stop_workspace(workspace_id)
        
        # 2. 创建归档
        archive_path = await self._create_archive(workspace)
        
        # 3. 更新状态
        await self._transition_state(workspace, WorkspaceStatus.ARCHIVED)
        workspace.archive_path = archive_path
        await self.workspace_mgr.save(workspace)
        
        # 4. 清理资源
        await self._cleanup_resources(workspace)
    
    async def _health_check_loop(self, workspace: Workspace):
        """健康检查循环"""
        while workspace.status == WorkspaceStatus.ACTIVE:
            try:
                healthy = await self.health_checker.check(workspace.main_port)
                
                if not healthy:
                    # 健康检查失败，进入降级状态
                    await self._transition_state(workspace, WorkspaceStatus.DEGRADED)
                    
                    # 尝试恢复
                    recovered = await self._attempt_recovery(workspace)
                    
                    if recovered:
                        await self._transition_state(workspace, WorkspaceStatus.ACTIVE)
                    else:
                        # 恢复失败，停止工作区
                        await self.stop_workspace(str(workspace.id))
                        break
                
                await asyncio.sleep(30)  # 每30秒检查一次
                
            except Exception as e:
                logger.error(f"Health check error for workspace {workspace.id}: {e}")
                break
    
    async def _transition_state(
        self,
        workspace: Workspace,
        new_state: WorkspaceStatus
    ):
        """状态转换"""
        old_state = workspace.status
        workspace.status = new_state
        workspace.status_history.append({
            "from": old_state.value,
            "to": new_state.value,
            "timestamp": datetime.utcnow().isoformat()
        })
        
        logger.info(f"Workspace {workspace.id} state transition: {old_state} -> {new_state}")
```

---

## 资源调度

### 资源配额管理

```python
@dataclass
class ResourceQuota:
    """资源配额"""
    max_workspaces_per_user: int = 10
    max_concurrent_workspaces: int = 3
    
    memory_per_workspace_mb: int = 4096
    cpu_per_workspace: float = 2.0
    disk_per_workspace_gb: int = 50
    
    max_session_duration_hours: int = 8
    idle_timeout_minutes: int = 30


class ResourceScheduler:
    """资源调度器"""
    
    def __init__(self, quota: ResourceQuota):
        self.quota = quota
        self.active_workspaces: Dict[str, Workspace] = {}
        self.lock = asyncio.Lock()
    
    async def can_start_workspace(self, user_id: str) -> Tuple[bool, str]:
        """检查是否可以启动工作区"""
        
        async with self.lock:
            # 1. 检查并发限制
            user_active = [
                ws for ws in self.active_workspaces.values()
                if ws.user_id == user_id
            ]
            
            if len(user_active) >= self.quota.max_concurrent_workspaces:
                return False, f"已达到最大并发工作区数 ({self.quota.max_concurrent_workspaces})"
            
            # 2. 检查全局资源
            total_memory = sum(
                ws.resources.get("memory_limit_mb", 0)
                for ws in self.active_workspaces.values()
            )
            
            available_memory = get_total_memory() - total_memory
            if available_memory < self.quota.memory_per_workspace_mb:
                return False, "系统内存不足"
            
            return True, "OK"
    
    async def schedule_auto_cleanup(self):
        """调度自动清理"""
        
        while True:
            await asyncio.sleep(300)  # 每5分钟检查一次
            
            async with self.lock:
                now = datetime.utcnow()
                
                for workspace in list(self.active_workspaces.values()):
                    # 检查空闲超时
                    if workspace.last_activity_at:
                        idle_minutes = (now - workspace.last_activity_at).total_seconds() / 60
                        
                        if idle_minutes > self.quota.idle_timeout_minutes:
                            logger.info(
                                f"Workspace {workspace.id} idle for {idle_minutes} minutes, "
                                f"scheduling stop"
                            )
                            
                            # 发送通知
                            await self._send_idle_warning(workspace)
                            
                            # 延迟停止 (给用户5分钟响应时间)
                            asyncio.create_task(
                                self._delayed_stop(workspace.id, delay=300)
                            )
```

### 工作区选择器

```python
class WorkspaceSelector:
    """工作区选择器 - 帮助用户快速选择工作区"""
    
    async def suggest_workspace(
        self,
        user_id: str,
        context: Dict[str, Any]
    ) -> Optional[Workspace]:
        """根据上下文推荐工作区"""
        
        # 1. 获取用户活跃工作区
        workspaces = await self.workspace_mgr.list_user_workspaces(
            user_id,
            status=[WorkspaceStatus.ACTIVE, WorkspaceStatus.INACTIVE]
        )
        
        if not workspaces:
            return None
        
        # 2. 如果有活跃工作区，优先返回
        active = [ws for ws in workspaces if ws.status == WorkspaceStatus.ACTIVE]
        if len(active) == 1:
            return active[0]
        
        # 3. 根据最近使用排序
        workspaces.sort(key=lambda ws: ws.last_accessed_at or datetime.min, reverse=True)
        
        # 4. 根据项目匹配
        if "project" in context:
            for ws in workspaces:
                if ws.project_id == context["project"]:
                    return ws
        
        # 5. 返回最近使用的
        return workspaces[0] if workspaces else None
    
    async def quick_switch(
        self,
        user_id: str,
        identifier: str
    ) -> Workspace:
        """快速切换工作区"""
        
        # identifier可以是:
        # - 工作区ID
        # - 工作区名称
        # - 项目ID
        # - 项目路径的一部分
        
        # 1. 尝试精确匹配ID
        workspace = await self.workspace_mgr.get_by_id(identifier)
        if workspace and workspace.user_id == user_id:
            return await self._activate_and_return(workspace)
        
        # 2. 尝试匹配名称
        workspaces = await self.workspace_mgr.list_user_workspaces(user_id)
        
        for ws in workspaces:
            if ws.name.lower() == identifier.lower():
                return await self._activate_and_return(ws)
        
        # 3. 尝试匹配项目ID
        for ws in workspaces:
            if ws.project_id.lower() == identifier.lower():
                return await self._activate_and_return(ws)
        
        # 4. 模糊匹配
        matches = [
            ws for ws in workspaces
            if identifier.lower() in ws.name.lower()
            or identifier.lower() in ws.project_id.lower()
            or identifier.lower() in ws.project_path.lower()
        ]
        
        if len(matches) == 1:
            return await self._activate_and_return(matches[0])
        elif len(matches) > 1:
            raise AmbiguousWorkspaceError(
                f"找到多个匹配的工作区: {[ws.name for ws in matches]}"
            )
        
        raise WorkspaceNotFoundError(f"未找到工作区: {identifier}")
```

---

*文档版本: 1.0*
*最后更新: 2026-03-25*
