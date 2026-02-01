# LLM 闭环验证框架

## 概述

本框架用于在全面接入前端之前，对后端 `sail_server` 的 LLM 相关功能进行充分的调试和验证。

## 验证内容

1. **LLM 连接稳定性** (`validators/connection.py`)
   - 环境变量配置检查
   - LLM 客户端初始化
   - 真实连接测试（OpenAI、Anthropic、Google、Local）
   - 错误处理验证
   - 稳定性测试（多次调用）

2. **Prompt 模板功能** (`validators/prompt.py`)
   - 模板管理器初始化
   - 内置模板验证
   - 模板渲染功能
   - 变量替换
   - 输出 Schema 验证
   - 导出格式验证
   - 渲染性能测试

3. **Task 闭环流程** (`validators/task.py`)
   - 模块导入验证
   - 数据库连接验证
   - 任务执行器初始化
   - Prompt Only 模式完整闭环
   - LLM Direct 模式（可选）
   - 结果导入功能
   - 结果审核流程

## 使用方法

### 命令行运行

```bash
# 进入项目根目录
cd d:\ws\repos\SailZen

# 快速检查（不调用真实 LLM）
python tests/llm_integration/run_validation.py quick

# 验证 LLM 连接
python tests/llm_integration/run_validation.py connection --real-connection

# 验证 Prompt 模板
python tests/llm_integration/run_validation.py prompt

# 验证任务流程（最小模式，不需要数据库）
python tests/llm_integration/run_validation.py task --minimal

# 验证任务流程（完整模式，需要数据库）
python tests/llm_integration/run_validation.py task

# 运行所有验证
python tests/llm_integration/run_validation.py all

# 使用真实 LLM 测试
python tests/llm_integration/run_validation.py all --real-connection --real-llm --llm-provider google

# 导出报告
python tests/llm_integration/run_validation.py all -o report.json
python tests/llm_integration/run_validation.py all -o report.md --format markdown
```

### pytest 运行

```bash
# 运行所有 LLM 集成测试
pytest tests/llm_integration/ -v

# 运行特定测试
pytest tests/llm_integration/test_llm_connection.py -v
pytest tests/llm_integration/test_prompt_templates.py -v
pytest tests/llm_integration/test_task_flow.py -v

# 跳过需要真实 LLM 的测试
pytest tests/llm_integration/ -v -m "not real_llm"

# 运行需要数据库的测试
pytest tests/llm_integration/ -v --db
```

## 验证级别

- `SUCCESS` (✓): 验证通过
- `WARNING` (⚠): 功能可用但存在问题
- `ERROR` (✗): 功能不可用
- `SKIPPED` (○): 前置条件不满足，跳过

## 配置要求

### 环境变量

在 `.env.dev` 或 `.env.prod` 中配置：

```env
# OpenAI
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4

# Google Gemini
GOOGLE_API_KEY=...
GOOGLE_MODEL=gemini-2.0-flash

# Anthropic
ANTHROPIC_API_KEY=...
ANTHROPIC_MODEL=claude-3-opus-20240229
```

### 数据库

完整的任务流程验证需要数据库连接。确保 `POSTGRE_URI` 配置正确。

## 验证报告示例

```
============================================================
Validation Report: Full LLM Integration Validation
============================================================
Total: 25 | Success: 20 | Warning: 3 | Error: 0 | Skipped: 2
Total Duration: 5230ms
============================================================

Details:
  [✓] env_google: GOOGLE_API_KEY configured (15ms)
  [✓] client_init_google: google client initialized (23ms)
  [✓] connection_google: Connection successful (latency: 1250ms) (1285ms)
  [✓] template_outline_extraction_v1: Template '大纲提取 - 基础版' valid (2ms)
  ...

Overall Status: PASSED ✓
============================================================
```

## 开发扩展

### 添加新的验证器

1. 在 `validators/` 目录创建新文件
2. 继承 `BaseValidator` 类
3. 实现 `validate()` 方法
4. 在 `__init__.py` 中导出

示例：

```python
from .base import BaseValidator, ValidationReport

class MyValidator(BaseValidator):
    def __init__(self):
        super().__init__("My Validator")
    
    async def validate(self) -> ValidationReport:
        started_at = datetime.utcnow()
        
        # 执行验证
        self._success("my_check", "Check passed")
        
        return ValidationReport(
            validator_name=self.name,
            started_at=started_at,
            results=self.results,
        )
```

### 添加新的 pytest 测试

在 `test_*.py` 文件中添加新的测试类或方法：

```python
class TestMyFeature:
    @pytest.mark.asyncio
    async def test_something(self):
        # 测试代码
        pass
```

## 文件结构

```
tests/llm_integration/
├── __init__.py              # 包初始化
├── conftest.py              # pytest 配置和 fixtures
├── run_validation.py        # 命令行入口
├── README.md                # 本文档
├── validators/
│   ├── __init__.py
│   ├── base.py              # 验证器基类
│   ├── connection.py        # LLM 连接验证器
│   ├── prompt.py            # Prompt 模板验证器
│   └── task.py              # 任务流程验证器
├── test_llm_connection.py   # 连接测试用例
├── test_prompt_templates.py # Prompt 测试用例
└── test_task_flow.py        # 任务流程测试用例
```
