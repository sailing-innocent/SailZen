# 核心数据记录

accounts

acounts
饭卡，支付宝，工行卡，家庭，中行卡……
body_size
id, waist, hip, chest, tag, htime
budget_items
budgets
consumptions
inventory_id,quality,htime,reason,ctime
devices: 记录的连接名
days 基础节奏，我的生命


## Rhythm

rhythm_day_templates
rhythm_affairs

precept: 戒律
venture: 

state
- ACTIVE
- INBOX
- ARCHIVED
- DONE
- CANCELLED

kind_meta
- target_date: null
- spare_time_only: true
- totol_est_hours: 0
- weekly_budget_hours: 6
- state: ARCHIVED

健康速记：精力 life precept
健康速记：情绪
健康速记：水米那
减轻体重

importance
urgency_ddl
energy_cost
money_cost
budget_id
est_minutes
window_start
window_end
splittable
min_chunk_minutes
fallback_plan
recurrence_rule_id
day_id
timespan_id
parent_id
info_collection_type
ai_hint
score
ref
- actual_minutes
- health_constraint

直接创建
- title
- description

#challenge#early_sleep#7#早睡早起

rhythm_discipline_logs
id, affair_id, log_date, cycle_key, result, note, source: health


rhythm_time_blocks
id
day_id
affair_id
block_type: focus
start_time
end_time
status: Planned
pinned: false
plan_version 1
ref: label

rhythm_reviews

week2026-33 81.54

rhythm_policies

reminder_rules
- type: rhythm.daily_brief
- title
body
priorty: normal
source: rhythm
state
trigger_time
