---
name: commit-current-change
description: |
  在 Windows 开发环境下安全提交当前修改。
  自动检测并清理 AI 辅助工具生成的 `nul` 文件（Windows 下会阻塞 git add），
  然后暂存所有变更并提交。
---

# Commit Current Change

## 何时使用此 Skill

- 完成一个功能点或修复后，需要提交当前工作目录的所有修改
- git add 报错或卡住，怀疑有 `nul` 文件阻塞
- 日常开发提交，在执行 `finalize_today_work` 之前

---

## 背景：`nul` 文件问题

AI 辅助工具（如 GitHub Copilot、某些 LLM 工具链）在 Windows 下有时会创建名为 `nul` 的文件。

`nul` 是 Windows 的保留设备名，相当于 `/dev/null`。
- PowerShell 无法删除它（`Remove-Item nul` 删除的是同名普通文件，但设备名会干扰 git）
- **必须在 Git Bash（`sh.exe` / `bash.exe`）中使用 `rm nul` 才能清除**

症状：`git add .` 卡住或报错 `error: unable to index file nul`

---

## 执行步骤

### Step 1 — 检查是否存在 `nul` 文件

```powershell
# 在 PowerShell / pwsh 中检查
pwsh -Command "git status --short | Select-String 'nul'"
```

如果输出包含 `?? nul` 或 `nul`，则需要执行 Step 2，否则跳到 Step 3。

### Step 2 — 用 Git Bash 清除 `nul` 文件

```bash
# 必须使用 git bash（sh.exe），不能用 pwsh
"C:\Program Files\Git\bin\sh.exe" -c "rm nul"
```

如果 Git Bash 路径不同，常见备选：

```bash
"C:\Program Files\Git\usr\bin\bash.exe" -c "rm nul"
# 或直接在已打开的 Git Bash 终端中运行：
rm nul
```

删除后再次确认：

```bash
pwsh -Command "git status --short"
# nul 条目应已消失
```

### Step 3 — 暂存所有变更

```powershell
pwsh -Command "git add -A"
```

如果只想暂存特定文件：

```powershell
pwsh -Command "git add path/to/file1 path/to/file2"
```

### Step 4 — 确认暂存内容

```powershell
pwsh -Command "git diff --cached --stat"
```

检查：
- [ ] 没有意外文件（密钥、`.env`、大型二进制文件）
- [ ] 修改的文件数量符合预期
- [ ] 没有 `nul` 残留

### Step 5 — 提交

```powershell
pwsh -Command "git commit -m '<type>: <short description>'"
```

Commit message 规范（本项目约定）：

| type | 用途 |
|------|------|
| `feat` | 新功能 |
| `fix` | Bug 修复 |
| `refactor` | 重构（不改变行为） |
| `docs` | 仅文档变更 |
| `chore` | 构建/工具/配置 |
| `perf` | 性能优化 |

示例：

```powershell
pwsh -Command "git commit -m 'perf: concurrentize NoteParserV2 note loading'"
pwsh -Command "git commit -m 'docs: add VSCode plugin architecture guide'"
pwsh -Command "git commit -m 'feat: add StartupProfiler local perf logging'"
```

---

## 完整一键流程（无 nul 文件时）

```powershell
pwsh -Command "git add -A; git diff --cached --stat"
# 确认内容后：
pwsh -Command "git commit -m 'type: description'"
```

## 完整一键流程（有 nul 文件时）

```bash
# 1. Git Bash 中删除 nul
"C:\Program Files\Git\bin\sh.exe" -c "rm nul"

# 2. PowerShell 中暂存并提交
pwsh -Command "git add -A; git diff --cached --stat"
pwsh -Command "git commit -m 'type: description'"
```

---

## 常见错误排查

| 错误 | 原因 | 解决 |
|------|------|------|
| `git add` 卡住不返回 | `nul` 文件阻塞 | 执行 Step 2 用 Git Bash 删除 |
| `error: unable to index file nul` | 同上 | 同上 |
| `Remove-Item : Cannot remove item nul` | PowerShell 无法删除设备名文件 | 必须用 Git Bash `rm nul` |
| `nothing to commit` | 没有已暂存的变更 | 先执行 `git add -A` |
| 提交后发现漏文件 | `git add` 了具体路径但遗漏 | 补一个新 commit，不要 amend 已推送的 |

---

## 注意事项

- **不要使用 `git commit --amend`**，除非该 commit 尚未生成 patch/未推送
- **不要提交** `.env*`、`*.key`、`*.pem` 等敏感文件
- 提交后继续工作，一天结束时使用 `finalize_today_work` skill 生成 patch
