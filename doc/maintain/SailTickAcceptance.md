# SailTick 部署与验收手册

> 版本: v1.0 | 适用: SailTick v1.0 (sailtick/) | 关联: [设计文档](../design/agent-system/sailtick.md)
> 目标读者: 用户本人（在服务器上完成部署并跑通 Day-1 剧本）

## 1. 前置检查

| 项 | 要求 | 检查命令 |
|---|---|---|
| Python | >= 3.13 | `python3 --version` |
| uv | 已安装 | `uv --version` |
| sail_server | 已部署且运行（本手册假设同机） | `curl -s http://127.0.0.1:1974/api/v1/health` |
| 端口 | 9070 未被占用（管理 API） | `ss -tlnp \| grep 9070` |
| 磁盘 | data/sailtick 预估 < 100MB/年 | `df -h <repo>` |
| LLM key | DEEPSEEK_API_KEY 已配置（flash 级视为无限量） | 见 `.env.prod` |

## 2. 部署步骤

```bash
# 1. 拉代码（服务器仓库路径，以下用 $REPO 表示，如 /home/<user>/SailZen）
cd $REPO && git pull

# 2. 配置环境变量：在 .env.prod 中确认/新增 SAILTICK 段（见 .env.template）
#    至少确认：SAILZEN_API_TOKEN、DEEPSEEK_API_KEY 已存在

# 3. 配置 sailtick.yaml：复制模板并填写 sail_server.api_base（按实际端口）
cp sailtick.yaml sailtick.yaml  # 模板已在仓库根；按需修改

# 4. 初始化（DB 自动建表，幂等）
uv run python -m sailtick doctor        # 体检：配置/DB/sail_server/LLM key/目录
uv run python -m sailtick bootstrap     # goal=70kg + 计划 v0.1 + 首批问卷票据

# 5. 安装 systemd 服务
sudo cp scripts/sailtick.service /etc/systemd/system/sailtick.service
# 编辑 unit 中 %I（用户名）与路径后：
sudo systemctl daemon-reload
sudo systemctl enable --now sailtick
```

## 3. 验证清单

按顺序逐项打勾：

| # | 验证项 | 方法 | 期望 |
|---|---|---|---|
| 1 | 管理 API 健康 | `curl -s http://127.0.0.1:9070/health` | 返回 `status: running` + db_stats + schedules(4 个 slot) |
| 2 | 排程注册 | 同上看到 `schedules` 含 tick_00/06/12/18 | next_run_time 为当天对应整点 |
| 3 | 手动触发 | `uv run python -m sailtick trigger midday_checkin` | 前台跑完，输出 `Tick result: completed` |
| 4 | handoff 文件 | `ls data/sailtick/handoffs/` | 出现 `YYYY-MM-DD_midday_checkin.md` |
| 5 | 票据生成 | 打开网页 `http://<server>:1974/tick` | 看到 bootstrap 的问卷票据（当前体重/作息） |
| 6 | 回复链路 | 在网页回复一张问卷 → `trigger evening_review` | 再查 `:9070/ticks` 的最新 tick；sailtick.db episodes 出现 `new_replies: 1` 的 scan 记录 |
| 7 | 手机推送 | 创建 high 优先测试票据（见 §6 测试命令） | Android App 收到推送（复用 reminder WS 通道） |
| 8 | 成本统计 | `curl -s http://127.0.0.1:9070/cost` | `daily_tokens` 有值；flash 级消耗应极小 |
| 9 | 安静时段 | 23:00–08:00 间触发 tick 且计划只有 normal 票据 | 手机不推送，但票据落库、网页可见 |
| 10 | 幂等 | 同一天重复 `trigger midday_checkin` | 第二次返回 `skipped/already_completed`，不重复发票据 |

## 4. Day-1 剧本（首周观察点）

| 天数 | 观察点 |
|---|---|
| Day 1 | bootstrap 票据可见；网页可回复；当日 4 个 slot 到点自动唤醒（`journalctl -u sailtick` 有 Tick START/END） |
| Day 2 | 问卷回复后，下一个 Tick 的 handoff「用户状态摘要」体现回复内容；无回复票据按 fallback 假设推进 |
| Day 3 | 体重记录 ≥ 2 天（网页快速记体重或 health API）；数据包中 weight 信号非空 |
| Day 4 | 检查 `data/sailtick/handoffs/` 文件数 == 已完成 tick 数；无 `interrupted`（或仅有解释得通的） |
| Day 5 | `curl :9070/cost` 日消耗符合预期；无 LLM 报错刷屏（`journalctl -u sailtick \| grep -i error`） |
| Day 7 | 周日晚 evening_review 做 weekly review（与 rhythm 周复盘对齐）；计划仍为 v0.1 或已滚动更新；你感觉被询问的频率可接受 |

## 5. 常见问题

| 现象 | 排查 |
|---|---|
| doctor 报 sail_server unreachable | sail_server 未启动 / 端口不符 → 检查 sailtick.yaml 的 api_base |
| 票据创建了但手机没推送 | 仅 high/urgent 推送；检查 App 是否在线（离线时走轮询兜回）；quiet hours 内非 urgent 不推 |
| Tick 错过 | daemon 重启时自动补跑（最多 1 个）；日志搜 `Missed tick` |
| LLM 计划全是规则模板 | 正常降级（key 未配或超预算）；`journalctl -u sailtick \| grep PLAN` 看原因 |
| 数据包空 | `sailtick doctor` 的 sail_server 项；体重等数据源需先有记录 |

**日志位置**: `journalctl -u sailtick -f` 或 `$REPO/logs/sailtick/sailtick_YYYYMMDD.log`

## 6. 运维命令速查

```bash
systemctl status sailtick            # 服务状态
uv run python -m sailtick status     # daemon 健康（需 daemon 在跑）
uv run python -m sailtick doctor     # 依赖体检
uv run python -m sailtick bootstrap  # 重建初始计划/票据（幂等，不会重复建）
uv run python scripts/sailtick_smoke.py   # 端到端冒烟（自起临时库，不影响生产）

# 测试推送（高优先票据触发 WS 广播）
curl -X POST http://127.0.0.1:1974/api/v1/tick/tickets \
  -H "Authorization: Bearer $SAILZEN_API_TOKEN" -H "Content-Type: application/json" \
  -d '{"type":"info","title":"推送测试","priority":"high"}'
```

## 7. 回滚

```bash
sudo systemctl disable --now sailtick
# 备份（可选保留，仅占空间）
tar czf sailtick-backup-$(date +%F).tar.gz data/sailtick logs/sailtick
# 清理
rm -rf data/sailtick logs/sailtick
```

- 主库仅多出一张 `sail_tick_tickets` 表，可安全保留（不影响其他功能），
  或 `DROP TABLE sail_tick_tickets;` 移除。
- 回滚 sail_server 代码到部署前 commit 即可（票据路由只在被调用时工作）。
- sailtick/ 包为纯新增，删除目录即完全移除；共享引擎 dag_client 的两处 import
  修复对旧行为无影响（见迁移说明 B6/B7）。
