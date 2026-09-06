---
name: start-today-work
description: |
  一天工作开始时的准备流程。
  检查 patches/ 目录中是否有待应用的 patch，验证 patch 基于 origin 上的同名分支，
  应用 patch 后将本地分支回退到 origin 状态，再拉取 origin 最新更新，
  确保本地工作区从最新的 origin 状态干净起步。
---

# Start Today's Work

## 何时使用此 Skill

- 每天开始工作前，需要同步昨天在其他环境 push 的内容
- patches/ 目录下有尚未应用（或已在其他环境 apply+push）的 patch 文件
- 需要将本地分支重置回 origin，以最新状态开始新一天的开发

---

## 整体流程

```
patches/ 下有 patch?
    YES --> 验证 patch 基于 origin/<当前分支>
        --> 已在其他环境 apply+push? --> 跳过 apply，直接 Step 3
        --> 未 apply     --> 提示手动在其他环境 apply（本环境禁止 push）
    NO  --> 直接 Step 3
Step 3: 本地分支回退到 origin/<当前分支>
Step 4: 拉取 origin 最新内容
Step 5: 确认状态，准备开始
```

---

## 执行步骤

### Step 1 — 确认当前分支和 origin 对应关系

```powershell
# 查看当前分支及其 tracking 信息
pwsh -Command "git branch -vv"

# 查看 origin 上同名分支的最新 commit
pwsh -Command "git fetch origin; git log origin/<branch> --oneline -5"
```

将 `<branch>` 替换为当前分支名（通常是 `ai` 或 `master`）。

**关键变量**：
- `CURRENT_BRANCH`：当前本地分支名（`git branch --show-current`）
- `ORIGIN_BRANCH`：`origin/<CURRENT_BRANCH>`

```powershell
# 一次性获取当前分支名
pwsh -Command "git branch --show-current"
```

---

### Step 2 — 检查 patches/ 目录，验证 patch

```powershell
# 列出所有 patch 文件（按时间倒序）
pwsh -Command "Get-ChildItem patches/ -Filter '*.patch' | Sort-Object LastWriteTime -Descending | Select-Object Name, LastWriteTime, Length"
```

如果目录不存在或没有 patch，跳到 Step 3。

**验证最新 patch 是否基于 origin 同名分支：**

```powershell
# 查看 patch 文件头部，确认 base commit
pwsh -Command "Get-Content 'patches/<patch-name>.patch' -TotalCount 30"
```

在 patch 文件头部，找到类似如下的行：

```
From <commit-sha> Mon Sep 17 00:00:00 2001
From: ...
Date: ...
Subject: [PATCH 1/N] ...
```

然后验证 patch 的 base 是否与 origin 同名分支的当前 HEAD 一致：

```powershell
# 获取 origin 上同名分支的 HEAD commit SHA
pwsh -Command "git rev-parse origin/<branch>"

# 获取 patch 的 base（patch 文件里第一个 From 行之前的 commit 即为 base）
# 或用 git am --dry-run 检查（见下）
```

**dry-run 验证（推荐）**：

```powershell
# 切换到一个临时检查状态：fetch 最新 origin，然后 dry-run apply
pwsh -Command "git fetch origin"

# 用 git apply --check 对比当前 origin/<branch> 状态下能否干净应用
# 注意：此时本地分支还有本地 commit，需先了解 patch 是否已在 origin 上
```

**判断 patch 是否已在 origin 应用**：

```powershell
# 查看 origin/<branch> 上最新的几条 commit，与 patch 的 Subject 对比
pwsh -Command "git log origin/<branch> --oneline -10"
```

- 如果 origin 上已有这些 commit（Subject 匹配）→ patch **已被应用并 push**，继续 Step 3
- 如果 origin 上没有 → patch **尚未应用**，需在其他环境操作后再来，或确认自己的意图

> **⚠️ 警告**：本环境禁止 `git push origin`。如果 patch 还未在其他环境 apply，
> 不能在这里直接操作，需先在允许 push 的环境完成 `git am + git push`。

---

### Step 3 — 本地分支回退到 origin 状态

**前提**：确认 patch 已在其他环境成功 apply+push，origin 上包含最新内容。

```powershell
# 先 fetch，确保本地 origin/<branch> 引用是最新的
pwsh -Command "git fetch origin"

# 确认 origin/<branch> 的 HEAD（要重置到这个位置）
pwsh -Command "git log origin/<branch> --oneline -5"
```

**执行重置（回退本地分支到 origin 状态）**：

```powershell
# 将当前分支 reset 到 origin/<branch>（保留工作区文件不变，仅移动 HEAD）
pwsh -Command "git reset origin/<branch>"

# 如果工作目录干净，可用 --hard（彻底回到 origin 状态）
pwsh -Command "git reset --hard origin/<branch>"
```

> **选择 reset 模式**：
> - `--hard`：彻底回到 origin 状态，本地所有未提交的修改和多余 commit 全部丢弃（常用，开始新一天时工作区应为干净状态）
> - `--mixed`（默认）：移动 HEAD，但保留工作区变更为 unstaged 状态（用于保留部分未提交的实验性修改）
> - `--soft`：移动 HEAD，保留所有变更为 staged 状态（少用）

**确认重置结果**：

```powershell
pwsh -Command "git log --oneline -5"
pwsh -Command "git status --short"
```

期望输出：
- log 与 `git log origin/<branch> --oneline -5` 完全一致
- status 显示 `nothing to commit, working tree clean`（使用 --hard 时）

---

### Step 4 — 拉取 origin 最新更新

```powershell
# pull = fetch + merge（tracking 分支已配置时，直接用 pull）
pwsh -Command "git pull origin <branch>"
```

如果使用了 `--hard reset`，当前 HEAD 已经和 origin 一致，pull 通常输出 `Already up to date.`。

此步骤的目的是：确保在 reset 之后，如果 origin 又有新内容（例如在其他地方做了额外修改），也能同步到本地。

---

### Step 5 — 清理旧 patch 文件（可选）

已成功应用并 push 的 patch 文件可以归档或删除，避免下次误用：

```powershell
# 移动到归档目录（推荐保留）
pwsh -Command "if (!(Test-Path 'patches/applied')) { New-Item -ItemType Directory -Path 'patches/applied' }; Move-Item 'patches/<patch-name>.patch' 'patches/applied/'"

# 或直接删除（如已有外部备份）
pwsh -Command "Remove-Item 'patches/<patch-name>.patch'"
```

---

### Step 6 — 最终状态确认

```powershell
# 查看最终状态
pwsh -Command "git log --oneline -5"
pwsh -Command "git status"
pwsh -Command "git branch -vv"
```

确认：
- [ ] 当前分支与 `origin/<branch>` 处于同一 commit（无 ahead/behind）
- [ ] 工作目录干净（clean）
- [ ] 没有残留的待应用 patch 文件（或已移入 applied/）
- [ ] 可以开始今天的开发工作

---

## 完整一键流程

```powershell
# 替换 <branch> 为实际分支名（如 ai 或 master）
$branch = pwsh -Command "git branch --show-current"

# 1. fetch 最新 origin
pwsh -Command "git fetch origin"

# 2. 检查 origin 上的最新 commit（与 patch Subject 对比）
pwsh -Command "git log origin/$branch --oneline -10"

# 3. 检查本地 patches/ 目录
pwsh -Command "Get-ChildItem patches/ -Filter '*.patch' -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending | Select-Object Name, LastWriteTime"

# 4. （确认 patch 已在其他环境 push 后）重置到 origin
pwsh -Command "git reset --hard origin/$branch"

# 5. pull 确保最新
pwsh -Command "git pull origin $branch"

# 6. 最终确认
pwsh -Command "git log --oneline -5; git status"
```

---

## 故障排查

| 场景 | 原因 | 处理方式 |
|------|------|----------|
| `git reset --hard` 后文件丢失 | 本地有未提交的改动 | 重置前先确认工作区干净，或用 `git stash` 暂存 |
| `git pull` 有 merge conflict | origin 有不兼容修改 | 检查是否有人直接 push 了不经过 patch 的内容，手动解决冲突 |
| patch 文件 `git apply --check` 失败 | patch base 与当前 origin HEAD 不一致 | 确认 patch 是基于哪个 commit 生成的；可能需要 `git am` 并手动解决冲突 |
| origin/<branch> 没有 patch 中的 commit | patch 尚未在其他环境 apply+push | 在允许 push 的环境执行 `git am < patch; git push origin <branch>` 后再来 |
| `git branch -vv` 显示 `gone` | origin 上的分支被删除 | `git remote prune origin` 清理，然后重新设置 tracking |

---

## 与其他 Skill 的关系

```
其他环境（允许 push）:
  git am < patches/YYYY-MM-DD-sailzen-xxx.patch
  git push origin <branch>
          |
          v
[start-today-work]  <-- 本地准备，重置到最新 origin 状态
          |
          v
开发工作中 --> [commit-current-change] --> 本地 commit
          |
          v
一天结束   --> [finalize-today-work]   --> patches/ 下生成 .patch 文件
          |
          v
其他环境（允许 push）:
  git am < patches/YYYY-MM-DD-sailzen-xxx.patch
  git push origin <branch>
```
