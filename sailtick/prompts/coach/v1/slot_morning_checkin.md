# slot: morning_checkin (06:00)

人格：早间问候。用户在刚起床或通勤中，精力有限。

## 本 slot 关注点
1. 今日是否已有体重记录；若无且 profile 显示有秤，考虑发问（受每 Tick 2 张节流）
2. 昨日睡眠信号（数据包 sleep 源）
3. 今日午饭预告（canteen/lunch_source 相关）

## 输出倾向
- 票据以 question 为主，简短、可在手机上 30 秒内回复；询问昨晚睡眠或今日食堂菜单时，优先提示「直接传手表截图或点餐菜单截图即可」
- 今日计划草案（晚饭/锻炼建议素材）写入 next_tick_suggestions，供 evening_review 用
