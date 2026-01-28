# Reminder 消息提醒系统设计

> 消息提醒是 SailZen 系统的核心基础组件，负责聚合各模块的提醒事项，以 TODO List 的形式展示在主页面上，帮助用户追踪和管理待办事项。

## 1. 系统概述

### 1.1 核心功能

- **聚合提醒**：整合来自 Project、Necessity、Budget、Health 等模块的提醒
- **TODO List 展示**：在主页面以清单形式展示所有待办提醒
- **优先级排序**：按紧急程度和重要性智能排序
- **快捷操作**：支持标记完成、稍后提醒、跳转详情等操作
- **实时更新**：条件触发型提醒自动计算并展示

### 1.2 设计原则

1. **统一入口**：所有模块的提醒通过统一的 Reminder 系统管理
2. **模块解耦**：各模块只需注册提醒规则，无需关心展示逻辑
3. **用户可控**：用户可自定义提醒偏好和过滤条件
4. **轻量高效**：主页面加载快速，支持懒加载和分页

### 1.3 系统架构

```
┌─────────────────────────────────────────────────────────────┐
│                     Frontend (React)                        │
│  ┌─────────────────────────────────────────────────────┐   │
│  │              MainPage (TODO List)                    │   │
│  │  ┌─────────┐  ┌─────────┐  ┌─────────┐             │   │
│  │  │Reminder │  │Reminder │  │Reminder │  ...        │   │
│  │  │  Card   │  │  Card   │  │  Card   │             │   │
│  │  └─────────┘  └─────────┘  └─────────┘             │   │
│  └─────────────────────────────────────────────────────┘   │
│                          │                                  │
│                   ReminderStore (Zustand)                   │
└──────────────────────────┼──────────────────────────────────┘
                           │ API
┌──────────────────────────┼──────────────────────────────────┐
│                     Backend (Litestar)                      │
│  ┌───────────────────────┼───────────────────────────────┐ │
│  │              ReminderController                        │ │
│  └───────────────────────┼───────────────────────────────┘ │
│                          │                                  │
│  ┌───────────────────────┼───────────────────────────────┐ │
│  │              ReminderService                           │ │
│  │  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐  │ │
│  │  │ Project │  │Necessity│  │ Budget  │  │ Health  │  │ │
│  │  │ Checker │  │ Checker │  │ Checker │  │ Checker │  │ │
│  │  └─────────┘  └─────────┘  └─────────┘  └─────────┘  │ │
│  └───────────────────────────────────────────────────────┘ │
│                          │                                  │
│                     Reminder Table                          │
└─────────────────────────────────────────────────────────────┘
```

---

## 2. 数据模型设计

### 2.1 Reminder 表 (数据库持久化)

用于存储用户创建的提醒和系统生成的持久化提醒。

```python
from sqlalchemy import Column, Integer, String, TIMESTAMP, Boolean, Enum
from sqlalchemy.dialects.postgresql import JSONB
from sail_server.data.orm import ORMBase
from datetime import datetime
import enum


class ReminderType(str, enum.Enum):
    """提醒类型"""
    TASK_DEADLINE = "task_deadline"      # 任务截止
    MILESTONE = "milestone"              # 里程碑
    PROJECT_STALE = "project_stale"      # 项目停滞
    ITEM_EXPIRY = "item_expiry"          # 物品过期
    ITEM_LOW_STOCK = "item_low_stock"    # 库存不足
    BUDGET_WARNING = "budget_warning"    # 预算预警
    HEALTH_CHECKUP = "health_checkup"    # 健康检查
    HEALTH_REMINDER = "health_reminder"  # 健康提醒
    DAILY_SUMMARY = "daily_summary"      # 每日摘要
    CUSTOM = "custom"                    # 自定义


class ReminderPriority(str, enum.Enum):
    """提醒优先级"""
    URGENT = "urgent"      # 紧急 - 红色
    HIGH = "high"          # 高 - 橙色
    NORMAL = "normal"      # 普通 - 蓝色
    LOW = "low"            # 低 - 灰色


class ReminderStatus(str, enum.Enum):
    """提醒状态"""
    PENDING = "pending"      # 待处理
    SNOOZED = "snoozed"      # 已延后
    COMPLETED = "completed"  # 已完成
    DISMISSED = "dismissed"  # 已忽略
    EXPIRED = "expired"      # 已过期


class Reminder(ORMBase):
    """提醒数据表"""
    __tablename__ = "reminders"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # 基本信息
    title = Column(String, nullable=False)           # 提醒标题
    message = Column(String, default="")             # 提醒详情
    reminder_type = Column(String, nullable=False)   # 提醒类型
    priority = Column(String, default="normal")      # 优先级
    status = Column(String, default="pending")       # 状态
    
    # 关联信息
    source_module = Column(String, nullable=False)   # 来源模块：project/necessity/budget/health
    source_id = Column(Integer, nullable=True)       # 来源实体ID
    source_type = Column(String, nullable=True)      # 来源实体类型：mission/project/item/budget
    
    # 时间信息
    trigger_time = Column(TIMESTAMP, nullable=True)  # 触发时间
    snooze_until = Column(TIMESTAMP, nullable=True)  # 延后至
    created_at = Column(TIMESTAMP, default=datetime.now)
    updated_at = Column(TIMESTAMP, default=datetime.now, onupdate=datetime.now)
    completed_at = Column(TIMESTAMP, nullable=True)  # 完成时间
    
    # 扩展信息
    metadata = Column(JSONB, default={})             # 额外元数据
    action_url = Column(String, nullable=True)       # 跳转链接
    
    # 用户设置
    is_auto_generated = Column(Boolean, default=True)  # 是否系统自动生成
    is_recurring = Column(Boolean, default=False)      # 是否重复
    recurrence_rule = Column(String, nullable=True)    # 重复规则 (RRULE格式)
```

### 2.2 Pydantic 数据模型

```python
from pydantic import BaseModel
from datetime import datetime
from typing import Optional, Dict, Any, List


class ReminderData(BaseModel):
    """提醒数据传输对象"""
    id: Optional[int] = None
    title: str
    message: str = ""
    reminder_type: str
    priority: str = "normal"
    status: str = "pending"
    
    source_module: str
    source_id: Optional[int] = None
    source_type: Optional[str] = None
    
    trigger_time: Optional[datetime] = None
    snooze_until: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    metadata: Dict[str, Any] = {}
    action_url: Optional[str] = None
    
    is_auto_generated: bool = True
    is_recurring: bool = False
    recurrence_rule: Optional[str] = None
    
    class Config:
        from_attributes = True
    
    @classmethod
    def read_from_orm(cls, orm_obj: "Reminder") -> "ReminderData":
        return cls(
            id=orm_obj.id,
            title=orm_obj.title,
            message=orm_obj.message,
            reminder_type=orm_obj.reminder_type,
            priority=orm_obj.priority,
            status=orm_obj.status,
            source_module=orm_obj.source_module,
            source_id=orm_obj.source_id,
            source_type=orm_obj.source_type,
            trigger_time=orm_obj.trigger_time,
            snooze_until=orm_obj.snooze_until,
            created_at=orm_obj.created_at,
            updated_at=orm_obj.updated_at,
            completed_at=orm_obj.completed_at,
            metadata=orm_obj.metadata or {},
            action_url=orm_obj.action_url,
            is_auto_generated=orm_obj.is_auto_generated,
            is_recurring=orm_obj.is_recurring,
            recurrence_rule=orm_obj.recurrence_rule,
        )


class ReminderCreateProps(BaseModel):
    """创建提醒的请求体"""
    title: str
    message: str = ""
    reminder_type: str = "custom"
    priority: str = "normal"
    source_module: str = "custom"
    source_id: Optional[int] = None
    source_type: Optional[str] = None
    trigger_time: Optional[datetime] = None
    metadata: Dict[str, Any] = {}
    action_url: Optional[str] = None
    is_recurring: bool = False
    recurrence_rule: Optional[str] = None


class ReminderUpdateProps(BaseModel):
    """更新提醒的请求体"""
    title: Optional[str] = None
    message: Optional[str] = None
    priority: Optional[str] = None
    trigger_time: Optional[datetime] = None
    metadata: Optional[Dict[str, Any]] = None
    action_url: Optional[str] = None


class ReminderListResponse(BaseModel):
    """提醒列表响应"""
    items: List[ReminderData]
    total: int
    pending_count: int
    urgent_count: int
```

### 2.3 条件检查器接口

各模块实现此接口来注册条件触发的提醒。

```python
from abc import ABC, abstractmethod
from typing import List


class ReminderChecker(ABC):
    """提醒检查器基类"""
    
    @abstractmethod
    async def check(self, db) -> List[ReminderData]:
        """
        检查并返回当前需要展示的提醒
        
        Returns:
            List[ReminderData]: 需要展示的提醒列表
        """
        pass
    
    @property
    @abstractmethod
    def module_name(self) -> str:
        """返回模块名称"""
        pass


class ProjectReminderChecker(ReminderChecker):
    """项目模块提醒检查器"""
    
    @property
    def module_name(self) -> str:
        return "project"
    
    async def check(self, db) -> List[ReminderData]:
        reminders = []
        
        # 检查即将到期的任务（24小时内）
        upcoming_missions = await self._get_upcoming_missions(db, hours=24)
        for mission in upcoming_missions:
            reminders.append(ReminderData(
                title=f"任务即将到期: {mission.name}",
                message=f"截止时间: {mission.ddl}",
                reminder_type="task_deadline",
                priority="high" if mission.ddl_hours <= 2 else "normal",
                source_module="project",
                source_id=mission.id,
                source_type="mission",
                trigger_time=mission.ddl,
                action_url=f"/project?mission={mission.id}",
                is_auto_generated=True,
            ))
        
        # 检查已逾期的任务
        overdue_missions = await self._get_overdue_missions(db)
        for mission in overdue_missions:
            reminders.append(ReminderData(
                title=f"任务已逾期: {mission.name}",
                message=f"已逾期 {mission.overdue_hours} 小时",
                reminder_type="task_deadline",
                priority="urgent",
                source_module="project",
                source_id=mission.id,
                source_type="mission",
                action_url=f"/project?mission={mission.id}",
                is_auto_generated=True,
            ))
        
        # 检查停滞的项目（7天无更新）
        stale_projects = await self._get_stale_projects(db, days=7)
        for project in stale_projects:
            reminders.append(ReminderData(
                title=f"项目停滞: {project.name}",
                message=f"已 {project.stale_days} 天无进展",
                reminder_type="project_stale",
                priority="low",
                source_module="project",
                source_id=project.id,
                source_type="project",
                action_url=f"/project?project={project.id}",
                is_auto_generated=True,
            ))
        
        return reminders


class BudgetReminderChecker(ReminderChecker):
    """预算模块提醒检查器"""
    
    @property
    def module_name(self) -> str:
        return "budget"
    
    async def check(self, db) -> List[ReminderData]:
        reminders = []
        
        # 检查预算使用超过80%的项目
        low_budgets = await self._get_low_budgets(db, threshold=0.8)
        for budget in low_budgets:
            priority = "urgent" if budget.usage_rate >= 0.95 else "high"
            reminders.append(ReminderData(
                title=f"预算即将用尽: {budget.name}",
                message=f"已使用 {budget.usage_rate*100:.0f}%，剩余 ¥{budget.remaining:.2f}",
                reminder_type="budget_warning",
                priority=priority,
                source_module="budget",
                source_id=budget.id,
                source_type="budget",
                action_url=f"/money?budget={budget.id}",
                metadata={"usage_rate": budget.usage_rate, "remaining": budget.remaining},
                is_auto_generated=True,
            ))
        
        return reminders


class NecessityReminderChecker(ReminderChecker):
    """物资模块提醒检查器"""
    
    @property
    def module_name(self) -> str:
        return "necessity"
    
    async def check(self, db) -> List[ReminderData]:
        reminders = []
        
        # 检查即将过期的物品（30天内）
        expiring_items = await self._get_expiring_items(db, days=30)
        for item in expiring_items:
            priority = "urgent" if item.days_until_expiry <= 7 else "normal"
            reminders.append(ReminderData(
                title=f"物品即将过期: {item.name}",
                message=f"将于 {item.expiry_date} 过期（{item.days_until_expiry}天后）",
                reminder_type="item_expiry",
                priority=priority,
                source_module="necessity",
                source_id=item.id,
                source_type="item",
                action_url=f"/necessity?item={item.id}",
                is_auto_generated=True,
            ))
        
        # 检查库存不足的消耗品
        low_stock_items = await self._get_low_stock_items(db)
        for item in low_stock_items:
            reminders.append(ReminderData(
                title=f"库存不足: {item.name}",
                message=f"当前库存: {item.quantity}，建议补货",
                reminder_type="item_low_stock",
                priority="normal",
                source_module="necessity",
                source_id=item.id,
                source_type="consumable",
                action_url=f"/necessity?item={item.id}",
                is_auto_generated=True,
            ))
        
        return reminders


class HealthReminderChecker(ReminderChecker):
    """健康模块提醒检查器"""
    
    @property
    def module_name(self) -> str:
        return "health"
    
    async def check(self, db) -> List[ReminderData]:
        reminders = []
        
        # 检查健康护理提醒（洗牙、复诊等）
        health_reminders = await self._get_pending_health_reminders(db)
        for hr in health_reminders:
            reminders.append(ReminderData(
                title=hr.title,
                message=hr.message,
                reminder_type="health_reminder",
                priority="normal",
                source_module="health",
                source_id=hr.id,
                source_type="health_reminder",
                trigger_time=hr.remind_date,
                action_url="/health",
                is_auto_generated=True,
            ))
        
        return reminders
```

---

## 3. API 接口设计

### 3.1 接口列表 (`/api/reminder`)

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/` | 获取提醒列表（支持筛选和分页）|
| GET | `/pending` | 获取所有待处理提醒 |
| GET | `/count` | 获取各状态提醒数量统计 |
| GET | `/{id}` | 获取单个提醒详情 |
| POST | `/` | 创建自定义提醒 |
| PUT | `/{id}` | 更新提醒 |
| DELETE | `/{id}` | 删除提醒 |
| POST | `/{id}/complete` | 标记提醒为已完成 |
| POST | `/{id}/dismiss` | 关闭/忽略提醒 |
| POST | `/{id}/snooze` | 稍后提醒 |
| POST | `/refresh` | 刷新条件触发型提醒 |

### 3.2 Controller 实现

```python
from litestar import Controller, get, post, put, delete
from litestar.params import Parameter
from datetime import datetime, timedelta
from typing import Optional, List


class ReminderController(Controller):
    path = "/reminder"
    tags = ["reminder"]
    
    @get("/")
    async def get_reminders(
        self,
        db,
        status: Optional[str] = Parameter(default=None),
        priority: Optional[str] = Parameter(default=None),
        source_module: Optional[str] = Parameter(default=None),
        reminder_type: Optional[str] = Parameter(default=None),
        include_auto: bool = Parameter(default=True),
        skip: int = Parameter(default=0),
        limit: int = Parameter(default=50),
    ) -> ReminderListResponse:
        """获取提醒列表，支持多条件筛选"""
        # 1. 从数据库获取持久化的提醒
        db_reminders = await get_reminders_impl(
            db, status=status, priority=priority,
            source_module=source_module, skip=skip, limit=limit
        )
        
        # 2. 如果包含自动生成的提醒，运行各模块检查器
        auto_reminders = []
        if include_auto:
            auto_reminders = await self._run_checkers(db, source_module)
        
        # 3. 合并、去重、排序
        all_reminders = self._merge_reminders(db_reminders, auto_reminders)
        
        # 4. 应用筛选条件
        if priority:
            all_reminders = [r for r in all_reminders if r.priority == priority]
        if reminder_type:
            all_reminders = [r for r in all_reminders if r.reminder_type == reminder_type]
        
        # 5. 排序：紧急 > 高 > 普通 > 低，同优先级按时间
        all_reminders = self._sort_reminders(all_reminders)
        
        # 6. 统计
        pending_count = sum(1 for r in all_reminders if r.status == "pending")
        urgent_count = sum(1 for r in all_reminders if r.priority == "urgent")
        
        return ReminderListResponse(
            items=all_reminders[skip:skip+limit] if limit > 0 else all_reminders,
            total=len(all_reminders),
            pending_count=pending_count,
            urgent_count=urgent_count,
        )
    
    @get("/pending")
    async def get_pending_reminders(self, db) -> List[ReminderData]:
        """获取所有待处理的提醒（用于主页 TODO List）"""
        return await self.get_reminders(
            db, status="pending", include_auto=True, limit=-1
        )
    
    @get("/count")
    async def get_reminder_counts(self, db) -> dict:
        """获取提醒数量统计"""
        all_reminders = await self.get_reminders(db, include_auto=True, limit=-1)
        return {
            "total": len(all_reminders.items),
            "pending": all_reminders.pending_count,
            "urgent": all_reminders.urgent_count,
            "by_module": self._count_by_module(all_reminders.items),
            "by_type": self._count_by_type(all_reminders.items),
        }
    
    @get("/{reminder_id:int}")
    async def get_reminder(self, db, reminder_id: int) -> ReminderData:
        """获取单个提醒详情"""
        return await get_reminder_impl(db, reminder_id)
    
    @post("/")
    async def create_reminder(self, db, data: ReminderCreateProps) -> ReminderData:
        """创建自定义提醒"""
        return await create_reminder_impl(db, data)
    
    @put("/{reminder_id:int}")
    async def update_reminder(
        self, db, reminder_id: int, data: ReminderUpdateProps
    ) -> ReminderData:
        """更新提醒"""
        return await update_reminder_impl(db, reminder_id, data)
    
    @delete("/{reminder_id:int}")
    async def delete_reminder(self, db, reminder_id: int) -> dict:
        """删除提醒"""
        await delete_reminder_impl(db, reminder_id)
        return {"status": "success"}
    
    @post("/{reminder_id:int}/complete")
    async def complete_reminder(self, db, reminder_id: int) -> ReminderData:
        """标记提醒为已完成"""
        return await change_reminder_status_impl(
            db, reminder_id, "completed", completed_at=datetime.now()
        )
    
    @post("/{reminder_id:int}/dismiss")
    async def dismiss_reminder(self, db, reminder_id: int) -> ReminderData:
        """关闭/忽略提醒"""
        return await change_reminder_status_impl(db, reminder_id, "dismissed")
    
    @post("/{reminder_id:int}/snooze")
    async def snooze_reminder(
        self, db, reminder_id: int, minutes: int = Parameter(default=30)
    ) -> ReminderData:
        """稍后提醒"""
        snooze_until = datetime.now() + timedelta(minutes=minutes)
        return await change_reminder_status_impl(
            db, reminder_id, "snoozed", snooze_until=snooze_until
        )
    
    @post("/refresh")
    async def refresh_reminders(self, db) -> dict:
        """手动刷新条件触发型提醒"""
        auto_reminders = await self._run_checkers(db, None)
        return {
            "status": "success",
            "refreshed_count": len(auto_reminders),
        }
    
    async def _run_checkers(
        self, db, source_module: Optional[str]
    ) -> List[ReminderData]:
        """运行各模块的提醒检查器"""
        checkers = [
            ProjectReminderChecker(),
            BudgetReminderChecker(),
            NecessityReminderChecker(),
            HealthReminderChecker(),
        ]
        
        if source_module:
            checkers = [c for c in checkers if c.module_name == source_module]
        
        all_reminders = []
        for checker in checkers:
            try:
                reminders = await checker.check(db)
                all_reminders.extend(reminders)
            except Exception as e:
                # 记录错误但不中断
                print(f"Checker {checker.module_name} failed: {e}")
        
        return all_reminders
    
    def _sort_reminders(self, reminders: List[ReminderData]) -> List[ReminderData]:
        """按优先级和时间排序"""
        priority_order = {"urgent": 0, "high": 1, "normal": 2, "low": 3}
        return sorted(
            reminders,
            key=lambda r: (
                priority_order.get(r.priority, 2),
                r.trigger_time or datetime.max,
            )
        )
```

---

## 4. 前端设计

### 4.1 TypeScript 数据类型

```typescript
// lib/data/reminder.ts

export type ReminderType =
  | 'task_deadline'
  | 'milestone'
  | 'project_stale'
  | 'item_expiry'
  | 'item_low_stock'
  | 'budget_warning'
  | 'health_checkup'
  | 'health_reminder'
  | 'daily_summary'
  | 'custom'

export type ReminderPriority = 'urgent' | 'high' | 'normal' | 'low'

export type ReminderStatus = 'pending' | 'snoozed' | 'completed' | 'dismissed' | 'expired'

export interface ReminderData {
  id?: number
  title: string
  message: string
  reminder_type: ReminderType
  priority: ReminderPriority
  status: ReminderStatus
  
  source_module: string
  source_id?: number
  source_type?: string
  
  trigger_time?: string  // ISO datetime string
  snooze_until?: string
  created_at?: string
  updated_at?: string
  completed_at?: string
  
  metadata: Record<string, any>
  action_url?: string
  
  is_auto_generated: boolean
  is_recurring: boolean
  recurrence_rule?: string
}

export interface ReminderCreateProps {
  title: string
  message?: string
  reminder_type?: ReminderType
  priority?: ReminderPriority
  source_module?: string
  source_id?: number
  source_type?: string
  trigger_time?: string
  metadata?: Record<string, any>
  action_url?: string
  is_recurring?: boolean
  recurrence_rule?: string
}

export interface ReminderListResponse {
  items: ReminderData[]
  total: number
  pending_count: number
  urgent_count: number
}

export interface ReminderCounts {
  total: number
  pending: number
  urgent: number
  by_module: Record<string, number>
  by_type: Record<string, number>
}
```

### 4.2 API 调用封装

```typescript
// lib/api/reminder.ts

import { fetchJson, get_url } from './config'
import type {
  ReminderData,
  ReminderCreateProps,
  ReminderListResponse,
  ReminderCounts,
} from '@lib/data/reminder'

const BASE_URL = `${get_url()}/reminder`

export interface ReminderFilters {
  status?: string
  priority?: string
  source_module?: string
  reminder_type?: string
  include_auto?: boolean
  skip?: number
  limit?: number
}

export async function api_get_reminders(
  filters: ReminderFilters = {}
): Promise<ReminderListResponse> {
  const params = new URLSearchParams()
  Object.entries(filters).forEach(([key, value]) => {
    if (value !== undefined) {
      params.append(key, String(value))
    }
  })
  const queryString = params.toString()
  const url = queryString ? `${BASE_URL}?${queryString}` : BASE_URL
  return fetchJson(url)
}

export async function api_get_pending_reminders(): Promise<ReminderData[]> {
  return fetchJson(`${BASE_URL}/pending`)
}

export async function api_get_reminder_counts(): Promise<ReminderCounts> {
  return fetchJson(`${BASE_URL}/count`)
}

export async function api_get_reminder(id: number): Promise<ReminderData> {
  return fetchJson(`${BASE_URL}/${id}`)
}

export async function api_create_reminder(
  data: ReminderCreateProps
): Promise<ReminderData> {
  return fetchJson(BASE_URL, {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

export async function api_update_reminder(
  id: number,
  data: Partial<ReminderCreateProps>
): Promise<ReminderData> {
  return fetchJson(`${BASE_URL}/${id}`, {
    method: 'PUT',
    body: JSON.stringify(data),
  })
}

export async function api_delete_reminder(id: number): Promise<{ status: string }> {
  return fetchJson(`${BASE_URL}/${id}`, {
    method: 'DELETE',
  })
}

export async function api_complete_reminder(id: number): Promise<ReminderData> {
  return fetchJson(`${BASE_URL}/${id}/complete`, {
    method: 'POST',
  })
}

export async function api_dismiss_reminder(id: number): Promise<ReminderData> {
  return fetchJson(`${BASE_URL}/${id}/dismiss`, {
    method: 'POST',
  })
}

export async function api_snooze_reminder(
  id: number,
  minutes: number = 30
): Promise<ReminderData> {
  return fetchJson(`${BASE_URL}/${id}/snooze?minutes=${minutes}`, {
    method: 'POST',
  })
}

export async function api_refresh_reminders(): Promise<{ status: string; refreshed_count: number }> {
  return fetchJson(`${BASE_URL}/refresh`, {
    method: 'POST',
  })
}
```

### 4.3 Zustand Store

```typescript
// lib/store/reminder.ts

import { create, type StoreApi, type UseBoundStore } from 'zustand'
import type {
  ReminderData,
  ReminderCreateProps,
  ReminderCounts,
  ReminderListResponse,
} from '@lib/data/reminder'
import {
  api_get_reminders,
  api_get_pending_reminders,
  api_get_reminder_counts,
  api_create_reminder,
  api_complete_reminder,
  api_dismiss_reminder,
  api_snooze_reminder,
  api_refresh_reminders,
  type ReminderFilters,
} from '@lib/api/reminder'

export interface ReminderState {
  // 数据
  reminders: ReminderData[]
  counts: ReminderCounts | null
  isLoading: boolean
  error: string | null
  lastRefreshed: Date | null
  
  // 筛选状态
  filters: ReminderFilters
  
  // Actions
  fetchReminders: (filters?: ReminderFilters) => Promise<void>
  fetchPendingReminders: () => Promise<void>
  fetchCounts: () => Promise<void>
  createReminder: (data: ReminderCreateProps) => Promise<ReminderData>
  completeReminder: (id: number) => Promise<void>
  dismissReminder: (id: number) => Promise<void>
  snoozeReminder: (id: number, minutes?: number) => Promise<void>
  refreshReminders: () => Promise<void>
  setFilters: (filters: ReminderFilters) => void
  clearError: () => void
}

export const useReminderStore: UseBoundStore<StoreApi<ReminderState>> = create<ReminderState>(
  (set, get) => ({
    reminders: [],
    counts: null,
    isLoading: false,
    error: null,
    lastRefreshed: null,
    filters: {},
    
    fetchReminders: async (filters?: ReminderFilters): Promise<void> => {
      set({ isLoading: true, error: null })
      try {
        const appliedFilters = filters || get().filters
        const response = await api_get_reminders(appliedFilters)
        set({
          reminders: response.items,
          isLoading: false,
          lastRefreshed: new Date(),
        })
      } catch (error) {
        set({ isLoading: false, error: (error as Error).message })
        throw error
      }
    },
    
    fetchPendingReminders: async (): Promise<void> => {
      set({ isLoading: true, error: null })
      try {
        const reminders = await api_get_pending_reminders()
        set({
          reminders,
          isLoading: false,
          lastRefreshed: new Date(),
        })
      } catch (error) {
        set({ isLoading: false, error: (error as Error).message })
        throw error
      }
    },
    
    fetchCounts: async (): Promise<void> => {
      try {
        const counts = await api_get_reminder_counts()
        set({ counts })
      } catch (error) {
        set({ error: (error as Error).message })
      }
    },
    
    createReminder: async (data: ReminderCreateProps): Promise<ReminderData> => {
      const newReminder = await api_create_reminder(data)
      set((state) => ({
        reminders: [newReminder, ...state.reminders],
      }))
      return newReminder
    },
    
    completeReminder: async (id: number): Promise<void> => {
      const updatedReminder = await api_complete_reminder(id)
      set((state) => ({
        reminders: state.reminders.map((r) =>
          r.id === id ? updatedReminder : r
        ),
      }))
    },
    
    dismissReminder: async (id: number): Promise<void> => {
      const updatedReminder = await api_dismiss_reminder(id)
      set((state) => ({
        reminders: state.reminders.map((r) =>
          r.id === id ? updatedReminder : r
        ),
      }))
    },
    
    snoozeReminder: async (id: number, minutes: number = 30): Promise<void> => {
      const updatedReminder = await api_snooze_reminder(id, minutes)
      set((state) => ({
        reminders: state.reminders.map((r) =>
          r.id === id ? updatedReminder : r
        ),
      }))
    },
    
    refreshReminders: async (): Promise<void> => {
      set({ isLoading: true })
      try {
        await api_refresh_reminders()
        await get().fetchPendingReminders()
      } catch (error) {
        set({ isLoading: false, error: (error as Error).message })
      }
    },
    
    setFilters: (filters: ReminderFilters): void => {
      set({ filters })
    },
    
    clearError: (): void => {
      set({ error: null })
    },
  })
)
```

### 4.4 UI 组件设计

#### 4.4.1 组件列表

| 组件 | 文件 | 功能 |
|------|------|------|
| ReminderTodoList | `reminder_todo_list.tsx` | 主页 TODO List 容器 |
| ReminderCard | `reminder_card.tsx` | 单个提醒卡片 |
| ReminderFilters | `reminder_filters.tsx` | 筛选控件 |
| ReminderAddDialog | `reminder_add_dialog.tsx` | 新建自定义提醒对话框 |
| ReminderBadge | `reminder_badge.tsx` | 提醒数量徽章（用于导航栏）|

#### 4.4.2 ReminderCard 组件

```tsx
// components/reminder_card.tsx

import React from 'react'
import { Card, CardContent } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Checkbox } from '@/components/ui/checkbox'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import {
  Clock,
  MoreHorizontal,
  Bell,
  BellOff,
  ExternalLink,
  AlertTriangle,
  Calendar,
  Package,
  Wallet,
  Heart,
} from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { useReminderStore } from '@lib/store/reminder'
import type { ReminderData } from '@lib/data/reminder'
import { cn } from '@lib/utils'

interface ReminderCardProps {
  reminder: ReminderData
  compact?: boolean
}

const priorityConfig = {
  urgent: { color: 'bg-red-500', textColor: 'text-red-600', label: '紧急' },
  high: { color: 'bg-orange-500', textColor: 'text-orange-600', label: '高' },
  normal: { color: 'bg-blue-500', textColor: 'text-blue-600', label: '普通' },
  low: { color: 'bg-gray-400', textColor: 'text-gray-500', label: '低' },
}

const moduleIcons: Record<string, React.ComponentType<{ className?: string }>> = {
  project: Calendar,
  budget: Wallet,
  necessity: Package,
  health: Heart,
  custom: Bell,
}

export const ReminderCard: React.FC<ReminderCardProps> = ({ reminder, compact = false }) => {
  const navigate = useNavigate()
  const { completeReminder, dismissReminder, snoozeReminder } = useReminderStore()
  
  const priority = priorityConfig[reminder.priority] || priorityConfig.normal
  const ModuleIcon = moduleIcons[reminder.source_module] || Bell
  
  const handleComplete = async () => {
    if (reminder.id) {
      await completeReminder(reminder.id)
    }
  }
  
  const handleDismiss = async () => {
    if (reminder.id) {
      await dismissReminder(reminder.id)
    }
  }
  
  const handleSnooze = async (minutes: number) => {
    if (reminder.id) {
      await snoozeReminder(reminder.id, minutes)
    }
  }
  
  const handleNavigate = () => {
    if (reminder.action_url) {
      navigate(reminder.action_url)
    }
  }
  
  const formatTriggerTime = (time?: string) => {
    if (!time) return null
    const date = new Date(time)
    const now = new Date()
    const diffHours = (date.getTime() - now.getTime()) / (1000 * 60 * 60)
    
    if (diffHours < 0) {
      return `已逾期 ${Math.abs(Math.floor(diffHours))} 小时`
    } else if (diffHours < 24) {
      return `${Math.floor(diffHours)} 小时后`
    } else {
      return date.toLocaleDateString('zh-CN', { month: 'short', day: 'numeric' })
    }
  }
  
  if (reminder.status === 'completed' || reminder.status === 'dismissed') {
    return null
  }
  
  return (
    <Card
      className={cn(
        'group transition-all hover:shadow-md',
        reminder.priority === 'urgent' && 'border-l-4 border-l-red-500',
        reminder.priority === 'high' && 'border-l-4 border-l-orange-500'
      )}
    >
      <CardContent className={cn('p-4', compact && 'p-3')}>
        <div className="flex items-start gap-3">
          {/* Checkbox */}
          <Checkbox
            checked={reminder.status === 'completed'}
            onCheckedChange={handleComplete}
            className="mt-1"
          />
          
          {/* Content */}
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-1">
              <ModuleIcon className={cn('h-4 w-4', priority.textColor)} />
              <span className="font-medium truncate">{reminder.title}</span>
              {reminder.priority === 'urgent' && (
                <AlertTriangle className="h-4 w-4 text-red-500 flex-shrink-0" />
              )}
            </div>
            
            {!compact && reminder.message && (
              <p className="text-sm text-muted-foreground mb-2 line-clamp-2">
                {reminder.message}
              </p>
            )}
            
            <div className="flex items-center gap-2 text-xs text-muted-foreground">
              <Badge variant="outline" className="text-xs">
                {reminder.source_module}
              </Badge>
              {reminder.trigger_time && (
                <span className="flex items-center gap-1">
                  <Clock className="h-3 w-3" />
                  {formatTriggerTime(reminder.trigger_time)}
                </span>
              )}
            </div>
          </div>
          
          {/* Actions */}
          <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
            {reminder.action_url && (
              <Button
                variant="ghost"
                size="icon"
                className="h-8 w-8"
                onClick={handleNavigate}
              >
                <ExternalLink className="h-4 w-4" />
              </Button>
            )}
            
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="ghost" size="icon" className="h-8 w-8">
                  <MoreHorizontal className="h-4 w-4" />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                <DropdownMenuItem onClick={() => handleSnooze(30)}>
                  <Bell className="h-4 w-4 mr-2" />
                  30 分钟后提醒
                </DropdownMenuItem>
                <DropdownMenuItem onClick={() => handleSnooze(60)}>
                  <Bell className="h-4 w-4 mr-2" />
                  1 小时后提醒
                </DropdownMenuItem>
                <DropdownMenuItem onClick={() => handleSnooze(1440)}>
                  <Bell className="h-4 w-4 mr-2" />
                  明天提醒
                </DropdownMenuItem>
                <DropdownMenuItem onClick={handleDismiss}>
                  <BellOff className="h-4 w-4 mr-2" />
                  忽略
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}
```

#### 4.4.3 ReminderTodoList 组件

```tsx
// components/reminder_todo_list.tsx

import React, { useEffect, useState } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Skeleton } from '@/components/ui/skeleton'
import {
  RefreshCw,
  Plus,
  CheckCircle2,
  AlertCircle,
  Clock,
  Filter,
} from 'lucide-react'
import { ReminderCard } from './reminder_card'
import { ReminderAddDialog } from './reminder_add_dialog'
import { ReminderFilters } from './reminder_filters'
import { useReminderStore } from '@lib/store/reminder'
import type { ReminderData } from '@lib/data/reminder'

interface ReminderTodoListProps {
  title?: string
  showFilters?: boolean
  maxItems?: number
  modules?: string[]  // 只显示特定模块的提醒
}

export const ReminderTodoList: React.FC<ReminderTodoListProps> = ({
  title = '待办事项',
  showFilters = true,
  maxItems,
  modules,
}) => {
  const {
    reminders,
    counts,
    isLoading,
    error,
    fetchPendingReminders,
    fetchCounts,
    refreshReminders,
  } = useReminderStore()
  
  const [showAddDialog, setShowAddDialog] = useState(false)
  const [showFiltersPanel, setShowFiltersPanel] = useState(false)
  const [activeTab, setActiveTab] = useState('all')
  
  useEffect(() => {
    fetchPendingReminders()
    fetchCounts()
    
    // 每5分钟自动刷新
    const interval = setInterval(() => {
      fetchPendingReminders()
    }, 5 * 60 * 1000)
    
    return () => clearInterval(interval)
  }, [fetchPendingReminders, fetchCounts])
  
  // 筛选提醒
  const filteredReminders = reminders.filter((r) => {
    // 模块筛选
    if (modules && !modules.includes(r.source_module)) {
      return false
    }
    
    // Tab 筛选
    if (activeTab === 'urgent' && r.priority !== 'urgent') {
      return false
    }
    if (activeTab === 'today') {
      if (!r.trigger_time) return false
      const today = new Date()
      const triggerDate = new Date(r.trigger_time)
      return triggerDate.toDateString() === today.toDateString()
    }
    
    return r.status === 'pending'
  })
  
  // 限制数量
  const displayReminders = maxItems
    ? filteredReminders.slice(0, maxItems)
    : filteredReminders
  
  // 按优先级分组
  const urgentReminders = filteredReminders.filter((r) => r.priority === 'urgent')
  const normalReminders = filteredReminders.filter((r) => r.priority !== 'urgent')
  
  const handleRefresh = async () => {
    await refreshReminders()
  }
  
  if (error) {
    return (
      <Card className="border-destructive">
        <CardContent className="p-6">
          <div className="flex items-center gap-2 text-destructive">
            <AlertCircle className="h-5 w-5" />
            <span>加载失败: {error}</span>
          </div>
          <Button variant="outline" className="mt-4" onClick={handleRefresh}>
            重试
          </Button>
        </CardContent>
      </Card>
    )
  }
  
  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <CardTitle className="text-lg">{title}</CardTitle>
            {counts && (
              <div className="flex items-center gap-2">
                <Badge variant="secondary">
                  {counts.pending} 待办
                </Badge>
                {counts.urgent > 0 && (
                  <Badge variant="destructive">
                    {counts.urgent} 紧急
                  </Badge>
                )}
              </div>
            )}
          </div>
          
          <div className="flex items-center gap-2">
            {showFilters && (
              <Button
                variant="ghost"
                size="icon"
                onClick={() => setShowFiltersPanel(!showFiltersPanel)}
              >
                <Filter className="h-4 w-4" />
              </Button>
            )}
            <Button
              variant="ghost"
              size="icon"
              onClick={handleRefresh}
              disabled={isLoading}
            >
              <RefreshCw className={`h-4 w-4 ${isLoading ? 'animate-spin' : ''}`} />
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setShowAddDialog(true)}
            >
              <Plus className="h-4 w-4 mr-1" />
              新建
            </Button>
          </div>
        </div>
        
        {/* Filters Panel */}
        {showFiltersPanel && (
          <ReminderFilters className="mt-4" />
        )}
      </CardHeader>
      
      <CardContent>
        <Tabs value={activeTab} onValueChange={setActiveTab}>
          <TabsList className="mb-4">
            <TabsTrigger value="all" className="gap-1">
              全部
              <Badge variant="secondary" className="ml-1">
                {filteredReminders.length}
              </Badge>
            </TabsTrigger>
            <TabsTrigger value="urgent" className="gap-1">
              <AlertCircle className="h-3 w-3" />
              紧急
              {urgentReminders.length > 0 && (
                <Badge variant="destructive" className="ml-1">
                  {urgentReminders.length}
                </Badge>
              )}
            </TabsTrigger>
            <TabsTrigger value="today" className="gap-1">
              <Clock className="h-3 w-3" />
              今日
            </TabsTrigger>
          </TabsList>
          
          <TabsContent value={activeTab} className="mt-0">
            {isLoading ? (
              <div className="space-y-3">
                {[1, 2, 3].map((i) => (
                  <Skeleton key={i} className="h-20 w-full" />
                ))}
              </div>
            ) : displayReminders.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-12 text-muted-foreground">
                <CheckCircle2 className="h-12 w-12 mb-4 text-green-500" />
                <p className="text-lg font-medium">暂无待办事项</p>
                <p className="text-sm">所有任务都已完成！</p>
              </div>
            ) : (
              <div className="space-y-3">
                {/* 紧急提醒优先显示 */}
                {urgentReminders.length > 0 && activeTab === 'all' && (
                  <div className="mb-4">
                    <h4 className="text-sm font-medium text-red-600 mb-2 flex items-center gap-1">
                      <AlertCircle className="h-4 w-4" />
                      需要立即处理
                    </h4>
                    {urgentReminders.map((reminder) => (
                      <ReminderCard
                        key={`${reminder.source_module}-${reminder.source_id || reminder.id}`}
                        reminder={reminder}
                      />
                    ))}
                  </div>
                )}
                
                {/* 普通提醒 */}
                {(activeTab === 'all' ? normalReminders : displayReminders).map((reminder) => (
                  <ReminderCard
                    key={`${reminder.source_module}-${reminder.source_id || reminder.id}`}
                    reminder={reminder}
                  />
                ))}
                
                {/* 显示更多 */}
                {maxItems && filteredReminders.length > maxItems && (
                  <Button variant="ghost" className="w-full">
                    查看全部 {filteredReminders.length} 项
                  </Button>
                )}
              </div>
            )}
          </TabsContent>
        </Tabs>
      </CardContent>
      
      {/* Add Dialog */}
      <ReminderAddDialog
        open={showAddDialog}
        onOpenChange={setShowAddDialog}
      />
    </Card>
  )
}
```

#### 4.4.4 更新主页面

```tsx
// pages/main.tsx

import React from 'react'
import PageLayout from '@components/page_layout'
import { ReminderTodoList } from '@components/reminder_todo_list'
import { get_url } from '@lib/api'
import { useServerStore } from '@lib/store/'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { 
  Wallet, 
  Heart, 
  FolderKanban, 
  Package,
  Activity,
} from 'lucide-react'

const MainPage = () => {
  const url = get_url()
  const serverHealth = useServerStore((state) => state.serverHealth)

  return (
    <PageLayout>
      <div className="p-6 space-y-6">
        {/* 页面标题 */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold">欢迎回来</h1>
            <p className="text-muted-foreground">
              {new Date().toLocaleDateString('zh-CN', {
                weekday: 'long',
                year: 'numeric',
                month: 'long',
                day: 'numeric',
              })}
            </p>
          </div>
          <Badge variant={serverHealth ? 'default' : 'destructive'}>
            <Activity className="h-3 w-3 mr-1" />
            {serverHealth ? '服务正常' : '服务异常'}
          </Badge>
        </div>

        <div className="grid gap-6 md:grid-cols-3">
          {/* 待办事项 TODO List - 占2列 */}
          <div className="md:col-span-2">
            <ReminderTodoList 
              title="待办事项"
              showFilters={true}
            />
          </div>

          {/* 快捷入口 */}
          <div className="space-y-4">
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-base">快捷入口</CardTitle>
              </CardHeader>
              <CardContent className="grid grid-cols-2 gap-2">
                <QuickAccessCard
                  icon={<Wallet className="h-5 w-5" />}
                  label="财务"
                  href="/money"
                  color="text-green-600"
                />
                <QuickAccessCard
                  icon={<Heart className="h-5 w-5" />}
                  label="健康"
                  href="/health"
                  color="text-red-500"
                />
                <QuickAccessCard
                  icon={<FolderKanban className="h-5 w-5" />}
                  label="项目"
                  href="/project"
                  color="text-blue-600"
                />
                <QuickAccessCard
                  icon={<Package className="h-5 w-5" />}
                  label="物资"
                  href="/necessity"
                  color="text-orange-500"
                />
              </CardContent>
            </Card>

            {/* 今日概览 */}
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-base">今日概览</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-2 text-sm">
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">待完成任务</span>
                    <span className="font-medium">5 项</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">紧急事项</span>
                    <span className="font-medium text-red-500">2 项</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">今日支出</span>
                    <span className="font-medium">¥128.50</span>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>
        </div>
      </div>
    </PageLayout>
  )
}

interface QuickAccessCardProps {
  icon: React.ReactNode
  label: string
  href: string
  color?: string
}

const QuickAccessCard: React.FC<QuickAccessCardProps> = ({
  icon,
  label,
  href,
  color = 'text-primary',
}) => {
  return (
    <a
      href={href}
      className="flex flex-col items-center justify-center p-4 rounded-lg border hover:bg-accent transition-colors"
    >
      <span className={color}>{icon}</span>
      <span className="mt-1 text-sm">{label}</span>
    </a>
  )
}

export default MainPage
```

---

## 5. 与其他模块集成

### 5.1 集成方式

各模块通过实现 `ReminderChecker` 接口来注册条件触发型提醒，无需修改 Reminder 核心代码。

```python
# 在各模块的 __init__.py 中注册检查器
from sail_server.model.reminder import register_checker, ProjectReminderChecker

register_checker(ProjectReminderChecker())
```

### 5.2 Project 模块集成

**触发条件**：
- 任务截止时间前 24/2/0.5 小时
- 任务已逾期
- 项目 7 天无更新

**提醒数据来源**：
- `missions` 表：检查 `ddl` 字段
- `projects` 表：检查 `mtime` 字段

### 5.3 Budget 模块集成

**触发条件**：
- 预算使用超过 80%
- 预算使用超过 95%（紧急）
- 预算已超支

**提醒数据来源**：
- `budgets` 表：计算 `consumed / amount` 比例

### 5.4 Necessity 模块集成（待实现）

**触发条件**：
- 物品有效期前 30/7 天
- 消耗品库存低于阈值

**提醒数据来源**：
- `items` 表：检查 `expiry_date` 字段
- `consumables` 表：检查 `quantity` 与 `threshold`

### 5.5 Health 模块集成

**触发条件**：
- 健康护理提醒日期到达
- 连续工作超过 2 小时

**提醒数据来源**：
- `oral_care_reminders` 表
- 其他健康提醒表

---

## 6. 实现计划

### Phase 1: 基础框架 ✅ 已实现

1. **Mission 状态转换 API** ✅ - 后端支持任务状态变更（pending/ready/doing/done/cancel）
2. **任务延期 API** ✅ - 后端支持任务截止日期延期
3. **任务提醒查询 API** ✅ - 获取即将到期和已逾期任务
4. **前端 Store 扩展** ✅ - Zustand store 支持状态操作
5. **MissionCard 组件** ✅ - 任务卡片组件，支持状态显示和操作
6. **MissionPostponeDialog** ✅ - 任务延期对话框
7. **ReminderTodoList 组件** ✅ - 主页 TODO List 组件
8. **主页集成** ✅ - MainPage 集成待办任务列表

### Phase 2: 模块集成

1. **Project 检查器** - 任务截止、项目停滞检测
2. **Budget 检查器** - 预算预警检测
3. **独立 Reminder 表** - 持久化提醒数据

### Phase 3: 增强功能

1. **自定义提醒** - ReminderAddDialog 实现
2. **筛选与搜索** - ReminderFilters 组件
3. **设置面板** - 用户偏好配置

### Phase 4: 高级功能

1. **浏览器推送** - Web Push 通知
2. **每日摘要** - 定时任务发送摘要
3. **移动端适配** - 响应式优化

---

## 7. 待办清单

### 已完成 ✅
- [x] Mission 状态转换 API（pending/ready/doing/done/cancel）
- [x] Mission 延期 API（postpone）
- [x] 即将到期/已逾期任务查询 API
- [x] 前端 MissionsStore 扩展（状态操作、提醒查询）
- [x] MissionCard 组件（状态显示、快捷操作）
- [x] MissionPostponeDialog 延期对话框
- [x] ReminderTodoList 组件（主页 TODO List）
- [x] MainPage 集成待办任务列表
- [x] ProjectMissionColumn 使用 MissionCard

### 高优先级
- [ ] 创建独立的 `reminders` 数据库表
- [ ] 实现 ReminderController 基础 CRUD
- [ ] 实现独立的 ReminderStore

### 中优先级
- [ ] 实现 ProjectReminderChecker（项目停滞检测）
- [ ] 实现 BudgetReminderChecker（预算预警）
- [ ] 实现稍后提醒功能（snooze）

### 低优先级
- [ ] 实现 NecessityReminderChecker
- [ ] 实现 HealthReminderChecker
- [ ] 实现自定义提醒功能
- [ ] 实现浏览器推送通知
