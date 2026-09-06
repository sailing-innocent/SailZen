# SailSite Mock API 服务器

## 简介

这是一个为 SailSite 项目开发的本地 Mock API 服务器，支持完整的增删查改操作。它模拟了所有后端 API 接口，便于前端开发和调试。

## 功能特性

### 📊 Finance API
- **账户管理** - 支持创建、查询、修改账户信息
- **交易记录** - 支持创建、查询、删除交易记录
- **余额计算** - 支持账户余额重新计算和修正

### 🏥 Health API
- **体重记录** - 支持创建、查询体重数据
- **时间范围查询** - 支持按时间范围筛选数据

### 🔧 技术特性
- **数据持久化** - 使用 JSON 文件存储数据，重启后数据不丢失
- **CORS 支持** - 支持跨域请求
- **错误处理** - 完善的错误处理和响应
- **热重载** - 支持开发模式下的热重载

## 快速开始

### 1. 安装依赖

```bash
# 安装主项目依赖
npm install

# 安装 mock 服务器依赖
npm run mock:install
```

### 2. 启动服务器

有多种启动方式：

#### 方式一：使用 npm 脚本（推荐）
```bash
# 只启动 mock 服务器
npm run mock:start

# 同时启动 mock 服务器和前端开发服务器
npm run dev:full
```

#### 方式二：使用启动脚本
```bash
# Windows PowerShell
.\start-mock.ps1

# Windows 命令提示符
start-mock.bat
```

#### 方式三：手动启动
```bash
cd mock
npm install  # 首次运行需要
npm start
```

### 3. 验证服务器

访问 http://localhost:3001/api/v1/health 应该返回：
```json
{
  "status": "ok",
  "message": "Mock server is running"
}
```

## API 接口文档

### 基础信息
- **服务器地址**: http://localhost:3001
- **API 基础路径**: /api/v1

### Health API

#### 健康检查
```
GET /api/v1/health
```

### Finance API

#### 账户相关
```
GET    /api/v1/finance/account/              # 获取所有账户
GET    /api/v1/finance/account/:id           # 获取指定账户
POST   /api/v1/finance/account/              # 创建账户
POST   /api/v1/finance/account/fix_balance/  # 修正账户余额
GET    /api/v1/finance/account/recalc_balance/:id    # 重新计算账户余额
GET    /api/v1/finance/account/update_balance/:id    # 更新账户余额
```

#### 交易相关
```
GET    /api/v1/finance/transaction/          # 获取交易记录
POST   /api/v1/finance/transaction/          # 创建交易记录
DELETE /api/v1/finance/transaction/:id       # 删除交易记录
```

### Health API

#### 体重记录
```
GET    /api/v1/health/weight/                # 获取体重记录
GET    /api/v1/health/weight/:id             # 获取指定体重记录
POST   /api/v1/health/weight/                # 创建体重记录
```

## 数据结构

### 账户数据 (AccountData)
```typescript
{
  id: number,
  name: string,
  description: string,
  balance: string,
  state: number,
  mtime: number
}
```

### 交易数据 (TransactionData)
```typescript
{
  id: number,
  from_acc_id: number,
  to_acc_id: number,
  value: string,
  description: string,
  tags: string,
  htime: number
}
```

### 体重数据 (WeightData)
```typescript
{
  id: number,
  value: string,
  htime: number
}
```

## 默认测试数据

### 账户
- 现金账户 (ID: 1) - 余额: 1000.00
- 银行卡 (ID: 2) - 余额: 5000.00
- 支付宝 (ID: 3) - 余额: 500.00

### 交易记录
- 现金 → 银行卡: 100.00 (转账测试)
- 银行卡 → 支付宝: 50.00 (充值支付宝)

### 体重记录
- 三条体重记录，时间递增

## 配置文件

### 环境变量 (.env.development)
```bash
SERVER_URL=http://localhost:3001
```

确保前端应用使用正确的服务器地址。

## 开发指南

### 文件结构
```
mock/
├── server.js          # 主服务器文件
├── package.json       # 依赖配置
└── data/              # 数据存储目录（自动创建）
    ├── accounts.json   # 账户数据
    ├── transactions.json # 交易数据
    └── weights.json    # 体重数据
```

### 数据持久化

所有数据都存储在 `mock/data/` 目录下的 JSON 文件中。首次启动时会自动创建目录和默认数据文件。

### 扩展 API

要添加新的 API 端点，只需在 `server.js` 中添加相应的路由处理器即可。

## 故障排除

### 端口冲突
如果 3001 端口被占用，可以修改 `mock/server.js` 中的 `PORT` 常量。

### 数据重置
删除 `mock/data/` 目录，重启服务器即可恢复默认数据。

### 依赖问题
```bash
# 重新安装依赖
cd mock
rm -rf node_modules
npm install
```

## 注意事项

1. Mock 服务器仅用于开发环境，不要在生产环境使用
2. 数据文件存储在本地，多人协作时注意数据同步
3. 服务器重启后数据保持不变，如需重置请删除 data 目录
4. 确保端口 3001 未被其他应用占用

## 许可证

MIT License
