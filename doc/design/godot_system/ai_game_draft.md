# AI 驱动独立游戏开发草案：俯视角回合制战棋 RPG

> 目标：基于 Godot 4.x，利用本地 Z-Image + Kimi API，单人完成一个 **30 小时内容量、卡通画风**的中等规模独立游戏。  
> 现状：已有 SailZen 个人工具链（飞书遥控、VSCode 笔记插件、Python 后端服务器、Kimi Token）。

---

## 1. 游戏核心设计：做减法，才能做完

### 1.1 品类定位

**俯视角（Top-Down）回合制 RPG + 轻量战棋（Tactical RPG Lite）**

- 参考作品：*Fire Emblem*（火纹）、*Advance Wars*（高级战争）、*Into the Breach*、*Triangle Strategy*（简化版）。
- 核心循环：**大地图探索（剧情/收集）→ 遭遇战（网格回合制）→ 养成/营地 → 推进主线**。
- 一句话设计："在一张可缩放的俯视角地图上，用 3-5 名角色在网格中走位、放技能、打怪升级，体验一段 30 小时的卡通风格冒险。"

### 1.2 为什么选这个品类？

| 优势 | 说明 |
|------|------|
| 时间可控 | 回合制对帧率、物理同步要求低，开发调试成本低 |
| AI 友好 | 2D/2.5D 卡通资产的 AI 生成成功率远高于写实 3D |
| 内容可模块化 | 关卡 = 地图数据 + 敌人配置，可用配置驱动大量内容 |
| 单人可驾驭 | 不需要复杂网络同步，单机即可承载 30 小时流程 |

### 1.3 30 小时内容量的「规模锚点」

不要试图做开放世界。**内容量 = 可重复游玩价值 × 关卡数 + 剧情厚度**。建议锚定如下：

- **主线关卡**：20 章（每章 1 张战斗地图 + 剧情对话）≈ 15 小时
- **支线/挑战**：10 个独立副本（每关 20-40 分钟）≈ 5 小时
- **养成/收集**：角色build实验、装备收集、图鉴 ≈ 5 小时
- **二周目/困难模式**：继承机制 ≈ 5 小时

**单局战斗时长控制在 10-20 分钟**，这是维持 30 小时不倦怠的关键。

---

## 2. Godot 技术架构与开源资源

### 2.1 引擎版本与渲染器

- **引擎**：Godot 4.4+（稳定版，TileMapLayer 系统已成熟）
- **渲染器**：Compatibility（GLES3）或 Forward+ 均可。卡通画风用 2D 为主，必要时混用 3D 做伪透视（2.5D）。
- **语言**：GDScript 2.x（开发快、AI 写起来准）或 C#（如果你更熟悉）。建议 **GDScript**，开源 Demo 资源最丰富。

### 2.2 必须复用的开源项目（不要从零写）

以下项目均为 MIT 或类似宽松协议，可直接提取代码或作为学习模板：

| 项目 | 地址 | 可复用内容 |
|------|------|------------|
| **GDQuest Tactical RPG Movement** | [gdquest.com/tutorial/godot/2d/tactical-rpg-movement](https://gdquest.com/tutorial/godot/2d/tactical-rpg-movement/) | **最核心**：网格移动、光标选择、AStar 寻路、移动预览。Godot 战棋必学基础。 |
| **ramaureirac/godot-tactical-rpg** | [github.com/ramaureirac/godot-tactical-rpg](https://github.com/ramaureirac/godot-tactical-rpg) | Godot 4.3 完整模板。含回合制、网格移动、攻击、基础敌人 AI、摄像机控制、手柄支持。 |
| **gdquest-demos/godot-open-rpg** | [github.com/gdquest-demos/godot-open-rpg](https://github.com/gdquest-demos/godot-open-rpg) | 回合制战斗系统、Inventory、角色成长、对话系统、UI 菜单。Kenney 资产包。 |
| **TylerMooney/Godot-4-Tactical-RPG-Tutorials** | [github.com/TylerMooney/Godot-4-Tactical-RPG-Tutorials](https://github.com/TylerMooney/Godot-4-Tactical-RPG-Tutorials) | 在 GDQuest 基础上扩展了攻击范围、悬停显示、单位碰撞、摄像机控制。 |
| **BlueBirdBack/godot-2d-grid-movement** | [github.com/BlueBirdBack/godot-2d-grid-movement](https://github.com/BlueBirdBack/godot-2d-grid-movement) | Godot 4.4 移植版，如果你用最新版引擎，从这里起步最干净。 |
| **Teslacrashed/godot-2D-turn-based-tactical-prototype** | [github.com/Teslacrashed/godot-2D-turn-based-tactical-prototype](https://github.com/Teslacrashed/godot-2D-turn-based-tactical-prototype) | TileGrid / TileCell 架构，资源化地图数据，适合想做配置驱动的人。 |
| **Godot 2.5D Demo** | [godotengine.org/asset-library/asset/2783](https://godotengine.org/asset-library/asset/2783) | 如果你想做 **2.5D（3D 场景 + 2D 精灵）**，这个项目展示了 Node25D 混合方案。 |

### 2.3 推荐技术方案：纯 2D 俯视角（非 2.5D）

对于单人 + AI 资产生产的卡通项目，**纯 2D 是最务实的选择**：

- **地图**：`TileMapLayer` + 自定义 `TileSet`。草地、水域、道路、障碍物全部用 Tile。
- **单位**：`CharacterBody2D` + `Sprite2D` + 动画状态机。角色只有 4 方向或 8 方向行走/攻击动画。
- **战斗网格**：在 TileMap 之上叠加一个逻辑网格层（`AStar2D`），处理移动范围和攻击范围。
- **UI**：Godot 内置 `Control` 节点，配合 `Theme` 统一卡通风格。
- **摄像机**：`Camera2D` + 平滑跟随 + 边界限制。战斗时聚焦当前单位，大地图时可缩放。

### 2.4 关键系统设计草案

```text
SceneTree 概览（单局战斗）
├── BattleManager (AutoLoad)       # 回合状态机：PlayerTurn -> EnemyTurn -> Resolve
├── Map (Node2D)
│   ├── TileMapLayer_Ground        # 地面 Tile
│   ├── TileMapLayer_Obstacle      # 障碍物（影响 AStar）
│   └── YSortLayer                 # 单位排序
│       ├── PlayerUnits (YSort)
│       │   ├── Hero_01
│       │   └── Hero_02
│       └── EnemyUnits (YSort)
│           ├── Enemy_01
│           └── Enemy_02
├── Cursor (Node2D)                # 网格光标，处理输入 raycast
├── UI_CanvasLayer
│   ├── ActionMenu                 # 移动/攻击/待机/技能
│   ├── UnitInfoPanel              # 选中单位信息
│   └── TurnOrderBar               # 回合顺序（可选，类似 XCOM）
└── VFX_CanvasLayer                # 技能特效、伤害数字
```

**战斗回合流程（简化版）**：
1. 进入玩家回合 → 高亮可行动单位
2. 玩家选择单位 → 显示移动范围（BFS / Dijkstra）
3. 玩家指定移动位置 → 播放移动动画（AStar 路径）
4. 玩家选择行动（攻击/技能/物品/待机）
5. 行动结算 → 播放动画/VFX/伤害数字 → 判定死亡/状态
6. 所有玩家单位行动完毕 → 切换至敌人回合（基础 AI：找最近玩家 → 移动到攻击范围 → 攻击）
7. 回合结束判定胜负条件

---

## 3. AI 资产生产管线：从文案到配乐

你有 **本地 Z-Image**（图像生成）+ **充足 Kimi Token**（文本/代码），这是核心生产力杠杆。

### 3.1 文案：Kimi 是主笔，你是主编

30 小时 RPG 的文案量巨大，必须让 Kimi 批量产出，你负责审校和拼接。

#### 需要生产的文案资产

| 资产类型 | 估计量级 | AI 生产策略 |
|----------|----------|-------------|
| 主线剧情大纲 | 1 份 | Kimi 出 3 版 → 你选 1 版并细化 |
| 单章剧本（对话） | 20 章 × 20 段 | Kimi 按角色人设批量生成，统一语气 |
| 角色人设卡 | 15-20 人 | 用结构化 Prompt 输出（姓名/性格/背景/口头禅/关系网） |
| 技能/装备描述 | 100+ 条 | Kimi 从词根扩展，保持风格统一 |
| 世界观/种族/地名设定 | 1 份设定集 | Kimi 出初稿 → 你定稿后锁定为「世界观 Bible」 |
| 任务/支线文案 | 30 条 | 基于主线剧情，让 Kimi 发散支线 |
| UI 文本/提示 | 200+ 条 | 边开发边补，用 Kimi 润色 |

#### 让文案风格统一的技巧

1. **先写「风格 Bible」**：用 500 字定义你的游戏基调（例如："轻松幽默的卡通奇幻，对话简短带网络梗，避免苦大仇深"）。
2. **锁定角色 Prompt**：每个角色给 Kimi 一个固定前缀，例如 `[艾拉：元气少女骑士，说话带「本小姐」，喜欢用食物比喻]`。
3. **批量生成 + 人工筛选**：一次让 Kimi 生成 5 个版本的技能名/对话，你挑最好的。
4. **版本管理**：用你现有的 **VSCode Dendron 笔记** 管理所有文案资产！这是 SailZen 的天然优势——每个角色、每章剧情都是一个 Markdown Note，带标签和链接。

### 3.2 贴图：Z-Image 本地出图 + Krita 修正

卡通画风的 2D 贴图需求：

| 资产类型 | 数量估计 | 规格建议 | AI 方案 |
|----------|----------|----------|---------|
| 角色立绘（半身） | 15-20 张 | 512×512 或 1024×1024，透明 PNG | Z-Image 出概念图 → Krita 抠图/修正 |
| 角色战斗精灵（8 方向） | 8-12 个角色 | 每个角色 4 帧/方向，64×64 或 128×128 | **难点**。建议用 Z-Image 出正交视角角色，再用 Aseprite/Krita 手动拆分/补帧。或直接用 Spine/Live2D 做骨骼动画减少帧数。 |
| 地形 Tileset | 1 套核心 + 3-4 套主题 | 单格 32×32 或 64×64 | Z-Image 出无缝贴图 → Krita 切分/调整边缘 |
| UI 框架/按钮/图标 | 50+ 个 | 9-patch 或固定尺寸 | Z-Image 出风格参考 → 大量复用 Kenney/开源 UI 包，改色即可 |
| 技能特效/粒子纹理 | 20+ 张 | 256×256，透明 PNG | Z-Image 出单张特效元素 → Godot CPUParticles2D 组合 |
| 剧情 CG/背景 | 20 张 | 1920×1080 | Z-Image 出场景概念 → 可适当降分辨率使用 |

#### Z-Image 本地部署工作流优化

你已经本地部署了 Z-Image，建议围绕它搭建一条**批量管线**：

```
Prompt 工程（Kimi 辅助优化）
    ↓
ComfyUI / 脚本调用 Z-Image Turbo（8-12 steps，快速出图）
    ↓
批量输出到 assets/raw_ai/
    ↓
人工筛选（保留 20%，删除明显崩坏的）
    ↓
Krita / GIMP 精修（抠图、调色、改细节）
    ↓
按规范命名导入 Godot（res://assets/sprites/...）
```

**保持风格统一的关键**：
- 为 Z-Image 准备 **5-10 个固定 Negative Prompt** 和 **风格前缀**（例如：`cartoon style, top-down RPG, flat shading, bold outline, vibrant color, 2D game asset, white background`）。
- 用 **ControlNet（Canny/Depth）** 控制角色姿势和构图，避免 AI 随机发挥。
- 角色设计先做「三视图草稿」（正面/侧面/背面），用 ControlNet 锁定后再生成各方向精灵。

### 3.3 模型：2D 游戏不需要传统 3D 建模

如果你采用纯 2D 方案，"模型"指的是 **2D 骨骼动画模型** 或 **伪 3D 的堆叠切片（Stacked Sprite）**：

| 方案 | 工具 | 工作量 | 适用场景 |
|------|------|--------|----------|
| **帧动画 Sprite Sheet** | Aseprite / Krita | 高（每角色需画 32-64 帧） | 像素风、低帧卡通 |
| **2D 骨骼动画** | Spine / DragonBones / Godot Skeleton2D | 中（拆件 + 绑骨） | 现代卡通，省帧数 |
| **堆叠切片（类似 Paper Mario）** | Blender 或手动拼贴 | 中 | 伪 3D 效果，俯视角友好 |
| **AI 直接生成 Sprite Sheet** | Z-Image + 特定工作流 | 低（但一致性差） | 仅用于原型验证 |

**单人推荐方案**：
- 主角和重要 NPC 用 **2D 骨骼动画**（Spine 或 Godot 4.3+ 的 Skeleton2D）。一张立绘拆成头/身/手/脚，做行走/攻击动画只需调骨骼。
- 杂兵和小物件用 **单张 Sprite + 简单帧动画**（甚至只有 2 帧待机呼吸效果）。
- 如果一定要 3D 模型（比如想做 2.5D），用 **Blockbench** 做低多边形体素风角色，极快。

### 3.4 配乐与音效：AI 生成 + 开源库填充

| 类型 | 工具 | 策略 |
|------|------|------|
| **BGM（背景音乐）** | Suno / Udio / AIVA | 按「情绪标签」批量生成：战斗/探索/悲伤/欢快。选无歌词的 Instrumental 版。用 Audacity 剪辑成无缝循环（Loop）。 |
| **音效（SFX）** | 可灵 AI 音效 / OptimizerAI / Freesound.org | 可灵生成 10 秒内音效（剑砍、爆炸、UI 点击）。Freesound 补全环境音（风声、水流）。 |
| **语音（如有）** | ElevenLabs / 微软 Azure TTS | 仅给关键剧情配旁白/角色语音，大部分用文字+音效代替。 |

**音频管线建议**：
1. 用 Kimi 写一份「音频需求文档」，列出每首 BGM 的情绪、BPM、使用场景。
2. Suno 按批次生成（每次 2 首），下载后用 Audacity 检查是否能无缝循环——**不能循环的 BGM 在游戏中会很刺耳**。
3. 音效建立分类文件夹：`sfx/ui/`、`sfx/combat/`、`sfx/ambient/`，Godot 中用 `AudioStreamPlayer` + 字典管理。

---

## 4. 与现有 SailZen 工具链的整合

你的仓库不是空白的，这是一套**个人提效基础设施**。游戏里应复用它们。

### 4.1 已有什么？能做什么？

| 现有组件 | 在游戏项目中的角色 |
|----------|-------------------|
| **飞书 Bot / 卡片** | **CI/CD 通知 + 任务看板**。游戏构建完成后推送到飞书；用卡片做每日开发任务追踪（代替了外部项目管理工具）。 |
| **SailZen 服务器（Litestar）** | **游戏数据后台 + 内容管理**。可扩展一个「游戏 CMS」：管理关卡配置、角色数值、对话文本，甚至作为热更新服务器。 |
| **VSCode 插件（Dendron 笔记）** | **叙事设计器 +  Wiki 百科**。用 Markdown + YAML frontmatter 管理所有角色卡、剧情树、世界观设定。Dendron 的层级链接非常适合做「章节 → 场景 → 对话」的导航。 |
| **Kimi API 封装** | 已有 Python 调用层，可直接用于批量生成文案/代码辅助。 |
| **Z-Image 本地部署** | 图像资产生成节点。 |
| **Python 生态（uv + SQLAlchemy）** | 可快速搭建「游戏平衡模拟器」：用 Python 跑战斗数值模拟，验证 30 小时流程中的数值曲线。 |

### 4.2 建议的「游戏开发仪表盘」架构

利用你现成的服务器，搭一个内部用的 Web 仪表盘：

```
SailZen Server (Litestar)
├── /api/v1/game/cms
│   ├── /characters          # CRUD 角色数据
│   ├── /chapters            # 章节配置（解锁条件、关联地图）
│   ├── /levels              # 关卡数据（敌人配置、地形配置、胜利条件）
│   ├── /items               # 装备/道具数值表
│   └── /dialogues           # 对话树（可导出为 Godot JSON/CSV）
├── /api/v1/game/balance
│   └── /simulate            # 传入双方数值，跑 1000 场模拟，返回胜率
└── /api/v1/game/build
    └── /notify              # 构建完成后推飞书卡片
```

前端用你现有的 `site`（React + Tailwind）快速搭建几个表格页面即可，不需要很精美，这是**给自己用的工具**。

---

## 5. 缺失的必备工具与搭建建议

你现有的工具链偏向「通用后端/笔记/遥控」，缺少**游戏专用管线**。以下是必须补上的：

### 5.1 引擎与编辑器

| 工具 | 用途 | 优先级 |
|------|------|--------|
| **Godot 4.4+** | 游戏引擎本体 | 🔴 必须 |
| **Aseprite** 或 **PixelOver** | 像素画/精灵编辑、动画 | 🟡 高（也可用 Krita 代替） |
| **Krita**（已有 AI 插件） | 原画修正、概念设计、切图 | 🟡 高 |
| **Blender** | 如需 2.5D/3D 元素、法线贴图、简单模型 | 🟢 中 |

### 5.2 版本管理（游戏资产极占空间）

| 工具 | 用途 |
|------|------|
| **Git LFS** | 游戏仓库必须开 LFS，否则 PNG/音频/视频会迅速把 Git 撑爆 |
| **Fork** 或 **GitKraken** | 可视化管理大量资源提交（比命令行更直观） |

**建议**：游戏项目单独建一个仓库（不要塞进 SailZen），用 Git LFS 跟踪 `*.png`, `*.jpg`, `*.wav`, `*.mp3`, `*.ogg`, `*.tres`, `*.import`。

### 5.3 数据配置与平衡

| 工具 | 用途 |
|------|------|
| **CSV / JSON 配置表** | 角色数值、敌人属性、技能公式全部外置，策划驱动（你是策划+程序） |
| **Google Sheets / 飞书多维表格** | 快速填表，写脚本导出为 Godot 可读的 CSV/Resource |
| **自定义 Python 模拟器** | 用你现有的 uv + numpy 环境跑数值模拟，验证后期战斗不会刮痧/秒人 |

### 5.4 音频工具

| 工具 | 用途 |
|------|------|
| **Audacity** | BGM 剪辑、循环点处理、降噪、格式转换（导出 Ogg Vorbis 给 Godot） |
| **LMMS** 或 **Cakewalk** | 如需手动微调 AI 生成的 BGM（改某个乐器音量） |

### 5.5 叙事与关卡设计

| 工具 | 用途 |
|------|------|
| **Dendron / Obsidian（已有 VSCode 插件基础）** | 剧情树、角色关系网、世界观 Bible |
| **LDtk**（Level Designer Toolkit） | 如果你嫌 Godot TileMap 编辑器不够好用，LDtk 是 2D 关卡设计神器，可导出 JSON 再导入 Godot |
| **draw.io / Excalidraw** | 画战斗流程图、UI 线框图、关卡布局草图 |

### 5.6 构建与发布

| 工具 | 用途 |
|------|------|
| **Godot Export Templates** | 导出 Windows / Web / Android |
| **GitHub Actions / 自建 CI** | 每次推主分支自动导出可执行文件（可用你现有的服务器做 Runner） |
| **butler（itch.io）** | 一键推送到 itch.io 供测试分发 |

---

## 6. 开发里程碑（MVP → 完整版）

单人开发最忌「同时做所有事」。按这个顺序推进：

### Phase 0：工具链验证（1-2 周）

- [ ] Godot 4.4 安装，跑通 GDQuest Tactical RPG Movement Demo
- [ ] Z-Image 本地 ComfyUI 工作流调通，产出第一批角色概念图（3-5 个）
- [ ] Kimi 生成第一章剧本 + 5 个角色人设，导入 Dendron 笔记
- [ ] 搭建 Git 仓库 + Git LFS

### Phase 1：战斗原型（3-4 周）

- [ ] 实现网格移动 + AStar 寻路（从 GDQuest Demo 提取）
- [ ] 实现回合制基础：选中单位 → 移动 → 攻击 → 结束回合
- [ ] 1 个玩家角色 + 1 种敌人，1 张测试地图
- [ ] 基础 UI：血条、行动菜单、回合提示
- [ ] **可玩标准**：能打完一场 2 分钟的小战斗

### Phase 2：内容管线打通（3-4 周）

- [ ] 将角色数值、敌人配置外置到 CSV/JSON
- [ ] 用 Kimi 批量生成前 5 章对话，接入游戏内对话系统
- [ ] 用 Z-Image 产出主角 4 方向精灵 + 1 套地形 Tileset
- [ ] 接入 Suno BGM（3 首：探索/战斗/营地）
- [ ] **可玩标准**：能打完一章带剧情的完整流程（探索+战斗+对话）

### Phase 3：规模量产（8-12 周）

- [ ] 按「每周 1.5 章」的速度推进主线（需配合 AI 批量出文案/贴图）
- [ ] 完成 3 个可控角色 + 5 种敌人原型
- [ ] 搭建养成系统：经验值、升级、技能树（简版）
- [ ] 接入 SailZen 内部 CMS 管理关卡数据

### Phase 4：打磨与发布（4-6 周）

- [ ] 难度曲线测试（用 Python 跑模拟器验证）
- [ ] UI/UX 统一美化（字体、动效、过渡动画）
- [ ] 全文本审校、存档系统、设置菜单
- [ ] 导出 Web Demo（放 itch.io 收集反馈）→ 修正 → 导出完整版

---

## 7. AI 分工总览：谁做什么？

| 工作流 | 主力 | 你的角色 | 产出物 |
|--------|------|----------|--------|
| 代码框架 | **Kimi**（辅助生成 GDScript）+ 你 | 审校、调试、性能优化 | `.gd` 脚本、场景 `.tscn` |
| 剧情文案 | **Kimi** | 给方向、审校、拼接 | Markdown 剧本（存 Dendron） |
| 概念原画/贴图 | **Z-Image** | Prompt 工程、筛选、Krita 精修 | PNG Sprite、Tileset |
| 角色动画 | **你**（Spine/骨骼） | AI 暂无法稳定出连贯动画 | 骨骼文件 / Sprite Sheet |
| BGM/音效 | **Suno + 可灵** | 选曲、剪辑、循环处理 | Ogg 音频文件 |
| 数值设计 | **Python 模拟器** + 你 | 定公式、调参数 | 平衡报告、CSV 配置 |
| 关卡设计 | **你** | 手工摆放，AI 可做灵感发散 | Godot 场景 / LDtk 文件 |
| 测试构建 | **GitHub Actions / 自建 CI** | 看报错、修 Bug | 可执行文件 |

---

## 8. 风险控制：单人开发 30 小时游戏的常见死因

1. **画风漂移**：Z-Image 出图不稳定，第 1 章和第 10 章角色像两个游戏。**解法**：开头花 3 天锁定「风格 Bible + 固定 Prompt 模板 + 参考图集」，后期只微调。
2. **战斗系统过度设计**：想做出 *Fire Emblem* 的武器三角 + *XCOM* 的掩体 + *Disgaea* 的投掷……**解法**：只做「移动+普攻+2 个技能+待机」，其他系统发售后更新。
3. **文案写不完**：30 小时对应数万字对话。**解法**：Kimi 批量产出，你只做「主编」不做「主笔」。用 Dendron 的模板笔记快速结构化生成 Prompt。
4. **后期数值崩坏**：前期一刀一个，后期刮痧 50 回合。**解法**：第 2 周就写好 Python 模拟器，跑 1000 场自动化战斗，监控 TTK（Time To Kill）。
5. **没有随时可玩的版本**：做了 3 个月还是黑屏代码。**解法**：Phase 1 结束就必须有一个「能打完一场战斗」的可执行文件，每周都保持可运行状态。

---

## 9. 立即行动的 Checklist

- [ ] 新建 Git 仓库（独立 repo，开启 Git LFS）
- [ ] 下载 Godot 4.4，导入 GDQuest Tactical RPG + ramaureirac/godot-tactical-rpg 学习
- [ ] 在 Dendron 里新建 `game-design/` 层级，写入：世界观 Bible、风格指南、角色模板
- [ ] 调通 Z-Image 批量出图脚本（1 个 Prompt 出 4 张图自动保存）
- [ ] 用 Kimi 生成「第 1 章剧本 + 3 个角色人设」作为试金石
- [ ] 在 SailZen Server 里规划 `/api/v1/game/` 路由，搭建最小 CMS
- [ ] 注册 itch.io 账号，预留游戏页面

---

> **最后一句**：这是一个「工程问题」，不是「艺术问题」。30 小时的独立游戏不需要每个像素都完美，它需要**可运行的版本、稳定的内容产出管线、以及你持续 6 个月的执行力**。AI 已经抹平了 70% 的资产成本——剩下的 30%，是用你的工程能力把碎片拼成完整的体验。
