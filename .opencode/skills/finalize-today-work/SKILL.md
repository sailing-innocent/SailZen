---
name: finalize-today-work
description: |
  一天工作结束时的收尾流程。
  项目禁止直接 push 源代码，需要生成带有 日期-项目名 信息的 patch 文件，
  留存在本地，等待后续在其他环境 apply。
  基于 git-push skill 的约束，补充了命名规范和完整的收尾检查。
---

# Finalize Today's Work

## 何时使用此 Skill

- 一天开发工作结束，准备收工
- 需要将今天的所有 commit 打包成 patch，供后续在其他环境应用
- 完成某个完整功能模块后，需要生成阶段性 patch

---

## 重要约束（继承自 git-push skill）

> **⚠️ CRITICAL: 禁止执行 `git push origin <branch>`**

本项目开发环境不允许直接推送源代码到 origin。  
所有变更必须通过 `git format-patch` 生成 patch 文件，在其他（受信任）环境中 apply 后再推送。

---

## Patch 命名规范

格式：`<YYYY-MM-DD>-sailzen-<brief-topic>.patch`

示例：
```
2026-03-27-sailzen-plugin-perf-concurrency.patch
2026-03-27-sailzen-startup-profiler.patch
2026-03-27-sailzen-arch-docs.patch
2026-03-27-sailzen-mixed.patch        # 当天多个不相关改动混合时
```

Patch 文件保存位置：项目根目录下的 `patches/` 文件夹（已在 `.gitignore` 中排除）。

---

## 执行步骤

### Step 1 — 确认没有未提交的修改

```powershell
pwsh -Command "git status --short"
```

- 如果有未提交内容，先执行 `commit-current-change` skill 完成提交
- 工作目录必须干净（clean）才继续

### Step 2 — 查看今天新增的 commit

```powershell
# 查看当前分支比 origin/master 多出的所有 commit
pwsh -Command "git log origin/master..HEAD --oneline"
```

记录 commit 数量，确认内容符合预期。

### Step 3 — 确认 patches 目录存在

```powershell
pwsh -Command "if (!(Test-Path 'patches')) { New-Item -ItemType Directory -Path 'patches' }"
```

### Step 4 — 生成 Patch 文件

**方案 A — 所有新 commit 合并为一个 patch 文件（推荐，简洁）**

```powershell
# 格式：日期-sailzen-主题.patch
pwsh -Command "git format-patch origin/master --stdout > 'patches/2026-03-27-sailzen-mixed.patch'"
```

将 `2026-03-27` 替换为实际日期，`mixed` 替换为今天工作的主题词。

**方案 B — 每个 commit 生成独立 patch 文件**

```powershell
pwsh -Command "git format-patch origin/master -o patches/"
```

生成的文件按序号命名：`0001-xxx.patch`、`0002-xxx.patch`...  
如需重命名，在 `patches/` 目录下手动 rename。

**方案 C — 只打包最近 N 个 commit**

```powershell
# 最近 3 个 commit
pwsh -Command "git format-patch -3 --stdout > 'patches/2026-03-27-sailzen-mixed.patch'"
```

### Step 5 — 验证 Patch 文件

```powershell
# 查看 patch 元信息（不应用）
pwsh -Command "git apply --stat 'patches/2026-03-27-sailzen-mixed.patch'"

# 检查能否干净应用（dry-run）
pwsh -Command "git apply --check 'patches/2026-03-27-sailzen-mixed.patch'"
```

输出无错误即为有效 patch。

### Step 6 — 记录收尾状态

```powershell
# 查看最终 git 状态
pwsh -Command "git log --oneline -5"
pwsh -Command "git status"
```

确认：
- [ ] 工作目录干净
- [ ] patch 文件已生成在 `patches/` 下
- [ ] patch 文件名包含日期和项目名
- [ ] 没有执行 `git push origin`

---

## 完整一键流程

```powershell
# 1. 检查状态
pwsh -Command "git status --short; git log origin/master..HEAD --oneline"

# 2. 确保 patches 目录存在
pwsh -Command "if (!(Test-Path 'patches')) { New-Item -ItemType Directory -Path 'patches' }"

# 3. 生成 patch（修改日期和主题）
pwsh -Command "git format-patch origin/master --stdout > 'patches/2026-03-27-sailzen-mixed.patch'"

# 4. 验证
pwsh -Command "git apply --stat 'patches/2026-03-27-sailzen-mixed.patch'"
```

---

## 在其他环境应用 Patch

在允许 push 的环境中：

```bash
# 1. 复制 patch 文件到目标环境

# 2. 预览 patch 内容
git apply --stat 2026-03-27-sailzen-mixed.patch

# 3. 测试能否干净应用
git apply --check 2026-03-27-sailzen-mixed.patch

# 4. 应用（保留原始 commit 信息）
git am < 2026-03-27-sailzen-mixed.patch

# 5. 推送
git push origin master
```

如果 `git am` 有冲突：

```bash
# 跳过当前有冲突的 patch
git am --skip

# 或放弃整个 am 操作
git am --abort
```

---

## Patch 归档建议

`patches/` 目录已通过 `.gitignore` 排除，不会被提交。  
建议定期将 patch 文件复制到外部备份位置（如 OneDrive、本地归档目录）。

命名中包含日期可以方便按时间索引：

```
patches/
  2026-03-27-sailzen-plugin-perf-concurrency.patch
  2026-03-26-sailzen-finance-dashboard-fix.patch
  2026-03-25-sailzen-text-analysis-v2.patch
```

---

## 与 commit-current-change skill 的关系

```
开发中 --> [commit-current-change] --> 本地 commit
一天结束 --> [finalize-today-work]  --> patches/ 下的 .patch 文件
其他环境 --> git am + git push      --> 推送到 origin
```
