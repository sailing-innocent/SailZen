# 物资管理功能测试指南

## 概述

本指南提供物资管理（Necessity）模块的标准测试场景，用于验证功能闭环。

## 前置条件

1. **启动后端服务**
   ```bash
   cd sail_server
   python -m uvicorn main:app --reload --port 8000
   ```

2. **启动前端服务**
   ```bash
   cd packages/site
   npm run dev
   ```

3. **确保数据库已初始化**
   - 运行数据库迁移脚本 `sail_server/migration/create_necessity_tables.sql`

---

## 场景一：基础物资管理流程

### 步骤 1：访问物资管理页面

1. 打开浏览器访问 `http://localhost:5173`
2. 通过以下任一方式进入物资管理：
   - 点击侧边栏的 **"物资"** 菜单项（带有 📦 图标）
   - 点击首页快捷入口中的 **"物资"** 卡片
   - 直接访问 `http://localhost:5173/necessity`

**预期结果**：
- 页面标题显示 "物资管理"
- 左侧显示住所选择器（可能为空）
- 右侧显示库存/物资标签页

### 步骤 2：初始化物资类别

1. 如果显示 **"初始化物资类别"** 按钮，点击它
2. 等待初始化完成

**预期结果**：
- 按钮消失
- 系统预设类别已创建（证件文件、电子设备、衣物等）

### 步骤 3：创建第一个物资

1. 点击页面右上角的 **"添加物资"** 按钮
2. 填写物资信息：
   - 名称：`MacBook Pro 16寸`
   - 类型：唯一物品
   - 品牌：`Apple`
   - 描述：`工作用笔记本电脑`
   - 重要程度：5
   - 便携性：3
3. 点击 **"创建"**

**预期结果**：
- 对话框关闭
- 物资列表中显示新创建的物资
- 状态显示为 "正常"

### 步骤 4：查看物资列表

1. 切换到 **"物资"** 标签页
2. 查看物资表格

**预期结果**：
- 表格显示刚创建的物资
- 显示名称、类型、品牌、重要性（星星）、状态

---

## 场景二：住所与库存管理

### 步骤 1：创建住所（通过 API）

目前 UI 暂不支持创建住所，可通过 API 创建：

```bash
# 创建稳定仓库（合肥）
curl -X POST http://localhost:8000/api/v1/necessity/residence/ \
  -H "Content-Type: application/json" \
  -d '{
    "name": "合肥家",
    "code": "HF",
    "type": 0,
    "description": "合肥的家，作为主要物资存放地",
    "is_portable": false
  }'

# 创建生活住所（杭州）
curl -X POST http://localhost:8000/api/v1/necessity/residence/ \
  -H "Content-Type: application/json" \
  -d '{
    "name": "杭州租房",
    "code": "HZ",
    "type": 2,
    "description": "杭州工作租房",
    "is_portable": false
  }'

# 创建随身携带
curl -X POST http://localhost:8000/api/v1/necessity/residence/ \
  -H "Content-Type: application/json" \
  -d '{
    "name": "随身携带",
    "code": "PORTABLE",
    "type": 3,
    "description": "随身携带的物品",
    "is_portable": true
  }'
```

### 步骤 2：刷新页面并选择住所

1. 刷新物资管理页面
2. 在左侧住所选择器中点击任一住所

**预期结果**：
- 住所卡片显示为选中状态（蓝色边框）
- 右侧显示该住所的统计信息
- 库存列表更新（可能为空）

### 步骤 3：创建库存记录（通过 API）

```bash
# 假设物资ID为1，住所ID为1
curl -X POST http://localhost:8000/api/v1/necessity/inventory/ \
  -H "Content-Type: application/json" \
  -d '{
    "item_id": 1,
    "residence_id": 1,
    "quantity": "1",
    "unit": "台",
    "min_quantity": "1"
  }'
```

### 步骤 4：查看库存

1. 刷新页面
2. 选择对应住所
3. 查看库存标签页

**预期结果**：
- 统计卡片显示物资种类、总数量、低库存数量
- 库存表格显示物资详情

---

## 场景三：批量消耗品管理

### 步骤 1：创建消耗品

1. 点击 **"添加物资"**
2. 填写信息：
   - 名称：`抽纸`
   - 类型：批量物品
   - 品牌：`维达`
   - 重要程度：3
   - 便携性：5
3. 点击 **"创建"**

### 步骤 2：添加库存（通过 API）

```bash
# 假设抽纸物资ID为2，住所ID为1
curl -X POST http://localhost:8000/api/v1/necessity/inventory/ \
  -H "Content-Type: application/json" \
  -d '{
    "item_id": 2,
    "residence_id": 1,
    "quantity": "20",
    "unit": "包",
    "min_quantity": "5"
  }'
```

### 步骤 3：记录消耗（通过 API）

```bash
# 假设库存ID为2
curl -X POST http://localhost:8000/api/v1/necessity/inventory/2/consume \
  -H "Content-Type: application/json" \
  -d '{
    "quantity": "3",
    "reason": "日常使用"
  }'
```

### 步骤 4：验证低库存预警

1. 刷新页面
2. 查看库存列表

**预期结果**：
- 当库存低于最低库存时，显示红色 "低库存" 标签
- 统计卡片中低库存数量增加

---

## 场景四：旅程物资管理

### 步骤 1：创建旅程（通过 API）

```bash
# 从合肥到杭州的旅程
curl -X POST http://localhost:8000/api/v1/necessity/journey/ \
  -H "Content-Type: application/json" \
  -d '{
    "from_residence_id": 1,
    "to_residence_id": 2,
    "planned_start": "2026-02-05T08:00:00",
    "planned_end": "2026-02-05T12:00:00",
    "transport_mode": "高铁"
  }'
```

### 步骤 2：查看旅程卡片

1. 刷新页面
2. 查看左侧的旅程卡片

**预期结果**：
- 显示 "进行中的旅程" 或 "计划中的旅程"
- 显示起止住所和交通方式

### 步骤 3：管理旅程状态（通过 API）

```bash
# 开始旅程
curl -X POST http://localhost:8000/api/v1/necessity/journey/1/start

# 完成旅程
curl -X POST http://localhost:8000/api/v1/necessity/journey/1/complete
```

---

## 场景五：移动端测试

### 步骤 1：使用浏览器开发者工具

1. 按 F12 打开开发者工具
2. 切换到移动端视图（Ctrl+Shift+M）
3. 选择 iPhone 或 Android 设备

### 步骤 2：测试移动端导航

1. 点击右上角的菜单图标 (☰)
2. 在抽屉菜单中点击 **"物资"**

**预期结果**：
- 抽屉菜单正常展开
- 显示所有菜单项及图标
- 点击后正确跳转到物资管理页面

### 步骤 3：测试响应式布局

1. 查看物资管理页面布局

**预期结果**：
- 住所选择器和主内容区垂直排列
- 表格可横向滚动
- 按钮和表单正常显示

---

## 常见问题排查

### 问题 1：页面显示 "Loading..."

**原因**：后端服务未启动或网络问题

**解决方案**：
1. 确认后端服务正在运行
2. 检查 `packages/site/src/lib/api/config.ts` 中的 `SERVER_URL` 配置

### 问题 2：住所列表为空

**原因**：数据库中没有住所数据

**解决方案**：
1. 通过 API 创建住所
2. 或运行数据库种子脚本

### 问题 3：物资创建失败

**原因**：API 请求失败

**解决方案**：
1. 检查浏览器控制台错误信息
2. 检查后端日志
3. 确认数据库表已创建

### 问题 4：导航菜单不显示物资入口

**原因**：配置文件未更新（已修复）

**解决方案**：
1. 确认 `src/config/basic.ts` 中包含 Necessity 路由
2. 重启前端开发服务器

---

## API 端点参考

| 功能 | 方法 | 端点 |
|------|------|------|
| 获取住所列表 | GET | `/api/v1/necessity/residence/` |
| 创建住所 | POST | `/api/v1/necessity/residence/` |
| 获取物资列表 | GET | `/api/v1/necessity/item/` |
| 创建物资 | POST | `/api/v1/necessity/item/` |
| 获取库存列表 | GET | `/api/v1/necessity/inventory/` |
| 获取住所库存 | GET | `/api/v1/necessity/residence/{id}/inventory` |
| 获取低库存 | GET | `/api/v1/necessity/inventory/low-stock/` |
| 消耗库存 | POST | `/api/v1/necessity/inventory/{id}/consume` |
| 补货 | POST | `/api/v1/necessity/inventory/{id}/replenish` |
| 转移库存 | POST | `/api/v1/necessity/inventory/transfer` |
| 获取旅程列表 | GET | `/api/v1/necessity/journey/` |
| 创建旅程 | POST | `/api/v1/necessity/journey/` |
| 开始旅程 | POST | `/api/v1/necessity/journey/{id}/start` |
| 完成旅程 | POST | `/api/v1/necessity/journey/{id}/complete` |

---

## 测试检查清单

- [ ] 导航菜单显示 "物资" 入口
- [ ] 首页快捷入口可点击
- [ ] 物资页面正常加载
- [ ] 可以初始化物资类别
- [ ] 可以创建新物资
- [ ] 物资列表正确显示
- [ ] 可以删除物资
- [ ] 住所选择器正常工作
- [ ] 库存表格正确显示
- [ ] 低库存预警正常
- [ ] 统计卡片数据正确
- [ ] 旅程卡片正常显示
- [ ] 移动端导航正常
- [ ] 移动端布局正确
