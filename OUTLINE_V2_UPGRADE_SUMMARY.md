# 大纲提取 V2 升级总结

## 升级状态

✅ **升级完成，可以部署**

## 已完成的修改

### 1. 新增文件

| 文件 | 说明 | 状态 |
|------|------|------|
| `sail_server/service/outline_extraction_v2.py` | V2 核心数据结构（位置锚点、合并逻辑） | ✅ |
| `sail_server/service/outline_extractor_v2.py` | V2 提取服务（支持拆分-合并） | ✅ |
| `sail_server/model/analysis/outline_v2.py` | V2 数据库操作（两阶段保存） | ✅ |
| `doc/design/outline-extraction-parallel-merge.md` | 详细设计文档 | ✅ |
| `doc/dev/outline-extraction-v2-migration-guide.md` | 升级指南 | ✅ |
| `OUTLINE_V2_UPGRADE_QUICKSTART.md` | 快速参考 | ✅ |

### 2. 修改的文件

| 文件 | 修改内容 | 状态 |
|------|----------|------|
| `sail_server/controller/outline_extraction.py` | 添加 V1/V2 切换支持 | ✅ |
| `sail_server/service/outline_extractor.py` | 添加时间戳到标题和描述 | ✅ |

## 核心改进

### 1. 解决节点顺序问题

**V1 问题**: 父节点优先创建导致顺序错乱

**V2 解决方案**:
- 使用位置锚点（`chapter_index` + `in_chapter_order`）作为主要排序依据
- 两阶段保存：先创建所有节点，再建立父子关系

### 2. 增强标题和描述

**V1**:
- 标题: `自动提取 - main`
- 描述: `通过 LLM 自动提取的大纲，粒度：scene`

**V2**:
- 标题: `AI提取-主线-场景级 (2025-03-02 22:15)`
- 描述: `通过 LLM 自动提取的主线大纲 | 分析粒度：场景级 | 提取时间：2025-03-02 22:15:30 | 共 25 个节点`

### 3. 支持长文本拆分

V2 支持将长文本拆分为多个批次处理，然后合并结果，保持正确的节点顺序。

## 配置开关

在 `sail_server/controller/outline_extraction.py` 第 41 行：

```python
USE_V2_EXTRACTOR = True   # 启用 V2
USE_V2_EXTRACTOR = False  # 回退到 V1
```

## 部署步骤

### 1. 代码部署

确保所有新增和修改的文件已提交到代码库。

### 2. 配置检查

```python
# 确认 V2 已启用
USE_V2_EXTRACTOR = True
```

### 3. 重启服务

```bash
# 停止现有服务
# 启动新服务
uv run server.py
```

### 4. 验证

1. 检查启动日志：
   ```
   [OutlineExtraction] V2 extractor loaded successfully
   ```

2. 执行提取任务，检查任务日志：
   ```
   [Task xxx] Using V2 extractor
   ```

3. 保存后检查数据库：
   - 标题包含时间戳
   - 描述包含节点数量
   - 节点顺序与原文一致

## 回滚方案

如果出现问题，快速回滚：

1. 修改配置：`USE_V2_EXTRACTOR = False`
2. 重启服务

无需数据库迁移，V2 使用相同的表结构。

## 测试建议

### 基本测试

1. **单章提取**
   - 选择单章文本
   - 验证节点顺序正确

2. **多章提取**
   - 选择多章文本（超过 20 章触发批次划分）
   - 验证合并后顺序正确

3. **重复提取**
   - 同一文本提取多次
   - 验证标题有时间戳区分

### 验证要点

- [ ] 服务器启动无错误
- [ ] 任务创建成功
- [ ] 任务执行完成
- [ ] 保存结果成功
- [ ] 标题格式正确（含时间戳）
- [ ] 描述信息完整（含节点数）
- [ ] 节点顺序正确

## 已知限制

1. **串行处理**: 当前 V2 是串行处理多批次，非真正并行
2. **LLM 依赖**: 仍需要 LLM 提供位置锚点信息
3. **降级策略**: 如果 LLM 不提供位置锚点，使用批次索引估计

## 后续优化方向

1. **真正并行**: 使用 `asyncio.gather()` 并行处理批次
2. **缓存优化**: 添加批次结果缓存，支持断点续传
3. **冲突解决 UI**: 前端界面展示和解决合并冲突

## 联系与支持

- 设计文档: `doc/design/outline-extraction-parallel-merge.md`
- 升级指南: `doc/dev/outline-extraction-v2-migration-guide.md`
- 快速参考: `OUTLINE_V2_UPGRADE_QUICKSTART.md`

---

**升级完成时间**: 2025-03-02  
**版本**: V2.0  
**状态**: 可部署 ✅
