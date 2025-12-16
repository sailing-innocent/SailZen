# 时间戳字段迁移说明

## 概述
本迁移将代码库中所有 `ctime` 和 `mtime` 字段从 `Integer`/`BigInteger` 类型转换为 `TIMESTAMP` 类型，以提供更好的时间处理能力和一致性。

## 受影响的表
- `transactions` - 交易表
- `accounts` - 账户表  
- `chapter` - 章节表
- `vault_note` - 保险库笔记表
- `projects` - 项目表

## 迁移文件说明

### 1. 单独迁移文件
- `alter_table_transaction.sql` - 交易表迁移（已存在）
- `alter_table_account.sql` - 账户表迁移
- `alter_table_content.sql` - 内容表迁移（章节和保险库笔记）
- `alter_table_life.sql` - 生活表迁移（项目）

### 2. 综合迁移文件
- `migrate_all_timestamps.sql` - 包含所有迁移的综合脚本

## 迁移执行方式

### 方式一：单独执行（推荐）
```sql
-- 按顺序执行各个迁移文件
\i internal/migration/alter_table_transaction.sql
\i internal/migration/alter_table_account.sql  
\i internal/migration/alter_table_content.sql
\i internal/migration/alter_table_life.sql
```

### 方式二：一次性执行
```sql
-- 执行综合迁移脚本
\i internal/migration/migrate_all_timestamps.sql
```

## 迁移步骤说明

每个迁移文件都遵循相同的安全迁移模式：

1. **添加临时列** - 创建新的 TIMESTAMP 列
2. **数据转换** - 将现有整数时间戳转换为 TIMESTAMP
3. **处理空值** - 为 NULL 值设置当前时间戳
4. **删除旧列** - 移除原有的整数列
5. **重命名列** - 将临时列重命名为原列名
6. **设置默认值** - 为新列设置默认值

## 注意事项

### 执行前准备
- 备份数据库
- 确保应用已停止运行
- 验证所有表结构

### 执行后验证
```sql
-- 验证表结构
\d transactions
\d accounts  
\d chapter
\d vault_note
\d projects

-- 验证数据完整性
SELECT COUNT(*) FROM transactions WHERE ctime IS NULL;
SELECT COUNT(*) FROM accounts WHERE ctime IS NULL;
-- ... 其他表
```

### 回滚方案
如果需要回滚，需要：
1. 恢复数据库备份
2. 或者创建反向迁移脚本（将 TIMESTAMP 转换回整数）

## 兼容性说明

### 代码层面
- 所有数据模型已更新为使用 `TIMESTAMP` 类型
- 业务逻辑已更新为使用 `datetime.now()` 而不是 `int(time.time())`
- 数据类已更新为使用 `datetime` 类型

### 数据库层面
- 新插入的记录将自动使用 `CURRENT_TIMESTAMP` 作为默认值
- 现有数据已安全转换为 TIMESTAMP 格式
- 所有时间戳操作现在使用标准的 SQL TIMESTAMP 函数

## 执行时间估算
- 小规模数据库（< 10万条记录）：1-5分钟
- 中等规模数据库（10万-100万条记录）：5-30分钟  
- 大规模数据库（> 100万条记录）：30分钟以上

## 故障排除

### 常见问题
1. **权限不足** - 确保数据库用户有 ALTER TABLE 权限
2. **数据转换失败** - 检查是否有无效的时间戳值
3. **外键约束** - 确保没有外键约束阻止列删除

### 日志检查
```sql
-- 检查迁移过程中的错误
SELECT * FROM pg_stat_activity WHERE state = 'active';
```

## 联系信息
如有问题，请联系开发团队或查看相关文档。
