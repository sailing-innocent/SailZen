---
name: git-push
description: |
  由于开发环境限制，除非环境变量 $ALLOW_PUSH=1，否则不能直接执行git push到origin，
  所有新commit需要通过git format-patch生成patch后在其他环境提交。
  本技能确保AI操作前进行双重检查，防止错误提交。
---

# Git Push

## 重要约束

**⚠️ CRITICAL: 当前开发环境禁止直接执行 `git push origin`**，除非环境变量 $ALLOW_PUSH=1，如果需要push的时候，需要首先检查整个环境变量

由于开发环境限制：
- ❌ **禁止**: `git push origin <branch>`
- ✅ **必须**: 使用 `git format-patch` 生成patch文件

## 正确的工作流程

```bash
# 1. 添加更改
git add <files>

# 2. 提交到本地
git commit -m "your commit message"

# 3. 生成patch文件（关键步骤）
git format-patch origin/<branch> --stdout > changes.patch
# 或者生成多个patch文件:
git format-patch origin/<branch>

# 4. 在其他环境应用patch并规范提交
git am < changes.patch
# 或者使用git apply
git apply changes.patch
```

## AI操作检查清单

在每次Git操作前，AI必须确认：

### Pre-Commit 检查
- [ ] 是否有未提交的更改需要保存
- [ ] Commit message是否符合项目规范

### Pre-Push 检查（双重检查）
- [ ] ⚠️ 是否尝试执行 `git push origin`？
- [ ] ⚠️ 如果是，立即停止并切换到format-patch流程
- [ ] Patch文件是否已经生成并保存到安全位置

## 绕过检查（仅限紧急情况）

如需强制绕过pre-push钩子：

```bash
ALLOW_PUSH=1 git push origin <branch>
```

## 集成的Git Hooks

项目已配置以下hooks进行双重保护：

1. **prepare-commit-msg**: 提交时提醒patch工作流程
2. **pre-push**: 阻止直接push到origin，显示警告信息

## 与git-master skill的集成

当使用git-master skill时：

```bash
# 所有git命令必须带有GIT_MASTER=1前缀
GIT_MASTER=1 git status
GIT_MASTER=1 git add <files>
GIT_MASTER=1 git commit -m "message"

# ⚠️ 永远不要执行：
# GIT_MASTER=1 git push origin <branch>  ❌ 禁止

# ✅ 替代方案：
git format-patch origin/main --stdout > changes.patch
```

## 生成Patch的最佳实践

```bash
# 生成单个patch文件
git format-patch origin/main --stdout > changes.patch

# 生成多个patch文件（每个commit一个）
git format-patch origin/main

# 包含特定数量的commits
git format-patch -3 --stdout > last-3-commits.patch

# 指定commit范围
git format-patch abc123..def456 --stdout > range.patch
```

## 在其他环境应用Patch

```bash
# 查看patch内容
git apply --stat changes.patch

# 测试应用（不真正应用）
git apply --check changes.patch

# 应用patch
git am < changes.patch

# 如果应用失败，跳过当前patch
git am --skip

# 放弃应用
git am --abort
```
