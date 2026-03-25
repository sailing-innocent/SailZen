# Agent 类型定义与职责划分

## 目录

1. [Agent分类体系](#agent分类体系)
2. [核心Agent详解](#核心agent详解)
3. [Agent协作模式](#agent协作模式)
4. [Agent能力定义](#agent能力定义)

---

## Agent分类体系

### 整体架构

```
SailZen Multi-Agent System
│
├── 1️⃣ 开发类 Agents (Development)
│   ├── CodeAgent           # 代码生成与编辑
│   ├── ReviewAgent         # 代码审查
│   ├── TestAgent           # 测试执行
│   ├── RefactorAgent       # 代码重构
│   └── DebugAgent          # 调试分析
│
├── 2️⃣ 构建类 Agents (Build)
│   ├── BuildAgent          # 编译构建
│   ├── PackageAgent        # 打包发布
│   ├── DependencyAgent     # 依赖管理
│   └── LintAgent           # 代码检查
│
├── 3️⃣ 部署类 Agents (Deploy)
│   ├── DeployAgent         # 部署执行
│   ├── RollbackAgent       # 回滚操作
│   ├── ConfigAgent         # 配置管理
│   └── CanaryAgent         # 灰度发布
│
├── 4️⃣ 运维类 Agents (Operations)
│   ├── MonitorAgent        # 监控检查
│   ├── LogAgent            # 日志分析
│   ├── AlertAgent          # 告警处理
│   └── BackupAgent         # 备份管理
│
├── 5️⃣ 分析类 Agents (Analysis)
│   ├── AnalyzeAgent        # 代码分析
│   ├── DocAgent            # 文档生成
│   ├── MetricAgent         # 指标统计
│   └── SecurityAgent       # 安全扫描
│
├── 6️⃣ 交互类 Agents (Interaction)
│   ├── ChatAgent           # 对话交互
│   ├── IntentAgent         # 意图理解
│   ├── NotifyAgent         # 通知推送
│   └── CardAgent           # 卡片渲染
│
└── 7️⃣ 管理类 Agents (Management)
    ├── OrchestratorAgent   # 编排调度
    ├── WorkspaceAgent      # 工作区管理
    ├── StateAgent          # 状态管理
    └── RecoveryAgent       # 故障恢复
```

---

## 核心Agent详解

### 1. CodeAgent (代码开发Agent)

**职责范围：**
- 根据需求生成新代码
- 修改现有代码
- 实现函数/类/模块
- 编写测试用例

**能力定义：**

```python
class CodeAgent(BaseAgent):
    """代码开发Agent"""
    
    agent_type = "code"
    name = "代码开发助手"
    description = "专注于代码生成、修改和实现"
    
    capabilities = [
        "code_generation",
        "code_modification",
        "test_generation",
        "code_completion",
    ]
    
    supported_languages = [
        "python", "typescript", "javascript", 
        "java", "go", "rust", "cpp"
    ]
    
    tools = [
        "file_read",
        "file_write",
        "code_search",
        "ast_parser",
        "linter",
    ]
```

**输入参数：**

```json
{
  "task_type": "code_generation | code_modification | test_generation",
  "target_file": "文件路径",
  "language": "python",
  "requirement": "具体需求描述",
  "context": {
    "related_files": ["相关文件路径"],
    "existing_code": "已有代码片段",
    "constraints": ["约束条件"]
  },
  "style_guide": "遵循的代码规范",
  "test_framework": "pytest | jest | unittest"
}
```

**输出结果：**

```json
{
  "success": true,
  "generated_files": [
    {
      "path": "src/module.py",
      "content": "代码内容",
      "language": "python",
      "line_count": 100
    }
  ],
  "modified_files": [],
  "tests": [
    {
      "path": "tests/test_module.py",
      "test_cases": 5
    }
  ],
  "explanation": "实现说明",
  "confidence": 0.95
}
```

**工作流集成：**

```yaml
workflow:
  name: "feature-implementation"
  steps:
    - agent: "code_agent"
      action: "generate"
      input:
        requirement: "{{user_input}}"
        target_file: "{{project_structure.suggested_path}}"
      output:
        code: "generated_code"
        
    - agent: "review_agent"
      action: "review"
      input:
        code: "{{steps.code_agent.output.code}}"
      output:
        review_result: "review_report"
        
    - condition:
        if: "{{steps.review_agent.output.review_result.score}} > 80"
        then:
          - agent: "test_agent"
            action: "generate_tests"
            input:
              code: "{{steps.code_agent.output.code}}"
```

---

### 2. ReviewAgent (代码审查Agent)

**职责范围：**
- 代码质量审查
- 安全漏洞检测
- 性能问题识别
- 规范符合性检查
- 提供修改建议

**能力定义：**

```python
class ReviewAgent(BaseAgent):
    """代码审查Agent"""
    
    agent_type = "review"
    name = "代码审查助手"
    description = "专注于代码质量审查和改进建议"
    
    capabilities = [
        "code_review",
        "security_audit",
        "performance_analysis",
        "style_check",
        "best_practices",
    ]
    
    review_dimensions = [
        "correctness",      # 正确性
        "readability",      # 可读性
        "maintainability",  # 可维护性
        "performance",      # 性能
        "security",         # 安全性
        "testing",          # 测试覆盖
    ]
```

**输入参数：**

```json
{
  "task_type": "code_review | security_audit | performance_review",
  "files": [
    {
      "path": "src/module.py",
      "content": "代码内容",
      "language": "python"
    }
  ],
  "context": {
    "pr_description": "PR描述",
    "related_prs": [],
    "project_standards": "项目规范文件路径"
  },
  "review_depth": "quick | standard | thorough",
  "focus_areas": ["security", "performance"]
}
```

**输出结果：**

```json
{
  "success": true,
  "overall_score": 85,
  "summary": "总体评价",
  "issues": [
    {
      "severity": "critical | major | minor | info",
      "category": "security | performance | style | logic",
      "file": "src/module.py",
      "line": 42,
      "message": "问题描述",
      "suggestion": "修改建议",
      "code_snippet": "相关代码"
    }
  ],
  "strengths": ["优点1", "优点2"],
  "recommendations": ["建议1", "建议2"],
  "dimension_scores": {
    "correctness": 90,
    "readability": 85,
    "maintainability": 80,
    "performance": 75,
    "security": 95
  }
}
```

---

### 3. BuildAgent (构建Agent)

**职责范围：**
- 执行编译构建
- 管理构建缓存
- 处理构建依赖
- 收集构建产物

**能力定义：**

```python
class BuildAgent(BaseAgent):
    """构建Agent"""
    
    agent_type = "build"
    name = "构建助手"
    description = "专注于项目构建和编译"
    
    capabilities = [
        "compile",
        "bundle",
        "transpile",
        "cache_management",
    ]
    
    supported_build_tools = [
        "npm", "pnpm", "yarn",          # JavaScript
        "pip", "poetry", "uv",          # Python
        "maven", "gradle",              # Java
        "cargo",                         # Rust
        "make", "cmake",                 # C/C++
    ]
```

**输入参数：**

```json
{
  "task_type": "build | clean | rebuild",
  "project_path": "/path/to/project",
  "build_config": {
    "target": "production | development | test",
    "platform": "linux | windows | macos",
    "architecture": "x64 | arm64"
  },
  "cache_policy": "use | ignore | clean",
  "parallel_jobs": 4
}
```

**输出结果：**

```json
{
  "success": true,
  "build_time_seconds": 120,
  "artifacts": [
    {
      "name": "app.js",
      "path": "dist/app.js",
      "size_bytes": 1024000,
      "checksum": "sha256:xxx"
    }
  ],
  "warnings": [],
  "errors": [],
  "cache_hits": 45,
  "cache_misses": 12
}
```

---

### 4. TestAgent (测试Agent)

**职责范围：**
- 执行单元测试
- 执行集成测试
- 执行E2E测试
- 生成测试报告
- 分析测试覆盖

**能力定义：**

```python
class TestAgent(BaseAgent):
    """测试Agent"""
    
    agent_type = "test"
    name = "测试助手"
    description = "专注于测试执行和分析"
    
    capabilities = [
        "run_unit_tests",
        "run_integration_tests",
        "run_e2e_tests",
        "generate_coverage_report",
        "detect_flaky_tests",
    ]
    
    supported_frameworks = [
        "pytest", "unittest",            # Python
        "jest", "mocha", "vitest",       # JavaScript
        "junit", "testng",               # Java
        "cargo test",                     # Rust
    ]
```

**输入参数：**

```json
{
  "task_type": "unit | integration | e2e | all",
  "test_pattern": "tests/**/*.test.py",
  "selection": {
    "changed_only": true,
    "failed_first": true,
    "parallel": true
  },
  "coverage": {
    "enabled": true,
    "threshold": 80,
    "output_format": ["html", "json", "lcov"]
  },
  "timeout_seconds": 300
}
```

**输出结果：**

```json
{
  "success": true,
  "summary": {
    "total": 100,
    "passed": 95,
    "failed": 3,
    "skipped": 2,
    "duration_seconds": 120
  },
  "coverage": {
    "line_coverage": 85.5,
    "branch_coverage": 78.2,
    "function_coverage": 92.1
  },
  "failed_tests": [
    {
      "name": "test_function",
      "file": "tests/test_module.py",
      "line": 42,
      "error": "错误信息",
      "stack_trace": "堆栈信息"
    }
  ],
  "coverage_report_url": "/reports/coverage/index.html"
}
```

---

### 5. DeployAgent (部署Agent)

**职责范围：**
- 执行部署操作
- 管理部署环境
- 执行健康检查
- 处理部署回滚

**能力定义：**

```python
class DeployAgent(BaseAgent):
    """部署Agent"""
    
    agent_type = "deploy"
    name = "部署助手"
    description = "专注于应用部署和发布"
    
    capabilities = [
        "deploy_to_server",
        "deploy_to_kubernetes",
        "deploy_to_cloud",
        "blue_green_deploy",
        "canary_deploy",
        "rollback",
    ]
    
    supported_platforms = [
        "ssh", "docker", "kubernetes",
        "aws", "azure", "gcp", "aliyun"
    ]
```

**输入参数：**

```json
{
  "task_type": "deploy | rollback | verify",
  "environment": "staging | production | dev",
  "strategy": "rolling | blue_green | canary | all_at_once",
  "artifact": {
    "type": "docker_image | binary | zip",
    "location": "registry/image:tag"
  },
  "target": {
    "hosts": ["server1", "server2"],
    "kubernetes": {
      "namespace": "production",
      "deployment": "app"
    }
  },
  "health_check": {
    "enabled": true,
    "endpoint": "/health",
    "timeout_seconds": 60,
    "retry_count": 3
  }
}
```

**输出结果：**

```json
{
  "success": true,
  "deployment_id": "deploy-123456",
  "duration_seconds": 180,
  "steps": [
    {
      "name": "pull_image",
      "status": "success",
      "duration": 30
    },
    {
      "name": "deploy",
      "status": "success",
      "duration": 120
    },
    {
      "name": "health_check",
      "status": "success",
      "duration": 30
    }
  ],
  "health_check": {
    "passed": true,
    "response_time_ms": 50
  }
}
```

---

### 6. DocAgent (文档Agent)

**职责范围：**
- 生成API文档
- 更新变更日志
- 编写使用指南
- 维护README

**能力定义：**

```python
class DocAgent(BaseAgent):
    """文档Agent"""
    
    agent_type = "doc"
    name = "文档助手"
    description = "专注于技术文档生成和维护"
    
    capabilities = [
        "generate_api_doc",
        "update_changelog",
        "write_tutorial",
        "translate_document",
        "check_doc_coverage",
    ]
```

---

### 7. OrchestratorAgent (编排Agent)

**职责范围：**
- 工作流编排
- 任务调度
- 资源分配
- 异常处理

**能力定义：**

```python
class OrchestratorAgent(BaseAgent):
    """编排Agent - 工作流编排器"""
    
    agent_type = "orchestrator"
    name = "工作流编排器"
    description = "负责协调多个Agent完成复杂任务"
    
    capabilities = [
        "workflow_orchestration",
        "task_scheduling",
        "state_management",
        "error_handling",
        "checkpoint_management",
    ]
    
    async def execute_workflow(
        self,
        workflow: WorkflowDefinition,
        context: ExecutionContext
    ) -> WorkflowResult:
        """执行工作流"""
        # 1. 解析DAG
        # 2. 调度任务
        # 3. 监控执行
        # 4. 处理异常
        # 5. 保存状态
        pass
```

---

## Agent协作模式

### 模式1: 流水线协作

```
┌─────────┐    ┌─────────┐    ┌─────────┐    ┌─────────┐
│  Code   │───▶│ Review  │───▶│  Test   │───▶│ Deploy  │
│  Agent  │    │  Agent  │    │  Agent  │    │  Agent  │
└─────────┘    └─────────┘    └─────────┘    └─────────┘
     │              │              │              │
     │              │              │              │
     ▼              ▼              ▼              ▼
  代码生成      质量审查       测试验证       部署上线
```

**适用场景：** 标准化发布流程

---

### 模式2: 主从协作

```
                    ┌─────────────────┐
                    │  Orchestrator   │
                    │     Agent       │
                    └────────┬────────┘
                             │
            ┌────────────────┼────────────────┐
            │                │                │
            ▼                ▼                ▼
     ┌──────────┐     ┌──────────┐     ┌──────────┐
     │   Code   │     │  Review  │     │   Test   │
     │  Agent   │     │  Agent   │     │  Agent   │
     └────┬─────┘     └────┬─────┘     └────┬─────┘
          │                │                │
          └────────────────┼────────────────┘
                           │
                           ▼
                    ┌──────────┐
                    │  Result  │
                    │  Merge   │
                    └──────────┘
```

**适用场景：** 复杂任务分解与并行执行

---

### 模式3: 迭代协作

```
        ┌────────────────────────────────────┐
        │                                    │
        ▼                                    │
┌──────────────┐      ┌──────────────┐       │
│   Review     │─────▶│   Decision   │       │
│   Agent      │      │   Point      │       │
└──────────────┘      └──────┬───────┘       │
                             │                │
                    ┌────────┴────────┐       │
                    │                 │       │
              ┌─────▼─────┐     ┌─────▼─────┐ │
              │  Pass     │     │   Fail    │ │
              │ (>80)     │     │  (<60)    │ │
              └─────┬─────┘     └─────┬─────┘ │
                    │                 │       │
                    ▼                 ▼       │
              ┌───────────┐     ┌───────────┐ │
              │   Next    │     │   Code    │─┘
              │  Step     │     │   Agent   │
              └───────────┘     └───────────┘
```

**适用场景：** 需要多轮改进的任务

---

## Agent能力定义

### 能力注册格式

```python
@dataclass
class AgentCapability:
    """Agent能力定义"""
    name: str                          # 能力名称
    description: str                   # 能力描述
    input_schema: Dict[str, Any]       # 输入参数Schema
    output_schema: Dict[str, Any]      # 输出结果Schema
    required_tools: List[str]          # 必需工具
    estimated_duration: int            # 预估执行时间(秒)
    cost_estimate: CostEstimate        # 成本预估
```

### 能力示例

```python
CODE_GENERATION_CAPABILITY = AgentCapability(
    name="code_generation",
    description="根据需求生成代码",
    input_schema={
        "requirement": {"type": "string", "required": True},
        "language": {"type": "string", "required": True},
        "context": {"type": "object", "required": False}
    },
    output_schema={
        "success": {"type": "boolean"},
        "files": {"type": "array"},
        "explanation": {"type": "string"}
    },
    required_tools=["file_write", "code_search"],
    estimated_duration=60,
    cost_estimate=CostEstimate(
        estimated_tokens=2000,
        estimated_cost=0.02
    )
)
```

---

## Agent通信协议

### 消息格式

```json
{
  "message_id": "msg-uuid",
  "timestamp": "2026-03-25T10:00:00Z",
  "sender": "agent-type:agent-id",
  "receiver": "agent-type:agent-id",
  "message_type": "task_request | task_response | event | heartbeat",
  "payload": {
    // 具体消息内容
  },
  "metadata": {
    "workflow_id": "workflow-uuid",
    "session_id": "session-uuid",
    "priority": 5,
    "timeout_seconds": 300
  }
}
```

### 通信模式

| 模式 | 描述 | 适用场景 |
|------|------|----------|
| **Request/Response** | 同步调用，等待响应 | 需要立即结果的场景 |
| **Async Callback** | 异步调用，回调通知 | 长时间运行的任务 |
| **Event Pub/Sub** | 事件发布订阅 | 状态变更通知 |
| **Stream** | 流式传输 | 实时进度推送 |

---

*文档版本: 1.0*
*最后更新: 2026-03-25*
