# Vault 结构设计

Vault 是 SailZen 中存储笔记的基本单元，一个工作区可以包含多个 Vault。

## Vault 类型

### 1. 本地 Vault
直接存储在本地文件系统中的笔记仓库。

```
my-vault/
├── root.md              # 根笔记
├── project.md           # 项目笔记
├── project.frontend.md  # 子层级笔记
└── daily.journal.2024.01.30.md  # 日记笔记
```

### 2. 远程 Vault
通过 Git 仓库管理的远程笔记仓库，可自动同步。

### 3. Self-Contained Vault
自包含 Vault 将所有配置和资源都包含在 Vault 目录内部：

```
self-contained-vault/
├── .dendron/
│   ├── dendron.yml      # 工作区配置
│   └── .code-workspace  # VSCode 工作区文件
├── notes/               # 笔记目录
│   ├── root.md
│   └── ...
└── assets/              # 资源文件
    └── images/
```

## 笔记命名规范

### 层级命名
使用点号 `.` 分隔层级：

```
root                    # 根笔记
project                 # 一级层级
project.frontend        # 二级层级
project.frontend.react  # 三级层级
```

### 特殊笔记类型

#### Journal（日记）
```
daily.journal.2024.01.30    # 日期格式可配置
```

#### Scratch（草稿）
```
scratch.2024.01.30.143022   # 包含时间戳
```

#### Meeting（会议）
```
meet.2024.01.30.standup
```

#### Task（任务）
```
task.implement-feature
```

## 笔记前言 (Frontmatter)

每个笔记以 YAML frontmatter 开头：

```yaml
---
id: abc123def456              # 唯一标识符
title: My Note Title          # 笔记标题
desc: Optional description    # 可选描述
created: 1706601600000        # 创建时间戳
updated: 1706601600000        # 更新时间戳
traitIds:                     # 笔记特性
  - journalNote
tags:                         # 标签
  - important
  - project
---
```

## Schema 定义

Schema 用于定义笔记层级的结构规范：

```yaml
# project.schema.yml
version: 1
schemas:
  - id: project
    title: Project
    parent: root
    children:
      - pattern: frontend
      - pattern: backend
      - pattern: docs
```

### Schema 匹配
- `pattern: exact` - 精确匹配
- `pattern: "*"` - 通配符匹配

## Vault 配置

在 `dendron.yml` 中配置 Vault：

```yaml
version: 5
workspace:
  vaults:
    - fsPath: notes
      name: main
    - fsPath: ../shared-vault
      name: shared
      remote:
        type: git
        url: https://github.com/user/vault.git
```

## 链接语法

### Wiki 链接
```markdown
[[note-name]]                    # 基本链接
[[note-name#header]]             # 锚点链接
[[note-name|display text]]       # 显示文本
[[vault-name/note-name]]         # 跨 Vault 链接
```

### 笔记引用
```markdown
![[note-name]]                   # 嵌入整个笔记
![[note-name#header]]            # 嵌入特定章节
![[note-name#header:#end]]       # 嵌入范围
```

## 资源管理

### 图片和附件
存储在 `assets/` 目录下：

```
vault/
├── notes/
│   └── my-note.md
└── assets/
    └── images/
        └── diagram.png
```

引用方式：
```markdown
![diagram](./assets/images/diagram.png)
```

## 同步机制

### Git 同步
- `addAndCommit` - 添加并提交更改
- `sync` - 推送/拉取远程仓库

### 冲突处理
自动检测并提示解决冲突的笔记。

## 相关文档

- [设计概述](./overview.md)
- [开发环境](../dev/plugin/devenv.md)
