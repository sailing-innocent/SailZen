---
name: sailzen-finance-auto-tags
description: SailZen 财务交易自动批量补全标签工具。根据用户指定的时间范围，拉取该范围内所有 transaction，学习历史 tagging 模式与规范 tag 统计，自动推断缺失标签，生成待更新 CSV，经人工检查后可批量上传到服务器。适用于周期性标签补全、历史数据清理、批量重分类场景。
---

# SailZen 财务交易自动批量补全标签 Skill

你是一个专业的财务交易标签分类 agent。核心工作流：**解析时间范围 → 拉取交易 → 学习历史模式 → 推断标签 → 生成 CSV → 人工检查 → push 上传 → 验证**。

## 何时使用此 Skill

- 用户希望为指定时间范围内的交易批量补全/修正标签
- 用户要求 agent 学习已有的标签模式，自动分类一段时间内的交易
- 用户提到"交易标签补全"、"批量打标签"、"auto tag"、"标签清理"等关键词
- 用户指定了日期范围（如 2026年4-6月、最近三个月等）

## 前置条件

- `sailzen` CLI 已安装且可用（`uv tool install -e .`）
- sail_server 正在运行并可访问
- 工作目录下存在 `data/` 子目录用于存放临时工作文件

## 服务器地址

```
默认: http://localhost:8000
环境变量: SAIL_SERVER_URL
CLI 参数: --server http://<host>:<port>
```

## 完整工作流程

### Phase 0: 解析时间范围

从用户 prompt 中提取需要 auto-tag 的时间范围。

**常见时间范围格式：**

| 用户输入 | 解析结果 |
|----------|----------|
| "2026年4月" | from_time=2026-04-01, to_time=2026-04-30 23:59:59 |
| "2026年4-6月" | from_time=2026-04-01, to_time=2026-06-30 23:59:59 |
| "最近三个月" | 从当前日期往前推3个月 |
| "2026Q2" | from_time=2026-04-01, to_time=2026-06-30 23:59:59 |

**时间戳转换：**
```python
from datetime import datetime
import time

# 示例: 2026年4月1日 00:00:00
t_from = int(datetime(2026, 4, 1).timestamp())  # 1774444800
# 2026年6月30日 23:59:59
t_to = int(datetime(2026, 6, 30, 23, 59, 59).timestamp())  # 1779273599
```

### Phase 1: 拉取指定范围内的所有交易

使用 `sailzen finance pull` 拉取全部交易，然后在本地按时间范围过滤。所有临时工作文件统一存放在 `data/` 目录下。

```bash
# 拉取全部交易（不指定 account），临时文件放 data/ 目录
sailzen finance pull --server http://<host>:<port> --output data/transactions_all.csv
```

**本地过滤时间范围：**
```python
import csv
from datetime import datetime

def filter_by_time(csv_path, from_time, to_time, output_path):
    rows = []
    with open(csv_path, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            htime_str = row.get('htime', '')
            if not htime_str:
                continue
            # htime 可能是 ISO 格式或时间戳
            try:
                if 'T' in htime_str:
                    dt = datetime.fromisoformat(htime_str)
                else:
                    dt = datetime.fromtimestamp(float(htime_str))
                ts = dt.timestamp()
            except Exception:
                continue
            if from_time <= ts <= to_time:
                rows.append(row)
    
    with open(output_path, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=reader.fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return len(rows)
```

> 临时文件路径约定：
> - `data/transactions_all.csv` — 全量交易拉取
> - `data/auto_tags_{from_date}_{to_date}.csv` — 生成的待更新 CSV
> - `data/tag_patterns.json` — 缓存的历史模式
> - `data/tag_stats.json` — 缓存的标签统计

### Phase 2: 学习历史标签模式

通过 HTTP API 获取 tag patterns 和 tag stats，作为推断依据。

```bash
# 获取标签使用统计
GET /api/v1/finance/tag/stats

# 获取标签模式（限定在目标时间范围前，或全量）
GET /api/v1/finance/transaction/agent/tag-patterns?limit=500&min_occurrences=1
```

**关键信息整理：**
1. `tag_vocabulary`：所有已使用过的合法标签列表
2. `patterns`：description → tags 的精确映射（优先复用）
3. `stats`：各标签使用频率，识别高频标签
4. 默认标签体系：零食、交通、日用消耗、娱乐休闲、人际交往、医药健康、衣物、大宗电器、大宗收支

**构建推断规则集：**

| description 包含 | → 推断 tags |
|-----------------|-------------|
| 外卖 / 美团 / 饿了么 / 麻辣香锅 | 零食 |
| 滴滴 / 出租 / 地铁 / 公交 / 铁路 / 火车 / 12306 | 交通 |
| 京东 / 淘宝 / 拼多多 / 唯品会 / 超市 / 便利 | 日用消耗 或 零食 |
| 电影 / 游戏 / KTV / 游泳 | 娱乐休闲 |
| 红包 / 聚餐 / 礼物 | 人际交往 |
| 药 / 体检 / 就医 / 医院 | 医药健康 |
| 衣服 / 鞋 / 配饰 | 衣物 |
| 房租 / 学费 / 大额 | 大宗收支 |
| 家电 / 数码 / 手机 / 电脑 | 大宗电器 |

> ⚠️ **规则优先级**：精确匹配（description 完全相等）> 关键词匹配 > 模糊推断。对于无法确定的交易，宁可留空也不要乱打标签。

### Phase 3: 推断标签

对 Phase 1 过滤出的每条交易，逐条推断标签：

**推断策略（按优先级）：**

1. **精确匹配**：description 完全等于某个已知 pattern 的 description → 直接使用该 pattern 的 tags
2. **关键词匹配**：description 包含已知关键词 → 使用对应 tags
3. **金额+方向辅助**：
   - 大额支出（> 1000）→ 考虑 "大宗收支" 或 "大宗电器"
   - 收入交易（from_acc_id = -1）→ 跳过或标记为 income 类（若系统支持）
   - 转账（from_acc_id > 0, to_acc_id > 0）→ 通常不需要标签，可跳过
4. **无法判断**：保留原 tags（空），不打标签

**标签使用约束：**
- 单标签优先，多标签用逗号分隔
- 只使用 `tag_vocabulary` 中已有的标签，不要自创
- 宁缺毋滥：错误标签比无标签更难修正

### Phase 4: 生成待更新 CSV

将推断结果写入 CSV，保留原始字段，只更新 `tags` 列。

```csv
id,from_acc_id,to_acc_id,value,prev_value,description,tags,state,budget_id,htime,ctime,mtime
```

**生成规则：**
- 所有原始字段保留不变
- 只有 `tags` 列被更新（从空字符串变为推断的标签）
- 无法推断的 transaction，`tags` 保持为空
- 已有标签的 transaction，`tags` 保持原样（除非明确需要覆盖）

文件名：`data/auto_tags_{from_date}_{to_date}.csv`

### Phase 5: 人工检查（必须执行）

向用户展示统计摘要，并要求确认：

```
📊 自动标签推断报告
================================
时间范围: 2026-04-01 ~ 2026-06-30
总交易数: 523
待更新标签: 186 (35.6%)
保持原样: 337 (64.4%)

标签分布（推断）:
  零食: 45 条
  交通: 38 条
  日用消耗: 32 条
  娱乐休闲: 15 条
  医药健康: 8 条
  人际交往: 12 条
  大宗收支: 5 条

样例检查（前 10 条）:
  #1024: "美团外卖-麻辣香锅" (¥35.50) → 零食
  #1025: "滴滴出行" (¥12.00) → 交通
  ...

⚠️ 请检查 auto_tags_20260401_20260630.csv 中的标签分配是否合理。
确认无误后，执行上传。
```

用户确认后，进入 Phase 6。

### Phase 6: 上传到服务器

使用 `sailzen finance push` 将 CSV 中的修改推送回服务器。

```bash
# 先 dry-run 预览
sailzen finance push data/auto_tags_20260401_20260630.csv --server http://<host>:<port> --dry-run

# 确认后正式推送
sailzen finance push data/auto_tags_20260401_20260630.csv --server http://<host>:<port>
```

> ⚠️ `push` 只会发送标记为"可编辑"的字段（from_acc_id, to_acc_id, value, description, tags, budget_id, htime）。id 等只读字段不会被上传。

### Phase 7: 验证

1. 重新 pull 该时间范围的交易，检查 tags 列是否已更新
2. 统计已标签 / 未标签数量变化
3. 抽查几条关键记录确认标签正确

```bash
# 重新拉取验证
sailzen finance pull --server http://<host>:<port> --output data/verify.csv
```

### Phase 8: 手动补全非常规交易（必须执行）

批量自动推断后，通常会剩余少量非常规交易（如 "冲牙器"、"补卡费用"、"工资收入" 等）无法被关键词规则覆盖。

**原则**：
- 如果剩余未标签交易 ≤ 20 条，**不要**为此扩充关键词规则或修改推断逻辑
- 这些非常规样本应通过 `sailzen finance push` 或 Web 界面手动补全

**操作步骤**：

1. 查询该时间范围内仍无标签的交易：
   ```bash
   # 通过 API 获取未标签交易列表
   GET /api/v1/finance/transaction/agent/untagged?from_time={t_from}&to_time={t_to}&page_size=200
   ```

2. 将未标签交易导出为手动补全 CSV：
   ```csv
   id,from_acc_id,to_acc_id,value,description,tags,htime
   1999,5,-1,84.55,冲牙器,日用消耗,1775923200
   2000,-1,6,20445.32,三月工资,,1775404800
   ```

3. 用户逐条判断并填写 `tags` 后，执行：
   ```bash
   sailzen finance push data/manual_tags_{from_date}_{to_date}.csv --server http://<host>:<port>
   ```

> ⚠️ **重要**：此步骤的产出（手动补全了哪些 description → tags）应反馈给后续批量推断作为新的历史模式。可以在下次执行 auto-tags 前重新拉取 `tag-patterns`。

## 关键约束

1. **时间范围明确**：必须从用户 prompt 中准确解析 from_time 和 to_time
2. **保守策略**：宁可漏标，不可错标
3. **标签来源唯一**：只使用 `tag_vocabulary` / 已注册标签，不自创新标签
4. **dry-run 安全**：上传前必须先 dry-run
5. **人工确认**：生成 CSV 后必须展示统计摘要，等待用户确认
6. **幂等安全**：push 是覆盖写入，重复执行相同 CSV 不会叠加标签
7. **转账跳过**：账户间转账（from_acc_id > 0, to_acc_id > 0）通常不需要标签
8. **工作目录隔离**：所有临时文件必须放在 `data/` 目录下，不污染项目根目录
9. **非常规样本手动处理**：批量推断后剩余少量（< 20 条）非常规交易，不应为此专门扩充关键词规则，应在批量上传后由用户手动补全

## 故障排除

| 问题 | 可能原因 | 解决方案 |
|------|----------|----------|
| pull 后记录数为 0 | 服务器无数据或时间范围错误 | 检查服务器地址和时间范围 |
| tag patterns 为空 | 历史标签数据不足 | 扩大时间范围或手动标记部分样本 |
| 推断准确率差 | 新类型交易历史无样本 | 人工补充标记后重新学习 |
| push 失败 | 网络或服务器问题 | 检查服务器状态，重试 push |
| 中文乱码 | CSV 编码问题 | 确保使用 UTF-8 BOM 编码 |

## 与 sailzen-finance-auto-tag 的区别

| 特性 | sailzen-finance-auto-tag | sailzen-finance-auto-tags |
|------|--------------------------|---------------------------|
| 目标 | 未标签交易（全库） | 指定时间范围内的所有交易 |
| 工作流 | API 直接读写 | CSV 中间件（pull → 推断 → push） |
| 人工检查 | 每页确认 | 生成 CSV 后整体确认 |
| 适用场景 | 日常持续补全 | 周期性批量清理、历史回刷 |
