# SailZen 文档中心

> **版本**: v2.0 | **更新**: 2026-03-01

---

## 📚 快速导航

### 核心文档

| 文档 | 说明 | 状态 |
|------|------|------|
| [PRD.md](./PRD.md) | 产品需求文档 (完整版) | ✅ v2.0 |
| [TESTING.md](./TESTING.md) | 测试指南与用例 | ✅ |
| [KNOWN_ISSUES.md](./KNOWN_ISSUES.md) | 已知问题与解决方案 | ✅ |
| [refact_todo.md](./refact_todo.md) | 代码重构计划 | 🔄 进行中 |

### 开发文档

| 文档 | 说明 |
|------|------|
| [dev/README.md](./dev/README.md) | 开发环境搭建与规范 |
| [dev/text-analysis-system-todo.md](./dev/text-analysis-system-todo.md) | 文本分析系统开发计划 |
| [environment_variables.md](./environment_variables.md) | 环境变量配置参考 |

### 架构设计

| 文档 | 说明 |
|------|------|
| [design/overview.md](./design/overview.md) | 系统架构总览 |
| [design/text-analysis-system.md](./design/text-analysis-system.md) | AI文本分析系统设计 |
| [design/outline-extraction.md](./design/outline-extraction.md) | 大纲提取功能设计 |
| [design/agent-system.md](./design/agent-system.md) | Agent系统设计 |

### API 文档

| 模块 | 文档 | 说明 |
|------|------|------|
| API 概览 | [api/README.md](./api/README.md) | API 文档入口与通用规范 |
| 财务管理 | [api/finance.md](./api/finance.md) | 账户、交易、预算 API |
| 健康管理 | [api/health.md](./api/health.md) | 体重、运动、计划 API |
| 文本管理 | [api/text.md](./api/text.md) | 作品、版本、章节 API |
| AI 分析 | [api/analysis.md](./api/analysis.md) | 大纲、人物、设定 API |
| 项目管理 | [api/project.md](./api/project.md) | 项目、任务 API |
| 物资管理 | [api/necessity.md](./api/necessity.md) | 库存、住所、行程 API |

### 业务模块设计

| 模块 | 文档 | 状态 |
|------|------|------|
| 财务管理 | [design/manager/life_budget.md](./design/manager/life_budget.md) | ✅ 已实现 |
| 项目管理 | [design/manager/project.md](./design/manager/project.md) | ✅ 已实现 |
| 健康管理 | [design/manager/health.md](./design/manager/health.md) | 🔶 部分实现 |
| 物资管理 | [design/manager/necessity.md](./design/manager/necessity.md) | ✅ 已实现 |
| 文本管理 | [design/manager/text.md](./design/manager/text.md) | ✅ 已实现 |

### 运维文档

| 文档 | 说明 |
|------|------|
| [maintain/Database.md](./maintain/Database.md) | 数据库维护指南 |
| [maintain/TestCase.md](./maintain/TestCase.md) | 测试用例维护 |

---

## 📁 文档结构

```
doc/
├── README.md                          # 本文档 - 文档中心入口
├── PRD.md                             # 产品需求文档 (完整版)
├── TESTING.md                         # 测试指南
├── KNOWN_ISSUES.md                    # 已知问题追踪
├── refact_todo.md                     # 代码重构计划
├── environment_variables.md           # 环境变量配置
│
├── api/                               # API 接口文档
│   ├── README.md                      # API 文档入口
│   ├── finance.md                     # 财务管理 API
│   ├── health.md                      # 健康管理 API
│   ├── text.md                        # 文本管理 API
│   ├── analysis.md                    # AI 分析 API
│   ├── project.md                     # 项目管理 API
│   └── necessity.md                   # 物资管理 API
│
├── design/                            # 架构设计文档
│   ├── overview.md                    # 系统架构总览
│   ├── text-analysis-system.md        # AI文本分析系统设计
│   ├── outline-extraction.md          # 大纲提取设计
│   ├── agent-system.md                # Agent系统设计
│   └── manager/                       # 业务模块设计
│       ├── README.md
│       ├── life_budget.md             # 财务管理
│       ├── project.md                 # 项目管理
│       ├── health.md                  # 健康管理
│       ├── necessity.md               # 物资管理
│       └── text.md                    # 文本管理
│
├── dev/                               # 开发文档
│   ├── README.md                      # 开发环境指南
│   ├── text-analysis-system-todo.md   # 文本分析开发计划
│   ├── phase2.2-2.3-acceptance-report.md
│   └── archived/                      # 归档文档
│
└── maintain/                          # 运维文档
    ├── Database.md
    └── TestCase.md
```

---

## 🎯 按角色导航

### 如果你是产品经理/设计师
1. 阅读 [PRD.md](./PRD.md) 了解完整产品需求
2. 查看 [design/overview.md](./design/overview.md) 了解系统架构
3. 参考各模块设计文档了解详细设计

### 如果你是后端开发者
1. 阅读 [dev/README.md](./dev/README.md) 搭建开发环境
2. 查看 [design/overview.md](./design/overview.md) 了解后端架构
3. 参考各模块 [API 文档](./api/) 了解接口规范
4. 查看 [TESTING.md](./TESTING.md) 了解测试规范
5. 参考 [refact_todo.md](./refact_todo.md) 了解重构计划

### 如果你是前端开发者
1. 阅读 [dev/README.md](./dev/README.md) 搭建开发环境
2. 查看 [PRD.md](./PRD.md) 了解功能需求
3. 参考各模块 [API 文档](./api/) 了解接口调用
4. 查看前端 API 客户端代码 `packages/site/src/lib/api/`
5. 参考各模块设计文档了解UI设计

### 如果你是测试工程师
1. 阅读 [TESTING.md](./TESTING.md) 了解测试框架
2. 查看 [maintain/TestCase.md](./maintain/TestCase.md) 了解测试用例
3. 参考 [KNOWN_ISSUES.md](./KNOWN_ISSUES.md) 了解已知问题

---

## 🔄 文档更新规范

### 更新频率
- **PRD.md**: 需求变更时立即更新
- **架构文档**: 架构调整时更新
- **开发文档**: 开发过程中持续更新
- **测试文档**: 新功能发布前更新

### 版本标记
文档头部应包含版本信息：
```markdown
> **版本**: v2.0 | **更新**: 2026-03-01 | **状态**: 已完成
```

状态标记：
- ✅ 已完成
- 🔄 进行中
- 📋 规划中
- ⏸️ 暂停

---

## 📝 贡献指南

如需更新文档：
1. 确保文档结构符合本规范
2. 更新版本信息和日期
3. 在变更记录中说明修改内容
4. 保持与其他文档的链接一致性

---

*本文档由 AI Agent 维护，如有疑问请参考 PRD.md 或联系开发团队。*
