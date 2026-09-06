---
name: sailzen-finance-bill-upload
description: SailZen 财务账单规范化上传工具。自动检查文件结构、从服务器拉取当前记录、解析支付宝/微信原始账单、去重、生成待上传 CSV、人工检查后可上传到服务器。适用于周期性账单导入场景。
---

# SailZen 财务账单规范化上传 Skill

你是一个专业的财务账单导入 agent。核心工作流：**检查文件 → pull 服务器记录 → 解析原始账单 → 去重 → 生成待上传 CSV → 人工检查 description → 上传 → 验证**。

## 何时使用此 Skill

- 用户需要导入新一轮支付宝/微信账单
- 用户提到 "账单导入"、"上传交易"、"finance bill" 等关键词
- 用户给出了账单日期（如 20260607）和工作目录（如 data/mid/zen）

## 前置条件

工作目录下应包含：

| 文件/目录 | 说明 | 命名规律 |
|-----------|------|----------|
| `alipay_record_{YYYYMMDD}_*/alipay_record_{YYYYMMDD}_*.txt` | 支付宝原始账单（GBK编码CSV） | 目录和文件名一致 |
| `微信支付账单流水文件({起始日期}-{结束日期})_{时间戳}.xlsx` | 微信原始账单（Excel） | 可能有多个历史文件 |
| （可选）`alipay_trans.csv` | 服务器拉取的支付宝记录 | 由 `sailzen finance pull` 生成 |
| （可选）`wechat_trans.csv` | 服务器拉取的微信记录 | 由 `sailzen finance pull` 生成 |

> ⚠️ **重要**：如果工作目录下有多个历史账单文件，务必选择**最新一轮**的账单，否则去重会基于错误的原始数据。

## 完整工作流程

### Phase 1: 检查文件结构

1. 扫描工作目录，确认存在：
   - 支付宝原始账单目录（`alipay_record_*`）
   - 微信原始账单 xlsx 文件（`微信支付账单流水文件*.xlsx`）
2. 确认服务器可访问：
   ```bash
   sailzen finance list-accounts --server http://<host>:<port>
   ```
3. 确认 account ID：
   - 支付宝余额宝：通常为 5
   - 微信：通常为 6

### Phase 2: 从服务器拉取当前记录

```bash
# 拉取支付宝记录
sailzen finance pull --account 5 --output alipay_trans.csv --server http://<host>:<port>

# 拉取微信记录
sailzen finance pull --account 6 --output wechat_trans.csv --server http://<host>:<port>
```

**拉取后检查**：
- 记录数量是否正常
- 日期范围是否覆盖到上一轮账单日期
- 特别注意是否有 `1970-01-01` 的 balance fix 记录（这是正常的）

### Phase 3: 解析原始账单并去重

#### 支付宝去重

支付宝账单是 GBK 编码的文本文件，格式：
- 前 4 行为元数据（标题、账号、时间范围、分隔线）
- 第 5 行为 CSV 表头
- 之后为数据行

**去重键**：`(日期, abs(金额))`
- 服务器记录：取 `htime` 的 `YYYY-MM-DD` + `abs(float(value))`
- 支付宝记录：取 `交易创建时间` 的 `YYYY-MM-DD` + `abs(float(金额（元）))`

**仅处理支出记录**（`收/支 == "支出"`），忽略：
- 收入（如退款、转账入账）
- 不计收支（如余额宝收益）

**description 生成规则**：
- 默认：`交易对方|商品名称`
- 若商品名称是纯数字、空、或与交易对方重复，则只保留交易对方

#### 微信去重

微信账单是 xlsx 文件，需解析 OpenXML 格式。

> ⚠️ **关键**：目录下可能有**多个**历史微信账单 xlsx 文件，必须选择最新一轮的文件。
> 
> 文件名示例：
> - `微信支付账单流水文件(20260307-20260607)_20260607180613.xlsx` ← 新
> - `微信支付账单流水文件(20260407-20260507)_20260507002818.xlsx` ← 旧
> 
> **错误的排序方式**：按字符串 reverse 排序会把旧文件排前面！
> ```python
> # ❌ 错误
> sorted(xlsx_files, reverse=True)  # -> 20260507 的旧文件
> 
> # ✅ 正确：提取结束日期后排序
> def extract_date(fname):
>     m = re.search(r'(\d{8})[-_](\d{8})', fname)
>     if m:
>         return m.group(2)
>     return fname
> sorted(xlsx_files, key=extract_date, reverse=True)
> ```

表头行为包含 `交易时间` 的行。Excel 中的日期是 serial number，需要转换：
```python
from datetime import datetime, timedelta
def excel_serial_to_datetime(serial):
    epoch = datetime(1899, 12, 30)
    return epoch + timedelta(days=float(serial))
```

**去重键**：`(日期, abs(金额))`
- 服务器记录：同上
- 微信记录：Excel serial date → datetime → `YYYY-MM-DD` + `abs(float(金额(元)))`

**仅处理支出记录**（`收/支 == "支出"`）。

**description 简化规则**（参考历史风格）：

| 匹配条件 | description |
|----------|-------------|
| 交易类型含 "红包" | 红包 |
| 交易对方含 "luckin" 或 "瑞幸" | 咖啡 |
| 交易对方含 "汉堡王" | 汉堡王 |
| 交易对方含 "起点" | 起点 |
| 交易对方含 "京东" | 京东 |
| 交易对方含 "便利" | 零食 |
| 交易对方含 "泰茶" / "黑树" / "抹茶" | 奶茶 |
| 其他 | 交易对方（若商品有意义则加在后面） |

### Phase 4: 生成待上传 CSV

生成字段：
```csv
id,from_acc_id,to_acc_id,value,prev_value,description,tags,state,budget_id,htime,ctime,mtime
```

- `id` 留空 → 创建新记录
- `from_acc_id`：5（支付宝）或 6（微信）
- `to_acc_id`：-1（支出）
- `htime`：`YYYY-MM-DDT00:00:00`
- `tags` / `state` / `budget_id` / `prev_value` / `ctime` / `mtime` 留空

文件名：
- 支付宝：`to_upload.csv`
- 微信：`wechat_to_upload.csv`

### Phase 5: 人工检查 description

**必须执行此步骤！** 逐个检查 `to_upload.csv` 和 `wechat_to_upload.csv` 中的 `description` 字段：

1. 去除无意义的数字串、订单号
2. 将 "交易对方|商品名称" 中的商品名称替换为更清晰的描述
3. 确保 description 与历史风格一致
4. 标记需要打 tags 的记录（如房租、交通、零食等）

**常见 description 映射参考**：

| 原始描述 | 清理后 | tags |
|----------|--------|------|
| 每惠多 / 每惠多超市\|生活超市 | 零食 | 零食 |
| 联华超市华联龙南店\|... | 零食 | 零食 |
| 友邻便利\|... | 零食 | 零食 |
| 贝壳租房\|租房订单 | 房租 | 大宗收支 |
| 上海申通地铁...\|徐家汇-龙耀路 | 地铁徐家汇到龙耀路 | 交通 |
| 杭州杭港地铁... | 地铁 | 交通 |
| 铁路12306\|火车票 | 火车票 | 交通 |
| 游泳学院俱乐部\|... | 游泳 | 娱乐休闲 |
| 拼多多平台商户\|... | 拼多多 | 零食 |
| 唯品会\|... | 唯品会 | 零食 |
| 京东\|... | 京东 | 日用消耗 |
| 玉林**店\|湿毒清... | 买药 | 医药健康 |
| 海王易点药\|... | 买药 | 医药健康 |
| 美餐\|易生活订单 | 正餐 | 零食 |
| 叩福 / CORAL | 正餐 | 零食 |
| 亚中辅料 | 食材 | 零食 |
| 平杰造型\|收钱码收款 | 理发 | |
| DogAPI | DogAPI充值 | 日用消耗 |
| XUNJI APP PRO | XUNJI APP | 日用消耗 |
| 小米手环... | 小米手环 | 日用消耗 |
| 北京月之暗面科技有限公司 | Kimi会员 | 日用消耗 |
| 乐喝咖啡... | 咖啡 | 零食 |
| 高雨杂货店\|收钱码收款 | 日用消耗 | |

**默认清理规则**：
- 如果 `|` 后面的商品描述超过 20 字，或是订单号、包含"复制"、"NO."等，只保留商家名
- 如果商家名和商品名重复，只保留一个

### Phase 6: 上传到服务器

```bash
# 支付宝（先 dry-run 预览）
sailzen finance create-from-csv to_upload.csv --server http://<host>:<port> --dry-run
sailzen finance create-from-csv to_upload.csv --server http://<host>:<port>

# 微信（先 dry-run 预览）
sailzen finance create-from-csv wechat_to_upload.csv --server http://<host>:<port> --dry-run
sailzen finance create-from-csv wechat_to_upload.csv --server http://<host>:<port>
```

### Phase 7: 验证上传结果

1. 重新 pull 服务器记录，对比记录数是否增加
   ```bash
   sailzen finance pull --account 5 --output alipay_trans_new.csv --server http://<host>:<port>
   sailzen finance pull --account 6 --output wechat_trans_new.csv --server http://<host>:<port>
   ```
2. 抽查几条新上传的记录，确认日期、金额、description 正确
3. 检查是否有重复上传（同一日期同一金额出现多次）
4. 用新的 pull 结果替换旧的 `alipay_trans.csv` 和 `wechat_trans.csv`

## 关键约束

1. **只导入支出记录**，收入和转账不计入
2. **去重键是 (日期, abs(金额))**，同一天同金额的记录可能漏掉或误删，需人工复核
3. **description 必须人工检查**，自动生成的描述往往包含乱码或无意义信息
4. **上传前必须 dry-run**
5. **上传后必须验证**
6. **不要修改历史文件**，只生成新的 `*_trans.csv` 和 `*_to_upload.csv`
7. **微信文件选择必须正确**，多个 xlsx 时要用日期提取排序，不能简单字符串排序

## 故障排除

| 问题 | 可能原因 | 解决方案 |
|------|----------|----------|
| 支付宝账单乱码 | 编码不是 GBK | 尝试 gb18030 或 utf-8 |
| 微信 xlsx 解析失败 | 格式变化 | 检查表头行位置 |
| 微信去重后记录数为 0 | 选错了 xlsx 文件 | 检查文件名日期，用 extract_date 排序 |
| 去重后记录数异常 | 重复记录被误删 | 检查同一天同金额的记录 |
| 上传失败 | 服务器不可达 | 检查服务器地址和网络 |
| description 乱码 | 原始账单编码问题 | 手动修正 description |

## 扩展

此 Skill 可与 `sailzen-finance-auto-tag` 联动：
1. 先用本 Skill 导入新交易
2. 再用 auto-tag Skill 为未标签交易自动分类
