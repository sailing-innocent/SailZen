# 超长篇网络文学小说创作系统

> **版本**: 1.0 Draft  
> **作者**: sailing-innocent  
> **日期**: 2026-04-15  
> **状态**: 设计阶段  
> **依赖**: [novel_analysis_system.md](./novel_analysis_system.md) | [SailZen 3.0 路线图](../sailzen-3.0-roadmap.md)

## 1. 系统愿景

构建一个**基于 Git 仓库 + Markdown 文件规范**的超长篇网络小说多 Agent 协作创作系统。

**核心理念**：

> **一部小说 = 一个 Git 仓库 = 一个多 Agent 协作工作区**

每部小说独占一个 GitHub 仓库，通过**文件目录规范**和**命名约定**让多个 AI Agent 在同一个工作区内协作，完成从灵感收集、世界观构建、大纲规划、章节草稿、审核润色到最终发布的全流程。

### 1.1 为什么是 Git + Markdown？

| 优势 | 说明 |
|------|------|
| **版本控制** | 每次修改都有历史记录，可回溯任意版本 |
| **分支协作** | 不同 Agent 在不同分支工作，通过 PR 合并 |
| **冲突检测** | Git 天然的冲突检测机制用于发现设定矛盾 |
| **透明可审计** | 所有修改有 commit message，人类可随时审查 |
| **Markdown 原生** | AI Agent 天然擅长读写 Markdown |
| **工具生态** | OpenCode、GitHub Actions、飞书 Webhook 等无缝集成 |
| **离线可用** | 本地 clone 即可离线阅读和编辑 |

### 1.2 设计原则

1. **文件即数据库**: 所有创作内容存储为 Markdown 文件，Git 仓库是唯一的 truth source
2. **约定优于配置**: 通过目录结构和文件命名规范，Agent 无需额外配置就能找到需要的内容
3. **Agent 独立工作**: 每个 Agent 有明确的职责边界，通过文件系统交互而非直接通信
4. **Human-in-the-Loop**: 人类通过 PR Review、飞书消息、Web UI 参与关键决策
5. **渐进式精炼**: 草稿 → 审核 → 润色 → 校对 → 定稿，每一步都有质量关卡

## 2. 小说仓库目录结构

```
novel-{slug}/                          # 仓库根目录，如 novel-mystic-lord
├── novel.yaml                         # 📋 小说元数据（核心配置文件）
├── README.md                          # 📖 小说简介 + 创作状态看板
│
├── world/                             # 🌍 世界观设定（知识库）
│   ├── _index.md                      # 世界观总览与分类导航
│   ├── power-system.md                # 力量体系
│   ├── geography.md                   # 地理设定
│   ├── history.md                     # 历史年表
│   ├── organizations/                 # 组织势力
│   │   ├── _index.md
│   │   └── {org-slug}.md
│   ├── races/                         # 种族设定
│   │   ├── _index.md
│   │   └── {race-slug}.md
│   └── rules.md                       # ⚠️ 硬性规则（不可违反的设定约束）
│
├── characters/                        # 👤 人物档案
│   ├── _index.md                      # 人物总览（含关系图谱链接）
│   ├── _relations.md                  # 人物关系网络
│   ├── main/                          # 主要角色
│   │   └── {char-slug}.md
│   ├── supporting/                    # 重要配角
│   │   └── {char-slug}.md
│   └── minor/                         # 次要角色
│       └── {char-slug}.md
│
├── outline/                           # 📝 大纲体系
│   ├── _index.md                      # 大纲总览
│   ├── premise.md                     # 核心前提与主题
│   ├── arcs/                          # 故事弧
│   │   ├── arc-001-{slug}.md          # 第一卷/弧
│   │   ├── arc-002-{slug}.md
│   │   └── ...
│   └── timeline.md                    # 故事时间线
│
├── volumes/                           # 📚 正文内容（按卷组织）
│   ├── vol-01-{slug}/                 # 第一卷
│   │   ├── _meta.md                   # 卷元数据（摘要、状态）
│   │   ├── ch-001.md                  # 第一章
│   │   ├── ch-002.md                  # 第二章
│   │   └── ...
│   ├── vol-02-{slug}/
│   │   └── ...
│   └── specials/                      # 特殊章节
│       ├── prologue.md                # 楔子
│       ├── epilogue.md                # 尾声
│       └── side-stories/              # 番外
│           └── {slug}.md
│
├── drafts/                            # ✏️ 草稿区（Agent 写入，人类审核）
│   ├── _queue.md                      # 草稿队列与状态追踪
│   ├── pending/                       # 待审核草稿
│   │   └── ch-{NNN}-draft-{ts}.md
│   ├── review/                        # 审核中
│   │   └── ch-{NNN}-review-{ts}.md
│   └── rejected/                      # 被驳回（需重写）
│       └── ch-{NNN}-rejected-{ts}.md
│
├── quality/                           # 🔍 质量控制
│   ├── consistency-report.md          # 一致性检查报告
│   ├── style-guide.md                 # 文风指南（含示例段落）
│   ├── checklist.md                   # 审核检查清单
│   └── issues/                        # 已知问题追踪
│       └── issue-{NNN}.md
│
├── inspiration/                       # 💡 灵感收集
│   ├── _inbox.md                      # 灵感收件箱（人类随时记录）
│   ├── ideas/                         # 已整理的创意
│   │   └── idea-{slug}.md
│   ├── references/                    # 参考资料
│   │   └── ref-{slug}.md
│   └── feedback/                      # 读者反馈
│       └── feedback-{date}.md
│
├── .agents/                           # 🤖 Agent 配置与技能
│   ├── config.yaml                    # Agent 全局配置
│   ├── skills/                        # OpenCode Skills
│   │   ├── draft-writer/              # 草稿撰写 Skill
│   │   ├── world-auditor/             # 世界观审核 Skill
│   │   ├── style-polisher/            # 文字润色 Skill
│   │   ├── continuity-checker/        # 连续性校对 Skill
│   │   ├── setting-updater/           # 设定更新 Skill
│   │   └── inspiration-collector/     # 灵感收集 Skill
│   └── prompts/                       # 共享 Prompt 模板
│       ├── system-base.md             # 基础系统提示
│       ├── character-voice.md         # 角色语音指南
│       └── style-reference.md         # 风格参考
│
├── .github/                           # ⚙️ GitHub 自动化
│   └── workflows/
│       ├── on-draft-push.yml          # 草稿推送触发审核
│       ├── on-pr-review.yml           # PR 合并触发后处理
│       ├── daily-consistency.yml      # 每日一致性检查
│       └── publish.yml                # 发布到阅读平台
│
└── .sailzen/                          # 🔧 SailZen 集成配置
    ├── pipeline.yaml                  # DAG Pipeline 定义
    ├── feishu.yaml                    # 飞书集成配置
    └── publish.yaml                   # 发布渠道配置
```

## 3. 文件命名与格式规范

### 3.1 核心配置文件 `novel.yaml`

```yaml
# novel.yaml - 小说元数据
novel:
  title: "诡秘之主"
  slug: "mystic-lord"
  author: "爱潜水的乌贼"
  genre: ["玄幻", "悬疑", "克苏鲁"]
  status: "ongoing"              # planning | ongoing | completed | hiatus
  target_word_count: 4500000     # 目标总字数
  current_word_count: 0          # 当前字数（自动统计）

  # 卷规划
  volumes:
    - id: "vol-01"
      slug: "rising-grey"
      title: "灰雾之上"
      target_chapters: 200
      status: "drafting"

  # 更新规划
  schedule:
    chapters_per_update: 5       # 每次更新章数
    target_words_per_chapter: 3000
    update_frequency: "daily"

# Agent 角色分配
agents:
  drafter:
    role: "draft-writer"
    description: "负责根据大纲生成章节草稿"
    llm_config:
      provider: "moonshot"
      model: "kimi-k2.5"
      temperature: 0.85
      max_tokens: 8000
  
  auditor:
    role: "world-auditor"
    description: "审核草稿与世界观设定的一致性"
    llm_config:
      provider: "moonshot"
      model: "kimi-k2.5"
      temperature: 0.3
      max_tokens: 4000
  
  polisher:
    role: "style-polisher"
    description: "润色文字，统一文风"
    llm_config:
      provider: "moonshot"
      model: "kimi-k2.5"
      temperature: 0.6
      max_tokens: 6000
  
  checker:
    role: "continuity-checker"
    description: "校对连续性和一致性"
    llm_config:
      provider: "moonshot"
      model: "kimi-k2.5"
      temperature: 0.2
      max_tokens: 4000
  
  updater:
    role: "setting-updater"
    description: "根据新章节更新世界观和人物档案"
    llm_config:
      provider: "moonshot"
      model: "kimi-k2.5"
      temperature: 0.4
      max_tokens: 4000

# SailZen 集成
sailzen:
  server_url: "https://sailzen.example.com"
  work_id: null                  # 关联的 SailZen Text Work ID
  edition_id: null               # 关联的 Edition ID
  feishu_webhook: null           # 飞书通知 Webhook
```

### 3.2 章节文件格式

```markdown
---
# ch-001.md frontmatter
chapter: 1
title: "灰雾之上"
volume: "vol-01"
status: "final"           # draft | review | polished | final
word_count: 3200
pov: "周明瑞"             # 视角角色
location: "廷根市"
timeline: "1349-7-18"     # 故事内时间
created_at: "2026-04-15"
drafted_by: "agent:drafter"
reviewed_by: "human:sailing"
polished_by: "agent:polisher"
tags: ["序章", "穿越", "觉醒"]
---

# 第一章 灰雾之上

克莱恩·莫雷蒂猛地从噩梦中醒来...

<!-- 正文内容 -->
```

### 3.3 人物档案格式

```markdown
---
# characters/main/zhou-mingrui.md
char_id: "zhou-mingrui"
name: "周明瑞"
aliases: ["克莱恩·莫雷蒂", "愚者", "小丑"]
role: "protagonist"
first_appearance: "ch-001"
status: "alive"
last_updated: "2026-04-15"
updated_by: "agent:updater"
---

# 周明瑞 / 克莱恩·莫雷蒂

## 基本信息
- **年龄**: 22岁（穿越时）
- **身份**: 大学历史系毕业生 → 序列9占卜家 → ...
- **性格**: 谨慎、善于伪装、内心善良

## 能力演变
| 章节范围 | 序列 | 核心能力 | 备注 |
|----------|------|----------|------|
| ch-001~050 | 序列9·占卜家 | 灵摆占卜、冥想 | 初始阶段 |

## 重要关系
- **邓恩队长** → 上司（第五纪小队）
- **奥黛丽** → 塔罗会成员（正义小姐）

## Agent 备注
> ⚠️ 从 ch-150 开始，周明瑞的身份伪装层次增加，
> 撰写时注意内心独白与外在表现的反差。
```

### 3.4 世界观设定格式

```markdown
---
# world/power-system.md
setting_id: "power-system"
category: "core"
confidence: "canonical"     # canonical | semi-canon | speculative
last_verified: "ch-200"     # 最后验证到的章节
last_updated: "2026-04-15"
updated_by: "agent:updater"
---

# 力量体系：序列途径

## 硬性规则 ⛔
<!-- 这些规则不可违反，Agent 在创作时必须检查 -->
1. 每条途径有10个序列，从序列9到序列0
2. 序列越低越强大，但也越危险
3. 相邻途径可以互换（有副作用）
4. 同一序列的魔药不能重复服用

## 途径列表
| 途径 | 序列9 | 序列0 | 对应柱 |
|------|-------|-------|--------|
| 愚者 | 占卜家 | 愚者 | 原初之主 |

## 已确认的设定变更记录
| 章节 | 变更内容 | 原因 |
|------|----------|------|
| ch-150 | 新增"猎人"途径细节 | 情节需要 |
```

## 4. 多 Agent 协作体系

### 4.1 Agent 角色总览

系统定义 **6 个专职 Agent**，每个有明确的职责边界和工作区域：

```
┌─────────────────────────────────────────────────────────────┐
│                    Novel Creation Workspace                  │
│                                                             │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐                 │
│  │ 📝 Draft │  │ 🔍 Audit │  │ ✨ Polish│                 │
│  │  Writer  │→→│  or      │→→│  er      │                 │
│  │          │  │          │  │          │                 │
│  └──────────┘  └──────────┘  └──────────┘                 │
│       ↑              ↓              ↓                       │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐                 │
│  │ 💡Inspir-│  │ 📋Contin-│  │ 🔄Setting│                 │
│  │  ation   │  │  uity    │  │  Updater │                 │
│  │ Collector│  │  Checker │  │          │                 │
│  └──────────┘  └──────────┘  └──────────┘                 │
│                                                             │
│              👤 Human (PR Review / Feishu / Web)            │
└─────────────────────────────────────────────────────────────┘
```

| Agent | 职责 | 读取区域 | 写入区域 | 触发时机 |
|-------|------|----------|----------|----------|
| **Draft Writer** | 根据大纲生成章节草稿 | `outline/`, `world/`, `characters/`, `volumes/`(前文) | `drafts/pending/` | 收到"更新N章"任务 |
| **World Auditor** | 审核草稿与世界观一致性 | `world/rules.md`, `characters/`, `drafts/pending/` | `drafts/review/`, `quality/issues/` | 草稿进入 pending |
| **Style Polisher** | 润色文字、统一文风 | `quality/style-guide.md`, `drafts/review/` | `drafts/review/`(原地更新) | 审核通过后 |
| **Continuity Checker** | 校对前后文连续性 | `volumes/`(已发布章节), `drafts/review/` | `quality/issues/`, `quality/consistency-report.md` | 润色完成后 |
| **Setting Updater** | 根据定稿更新设定 | `volumes/`(新章节), `world/`, `characters/` | `world/`, `characters/` | 章节定稿合入 |
| **Inspiration Collector** | 整理灵感、读者反馈 | `inspiration/_inbox.md`, `inspiration/feedback/` | `inspiration/ideas/`, `outline/` | 定时/人工触发 |

### 4.2 章节创作流水线（核心工作流）

一个章节从无到有的完整生命周期：

```
                          ┌─────────────┐
                          │  任务触发    │
                          │ "更新5章"   │
                          └──────┬──────┘
                                 │
                    ┌────────────▼────────────┐
                    │  Step 1: Draft Writer    │
                    │  读取大纲+设定+前文      │
                    │  生成草稿到 drafts/pending│
                    │  分支: draft/ch-201-205  │
                    └────────────┬────────────┘
                                 │ git push
                    ┌────────────▼────────────┐
                    │  Step 2: World Auditor   │
                    │  逐章检查硬性规则        │
                    │  标注冲突位置            │
                    │  输出: 审核报告          │
                    └──────┬─────────┬────────┘
                           │         │
                    ┌──────▼──┐  ┌───▼────────┐
                    │ 通过 ✅  │  │ 驳回 ❌     │
                    │ 移入     │  │ 标注问题    │
                    │ review/  │  │ 回到 Step 1 │
                    └──────┬──┘  └────────────┘
                           │
                    ┌──────▼──────────────────┐
                    │  Step 3: Style Polisher   │
                    │  润色文字、调整节奏       │
                    │  保持角色语气一致         │
                    └────────────┬─────────────┘
                                 │
                    ┌────────────▼────────────┐
                    │  Step 4: Continuity Check │
                    │  前后文逻辑校验           │
                    │  时间线/地理一致性        │
                    └──────┬─────────┬────────┘
                           │         │
                    ┌──────▼──┐  ┌───▼────────┐
                    │ 通过 ✅  │  │ 发现问题 ⚠️ │
                    │         │  │ 生成 issue  │
                    └──────┬──┘  └────────────┘
                           │
                    ┌──────▼──────────────────┐
                    │  Step 5: Human Review     │
                    │  PR Review / 飞书卡片     │
                    │  人类最终审批             │
                    └──────┬─────────┬────────┘
                           │         │
                    ┌──────▼──┐  ┌───▼────────┐
                    │ 合入 ✅  │  │ 修改意见 📝 │
                    │ main    │  │ 回到 Step 3 │
                    └──────┬──┘  └────────────┘
                           │
              ┌────────────▼────────────┐
              │  Step 6: Post-Merge      │
              │  Setting Updater 更新设定│
              │  同步到 SailZen DB       │
              │  推送到发布平台          │
              └─────────────────────────┘
```

### 4.3 Git 分支策略

```
main                    ← 定稿内容，只通过 PR 合入
├── draft/ch-201-205    ← Draft Writer 工作分支
├── draft/ch-206-210    ← 并行的另一批草稿
├── review/ch-201-205   ← 审核润色分支
├── setting/sync-ch-205 ← Setting Updater 同步分支
└── idea/new-arc-3      ← 灵感/新弧线草案
```

**分支命名约定**:
- `draft/{scope}` - 草稿创作分支
- `review/{scope}` - 审核润色分支  
- `setting/{scope}` - 设定同步分支
- `idea/{slug}` - 灵感/实验分支
- `fix/{issue-id}` - 问题修复分支

**Commit Message 规范**:
```
<type>(<scope>): <description>

类型:
  draft:    草稿生成     draft(ch-201): 初稿完成
  audit:    审核结果     audit(ch-201): 世界观检查通过
  polish:   润色修改     polish(ch-201): 语言润色完成
  check:    校对结果     check(ch-201): 连续性检查通过
  sync:     设定同步     sync(characters): 更新周明瑞能力到序列7
  idea:     灵感记录     idea(arc-3): 新增第三卷构想
  fix:      问题修复     fix(issue-012): 修复时间线矛盾
  meta:     元数据       meta(novel.yaml): 更新字数统计
```

### 4.4 冲突解决与质量保障

**世界观冲突检测**（World Auditor 的核心算法）:

```python
# 伪代码: 世界观审核流程
async def audit_chapter(chapter_content: str, world_rules: list[Rule]) -> AuditReport:
    """
    1. 提取章节中涉及的实体和事件
    2. 逐条比对 world/rules.md 中的硬性规则
    3. 查找 characters/ 中相关人物的状态是否一致
    4. 检查 outline/timeline.md 的时间线顺序
    """
    # Step 1: 实体提取
    entities = await llm_extract_entities(chapter_content)
    
    # Step 2: 规则匹配
    violations = []
    for entity in entities:
        for rule in world_rules:
            if rule.applies_to(entity):
                check = await llm_check_rule(entity, rule, chapter_content)
                if not check.passed:
                    violations.append(Violation(
                        rule=rule,
                        entity=entity,
                        location=check.location,
                        severity=check.severity,  # error | warning | info
                        suggestion=check.suggestion
                    ))
    
    # Step 3: 人物状态一致性
    character_issues = await check_character_consistency(
        chapter_content, entities.characters
    )
    
    # Step 4: 时间线校验
    timeline_issues = await check_timeline(
        chapter_content, entities.events
    )
    
    return AuditReport(
        chapter=chapter_id,
        verdict="PASS" if not violations else "FAIL",
        violations=violations,
        character_issues=character_issues,
        timeline_issues=timeline_issues
    )
```

**质量评分维度**:

| 维度 | 权重 | 检查内容 |
|------|------|----------|
| 世界观一致性 | 30% | 硬性规则、设定矛盾 |
| 人物一致性 | 25% | 性格、能力、关系 |
| 情节连贯性 | 20% | 前后文逻辑、伏笔 |
| 文风一致性 | 15% | 语言风格、叙事节奏 |
| 时间线准确性 | 10% | 日期、顺序、间隔 |

## 5. OpenCode Skill 设计

每个 Agent 对应一个 OpenCode Skill，安装在小说仓库的 `.agents/skills/` 目录中。
Skill 通过 SailZen 的 Edge Runtime 调度执行。

### 5.1 Skill 总览

```
.agents/skills/
├── draft-writer/
│   ├── skill.md              # Skill 定义（指令文档）
│   ├── scripts/
│   │   ├── generate_draft.py # 草稿生成脚本
│   │   └── context_builder.py# 上下文构建器
│   └── prompts/
│       ├── draft_system.md   # 系统提示词
│       └── draft_template.md # 章节模板
│
├── world-auditor/
│   ├── skill.md
│   ├── scripts/
│   │   ├── audit_chapter.py  # 审核脚本
│   │   └── rule_parser.py    # 规则解析器
│   └── prompts/
│       └── audit_system.md
│
├── style-polisher/
│   ├── skill.md
│   ├── scripts/
│   │   ├── polish_chapter.py
│   │   └── style_analyzer.py
│   └── prompts/
│       └── polish_system.md
│
├── continuity-checker/
│   ├── skill.md
│   ├── scripts/
│   │   ├── check_continuity.py
│   │   └── timeline_validator.py
│   └── prompts/
│       └── check_system.md
│
├── setting-updater/
│   ├── skill.md
│   ├── scripts/
│   │   ├── update_characters.py
│   │   ├── update_world.py
│   │   └── diff_analyzer.py
│   └── prompts/
│       └── update_system.md
│
└── inspiration-collector/
    ├── skill.md
    ├── scripts/
    │   ├── process_inbox.py
    │   └── organize_ideas.py
    └── prompts/
        └── collect_system.md
```

### 5.2 Draft Writer Skill 详细设计

```markdown
# .agents/skills/draft-writer/skill.md

---
name: novel-draft-writer
version: 1.0.0
description: 根据大纲和设定生成小说章节草稿
author: sailzen
tags: [novel, creation, draft]
---

## 触发条件

当收到以下形式的指令时激活：
- "写第 N 章"
- "更新 N 章"  
- "续写从第 N 章开始的 M 章"

## 执行流程

### Step 1: 解析任务参数
从指令中提取:
- start_chapter: 起始章节号
- count: 需要生成的章节数
- special_instructions: 特殊要求（可选）

### Step 2: 构建上下文
读取以下文件构建创作上下文:

1. **大纲**: `outline/arcs/arc-{current}.md`
   - 提取当前章节对应的情节节点
   - 获取关键事件和转折点

2. **前文摘要**: 最近 5 章的正文
   - `volumes/vol-{N}/ch-{N-4}.md` ~ `ch-{N}.md`
   - 提取核心情节走向

3. **人物状态**: 本章涉及的角色档案
   - `characters/main/*.md` + `characters/supporting/*.md`
   - 获取当前能力、关系、情绪状态

4. **世界观约束**: `world/rules.md`
   - 加载所有硬性规则到上下文

5. **文风参考**: `quality/style-guide.md`
   - 加载语言风格要求

### Step 3: 逐章生成
对每一章:
1. 构建章节专属 prompt（含大纲节点 + 前文衔接 + 角色状态）
2. 调用 LLM 生成草稿
3. 自动填充 frontmatter 元数据
4. 保存到 `drafts/pending/ch-{NNN}-draft-{timestamp}.md`

### Step 4: 提交与通知
1. `git add drafts/pending/`
2. `git commit -m "draft(ch-{start}~{end}): 初稿完成"`
3. `git push origin draft/ch-{start}-{end}`
4. 更新 `drafts/_queue.md` 状态
```

### 5.3 World Auditor Skill 详细设计

```markdown
# .agents/skills/world-auditor/skill.md

---
name: novel-world-auditor
version: 1.0.0
description: 审核草稿与世界观设定的一致性
---

## 触发条件
- 草稿推送到 `drafts/pending/` 后自动触发
- 或手动: "审核第 N 章"

## 执行流程

### Step 1: 加载审核上下文
1. 读取 `world/rules.md` → 提取所有硬性规则
2. 读取待审核章节 `drafts/pending/ch-{NNN}-draft-*.md`
3. 读取相关人物档案 (从 frontmatter.pov 关联)

### Step 2: 规则逐条审核
对每条硬性规则:
1. 判断该规则是否与本章内容相关
2. 如果相关，用 LLM 检查是否违反
3. 输出: PASS / WARN(可能违反) / FAIL(明确违反)

### Step 3: 人物一致性检查
- 角色行为是否符合其性格设定
- 角色能力是否在当前阶段范围内
- 角色关系是否与档案一致

### Step 4: 输出审核报告
```yaml
# 审核报告示例
chapter: ch-203
auditor: agent:world-auditor
timestamp: 2026-04-15T10:30:00
verdict: WARN  # PASS | WARN | FAIL

violations:
  - rule: "序列9不能使用序列7的能力"
    severity: error
    location: "第3段第2句"
    quote: "克莱恩使用了纸人替身..."
    suggestion: "此时克莱恩尚未晋升序列7，建议改为使用占卜能力"

warnings:
  - type: "character_voice"
    character: "周明瑞"
    note: "第5段对话风格偏离，语气过于直接，不符合角色谨慎性格"

passed_checks:
  - "力量体系规则一致性: ✅"
  - "地理设定准确性: ✅"
  - "时间线连贯性: ✅"
```

### Step 5: 路由决策
- **全部 PASS**: 移入 `drafts/review/`, 通知 Style Polisher
- **有 WARN**: 移入 `drafts/review/`, 附带 warning 标记
- **有 FAIL**: 移入 `drafts/rejected/`, 通知 Draft Writer 重写
```

### 5.4 Setting Updater Skill 详细设计

```markdown
# .agents/skills/setting-updater/skill.md

---
name: novel-setting-updater
version: 1.0.0
description: 根据新定稿章节自动更新世界观和人物档案
---

## 触发条件
- PR 合入 main 分支后的 post-merge hook
- 或手动: "同步设定到第 N 章"

## 执行流程

### Step 1: Diff 分析
1. 获取本次合入的新章节列表
2. 分析每章引入的新实体:
   - 新角色出场
   - 已有角色状态变化（能力提升、关系变化、死亡等）
   - 新地点/组织/物品
   - 新设定/规则揭示

### Step 2: 人物档案更新
对每个涉及的角色:
1. 读取现有档案 `characters/{tier}/{slug}.md`
2. 生成更新 diff:
   - 追加能力演变记录
   - 更新关系变化
   - 添加 Agent 备注
3. 如果是新角色 → 创建新档案文件

### Step 3: 世界观更新
1. 检查是否有新设定揭示
2. 更新对应的 `world/*.md` 文件
3. 更新 `last_verified` 字段
4. 如果是设定变更 → 添加到变更记录表

### Step 4: 提交
1. `git checkout -b setting/sync-ch-{NNN}`
2. 提交所有更新文件
3. 创建 PR → 自动合入（或等待人工确认）
```

## 6. 多渠道触发与集成

### 6.1 触发渠道总览

```
┌─────────────────────────────────────────────────────────┐
│                    触发渠道 (Triggers)                    │
│                                                         │
│  ┌─────────┐  ┌────────────┐  ┌─────────┐  ┌────────┐ │
│  │  飞书    │  │  SailSite  │  │  CLI    │  │ GitHub │ │
│  │  Bot     │  │  Web UI    │  │  命令行  │  │ Action │ │
│  └────┬────┘  └─────┬──────┘  └────┬────┘  └───┬────┘ │
│       │             │              │            │      │
└───────┼─────────────┼──────────────┼────────────┼──────┘
        │             │              │            │
        ▼             ▼              ▼            ▼
┌─────────────────────────────────────────────────────────┐
│              SailZen Control Plane                       │
│                                                         │
│  ┌──────────────────────────────────────────────┐      │
│  │  Novel Task Router                            │      │
│  │  - 解析自然语言/结构化指令                     │      │
│  │  - 映射到具体 Pipeline                        │      │
│  │  - 分配到 Edge Runtime / OpenCode Session     │      │
│  └──────────────────────────────────────────────┘      │
│                                                         │
│  ┌──────────────────────────────────────────────┐      │
│  │  DAG Pipeline Orchestrator (复用已有)         │      │
│  │  - 任务编排和依赖管理                         │      │
│  │  - 节点状态追踪                               │      │
│  │  - Human Gate 管理                            │      │
│  └──────────────────────────────────────────────┘      │
└─────────────────────────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────────────────────────┐
│              Edge Runtime (本地执行)                     │
│                                                         │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐             │
│  │ OpenCode │  │ OpenCode │  │ OpenCode │             │
│  │ Session  │  │ Session  │  │ Session  │             │
│  │ (Draft)  │  │ (Audit)  │  │ (Polish) │             │
│  └──────────┘  └──────────┘  └──────────┘             │
│                                                         │
│  Novel Repo: D:\repos\novel-mystic-lord\               │
└─────────────────────────────────────────────────────────┘
```

### 6.2 飞书集成：从消息到任务

**场景 1: "帮我更新5章"**

```
用户 → 飞书消息: "更新5章"
  │
  ▼
sail_bot BotBrain 意图识别
  → ActionPlan: {
      action: "novel_create",
      sub_action: "batch_draft",
      params: { count: 5 }
    }
  │
  ▼
PlanExecutor → SailZen API
  POST /api/v1/novel/task/create
  {
    "task_type": "batch_draft",
    "novel_slug": "mystic-lord",
    "params": { "count": 5 }
  }
  │
  ▼
飞书回复交互卡片:
┌──────────────────────────────┐
│ 📝 创作任务已创建             │
│                              │
│ 小说: 诡秘之主               │
│ 任务: 更新5章 (ch-201~205)   │
│ 当前进度: 准备中...          │
│                              │
│ ┌─────────┐ ┌─────────┐     │
│ │ 查看详情 │ │ 取消任务 │     │
│ └─────────┘ └─────────┘     │
└──────────────────────────────┘
```

**场景 2: "完善设定并同步到飞书文档"**

```
用户 → 飞书消息: "把最新的人物设定同步到飞书文档"
  │
  ▼
sail_bot 意图识别
  → ActionPlan: {
      action: "novel_sync",
      sub_action: "export_settings_to_feishu",
      params: { scope: "characters" }
    }
  │
  ▼
Pipeline 执行:
  1. 读取 characters/ 目录下所有人物档案
  2. 转换为飞书文档格式
  3. 通过飞书 API 创建/更新知识库文档
  4. 回复飞书卡片: "✅ 已同步 42 个角色档案到飞书知识库"
```

### 6.3 SailSite Web UI 集成

新增 `/novel-studio` 页面（基于现有 DAG Pipeline 前端扩展）：

```
┌──────────────────────────────────────────────────────────┐
│ 📚 Novel Studio: 诡秘之主                    [设置] [帮助]│
├──────────┬───────────────────────────────────────────────┤
│          │                                               │
│ 📁 作品  │  ┌─────────────────────────────────────────┐  │
│ ├ 大纲   │  │          创作仪表板                      │  │
│ ├ 人物   │  │                                         │  │
│ ├ 设定   │  │  进度: ████████░░ 80% (201/250章)       │  │
│ ├ 正文   │  │  本周: 15章 / 45000字                   │  │
│ │ ├vol-1 │  │                                         │  │
│ │ └vol-2 │  │  ┌───────────┐  ┌───────────┐          │  │
│ ├ 草稿   │  │  │ ✏️ 更新5章  │  │ 🔍 全文审核 │          │  │
│ ├ 质量   │  │  └───────────┘  └───────────┘          │  │
│ └ 灵感   │  │  ┌───────────┐  ┌───────────┐          │  │
│          │  │  │ 📊 设定同步 │  │ 💡 整理灵感 │          │  │
│ 🔄 运行中 │  │  └───────────┘  └───────────┘          │  │
│ ├ 草稿..  │  │                                         │  │
│ └ 审核..  │  │  最近活动:                              │  │
│          │  │  10:30 ✅ ch-200 定稿合入                │  │
│ ⚠️ 待处理 │  │  10:25 📝 ch-200 润色完成               │  │
│ ├ 审核x2  │  │  10:15 🔍 ch-200 审核通过               │  │
│ └ issue  │  │  09:45 ✏️ ch-200 草稿生成                │  │
│          │  └─────────────────────────────────────────┘  │
├──────────┴───────────────────────────────────────────────┤
│ 💬 AI 助手: 有什么可以帮你的？  [_______________] [发送]  │
└──────────────────────────────────────────────────────────┘
```

### 6.4 CLI 集成

```bash
# 通过 SailZen CLI 操作小说项目
# 需要在小说仓库根目录执行

# 生成章节草稿
uv run sailzen novel draft --count 5

# 触发世界观审核
uv run sailzen novel audit --chapters 201-205

# 润色章节
uv run sailzen novel polish --chapters 201-205

# 同步设定
uv run sailzen novel sync-settings

# 整理灵感
uv run sailzen novel collect-ideas

# 发布章节到平台
uv run sailzen novel publish --chapters 201-205 --platform qidian

# 查看创作状态
uv run sailzen novel status

# 输出:
# Novel: 诡秘之主
# Progress: 200/250 chapters (80%)
# Words: 600,000 / 750,000
# Drafts: 5 pending, 2 in review
# Issues: 3 open
# Last activity: 10 minutes ago
```

### 6.5 GitHub Actions 自动化

```yaml
# .github/workflows/on-draft-push.yml
name: Draft Review Pipeline

on:
  push:
    branches: ['draft/**']
    paths: ['drafts/pending/**']

jobs:
  world-audit:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Setup SailZen
        uses: sailzen/setup-action@v1
        with:
          novel-repo: true
      - name: Run World Auditor
        run: |
          uv run sailzen novel audit --auto
          # 自动将 pending → review 或 rejected
      - name: Create Review PR
        if: success()
        run: |
          gh pr create \
            --title "📝 Review: ${{ github.ref_name }}" \
            --body "自动生成的审核 PR" \
            --reviewer sailing-innocent

# .github/workflows/on-pr-merge.yml
name: Post-Merge Pipeline

on:
  pull_request:
    types: [closed]
    branches: [main]

jobs:
  post-merge:
    if: github.event.pull_request.merged == true
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Setting Update
        run: uv run sailzen novel sync-settings --auto-commit
      - name: Sync to SailZen DB
        run: uv run sailzen novel sync-db
      - name: Notify via Feishu
        run: uv run sailzen novel notify --channel feishu --event merged

# .github/workflows/daily-consistency.yml
name: Daily Consistency Check

on:
  schedule:
    - cron: '0 2 * * *'  # 每天凌晨2点

jobs:
  consistency:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Full Consistency Check
        run: |
          uv run sailzen novel check-consistency --full
          # 检查所有已发布章节的设定一致性
      - name: Update Report
        run: |
          git add quality/consistency-report.md
          git commit -m "check: daily consistency report"
          git push
```

## 7. 与 SailZen 分析系统的集成

### 7.1 双向桥接：分析系统 ↔ 创作系统

创作系统与 [novel_analysis_system.md](./novel_analysis_system.md) 中定义的分析系统形成**双向闭环**：

```
┌─────────────────┐                    ┌─────────────────┐
│  Analysis System │                    │  Creation System │
│  (分析已有作品)   │                    │  (协作创作新章)   │
│                 │                    │                 │
│  ┌───────────┐  │    设定/人物/大纲    │  ┌───────────┐  │
│  │ Character  │──┼──────────────────→│  │ characters/│  │
│  │ Detection  │  │                    │  │ world/     │  │
│  │ Outline    │  │                    │  │ outline/   │  │
│  │ Setting    │  │                    │  └───────────┘  │
│  └───────────┘  │                    │       │         │
│                 │    新章节回流分析    │       ▼         │
│  ┌───────────┐  │←──────────────────┼─  volumes/      │
│  │ Enrich    │  │                    │  (定稿章节)     │
│  │ Pipeline  │  │                    │                 │
│  └───────────┘  │                    │                 │
│                 │                    │                 │
└─────────────────┘                    └─────────────────┘

        SailZen DB                        Git Repo
     (PostgreSQL)                       (GitHub)
```

### 7.2 分析系统为创作系统提供的能力

| 能力 | 来源 Pipeline | 用途 |
|------|---------------|------|
| **人物图谱** | Analyze → char_detect + char_merge | 初始化 `characters/` 目录 |
| **大纲结构** | Analyze → outline_extract + outline_merge | 初始化 `outline/arcs/` |
| **世界观设定** | Analyze → setting_extract + setting_merge | 初始化 `world/` 目录 |
| **一致性检查** | Enrich → consistency | World Auditor 的规则库 |
| **关系图谱** | Enrich → relation_graph | `characters/_relations.md` |
| **时间线** | Enrich → timeline | `outline/timeline.md` |

### 7.3 从分析到创作的初始化流程

当基于已有作品（如经典网文）创建创作项目时：

```
1. 用户上传已有小说 txt 到 SailZen
   ↓
2. 运行 Ingest Pipeline (novel_analysis_system)
   → 导入、清洗、切分章节
   ↓
3. 运行 Analyze Pipeline
   → 人物检测 + 大纲提取 + 设定提取
   ↓
4. 运行 Enrich Pipeline
   → 关系图谱 + 时间线 + 一致性检查
   ↓
5. 运行 "Export to Novel Repo" 任务 (新增)
   → 将分析结果导出为 Markdown 文件
   → 创建 Git 仓库并初始化目录结构
   → 填充 characters/ + world/ + outline/
   ↓
6. 创作系统接管
   → 人类补充 outline/ 后续情节
   → Draft Writer 开始生成新章节
```

### 7.4 DAG Pipeline 对接

创作系统的工作流复用 `novel_analysis_system.md` 中已有的 DAG Pipeline 基础设施：

```jsonc
// .sailzen/pipeline.yaml → 转换为 SailZen Pipeline JSON

{
  "id": "novel-create-batch",
  "name": "批量创作: {novel_title} ch-{start}~{end}",
  "description": "批量生成、审核、润色、校对章节",
  "params_schema": {
    "novel_slug": { "type": "string", "required": true },
    "repo_path": { "type": "string", "required": true },
    "start_chapter": { "type": "integer", "required": true },
    "count": { "type": "integer", "default": 5 }
  },
  "nodes": [
    {
      "id": "context_build",
      "name": "构建创作上下文",
      "type": "builtin",
      "handler": "novel.create.build_context",
      "description": "读取大纲、设定、前文，构建 Agent 上下文",
      "depends_on": []
    },
    {
      "id": "batch_draft",
      "name": "批量生成草稿",
      "type": "opencode",
      "handler": "novel.create.run_draft_writer",
      "description": "启动 OpenCode Session 运行 draft-writer skill",
      "depends_on": ["context_build"],
      "opencode_config": {
        "skill": "draft-writer",
        "workspace": "{repo_path}"
      }
    },
    {
      "id": "world_audit",
      "name": "世界观审核",
      "type": "opencode",
      "handler": "novel.create.run_world_auditor",
      "description": "启动 OpenCode Session 运行 world-auditor skill",
      "depends_on": ["batch_draft"],
      "opencode_config": {
        "skill": "world-auditor",
        "workspace": "{repo_path}"
      }
    },
    {
      "id": "audit_gate",
      "name": "审核门控",
      "type": "human_gate",
      "handler": "novel.create.audit_gate",
      "description": "如果有 FAIL 项，等待人工确认",
      "depends_on": ["world_audit"],
      "gate_config": {
        "auto_approve_if": "world_audit.verdict == 'ALL_PASS'",
        "timeout_hours": 48
      }
    },
    {
      "id": "style_polish",
      "name": "文字润色",
      "type": "opencode",
      "handler": "novel.create.run_style_polisher",
      "depends_on": ["audit_gate"],
      "opencode_config": {
        "skill": "style-polisher",
        "workspace": "{repo_path}"
      }
    },
    {
      "id": "continuity_check",
      "name": "连续性校对",
      "type": "opencode",
      "handler": "novel.create.run_continuity_checker",
      "depends_on": ["audit_gate"],
      "opencode_config": {
        "skill": "continuity-checker",
        "workspace": "{repo_path}"
      }
    },
    {
      "id": "human_review",
      "name": "人工最终审校",
      "type": "human_gate",
      "handler": "novel.create.final_review",
      "description": "创建 PR，等待人类审批",
      "depends_on": ["style_polish", "continuity_check"],
      "gate_config": {
        "timeout_hours": 72,
        "notify": ["feishu", "web"]
      }
    },
    {
      "id": "post_merge",
      "name": "后处理",
      "type": "builtin",
      "handler": "novel.create.post_merge",
      "description": "合并 PR、更新设定、同步 DB、发布",
      "depends_on": ["human_review"]
    }
  ]
}
```

**Pipeline 并行化设计**:
```
context_build
     │
 batch_draft
     │
 world_audit
     │
 audit_gate
   /     \
style_polish  continuity_check    ← 并行
   \     /
 human_review
     │
 post_merge
```

## 8. 超长篇特殊挑战与解决方案

### 8.1 上下文窗口管理

超长篇小说（1000+ 章、300万+ 字）的核心挑战是 **LLM 上下文窗口有限**。

**解决策略：分层上下文构建**

```python
class NovelContextBuilder:
    """为 Agent 构建分层上下文"""
    
    def build_draft_context(self, chapter_num: int) -> str:
        """构建草稿撰写上下文（目标: < 30K tokens）"""
        
        context_layers = []
        
        # Layer 1: 核心约束 (~2K tokens)
        # 世界观硬性规则 + 文风要求
        context_layers.append(self.load_rules())       # world/rules.md
        context_layers.append(self.load_style_guide())  # quality/style-guide.md
        
        # Layer 2: 情节锚点 (~3K tokens)
        # 当前弧线大纲 + 本章具体节点
        context_layers.append(self.load_arc_outline(chapter_num))
        context_layers.append(self.load_chapter_plan(chapter_num))
        
        # Layer 3: 近期记忆 (~10K tokens)
        # 最近 3-5 章全文（衔接用）
        context_layers.append(self.load_recent_chapters(chapter_num, lookback=3))
        
        # Layer 4: 人物状态 (~5K tokens)
        # 本章涉及人物的当前状态快照
        involved_chars = self.predict_involved_characters(chapter_num)
        context_layers.append(self.load_character_snapshots(involved_chars))
        
        # Layer 5: 远期摘要 (~5K tokens)
        # 早期重要事件的压缩摘要
        context_layers.append(self.load_volume_summaries(chapter_num))
        
        return self.assemble_prompt(context_layers)
    
    def load_recent_chapters(self, chapter_num: int, lookback: int = 3) -> str:
        """加载最近 N 章全文（最关键的衔接上下文）"""
        chapters = []
        for i in range(max(1, chapter_num - lookback), chapter_num):
            path = self.resolve_chapter_path(i)
            content = self.read_chapter_content(path)
            # 如果单章太长，取最后 2000 字
            if len(content) > 6000:
                content = f"[...前文省略...]\n\n{content[-6000:]}"
            chapters.append(content)
        return "\n\n---\n\n".join(chapters)
```

### 8.2 设定漂移检测

随着章节增加，世界观设定可能出现**隐性漂移**（非明确矛盾，但逐渐偏离原始设定）。

```python
class SettingDriftDetector:
    """检测设定隐性漂移"""
    
    async def detect_drift(self, edition_id: int, window_size: int = 50):
        """每 50 章做一次设定快照对比"""
        
        # 1. 提取每个窗口期的设定快照
        snapshots = []
        for start in range(0, total_chapters, window_size):
            snapshot = await self.extract_setting_snapshot(
                edition_id, start, start + window_size
            )
            snapshots.append(snapshot)
        
        # 2. 对比相邻快照，检测漂移
        drifts = []
        for i in range(1, len(snapshots)):
            diff = await self.compare_snapshots(snapshots[i-1], snapshots[i])
            if diff.drift_score > 0.3:  # 阈值
                drifts.append(DriftAlert(
                    period=f"ch-{(i-1)*window_size}~{i*window_size}",
                    drift_score=diff.drift_score,
                    changed_settings=diff.changed_items,
                    severity="warning" if diff.drift_score < 0.6 else "error"
                ))
        
        return drifts
```

### 8.3 角色语音一致性

超长篇中保持角色对话风格一致是巨大挑战。

**解决方案: 角色语音指纹**

```markdown
<!-- .agents/prompts/character-voice.md -->

# 角色语音指纹

## 周明瑞 / 克莱恩
- **语气**: 内敛、自嘲、偶尔幽默
- **口头禅**: "相当合理"、"这很不正常"
- **思维模式**: 先分析利弊，再做决定；习惯性自我吐槽
- **禁忌**: 不会直接表露强烈情感；不会说网络用语
- **示例段落**:
  > "克莱恩端起咖啡，缓缓抿了一口，借此掩饰内心的波澜。
  > '看来我需要重新评估这件事的危险程度。'他在心里默默补充道：
  > '从"可能会死"升级到"一定会死"的那种。'"

## 奥黛丽
- **语气**: 优雅、好奇、偶尔天真
- **口头禅**: "太有趣了"
- **思维模式**: 观察力敏锐，喜欢分析他人心理
```

### 8.4 伏笔与回收追踪

```markdown
<!-- outline/foreshadowing.md -->
# 伏笔追踪表

| ID | 伏笔描述 | 埋设章节 | 计划回收 | 实际回收 | 状态 |
|----|----------|----------|----------|----------|------|
| F-001 | 灰雾之上的神秘存在 | ch-001 | ch-200 | ch-198 | ✅ 已回收 |
| F-002 | 旧日记中的暗号 | ch-045 | ch-150 | - | ⏳ 待回收 |
| F-003 | 酒馆老板的异常行为 | ch-089 | ch-250 | - | 📝 规划中 |

## Agent 指令
> Draft Writer 在撰写 ch-150 附近时，注意回收 F-002 伏笔。
> 具体要求: 主角在整理遗物时发现旧日记，破解其中的暗号。
```

## 9. 实施路线

### Phase 1: 仓库规范与基础工具 (2 周)

**目标**: 确立仓库规范，能手动走通创作流程

- [ ] 定义并文档化完整的目录结构和文件格式规范
- [ ] 创建 `novel-template` 模板仓库（GitHub Template）
- [ ] 实现 `sailzen novel init` CLI 命令（从模板创建新小说仓库）
- [ ] 编写 `draft-writer` Skill 的 skill.md 和基础 prompt
- [ ] 手动测试: 用 OpenCode 运行 draft-writer 生成一章草稿
- [ ] 验证 frontmatter 元数据的正确性

### Phase 2: Agent 技能实现 (3-4 周)

**目标**: 6 个 Agent Skill 全部可用

- [ ] 实现 `draft-writer` Skill（含 context_builder + generate_draft）
- [ ] 实现 `world-auditor` Skill（含 rule_parser + audit_chapter）
- [ ] 实现 `style-polisher` Skill（含 style_analyzer + polish_chapter）
- [ ] 实现 `continuity-checker` Skill（含 timeline_validator）
- [ ] 实现 `setting-updater` Skill（含 diff_analyzer）
- [ ] 实现 `inspiration-collector` Skill
- [ ] 端到端测试: 手动串联运行完整 6-step Pipeline

### Phase 3: DAG Pipeline 集成 (2-3 周)

**目标**: 通过 SailZen Pipeline 自动编排 Agent

- [ ] 编写 `novel-create-batch.json` Pipeline 定义
- [ ] 实现 `opencode` 节点类型（复用 Edge Runtime + OpenCode Session）
- [ ] 实现 Pipeline → OpenCode Session 的参数传递
- [ ] 实现 Human Gate 与飞书/Web 通知集成
- [ ] 前端: Novel Studio 页面基础框架
- [ ] 验证: 从 Web UI 触发"更新5章"Pipeline 完整运行

### Phase 4: 多渠道触发 (2 周)

**目标**: 飞书 / Web / CLI / GitHub Actions 全部打通

- [ ] sail_bot 添加 novel 意图识别
- [ ] 实现飞书交互卡片（任务创建、进度、审核）
- [ ] 实现 GitHub Actions 工作流
- [ ] CLI 命令完善（draft / audit / polish / sync / publish）
- [ ] 前端 Novel Studio 完善（仪表板、文件浏览器、AI 助手）

### Phase 5: 分析系统集成 (2 周)

**目标**: 打通分析 → 创作的完整闭环

- [ ] 实现 "Export to Novel Repo" Pipeline
- [ ] 从 SailZen DB 分析结果生成 Markdown 文件
- [ ] 实现创作章节回流到分析系统
- [ ] 实现设定漂移检测
- [ ] 实现伏笔追踪系统

### Phase 6: 优化与规模化 (持续)

**目标**: 支持 1000+ 章的超长篇项目

- [ ] 上下文窗口优化（摘要层级化、智能裁剪）
- [ ] 角色语音指纹系统
- [ ] 批量创作性能优化（并行 Session）
- [ ] LLM 成本追踪与优化
- [ ] 发布平台对接（起点中文网 API 等）
- [ ] 读者反馈收集与分析

## 10. 设计决策记录

### Q: 为什么选择 Git + Markdown 而不是全部存在数据库？

**A**:
1. **Agent 友好**: OpenCode/Agent 天然以文件系统为工作空间，读写 Markdown 零成本
2. **版本控制**: Git 提供比数据库更细粒度的变更追踪和回滚能力
3. **协作模型**: Git 分支 + PR 的协作模型完美适配多 Agent 协作场景
4. **可移植性**: 仓库可以随时 clone 到任何机器，不依赖在线服务
5. **透明度**: 所有内容和变更对人类完全透明，不存在"黑盒"

数据库（SailZen DB）作为**辅助索引层**，存储分析结果、统计数据、运行状态等结构化信息，但不是 truth source。

### Q: 为什么每个 Agent 用独立的 OpenCode Session？

**A**:
1. **隔离性**: 每个 Agent 有独立的上下文窗口和 Skill，互不干扰
2. **并行能力**: Style Polisher 和 Continuity Checker 可以并行工作
3. **可重启性**: 单个 Agent 失败不影响其他 Agent
4. **可审计性**: 每个 Session 有独立的日志，方便排查问题

代价是需要更多的进程管理开销，但 Edge Runtime 的 ManagedSession 机制已经解决了这个问题。

### Q: 如何处理 Agent 生成内容的质量问题？

**A**:
多层防御策略：
1. **Prompt Engineering**: 精心设计的 system prompt + 角色语音指纹 + 文风参考
2. **规则审核**: World Auditor 自动检查硬性规则违反
3. **风格对齐**: Style Polisher 对标原文风格
4. **连续性校验**: Continuity Checker 检查前后文逻辑
5. **人类把关**: 所有内容最终需要人类 PR Review 才能合入 main

关键原则：**Agent 负责生产力，人类负责质量把关**。系统的目标不是完全替代人类创作，而是让人类从"写作者"变为"审核者 + 创意者"。

### Q: 如何在超长篇中保持设定一致性？

**A**:
三重保障：
1. **硬性规则文件** (`world/rules.md`): 不可违反的核心设定，Agent 每次创作前必须读取
2. **设定变更追踪**: 每个设定文件都有变更记录表，记录何时何章何因变更
3. **定期漂移检测**: 每 50 章自动运行设定漂移检测，发现隐性偏移

### Q: 与 novel_analysis_system.md 的关系是什么？

**A**:
- **分析系统**: 处理**已有作品**的导入、整理、分析、知识提取
- **创作系统**: 基于分析结果（或全新规划）进行**多 Agent 协作创作**
- **共享基础设施**: DAG Pipeline、LLM Batch Scheduler、Human Gate、Edge Runtime
- **数据流向**: 分析系统 → 结构化知识 → 导出为 Markdown → 创作系统消费
- **反馈闭环**: 创作的新章节 → 回流到分析系统 → 更新知识图谱

两个系统互为补充，分析系统是"理解世界"，创作系统是"扩展世界"。
