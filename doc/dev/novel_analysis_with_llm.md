# LLM 辅助小说分析功能需求文档
# Novel Analysis with LLM Integration - Feature Requirements

================================================================================
## 1. 概述 Overview
================================================================================

本文档详细描述 Phase 5 LLM 辅助分析功能的开发计划。目标是实现一个完整的异步工作流：
- 用户可通过前端发起 LLM 分析任务
- 后台异步执行任务（支持直接 LLM 调用或生成 Prompt 供外部工具使用）
- 实时监控任务状态
- 结果审核与应用

### 1.1 当前实现状态

已完成：
- [x] 数据库表结构（analysis_tasks, analysis_results）
- [x] ORM 模型（AnalysisTask, AnalysisResult）
- [x] DTO 数据类（AnalysisTaskData, AnalysisResultData）
- [x] 基础 API 控制器（AnalysisTaskController）
- [x] 任务创建、查询、取消 API
- [x] 结果审核流程 API

尚未实现：
- [ ] LLM 客户端封装
- [ ] 提示词模板管理系统
- [ ] 后台任务调度器
- [ ] 异步任务执行引擎
- [ ] 任务状态实时推送
- [ ] Prompt 导出功能
- [ ] 前端任务管理界面完善
- [ ] WebSocket/SSE 状态监控

================================================================================
## 2. 后端开发计划 Backend Development Plan
================================================================================

### 2.1 LLM 客户端封装

**文件**: `sail_server/utils/llm/client.py`

```python
# LLM 客户端抽象层
class LLMProvider(Enum):
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    LOCAL = "local"          # 本地 Ollama 等
    EXTERNAL = "external"    # 仅生成 Prompt，不调用

class LLMConfig:
    """LLM 配置"""
    provider: LLMProvider
    model: str              # gpt-4, claude-3, llama2, etc.
    api_key: Optional[str]
    api_base: Optional[str]  # 支持自定义 endpoint
    temperature: float = 0.3
    max_tokens: int = 4096
    timeout: int = 120       # 超时秒数

class LLMClient:
    """统一的 LLM 调用客户端"""
    
    def __init__(self, config: LLMConfig):
        self.config = config
        self._client = self._init_client()
    
    async def complete(self, prompt: str, system: Optional[str] = None) -> str:
        """基础文本补全"""
        pass
    
    async def complete_json(self, prompt: str, schema: Dict[str, Any]) -> Dict:
        """JSON 模式输出"""
        pass
    
    async def stream_complete(self, prompt: str) -> AsyncIterator[str]:
        """流式输出"""
        pass
    
    def estimate_tokens(self, text: str) -> int:
        """估算 token 数量"""
        pass
    
    def generate_prompt_only(self, prompt: str, system: Optional[str] = None) -> Dict:
        """仅生成 Prompt（不调用 LLM），返回可导出的格式"""
        return {
            "provider": self.config.provider.value,
            "model": self.config.model,
            "system": system,
            "prompt": prompt,
            "parameters": {
                "temperature": self.config.temperature,
                "max_tokens": self.config.max_tokens,
            },
            "export_format": {
                "openai": self._format_for_openai(system, prompt),
                "anthropic": self._format_for_anthropic(system, prompt),
                "plain": f"{system}\n\n{prompt}" if system else prompt,
            }
        }
```

**任务清单**:
- [ ] 实现 OpenAI 客户端适配器
- [ ] 实现 Anthropic 客户端适配器  
- [ ] 实现本地 LLM 客户端（Ollama）
- [ ] 实现 "仅生成 Prompt" 模式
- [ ] Token 估算功能
- [ ] 错误处理与重试机制
- [ ] 请求/响应日志记录

--------------------------------------------------------------------------------

### 2.2 提示词模板管理系统

**文件**: `sail_server/utils/llm/prompts.py`

```python
class PromptTemplate:
    """提示词模板"""
    id: str                     # 模板唯一标识
    name: str                   # 显示名称
    description: str            # 模板说明
    task_type: str              # 适用的任务类型
    version: str                # 版本号
    system_prompt: str          # 系统提示词
    user_prompt_template: str   # 用户提示词模板（支持变量替换）
    output_schema: Dict         # 期望的输出 JSON Schema
    example_input: Optional[str]
    example_output: Optional[str]

class PromptTemplateManager:
    """提示词模板管理器"""
    
    def __init__(self, templates_dir: str = "prompts/"):
        self.templates: Dict[str, PromptTemplate] = {}
        self._load_templates(templates_dir)
    
    def get_template(self, template_id: str) -> Optional[PromptTemplate]:
        """获取模板"""
        pass
    
    def list_templates(self, task_type: Optional[str] = None) -> List[PromptTemplate]:
        """列出模板"""
        pass
    
    def render(self, template_id: str, variables: Dict[str, Any]) -> RenderedPrompt:
        """渲染模板，替换变量"""
        pass
    
    def validate_output(self, template_id: str, output: Dict) -> ValidationResult:
        """验证输出是否符合 schema"""
        pass
```

**提示词模板目录结构**:
```
sail_server/prompts/
├── outline_extraction/
│   ├── v1_basic.yaml
│   ├── v2_detailed.yaml
│   └── v3_with_timeline.yaml
├── character_detection/
│   ├── v1_basic.yaml
│   └── v2_with_relations.yaml
├── setting_extraction/
│   ├── v1_items.yaml
│   ├── v1_locations.yaml
│   └── v1_organizations.yaml
└── relation_analysis/
    └── v1_character_relations.yaml
```

**模板文件格式 (YAML)**:
```yaml
id: outline_extraction_v2
name: "大纲提取 - 详细版"
description: "从章节内容中提取详细的情节大纲，包括情节点、事件类型、重要程度"
task_type: outline_extraction
version: "2.0"

system_prompt: |
  你是一位专业的文学分析师，擅长分析小说结构和情节发展。
  请严格按照要求的 JSON 格式输出分析结果。

user_prompt_template: |
  ## 任务：提取小说章节的情节大纲
  
  ### 背景信息
  - 作品名称：{{work_title}}
  - 章节范围：第 {{start_chapter}} 章至第 {{end_chapter}} 章
  - 已知人物：{{known_characters}}
  
  ### 章节内容
  {{chapter_contents}}
  
  ### 要求
  1. 识别主要情节点（plot points）
  2. 标注情节类型：conflict | revelation | climax | resolution | setup
  3. 评估每个情节点的重要程度：critical | major | normal | minor
  4. 识别涉及的人物
  5. 提取关键原文作为证据
  
  ### 输出格式
  请以 JSON 格式输出，符合以下结构：

output_schema:
  type: object
  properties:
    plot_points:
      type: array
      items:
        type: object
        properties:
          title:
            type: string
            description: "情节标题"
          type:
            type: string
            enum: ["conflict", "revelation", "climax", "resolution", "setup"]
          importance:
            type: string
            enum: ["critical", "major", "normal", "minor"]
          summary:
            type: string
            description: "简要描述（50-100字）"
          chapter_number:
            type: integer
          evidence:
            type: string
            description: "原文引用（50-200字）"
          characters:
            type: array
            items:
              type: string
        required: ["title", "type", "importance", "summary"]
    overall_summary:
      type: string
      description: "本段落的整体概述"
  required: ["plot_points", "overall_summary"]
```

**任务清单**:
- [ ] 实现 YAML 模板解析器
- [ ] 实现模板变量渲染引擎（Jinja2 风格）
- [ ] 实现 JSON Schema 验证
- [ ] 创建大纲提取模板（v1, v2）
- [ ] 创建人物识别模板
- [ ] 创建设定提取模板
- [ ] 创建关系分析模板
- [ ] 提供模板管理 API

--------------------------------------------------------------------------------

### 2.3 后台任务调度器

**文件**: `sail_server/model/analysis/task_scheduler.py`

```python
from enum import Enum
from dataclasses import dataclass
from typing import Optional, Dict, Any, List
from datetime import datetime
import asyncio

class TaskExecutionMode(Enum):
    """任务执行模式"""
    LLM_DIRECT = "llm_direct"       # 直接调用 LLM API
    PROMPT_ONLY = "prompt_only"     # 仅生成 Prompt
    MANUAL = "manual"               # 人工处理

@dataclass
class TaskExecutionPlan:
    """任务执行计划"""
    task_id: int
    mode: TaskExecutionMode
    chunks: List[Dict]              # 分块信息
    estimated_tokens: int           # 估算 token
    estimated_cost: float           # 估算费用
    prompt_template_id: str         # 使用的模板
    llm_config: Optional[Dict]      # LLM 配置

class AnalysisTaskScheduler:
    """分析任务调度器"""
    
    def __init__(self, db_session_factory, llm_config: LLMConfig):
        self.db_factory = db_session_factory
        self.llm_config = llm_config
        self.running_tasks: Dict[int, asyncio.Task] = {}
        self._shutdown = False
    
    async def create_execution_plan(
        self, 
        task_id: int, 
        mode: TaskExecutionMode
    ) -> TaskExecutionPlan:
        """创建任务执行计划（用于预览和确认）"""
        pass
    
    async def submit_task(self, task_id: int, mode: TaskExecutionMode) -> bool:
        """提交任务到执行队列"""
        pass
    
    async def cancel_task(self, task_id: int) -> bool:
        """取消正在执行的任务"""
        pass
    
    async def get_task_progress(self, task_id: int) -> Dict[str, Any]:
        """获取任务进度"""
        pass
    
    async def retry_task(self, task_id: int) -> bool:
        """重试失败的任务"""
        pass
    
    async def start_worker(self):
        """启动后台工作线程"""
        pass
    
    async def shutdown(self):
        """关闭调度器"""
        pass
```

**任务清单**:
- [ ] 实现任务执行计划生成
- [ ] 实现任务提交与队列管理
- [ ] 实现任务取消功能
- [ ] 实现进度追踪
- [ ] 实现重试机制
- [ ] 实现后台 Worker

--------------------------------------------------------------------------------

### 2.4 异步任务执行引擎

**文件**: `sail_server/model/analysis/task_runner.py`

```python
class AnalysisTaskRunner:
    """任务执行器"""
    
    def __init__(self, scheduler: AnalysisTaskScheduler):
        self.scheduler = scheduler
        self.llm_client: Optional[LLMClient] = None
        self.template_manager = PromptTemplateManager()
    
    async def run_task(self, task: AnalysisTaskData) -> TaskRunResult:
        """执行分析任务"""
        # 1. 加载任务配置
        # 2. 准备文本数据
        # 3. 分块处理
        # 4. 调用 LLM 或生成 Prompt
        # 5. 解析结果
        # 6. 保存到 analysis_results
        pass
    
    async def run_outline_extraction(self, task: AnalysisTaskData) -> Dict:
        """执行大纲提取"""
        pass
    
    async def run_character_detection(self, task: AnalysisTaskData) -> Dict:
        """执行人物识别"""
        pass
    
    async def run_setting_extraction(self, task: AnalysisTaskData) -> Dict:
        """执行设定提取"""
        pass
    
    async def run_relation_analysis(self, task: AnalysisTaskData) -> Dict:
        """执行关系分析"""
        pass
    
    def _prepare_chapter_content(
        self, 
        edition_id: int, 
        node_ids: List[int]
    ) -> List[ChapterChunk]:
        """准备章节内容，进行分块"""
        pass
    
    def _parse_llm_response(
        self, 
        response: str, 
        template_id: str
    ) -> ParsedResult:
        """解析 LLM 响应"""
        pass

class TaskProgress:
    """任务进度追踪"""
    task_id: int
    status: str
    current_step: str
    total_chunks: int
    completed_chunks: int
    current_chunk_info: Optional[str]
    started_at: datetime
    estimated_completion: Optional[datetime]
    error: Optional[str]
```

**任务清单**:
- [ ] 实现任务执行主流程
- [ ] 实现章节内容预处理与分块
- [ ] 实现各类型任务的执行逻辑
- [ ] 实现 LLM 响应解析
- [ ] 实现进度追踪与更新
- [ ] 错误处理与恢复

--------------------------------------------------------------------------------

### 2.5 任务状态实时推送

**文件**: `sail_server/router/analysis_ws.py`

```python
from litestar import WebSocket
from litestar.handlers import WebsocketListener

class TaskStatusWebSocket(WebsocketListener):
    """任务状态 WebSocket 端点"""
    path = "/ws/analysis/task/{task_id:int}"
    
    async def on_accept(self, socket: WebSocket, task_id: int):
        """连接建立"""
        # 验证任务存在
        # 订阅任务状态更新
        pass
    
    async def on_receive(self, data: str) -> str:
        """接收消息"""
        # 处理客户端命令（如：refresh, cancel）
        pass
    
    async def on_disconnect(self, socket: WebSocket):
        """连接断开"""
        # 取消订阅
        pass

# 备选方案：SSE (Server-Sent Events)
class TaskStatusSSE:
    """任务状态 SSE 端点"""
    
    @get("/sse/analysis/task/{task_id:int}")
    async def stream_task_status(self, task_id: int) -> Stream[bytes]:
        """SSE 流式推送任务状态"""
        pass
```

**状态消息格式**:
```json
{
    "type": "progress",
    "task_id": 123,
    "data": {
        "status": "running",
        "current_step": "processing_chunk",
        "progress": {
            "total_chunks": 10,
            "completed_chunks": 3,
            "current_chunk": "第5章-第8章"
        },
        "started_at": "2025-02-01T10:00:00Z",
        "estimated_remaining_seconds": 120
    }
}
```

**任务清单**:
- [ ] 实现 WebSocket 端点
- [ ] 实现 SSE 端点（备选）
- [ ] 实现状态发布/订阅机制
- [ ] 实现心跳检测
- [ ] 实现断线重连支持

--------------------------------------------------------------------------------

### 2.6 Prompt 导出功能

**文件**: `sail_server/model/analysis/prompt_export.py`

```python
class PromptExportFormat(Enum):
    """导出格式"""
    PLAIN_TEXT = "plain"       # 纯文本
    OPENAI_API = "openai"      # OpenAI API 格式
    ANTHROPIC_API = "anthropic" # Anthropic API 格式
    MARKDOWN = "markdown"      # Markdown 格式
    JSON = "json"              # JSON 结构

@dataclass
class ExportedPrompt:
    """导出的 Prompt"""
    task_id: int
    chunk_index: int
    total_chunks: int
    format: PromptExportFormat
    content: str
    metadata: Dict[str, Any]
    
class PromptExporter:
    """Prompt 导出器"""
    
    def export_task_prompts(
        self, 
        task_id: int, 
        format: PromptExportFormat
    ) -> List[ExportedPrompt]:
        """导出任务的所有 Prompt"""
        pass
    
    def export_single_chunk(
        self, 
        task_id: int, 
        chunk_index: int,
        format: PromptExportFormat
    ) -> ExportedPrompt:
        """导出单个分块的 Prompt"""
        pass
    
    def download_as_file(
        self, 
        prompts: List[ExportedPrompt],
        filename: str
    ) -> bytes:
        """打包为可下载文件"""
        pass
    
    def import_external_result(
        self, 
        task_id: int,
        chunk_index: int,
        result: str
    ) -> AnalysisResultData:
        """导入外部 LLM 的结果"""
        pass
```

**导出 API**:
```yaml
GET  /api/v1/analysis/task/{task_id}/prompts
     ?format=openai|anthropic|plain|markdown|json
     ?chunk=all|0|1|2...
     
POST /api/v1/analysis/task/{task_id}/import-result
     body: { chunk_index: 0, result: "..." }
```

**任务清单**:
- [ ] 实现多格式导出
- [ ] 实现批量下载（ZIP）
- [ ] 实现外部结果导入
- [ ] 实现导入结果验证
- [ ] 实现导入结果解析

================================================================================
## 3. 新增 API 端点 New API Endpoints
================================================================================

### 3.1 任务执行相关 API

```yaml
# 创建执行计划（预览）
POST /api/v1/analysis/task/{task_id}/plan
Request:
  mode: "llm_direct" | "prompt_only" | "manual"
Response:
  plan:
    task_id: int
    mode: string
    chunks: [{ index: int, chapter_range: string, token_estimate: int }]
    total_estimated_tokens: int
    estimated_cost_usd: float
    prompt_template_id: string
    
# 确认并开始执行任务
POST /api/v1/analysis/task/{task_id}/execute
Request:
  mode: "llm_direct" | "prompt_only"
  llm_config: { model: string, temperature: float, ... }  # optional
Response:
  success: bool
  message: string

# 获取任务实时进度
GET /api/v1/analysis/task/{task_id}/progress
Response:
  task_id: int
  status: string
  progress:
    current_step: string
    total_chunks: int
    completed_chunks: int
    current_chunk: string
  started_at: datetime
  estimated_remaining_seconds: int

# 暂停任务
POST /api/v1/analysis/task/{task_id}/pause
Response:
  success: bool

# 恢复任务
POST /api/v1/analysis/task/{task_id}/resume
Response:
  success: bool
```

### 3.2 Prompt 管理 API

```yaml
# 获取可用模板列表
GET /api/v1/analysis/prompts
Query:
  task_type: string (optional)
Response:
  templates: [{ id, name, description, task_type, version }]

# 获取模板详情
GET /api/v1/analysis/prompts/{template_id}
Response:
  template: PromptTemplate

# 预览渲染后的 Prompt
POST /api/v1/analysis/prompts/{template_id}/preview
Request:
  variables: { work_title: string, chapter_contents: string, ... }
Response:
  rendered_system: string
  rendered_user: string
  estimated_tokens: int
```

### 3.3 LLM 配置 API

```yaml
# 获取可用 LLM 提供商
GET /api/v1/analysis/llm/providers
Response:
  providers: [{ id, name, models: [{ id, name, context_length }] }]

# 测试 LLM 连接
POST /api/v1/analysis/llm/test
Request:
  provider: string
  api_key: string
  model: string
Response:
  success: bool
  message: string
  latency_ms: int

# 保存 LLM 配置（用户级）
POST /api/v1/analysis/llm/config
Request:
  provider: string
  api_key: string  # 将被加密存储
  default_model: string
  default_temperature: float
Response:
  success: bool
```

================================================================================
## 4. 前端开发计划 Frontend Development Plan
================================================================================

### 4.1 任务管理页面完善

**文件**: `packages/site/src/pages/analysis.tsx`

**新增功能**:
- [ ] 任务创建向导（选择类型、范围、模式）
- [ ] 任务列表（带状态筛选、分页）
- [ ] 任务详情面板
- [ ] 实时进度显示
- [ ] 结果审核界面

### 4.2 新增组件

**任务创建向导**:
`packages/site/src/components/analysis/task_create_wizard.tsx`
```typescript
interface TaskCreateWizardProps {
  editionId: number;
  onComplete: (task: AnalysisTask) => void;
  onCancel: () => void;
}

// 步骤:
// 1. 选择任务类型（大纲/人物/设定/关系）
// 2. 选择章节范围
// 3. 选择执行模式（LLM 直接调用 / 仅生成 Prompt）
// 4. 配置 LLM 参数（如果是直接调用模式）
// 5. 预览执行计划
// 6. 确认创建
```

**任务进度面板**:
`packages/site/src/components/analysis/task_progress_panel.tsx`
```typescript
interface TaskProgressPanelProps {
  taskId: number;
  onComplete: () => void;
  onError: (error: string) => void;
}

// 功能:
// - 实时显示任务进度
// - 显示当前处理的分块
// - 取消/暂停按钮
// - 错误信息显示
// - 完成后的摘要
```

**Prompt 导出对话框**:
`packages/site/src/components/analysis/prompt_export_dialog.tsx`
```typescript
interface PromptExportDialogProps {
  taskId: number;
  isOpen: boolean;
  onClose: () => void;
}

// 功能:
// - 选择导出格式
// - 预览 Prompt 内容
// - 下载单个/全部
// - 复制到剪贴板
```

**外部结果导入对话框**:
`packages/site/src/components/analysis/result_import_dialog.tsx`
```typescript
interface ResultImportDialogProps {
  taskId: number;
  chunkIndex: number;
  isOpen: boolean;
  onClose: () => void;
  onImport: (result: AnalysisResult) => void;
}

// 功能:
// - 粘贴外部 LLM 结果
// - 自动验证格式
// - 预览解析结果
// - 确认导入
```

**结果审核面板**:
`packages/site/src/components/analysis/result_review_panel.tsx`
```typescript
interface ResultReviewPanelProps {
  taskId: number;
  onApplyAll: () => void;
}

// 功能:
// - 逐条显示分析结果
// - 显示原文证据
// - 批准/拒绝/修改操作
// - 批量操作
// - 置信度过滤
```

### 4.3 状态管理

**文件**: `packages/site/src/lib/store/analysis.ts`

```typescript
import { create } from 'zustand';

interface AnalysisState {
  // 当前选中的版本
  currentEditionId: number | null;
  
  // 任务列表
  tasks: AnalysisTask[];
  tasksLoading: boolean;
  
  // 当前任务进度
  activeTaskId: number | null;
  taskProgress: TaskProgress | null;
  
  // WebSocket 连接状态
  wsConnected: boolean;
  
  // Actions
  fetchTasks: (editionId: number) => Promise<void>;
  createTask: (data: CreateTaskRequest) => Promise<AnalysisTask>;
  startTask: (taskId: number, mode: TaskExecutionMode) => Promise<void>;
  cancelTask: (taskId: number) => Promise<void>;
  subscribeToTask: (taskId: number) => void;
  unsubscribeFromTask: () => void;
}

export const useAnalysisStore = create<AnalysisState>((set, get) => ({
  // ... implementation
}));
```

### 4.4 API 客户端扩展

**文件**: `packages/site/src/lib/api/analysis.ts`

```typescript
// 新增 API 函数

// 任务执行
export async function createTaskPlan(
  taskId: number, 
  mode: TaskExecutionMode
): Promise<TaskExecutionPlan>

export async function executeTask(
  taskId: number, 
  mode: TaskExecutionMode,
  llmConfig?: LLMConfig
): Promise<void>

export async function getTaskProgress(taskId: number): Promise<TaskProgress>

export async function pauseTask(taskId: number): Promise<void>

export async function resumeTask(taskId: number): Promise<void>

// Prompt 管理
export async function getPromptTemplates(
  taskType?: string
): Promise<PromptTemplate[]>

export async function previewPrompt(
  templateId: string, 
  variables: Record<string, any>
): Promise<RenderedPrompt>

// Prompt 导出
export async function exportTaskPrompts(
  taskId: number, 
  format: ExportFormat
): Promise<ExportedPrompt[]>

export async function downloadPrompts(
  taskId: number, 
  format: ExportFormat
): Promise<Blob>

export async function importExternalResult(
  taskId: number, 
  chunkIndex: number, 
  result: string
): Promise<AnalysisResult>

// LLM 配置
export async function getLLMProviders(): Promise<LLMProvider[]>

export async function testLLMConnection(
  config: LLMConfig
): Promise<{ success: boolean; message: string }>

export async function saveLLMConfig(config: LLMConfig): Promise<void>
```

### 4.5 WebSocket 客户端

**文件**: `packages/site/src/lib/websocket/task_status.ts`

```typescript
class TaskStatusWebSocket {
  private ws: WebSocket | null = null;
  private taskId: number | null = null;
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 5;
  
  constructor(
    private onProgress: (progress: TaskProgress) => void,
    private onComplete: (result: TaskRunResult) => void,
    private onError: (error: string) => void,
    private onConnectionChange: (connected: boolean) => void
  ) {}
  
  connect(taskId: number): void {
    this.taskId = taskId;
    const wsUrl = `${getWsBaseUrl()}/ws/analysis/task/${taskId}`;
    this.ws = new WebSocket(wsUrl);
    
    this.ws.onopen = () => {
      this.reconnectAttempts = 0;
      this.onConnectionChange(true);
    };
    
    this.ws.onmessage = (event) => {
      const message = JSON.parse(event.data);
      this.handleMessage(message);
    };
    
    this.ws.onclose = () => {
      this.onConnectionChange(false);
      this.attemptReconnect();
    };
    
    this.ws.onerror = (error) => {
      this.onError('WebSocket connection error');
    };
  }
  
  disconnect(): void {
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
  }
  
  private handleMessage(message: WebSocketMessage): void {
    switch (message.type) {
      case 'progress':
        this.onProgress(message.data);
        break;
      case 'complete':
        this.onComplete(message.data);
        break;
      case 'error':
        this.onError(message.data.message);
        break;
    }
  }
  
  private attemptReconnect(): void {
    if (this.reconnectAttempts < this.maxReconnectAttempts && this.taskId) {
      this.reconnectAttempts++;
      setTimeout(() => {
        this.connect(this.taskId!);
      }, Math.min(1000 * Math.pow(2, this.reconnectAttempts), 30000));
    }
  }
}
```

================================================================================
## 5. 数据库扩展 Database Extensions
================================================================================

### 5.1 新增表

```sql
-- ============================================================================
-- LLM 配置表 (llm_configs)
-- ============================================================================
CREATE TABLE llm_configs (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR,                    -- 用户标识（可选）
    provider VARCHAR NOT NULL,          -- openai | anthropic | local
    api_key_encrypted TEXT,             -- 加密存储的 API Key
    default_model VARCHAR,
    default_temperature NUMERIC(3, 2) DEFAULT 0.3,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================================
-- 任务执行日志表 (task_execution_logs)
-- ============================================================================
CREATE TABLE task_execution_logs (
    id SERIAL PRIMARY KEY,
    task_id INTEGER NOT NULL REFERENCES analysis_tasks(id) ON DELETE CASCADE,
    log_type VARCHAR NOT NULL,          -- start | progress | chunk_complete | error | complete
    message TEXT,
    details JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_task_logs_task ON task_execution_logs(task_id);
CREATE INDEX idx_task_logs_created ON task_execution_logs(created_at);

-- ============================================================================
-- 导出的 Prompt 表 (exported_prompts)
-- ============================================================================
CREATE TABLE exported_prompts (
    id SERIAL PRIMARY KEY,
    task_id INTEGER NOT NULL REFERENCES analysis_tasks(id) ON DELETE CASCADE,
    chunk_index INTEGER NOT NULL,
    prompt_template_id VARCHAR NOT NULL,
    rendered_system TEXT,
    rendered_user TEXT,
    token_estimate INTEGER,
    external_result TEXT,               -- 存储从外部导入的结果
    external_result_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(task_id, chunk_index)
);

CREATE INDEX idx_exported_prompts_task ON exported_prompts(task_id);
```

### 5.2 扩展现有表

```sql
-- 扩展 analysis_tasks 表
ALTER TABLE analysis_tasks ADD COLUMN execution_mode VARCHAR DEFAULT 'llm_direct';
ALTER TABLE analysis_tasks ADD COLUMN total_chunks INTEGER;
ALTER TABLE analysis_tasks ADD COLUMN completed_chunks INTEGER DEFAULT 0;
ALTER TABLE analysis_tasks ADD COLUMN current_chunk_info VARCHAR;
ALTER TABLE analysis_tasks ADD COLUMN estimated_completion_at TIMESTAMP WITH TIME ZONE;
ALTER TABLE analysis_tasks ADD COLUMN paused_at TIMESTAMP WITH TIME ZONE;
ALTER TABLE analysis_tasks ADD COLUMN llm_config_id INTEGER REFERENCES llm_configs(id);
```

================================================================================
## 6. 文件清单 File Manifest
================================================================================

### 6.1 新增后端文件

```
sail_server/
├── utils/
│   └── llm/
│       ├── __init__.py
│       ├── client.py              # LLM 客户端封装
│       ├── providers/
│       │   ├── __init__.py
│       │   ├── openai.py          # OpenAI 适配器
│       │   ├── anthropic.py       # Anthropic 适配器
│       │   └── ollama.py          # Ollama 本地适配器
│       ├── prompts.py             # 提示词模板管理
│       └── token_counter.py       # Token 计数器
├── prompts/                       # 提示词模板目录
│   ├── outline_extraction/
│   │   └── v1.yaml
│   ├── character_detection/
│   │   └── v1.yaml
│   ├── setting_extraction/
│   │   └── v1.yaml
│   └── relation_analysis/
│       └── v1.yaml
├── model/
│   └── analysis/
│       ├── task_scheduler.py      # 任务调度器
│       ├── task_runner.py         # 任务执行器
│       └── prompt_export.py       # Prompt 导出
├── router/
│   └── analysis_ws.py             # WebSocket 路由
├── data/
│   └── llm_config.py              # LLM 配置 ORM
└── migration/
    └── add_llm_analysis_tables.sql # 数据库迁移
```

### 6.2 新增前端文件

```
packages/site/src/
├── components/
│   └── analysis/
│       ├── task_create_wizard.tsx     # 任务创建向导
│       ├── task_progress_panel.tsx    # 进度面板
│       ├── prompt_export_dialog.tsx   # Prompt 导出
│       ├── result_import_dialog.tsx   # 结果导入
│       ├── result_review_panel.tsx    # 结果审核
│       ├── llm_config_dialog.tsx      # LLM 配置
│       └── task_list.tsx              # 任务列表
├── lib/
│   ├── api/
│   │   └── analysis.ts                # 扩展 API 函数
│   ├── store/
│   │   └── analysis.ts                # 状态管理
│   ├── websocket/
│   │   └── task_status.ts             # WebSocket 客户端
│   └── data/
│       └── analysis.ts                # 扩展类型定义
└── pages/
    └── analysis.tsx                   # 更新页面
```

================================================================================
## 7. 开发优先级与里程碑 Development Priority & Milestones
================================================================================

### Phase 5.1: 基础 LLM 集成（核心功能）

**目标**: 实现最小可用的 LLM 分析工作流

- [ ] LLM 客户端基础封装（OpenAI）
- [ ] 提示词模板系统（YAML 解析）
- [ ] 1-2 个基础模板（大纲提取、人物识别）
- [ ] 任务执行器基础版本
- [ ] 任务进度 API
- [ ] 前端任务创建基础版

### Phase 5.2: Prompt 导出模式

**目标**: 支持不使用 API 的用户

- [ ] Prompt 导出功能
- [ ] 多格式支持
- [ ] 外部结果导入
- [ ] 导入验证与解析

### Phase 5.3: 实时状态推送

**目标**: 改善用户体验

- [ ] WebSocket 状态推送
- [ ] 前端实时进度显示
- [ ] 断线重连
- [ ] 任务暂停/恢复

### Phase 5.4: 完善与优化

**目标**: 生产就绪

- [ ] 多 LLM 提供商支持
- [ ] LLM 配置管理
- [ ] 完整模板库
- [ ] 批量任务处理
- [ ] 性能优化
- [ ] 错误处理完善
- [ ] 日志与监控

================================================================================
## 8. 技术要点与风险 Technical Notes & Risks
================================================================================

### 8.1 技术要点

1. **异步执行**: 使用 Python asyncio 实现非阻塞任务执行
2. **任务队列**: 可选使用 Redis + Celery 或简单的内存队列
3. **状态管理**: 使用数据库持久化任务状态，支持服务重启恢复
4. **Token 管理**: 自动分块处理长文本，避免超过上下文限制
5. **结果解析**: 使用 JSON Schema 验证 LLM 输出

### 8.2 风险与缓解

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| LLM API 调用成本高 | 用户成本负担 | 提供 token 估算、Prompt 导出模式 |
| LLM 输出不稳定 | 解析失败 | 使用 JSON mode、多次重试、人工审核 |
| 长任务执行超时 | 任务失败 | 分块处理、断点续传、进度保存 |
| WebSocket 连接不稳定 | 状态更新丢失 | SSE 备选、轮询兜底、断线重连 |
| API Key 安全 | 密钥泄露 | 加密存储、环境变量、不记录日志 |

================================================================================
## 9. 使用场景示例 Usage Scenarios
================================================================================

### 场景 1: 直接 LLM 调用

```
用户 → 选择"大纲提取"任务
     → 选择章节范围（第1-50章）
     → 选择"LLM 直接调用"模式
     → 配置 LLM（GPT-4, temperature=0.3）
     → 确认执行计划（10个分块，预计费用 $2.5）
     → 开始执行
     
系统 → 分块处理章节
     → 调用 LLM API
     → 实时推送进度
     → 解析结果保存到 analysis_results
     
用户 → 查看任务完成
     → 审核分析结果
     → 批准/修改/拒绝
     → 应用到主表
```

### 场景 2: Prompt 导出模式

```
用户 → 选择"人物识别"任务
     → 选择章节范围
     → 选择"仅生成 Prompt"模式
     → 导出 Prompt（选择 Markdown 格式）
     → 下载 prompts.zip
     
用户 → 在 ChatGPT/Claude 等工具中粘贴 Prompt
     → 获取分析结果
     
用户 → 返回系统
     → 导入外部结果
     → 系统验证并解析
     → 审核并应用
```

================================================================================
## 10. 测试计划 Testing Plan
================================================================================

### 10.1 单元测试

- [ ] LLM 客户端 Mock 测试
- [ ] 提示词模板渲染测试
- [ ] 结果解析测试
- [ ] 任务状态机测试

### 10.2 集成测试

- [ ] 完整任务执行流程测试
- [ ] WebSocket 连接测试
- [ ] Prompt 导出导入测试
- [ ] 多 LLM 提供商测试

### 10.3 端到端测试

- [ ] 前端任务创建到完成
- [ ] 结果审核流程
- [ ] 错误处理场景

================================================================================
END OF DOCUMENT
================================================================================
