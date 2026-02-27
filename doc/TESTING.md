# 测试指南

## TypeScript 测试

### 运行测试

```bash
# 运行所有测试
pnpm test

# 运行特定包测试
pnpm test:common-all
pnpm test:common-server
pnpm test:unified

# 覆盖率测试
pnpm test:coverage
```

### 测试文件规范

- 测试文件: `*.test.ts`
- 位置: `src/__tests__/` 目录
- 命名: 与被测文件同名

## Python 测试

### 运行测试

```bash
# 运行所有测试
uv run pytest

# 运行特定标记的测试
uv run pytest -m "server"
uv run pytest -m "current"

# 跳过异步测试
uv run pytest -m "not asyncio"
```

### LLM 集成测试

```bash
# 测试 LLM 连接
uv run tests/llm_integration/run_validation.py connection --real-connection --providers google
```

## 功能测试指南

### 异步任务管理器测试

1. 启动服务
   ```bash
   uv run server.py          # 后端
   cd packages/site && pnpm dev  # 前端
   ```

2. 测试流程
   - 创建分析任务（作品分析页面）
   - 生成执行计划
   - Mock 模式执行任务
   - 查看并审核结果
   - 应用已批准的结果

### 物资管理测试

1. 创建住所（通过 API）
2. 初始化物资类别
3. 创建物资
4. 管理库存
5. 测试旅程管理

## API 测试示例

```bash
# 创建交易
curl -X POST http://localhost:8000/api/v1/finance/transaction/ \
  -H "Content-Type: application/json" \
  -d '{"from_acc_id": 1, "to_acc_id": -1, "value": "100"}'

# 获取任务进度
curl http://localhost:8000/api/v1/agent/tasks/1/progress
```
