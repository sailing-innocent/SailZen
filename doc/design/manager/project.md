# 项目管理功能

## 概述

项目管理模块是 SailZen 系统中的任务与目标管理核心功能，提供项目规划、任务追踪、进度管理和个人日程协调能力。本模块与生活预算和健康管理模块深度联动，实现全方位的个人生活管理。

### 功能定位

- **项目规划**：管理个人或工作项目的生命周期
- **任务追踪**：创建、分解和追踪任务执行
- **进度管理**：可视化项目和任务进度
- **日程协调**：与个人日程、健康状态协调任务安排
- **推送提醒**：及时推送任务截止、里程碑等重要事件

### 系统架构

```
┌─────────────────────────────────────────────────────────────┐
│                    Frontend (packages/site)                  │
├─────────────────────────────────────────────────────────────┤
│  Pages: project.tsx                                          │
│  Components: project_*, mission_*, quarter_biweek_calendar   │
│  Store: Zustand (useProjectsStore, useMissionsStore)         │
│  API Client: lib/api/project.ts                              │
├─────────────────────────────────────────────────────────────┤
│                    Backend (sail_server)                     │
├─────────────────────────────────────────────────────────────┤
│  Controllers: project.py (Project/Mission)                   │
│  Models: model/project.py                                    │
│  Data: data/project.py (ORM models)                          │
│  Utils: utils/time_utils.py (QuarterBiWeekTime)              │
└─────────────────────────────────────────────────────────────┘
```

---

## 1. 核心概念与数据模型

### 1.1 项目 (Project) ✅ 已实现

项目是目标的载体，代表一个有明确起止时间的工作集合。

| 字段 | 类型 | 说明 | 实现状态 |
|------|------|------|----------|
| id | Integer | 主键，自增 | ✅ |
| name | String | 项目名称（必填） | ✅ |
| description | String | 项目描述 | ✅ |
| state | Integer | 项目状态（状态机） | ✅ |
| start_time | Integer | 开始时间（QuarterBiWeekTime） | ✅ |
| end_time | Integer | 结束时间（QuarterBiWeekTime） | ✅ |
| ctime | TIMESTAMP | 创建时间 | ✅ |
| mtime | TIMESTAMP | 修改时间 | ✅ |
| priority | Integer | 优先级（1-5） | ❌ 待实现 |
| budget_id | Integer | 关联预算ID | ❌ 待实现 |
| progress | Float | 完成进度（0-100%） | ❌ 待实现 |
| tags | String | 标签（逗号分隔） | ❌ 待实现 |

**项目状态机** ✅ 已实现：

```
INVALID(0) → VALID(1) → PREPARE(2) → TRACKING(3) → DONE(4)
                                  ↓         ↑
                              PENDING(5) ───┘
                                  
任意状态 → CANCELED(6)
```

| 状态 | 值 | 说明 |
|------|-----|------|
| INVALID | 0 | 无效/草稿 |
| VALID | 1 | 已验证/待开始 |
| PREPARE | 2 | 准备中 |
| TRACKING | 3 | 进行中 |
| DONE | 4 | 已完成 |
| PENDING | 5 | 暂停中 |
| CANCELED | 6 | 已取消 |

### 1.2 任务/使命 (Mission) ✅ 已实现

任务是项目的基本执行单元，支持层级结构。

| 字段 | 类型 | 说明 | 实现状态 |
|------|------|------|----------|
| id | Integer | 主键，自增 | ✅ |
| name | String | 任务名称（必填） | ✅ |
| description | String | 任务描述 | ✅ |
| parent_id | Integer | 父任务ID（层级结构） | ✅ |
| project_id | Integer | 所属项目ID | ✅ |
| state | Integer | 任务状态（状态机） | ✅ |
| ddl | TIMESTAMP | 截止日期 | ✅ |
| lft | Integer | 嵌套集模型左值 | ✅ |
| rgt | Integer | 嵌套集模型右值 | ✅ |
| tree_id | Integer | 树ID | ✅ |
| ctime | TIMESTAMP | 创建时间 | ✅ |
| mtime | TIMESTAMP | 修改时间 | ✅ |
| priority | Integer | 优先级（1-5） | ❌ 待实现 |
| estimated_hours | Float | 预估工时 | ❌ 待实现 |
| actual_hours | Float | 实际工时 | ❌ 待实现 |
| assignee | String | 负责人 | ❌ 待实现 |
| tags | String | 标签 | ❌ 待实现 |
| reminder_time | TIMESTAMP | 提醒时间 | ❌ 待实现 |

**任务状态机** ✅ 已实现：

```
PENDING(0) → READY(1) → DOING(2) → DONE(3)

任意状态 → CANCELED(4)
```

| 状态 | 值 | 说明 |
|------|-----|------|
| PENDING | 0 | 待办/阻塞 |
| READY | 1 | 就绪/可开始 |
| DOING | 2 | 进行中 |
| DONE | 3 | 已完成 |
| CANCELED | 4 | 已取消 |

### 1.3 里程碑 (Milestone) ❌ 待实现

里程碑是项目的关键节点，用于标记重要阶段。

| 字段 | 类型 | 说明 |
|------|------|------|
| id | Integer | 主键，自增 |
| project_id | Integer | 所属项目ID |
| name | String | 里程碑名称 |
| description | String | 描述 |
| target_date | TIMESTAMP | 目标日期 |
| actual_date | TIMESTAMP | 实际完成日期 |
| status | String | 状态：pending/completed/missed |
| linked_missions | JSON | 关联的任务ID列表 |

### 1.4 日程事件 (Schedule) ❌ 待实现

日程事件用于个人时间规划，可与任务关联。

| 字段 | 类型 | 说明 |
|------|------|------|
| id | Integer | 主键，自增 |
| title | String | 事件标题 |
| description | String | 描述 |
| start_time | TIMESTAMP | 开始时间 |
| end_time | TIMESTAMP | 结束时间 |
| all_day | Boolean | 是否全天事件 |
| recurrence | String | 重复规则（RRULE格式） |
| mission_id | Integer | 关联任务ID（可选） |
| reminder_before | Integer | 提前提醒时间（分钟） |
| category | String | 分类：work/personal/health/finance |
| location | String | 地点 |
| status | String | 状态：scheduled/completed/cancelled |

### 1.5 提醒 (Reminder) ❌ 待实现

提醒用于推送通知，支持多种触发条件。

| 字段 | 类型 | 说明 |
|------|------|------|
| id | Integer | 主键，自增 |
| title | String | 提醒标题 |
| message | String | 提醒内容 |
| trigger_time | TIMESTAMP | 触发时间 |
| trigger_type | String | 触发类型：time/location/condition |
| related_type | String | 关联类型：mission/project/schedule/milestone |
| related_id | Integer | 关联对象ID |
| repeat_rule | String | 重复规则 |
| status | String | 状态：pending/sent/dismissed/snoozed |
| channels | JSON | 推送渠道：["push", "email", "wechat"] |

---

## 2. 后端 API 接口

### 2.1 项目接口 (`/api/project`) ✅ 部分实现

| 方法 | 路径 | 说明 | 实现状态 |
|------|------|------|----------|
| GET | `/` | 获取项目列表（支持分页） | ✅ |
| GET | `/{id}` | 获取项目详情 | ✅ |
| POST | `/` | 创建项目 | ✅ |
| PUT | `/{id}` | 更新项目 | ✅ |
| DELETE | `/{id}` | 删除项目 | ✅ |
| POST | `/{id}/state/{action}` | 状态转换 | ❌ 模型层已实现，API 待暴露 |
| GET | `/{id}/progress` | 获取项目进度 | ❌ 待实现 |
| GET | `/{id}/stats` | 获取项目统计 | ❌ 待实现 |
| GET | `/search` | 搜索项目 | ❌ 待实现 |

### 2.2 任务接口 (`/api/mission`) ✅ 部分实现

| 方法 | 路径 | 说明 | 实现状态 |
|------|------|------|----------|
| GET | `/` | 获取任务列表（支持筛选） | ✅ |
| GET | `/{id}` | 获取任务详情 | ✅ |
| POST | `/` | 创建任务 | ✅ |
| PUT | `/{id}` | 更新任务 | ✅ |
| DELETE | `/{id}` | 删除任务 | ✅ |
| POST | `/{id}/state/{action}` | 状态转换 | ❌ 模型层已实现，API 待暴露 |
| GET | `/overdue` | 获取逾期任务 | ❌ 待实现 |
| GET | `/upcoming` | 获取即将到期任务 | ❌ 待实现 |
| GET | `/today` | 获取今日任务 | ❌ 待实现 |
| POST | `/{id}/time-log` | 记录工时 | ❌ 待实现 |

### 2.3 里程碑接口 (`/api/milestone`) ❌ 待实现

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/` | 获取里程碑列表 |
| GET | `/{id}` | 获取里程碑详情 |
| POST | `/` | 创建里程碑 |
| PUT | `/{id}` | 更新里程碑 |
| DELETE | `/{id}` | 删除里程碑 |
| POST | `/{id}/complete` | 完成里程碑 |

### 2.4 日程接口 (`/api/schedule`) ❌ 待实现

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/` | 获取日程列表（按时间范围） |
| GET | `/{id}` | 获取日程详情 |
| POST | `/` | 创建日程 |
| PUT | `/{id}` | 更新日程 |
| DELETE | `/{id}` | 删除日程 |
| GET | `/day/{date}` | 获取指定日期日程 |
| GET | `/week/{date}` | 获取指定周日程 |
| GET | `/month/{year}/{month}` | 获取指定月日程 |
| POST | `/from-mission/{mission_id}` | 从任务创建日程 |
| GET | `/conflicts` | 检测日程冲突 |

### 2.5 提醒接口 (`/api/reminder`) ❌ 待实现

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/` | 获取提醒列表 |
| GET | `/pending` | 获取待发送提醒 |
| POST | `/` | 创建提醒 |
| PUT | `/{id}` | 更新提醒 |
| DELETE | `/{id}` | 删除提醒 |
| POST | `/{id}/dismiss` | 关闭提醒 |
| POST | `/{id}/snooze` | 稍后提醒 |

---

## 3. 前端功能模块

### 3.1 主页面布局 (`project.tsx`) ✅ 已实现

页面采用响应式设计：
- **桌面端**：看板区域(60%) + 日历区域(40%)
- **移动端**：垂直堆叠布局

主要区域：
1. ✅ 项目看板区
2. ✅ 季度双周日历
3. ❌ 任务筛选器（待实现）
4. ❌ 进度仪表盘（待实现）

### 3.2 项目管理组件

| 组件 | 文件 | 功能 | 实现状态 |
|------|------|------|----------|
| ProjectAddDialog | `project_add_dialog.tsx` | 新建项目对话框 | ✅ |
| ProjectMissionBoard | `project_mission_board.tsx` | 看板视图 | ✅ |
| ProjectMissionColumn | `project_mission_column.tsx` | 项目任务列 | ✅ |
| ProjectEditDialog | - | 编辑项目对话框 | ❌ 待实现 |
| ProjectCard | - | 项目卡片 | ❌ 待实现 |
| ProjectProgress | - | 项目进度条 | ❌ 待实现 |
| ProjectStats | - | 项目统计仪表盘 | ❌ 待实现 |

### 3.3 任务管理组件

| 组件 | 文件 | 功能 | 实现状态 |
|------|------|------|----------|
| MissionAddDialog | `mission_add_dialog.tsx` | 新建任务对话框 | ✅ |
| MissionEditDialog | - | 编辑任务对话框 | ❌ 待实现 |
| MissionCard | - | 任务卡片 | ❌ 待实现 |
| MissionList | - | 任务列表视图 | ❌ 待实现 |
| MissionTree | - | 任务树形视图 | ❌ 待实现 |
| MissionFilters | - | 任务筛选器 | ❌ 待实现 |
| MissionKanban | - | 任务看板（按状态） | ❌ 待实现 |

### 3.4 日程管理组件 ❌ 待实现

| 组件 | 文件 | 功能 |
|------|------|------|
| ScheduleCalendar | - | 日程日历视图 |
| ScheduleDayView | - | 日视图 |
| ScheduleWeekView | - | 周视图 |
| ScheduleMonthView | - | 月视图 |
| ScheduleEventCard | - | 日程事件卡片 |
| ScheduleAddDialog | - | 新建日程对话框 |
| ScheduleQuickAdd | - | 快速添加日程 |

### 3.5 提醒与通知组件 ❌ 待实现

| 组件 | 文件 | 功能 |
|------|------|------|
| ReminderBell | - | 提醒铃铛图标（显示未读数） |
| ReminderDropdown | - | 提醒下拉列表 |
| ReminderCard | - | 提醒卡片 |
| ReminderSettingsDialog | - | 提醒设置对话框 |
| NotificationToast | - | 通知弹窗 |

### 3.6 日历组件 ✅ 部分实现

| 组件 | 文件 | 功能 | 实现状态 |
|------|------|------|----------|
| QuarterBiweekCalendar | `quarter_biweek_calendar.tsx` | 季度双周日历 | ✅ |
| DatePicker | `date_picker.tsx` | 日期选择器 | ✅ |
| Calendar | `ui/calendar.tsx` | 基础日历组件 | ✅ |

---

## 4. 进度跟踪功能 ❌ 待实现

### 4.1 项目进度计算

项目进度基于以下维度计算：

1. **任务完成度**：已完成任务数 / 总任务数
2. **里程碑进度**：已完成里程碑 / 总里程碑
3. **时间进度**：(当前时间 - 开始时间) / (结束时间 - 开始时间)
4. **工时进度**：实际工时 / 预估总工时

**综合进度公式**：

```python
def calculate_project_progress(project):
    task_weight = 0.5
    milestone_weight = 0.3
    time_weight = 0.2
    
    task_progress = completed_tasks / total_tasks if total_tasks > 0 else 0
    milestone_progress = completed_milestones / total_milestones if total_milestones > 0 else 0
    time_progress = (now - start_time) / (end_time - start_time)
    
    return (task_progress * task_weight + 
            milestone_progress * milestone_weight + 
            min(time_progress, 1.0) * time_weight)
```

### 4.2 进度仪表盘

**统计卡片**：
- 项目总数 / 进行中 / 已完成
- 本周新增任务 / 完成任务
- 逾期任务数
- 平均任务完成时间

**图表**：
- 项目进度甘特图
- 任务燃尽图
- 任务分布饼图（按状态）
- 每周任务完成趋势

---

## 5. 推送提醒功能 ❌ 待实现

### 5.1 提醒触发器

| 触发类型 | 说明 | 示例 |
|----------|------|------|
| deadline_approaching | 截止日期临近 | 任务截止前24小时 |
| deadline_overdue | 任务逾期 | 超过截止日期 |
| milestone_due | 里程碑到期 | 里程碑日期当天 |
| schedule_start | 日程开始 | 日程开始前15分钟 |
| daily_summary | 每日摘要 | 每天早上8点 |
| weekly_review | 周报回顾 | 每周日晚上8点 |
| project_stale | 项目停滞 | 一周无进展 |
| health_balance | 健康平衡提醒 | 连续工作超时 |

### 5.2 推送渠道

```python
class NotificationChannel:
    PUSH = "push"           # 浏览器推送通知
    EMAIL = "email"         # 邮件通知
    WECHAT = "wechat"       # 微信通知（通过企业微信/公众号）
    SMS = "sms"             # 短信通知（紧急事项）
    IN_APP = "in_app"       # 应用内通知
```

### 5.3 提醒设置

```typescript
interface ReminderSettings {
  // 任务提醒
  task_deadline_hours: number[]  // 提前多少小时提醒，如 [24, 2, 0.5]
  task_overdue_enabled: boolean  // 是否提醒逾期
  
  // 日程提醒
  schedule_reminder_minutes: number[]  // 提前多少分钟提醒，如 [30, 10]
  
  // 每日摘要
  daily_summary_enabled: boolean
  daily_summary_time: string  // "08:00"
  
  // 周报
  weekly_review_enabled: boolean
  weekly_review_day: number  // 0-6，周日到周六
  weekly_review_time: string
  
  // 推送渠道偏好
  channels: {
    urgent: string[]    // 紧急事项渠道
    normal: string[]    // 普通事项渠道
    summary: string[]   // 摘要类渠道
  }
  
  // 免打扰时间
  quiet_hours: {
    enabled: boolean
    start: string  // "22:00"
    end: string    // "08:00"
  }
}
```

### 5.4 后端推送服务

```python
class NotificationService:
    async def schedule_task_reminders(self, mission: Mission):
        """根据任务截止日期安排提醒"""
        settings = await self.get_user_settings(mission.user_id)
        
        for hours_before in settings.task_deadline_hours:
            remind_time = mission.ddl - timedelta(hours=hours_before)
            if remind_time > datetime.now():
                await self.create_reminder(
                    title=f"任务即将到期: {mission.name}",
                    message=f"距离截止还有 {hours_before} 小时",
                    trigger_time=remind_time,
                    related_type="mission",
                    related_id=mission.id
                )
    
    async def send_daily_summary(self, user_id: int):
        """发送每日任务摘要"""
        today_tasks = await self.get_today_tasks(user_id)
        overdue_tasks = await self.get_overdue_tasks(user_id)
        upcoming_tasks = await self.get_upcoming_tasks(user_id, days=3)
        
        summary = self.format_daily_summary(today_tasks, overdue_tasks, upcoming_tasks)
        await self.send_notification(user_id, "每日任务摘要", summary, ["push", "email"])
    
    async def check_project_stale(self, project: Project):
        """检查项目是否停滞"""
        last_activity = await self.get_last_activity(project.id)
        if datetime.now() - last_activity > timedelta(days=7):
            await self.send_notification(
                project.user_id,
                f"项目停滞提醒: {project.name}",
                "该项目已一周没有更新，请检查进度",
                ["push"]
            )
```

---

## 6. 日程规划功能 ❌ 待实现

### 6.1 智能日程建议

基于任务信息自动建议日程安排：

```python
class ScheduleSuggestionService:
    async def suggest_schedule_for_mission(self, mission: Mission) -> List[ScheduleSuggestion]:
        """为任务建议时间段"""
        suggestions = []
        
        # 获取用户空闲时间
        busy_times = await self.get_busy_times(mission.user_id, mission.ddl)
        free_slots = self.calculate_free_slots(busy_times, mission.estimated_hours)
        
        # 考虑任务优先级
        if mission.priority >= 4:  # 高优先级
            suggestions.extend(self.prioritize_early_slots(free_slots))
        
        # 考虑健康因素
        health_status = await self.get_health_status(mission.user_id)
        if health_status.fatigue_level > 7:
            suggestions = self.filter_intense_work_slots(suggestions)
        
        return suggestions
    
    def auto_schedule_missions(self, missions: List[Mission], constraints: ScheduleConstraints):
        """自动为多个任务安排日程"""
        # 按优先级和截止日期排序
        sorted_missions = sorted(missions, key=lambda m: (m.priority * -1, m.ddl))
        
        scheduled = []
        for mission in sorted_missions:
            best_slot = self.find_best_slot(mission, scheduled, constraints)
            if best_slot:
                scheduled.append(Schedule(
                    mission_id=mission.id,
                    start_time=best_slot.start,
                    end_time=best_slot.end
                ))
        
        return scheduled
```

### 6.2 日程冲突检测

```python
def detect_schedule_conflicts(schedules: List[Schedule]) -> List[Conflict]:
    """检测日程冲突"""
    conflicts = []
    sorted_schedules = sorted(schedules, key=lambda s: s.start_time)
    
    for i, s1 in enumerate(sorted_schedules):
        for s2 in sorted_schedules[i+1:]:
            if s2.start_time >= s1.end_time:
                break
            if s1.end_time > s2.start_time:
                conflicts.append(Conflict(s1, s2, calculate_overlap(s1, s2)))
    
    return conflicts
```

### 6.3 时间块规划（Time Blocking）

支持将一天划分为不同类型的时间块：

```python
class TimeBlock:
    DEEP_WORK = "deep_work"       # 深度工作
    SHALLOW_WORK = "shallow_work" # 浅层工作
    MEETING = "meeting"           # 会议
    BREAK = "break"               # 休息
    PERSONAL = "personal"         # 个人时间
    HEALTH = "health"             # 健康活动

# 示例：每日时间块模板
daily_template = [
    TimeBlock("09:00", "11:30", TimeBlock.DEEP_WORK),
    TimeBlock("11:30", "12:00", TimeBlock.SHALLOW_WORK),
    TimeBlock("12:00", "13:30", TimeBlock.BREAK),
    TimeBlock("13:30", "15:00", TimeBlock.MEETING),
    TimeBlock("15:00", "17:30", TimeBlock.DEEP_WORK),
    TimeBlock("17:30", "18:00", TimeBlock.HEALTH),
]
```

---

## 7. 模块联动设计

### 7.1 与生活预算模块联动

#### 项目预算管理

```python
class ProjectBudget:
    """项目预算关联"""
    project_id: int
    budget_id: int          # 关联到 finance.Budget
    allocated_amount: str   # 分配金额
    spent_amount: str       # 已支出
    
    @property
    def remaining(self):
        return Money(self.allocated_amount) - Money(self.spent_amount)
```

**联动功能**：

1. **创建项目时关联预算**
   - 可选择创建新预算或关联现有预算
   - 预算标签自动包含项目名称

2. **任务支出追踪**
   - 任务可关联交易记录
   - 完成任务时提示记录相关支出

3. **项目成本统计**
   - 项目详情页显示成本统计
   - 按任务/时间段/标签分析支出

4. **预算超支提醒**
   - 项目支出接近预算时提醒
   - 支持设置预算阈值（如80%、100%）

#### 数据同步

```python
# 创建项目时同步创建预算
async def create_project_with_budget(project_data, budget_data):
    project = await create_project(project_data)
    if budget_data:
        budget = await create_budget({
            **budget_data,
            "tags": f"project:{project.id},{budget_data.get('tags', '')}"
        })
        project.budget_id = budget.id
        await update_project(project)
    return project

# 项目完成时汇总预算使用情况
async def complete_project(project_id):
    project = await get_project(project_id)
    if project.budget_id:
        analysis = await get_budget_analysis(project.budget_id)
        await create_project_cost_report(project_id, analysis)
    await update_project_state(project_id, "DONE")
```

### 7.2 与健康模块联动

#### 健康感知任务调度

```python
class HealthAwareScheduler:
    """考虑健康状态的任务调度"""
    
    async def adjust_schedule_for_health(self, user_id: int, schedules: List[Schedule]):
        """根据健康状态调整日程"""
        
        # 获取近期健身记录
        fitness_stats = await get_fitness_stats(user_id, days=7)
        
        # 获取体重趋势
        weight_trend = await get_weight_trend(user_id, days=30)
        
        # 计算疲劳指数
        fatigue_score = self.calculate_fatigue(
            recent_work_hours=await get_work_hours(user_id, days=7),
            sleep_quality=await get_sleep_data(user_id),
            exercise_frequency=fitness_stats.total_sessions
        )
        
        adjustments = []
        
        if fatigue_score > 7:
            # 高疲劳：减少工作密度，增加休息
            adjustments.append(AdjustmentSuggestion(
                type="reduce_density",
                message="您近期疲劳程度较高，建议减少工作强度"
            ))
        
        if fitness_stats.total_sessions < 3:
            # 运动不足：建议安排运动时间
            adjustments.append(AdjustmentSuggestion(
                type="add_exercise",
                message="本周运动次数不足，建议安排健身时间",
                suggested_slots=self.find_exercise_slots(schedules)
            ))
        
        return adjustments
```

#### 健康打卡影响任务优先级

```python
def adjust_priority_for_health(mission: Mission, health_status: HealthStatus) -> int:
    """根据健康状态调整任务优先级"""
    base_priority = mission.priority
    
    # 如果用户健康状况不佳，降低非紧急任务优先级
    if health_status.condition in ["sick", "fatigued"]:
        if not mission.is_urgent:
            return max(1, base_priority - 1)
    
    # 如果是健康相关任务，在健康状况不佳时提升优先级
    if "health" in mission.tags:
        if health_status.condition != "good":
            return min(5, base_priority + 1)
    
    return base_priority
```

#### 智能休息提醒

```python
class WorkHealthBalance:
    """工作健康平衡管理"""
    
    async def check_work_balance(self, user_id: int):
        """检查工作生活平衡"""
        
        today_schedules = await get_today_schedules(user_id)
        work_hours = sum(s.duration for s in today_schedules if s.category == "work")
        
        # 连续工作超过2小时提醒休息
        current_work_streak = self.get_current_work_streak(today_schedules)
        if current_work_streak > timedelta(hours=2):
            await send_break_reminder(user_id, "已连续工作2小时，建议休息10分钟")
        
        # 每日工作超过8小时提醒
        if work_hours > 8:
            await send_notification(
                user_id,
                "工作时长提醒",
                f"今日已工作{work_hours:.1f}小时，注意休息",
                priority="normal"
            )
        
        # 结合健身目标
        fitness_goal = await get_active_fitness_goal(user_id)
        if fitness_goal and not await has_exercise_today(user_id):
            await send_notification(
                user_id,
                "运动提醒",
                "今天还没有运动记录，别忘了锻炼身体",
                priority="low"
            )
```

### 7.3 跨模块仪表盘

创建一个综合仪表盘，整合三个模块的关键数据：

```typescript
interface IntegratedDashboard {
  // 项目管理
  projects: {
    active_count: number
    tasks_today: number
    overdue_tasks: number
    completion_rate_week: number
  }
  
  // 生活预算
  finance: {
    balance_total: string
    spent_this_month: string
    budget_remaining: string
    spending_vs_plan: number  // 实际/计划 比率
  }
  
  // 健康管理
  health: {
    weight_trend: 'up' | 'down' | 'stable'
    exercise_this_week: number
    health_score: number  // 0-100 综合健康评分
    streak_days: number   // 连续打卡天数
  }
  
  // 综合建议
  suggestions: IntegratedSuggestion[]
}

interface IntegratedSuggestion {
  type: 'warning' | 'info' | 'success'
  module: 'project' | 'finance' | 'health'
  title: string
  message: string
  action?: {
    label: string
    link: string
  }
}
```

---

## 8. 状态管理 (Zustand)

### 8.1 ProjectsStore ✅ 部分实现

```typescript
interface ProjectsStore {
  // 状态
  projects: ProjectData[]
  currentProject: ProjectData | null
  isLoading: boolean
  
  // 已实现
  fetchProjects: (skip?: number, limit?: number) => Promise<void>  // ✅
  createProject: (project: ProjectCreateProps) => Promise<void>    // ✅
  
  // 待实现
  updateProject: (id: number, updates: Partial<ProjectData>) => Promise<void>  // ❌
  deleteProject: (id: number) => Promise<void>                                  // ❌
  getProjectById: (id: number) => Promise<ProjectData>                          // ❌
  changeProjectState: (id: number, action: string) => Promise<void>             // ❌
  getProjectProgress: (id: number) => Promise<ProjectProgress>                  // ❌
  getProjectStats: (id: number) => Promise<ProjectStats>                        // ❌
}
```

### 8.2 MissionsStore ✅ 部分实现

```typescript
interface MissionsStore {
  // 状态
  missions: MissionData[]
  isLoading: boolean
  
  // 已实现
  fetchMissions: (params?: MissionQueryParams) => Promise<void>   // ✅
  createMission: (mission: MissionCreateProps) => Promise<void>   // ✅
  
  // 待实现
  updateMission: (id: number, updates: Partial<MissionData>) => Promise<void>  // ❌
  deleteMission: (id: number) => Promise<void>                                  // ❌
  changeMissionState: (id: number, action: string) => Promise<void>             // ❌
  getOverdueMissions: () => Promise<MissionData[]>                              // ❌
  getUpcomingMissions: (days: number) => Promise<MissionData[]>                 // ❌
  getTodayMissions: () => Promise<MissionData[]>                                // ❌
}
```

### 8.3 ScheduleStore ❌ 待实现

```typescript
interface ScheduleStore {
  schedules: ScheduleData[]
  selectedDate: Date
  viewMode: 'day' | 'week' | 'month'
  isLoading: boolean
  
  fetchSchedules: (start: Date, end: Date) => Promise<void>
  createSchedule: (schedule: ScheduleCreateProps) => Promise<void>
  updateSchedule: (id: number, updates: Partial<ScheduleData>) => Promise<void>
  deleteSchedule: (id: number) => Promise<void>
  createFromMission: (missionId: number, slotData: TimeSlot) => Promise<void>
  checkConflicts: (schedule: ScheduleData) => Promise<Conflict[]>
  setSelectedDate: (date: Date) => void
  setViewMode: (mode: 'day' | 'week' | 'month') => void
}
```

### 8.4 ReminderStore ❌ 待实现

```typescript
interface ReminderStore {
  reminders: ReminderData[]
  unreadCount: number
  settings: ReminderSettings
  isLoading: boolean
  
  fetchReminders: () => Promise<void>
  createReminder: (reminder: ReminderCreateProps) => Promise<void>
  dismissReminder: (id: number) => Promise<void>
  snoozeReminder: (id: number, minutes: number) => Promise<void>
  updateSettings: (settings: Partial<ReminderSettings>) => Promise<void>
  markAsRead: (ids: number[]) => Promise<void>
}
```

---

## 9. 实现优先级

### Phase 1: 基础完善（建议优先实现）

1. **项目状态转换 API** - 暴露已有的状态机方法
2. **任务编辑/删除功能** - 完善 CRUD
3. **项目编辑/删除功能** - 完善 CRUD
4. **任务筛选器** - 支持按状态/项目/截止日期筛选
5. **任务状态看板** - 按状态分列展示任务

### Phase 2: 进度追踪

1. **项目进度计算** - 实现进度计算逻辑
2. **进度仪表盘** - 统计卡片和图表
3. **任务燃尽图** - 可视化进度趋势
4. **里程碑管理** - 数据模型和 CRUD

### Phase 3: 日程规划

1. **日程数据模型** - 实现 Schedule 表
2. **日程日历视图** - 日/周/月视图
3. **任务-日程关联** - 从任务创建日程
4. **日程冲突检测** - 冲突提示和建议

### Phase 4: 推送提醒

1. **提醒数据模型** - 实现 Reminder 表
2. **提醒触发器** - 定时任务检查和触发
3. **浏览器推送** - Web Push 通知
4. **提醒设置** - 用户偏好配置

### Phase 5: 模块联动

1. **项目预算关联** - 与生活预算联动
2. **健康感知调度** - 与健康模块联动
3. **综合仪表盘** - 跨模块数据整合

---

## 10. 技术要点

### 10.1 时间管理

系统使用 `QuarterBiWeekTime` 进行项目时间规划：

```python
class QuarterBiWeekTime:
    """季度双周时间表示"""
    year: int
    quarter: int  # 1-4
    biweek: int   # 1-6 (每季度6个双周)
    
    def to_date_range(self) -> Tuple[date, date]:
        """转换为日期范围"""
        pass
    
    @classmethod
    def from_date(cls, d: date) -> 'QuarterBiWeekTime':
        """从日期创建"""
        pass
```

### 10.2 嵌套集模型

任务使用嵌套集模型（Nested Set Model）实现树形结构：

```sql
-- 查询某任务的所有子任务
SELECT * FROM missions 
WHERE tree_id = ? AND lft > ? AND rgt < ?
ORDER BY lft;

-- 查询某任务的祖先链
SELECT * FROM missions 
WHERE tree_id = ? AND lft < ? AND rgt > ?
ORDER BY lft;
```

### 10.3 定时任务

提醒系统需要后台定时任务：

```python
# 使用 APScheduler 或 Celery
from apscheduler.schedulers.asyncio import AsyncIOScheduler

scheduler = AsyncIOScheduler()

# 每分钟检查待发送提醒
@scheduler.scheduled_job('interval', minutes=1)
async def check_pending_reminders():
    pending = await get_pending_reminders()
    for reminder in pending:
        await send_reminder(reminder)

# 每天早上发送每日摘要
@scheduler.scheduled_job('cron', hour=8)
async def send_daily_summaries():
    users = await get_users_with_summary_enabled()
    for user in users:
        await send_daily_summary(user.id)
```

---

## 11. 待办事项

### 高优先级
- [ ] 暴露项目/任务状态转换 API
- [ ] 实现任务编辑对话框
- [ ] 实现任务删除功能
- [ ] 实现项目编辑/删除
- [ ] 任务筛选功能

### 中优先级
- [ ] 里程碑功能设计与实现
- [ ] 日程管理功能
- [ ] 进度追踪仪表盘
- [ ] 项目进度计算

### 低优先级
- [ ] 推送通知系统
- [ ] 模块联动实现
- [ ] 智能日程建议
- [ ] 健康感知调度
