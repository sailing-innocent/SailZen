# Money 类文档

## 概述

`Money` 类是一个类型安全的货币处理工具，支持创建、比较和运算货币值。

## 主要特性

### ✅ 多种创建方式

```typescript
// 从 "值 货币" 格式字符串创建
const m1 = new Money('1000.00 CNY')

// 从纯数字字符串创建（默认 CNY）
const m2 = new Money('1000.00')

// 从数字和货币代码创建
const m3 = new Money(1000.00, 'USD')

// 从数字创建（默认 CNY）
const m4 = new Money(1000.00)
```

### ✅ 默认货币

- 默认货币为 **CNY**（人民币）
- 可以指定其他货币（USD, EUR 等）

### ✅ 同币值比较

支持完整的比较操作（仅限相同货币）：

```typescript
const price1 = new Money('100.00 CNY')
const price2 = new Money('200.00 CNY')

// 基本比较
price1.equals(price2)           // false
price1.lessThan(price2)         // true
price1.lessThanOrEqual(price2)  // true
price1.greaterThan(price2)      // false
price1.greaterThanOrEqual(price2) // false

// 通用比较（返回负数/0/正数）
price1.compare(price2)          // 负数
```

### ✅ 算术运算

支持基本算术运算（仅限相同货币）：

```typescript
const m1 = new Money('100.00 CNY')
const m2 = new Money('50.00 CNY')

// 加法
const sum = m1.add(m2)          // 150.00 CNY

// 减法
const diff = m1.subtract(m2)    // 50.00 CNY

// 乘法（乘以标量）
const doubled = m1.multiply(2)  // 200.00 CNY

// 除法（除以标量）
const half = m1.divide(2)       // 50.00 CNY
```

### ✅ 格式化输出

```typescript
const money = new Money('1234.56 CNY')

// 标准格式
money.toString()                // "1234.56 CNY"

// 本地化格式
money.toFormattedString()       // "CN¥1,234.56"
```

### ✅ 属性访问

```typescript
const money = new Money('100.00 CNY')

money.value                     // 100.00 (number)
money.currency                  // "CNY" (string)
```

## 错误处理

### 货币不匹配

比较或运算不同货币时会抛出错误：

```typescript
const cny = new Money('100.00 CNY')
const usd = new Money('100.00 USD')

cny.add(usd)  // ❌ 抛出: "Cannot compare different currencies: CNY and USD"
```

### 除以零

```typescript
const money = new Money('100.00 CNY')
money.divide(0)  // ❌ 抛出: "Cannot divide by zero"
```

### 无效格式

```typescript
new Money('invalid')  // ❌ 抛出: "Invalid money value"
```

## 实际应用场景

### 1. 购物车总价计算

```typescript
const items = [
  new Money('100.00 CNY'),
  new Money('200.00 CNY'),
  new Money('150.50 CNY'),
]

const total = items.reduce(
  (sum, item) => sum.add(item),
  new Money('0 CNY')
)
console.log(total.toString())  // "450.50 CNY"
```

### 2. 折扣计算

```typescript
const originalPrice = new Money('1000.00 CNY')
const discountRate = 0.8  // 8折

const discountedPrice = originalPrice.multiply(discountRate)
console.log(discountedPrice.toString())  // "800.00 CNY"
```

### 3. 余额检查

```typescript
const balance = new Money('500.00 CNY')
const payment = new Money('300.00 CNY')

if (balance.greaterThanOrEqual(payment)) {
  const remaining = balance.subtract(payment)
  console.log(`成功！余额: ${remaining.toString()}`)
}
```

### 4. 价格排序

```typescript
const prices = [
  new Money('500.00 CNY'),
  new Money('100.00 CNY'),
  new Money('300.00 CNY'),
]

const sorted = prices.sort((a, b) => a.compare(b))
// 结果: [100.00 CNY, 300.00 CNY, 500.00 CNY]
```

## 测试

完整的测试套件位于 `money.test.ts`，包含：
- 构造函数测试
- 比较方法测试
- 算术运算测试
- 字符串转换测试
- 边界情况测试

运行测试：
```bash
npm test -- money.test.ts
```

## 注意事项

1. **货币类型安全**：所有比较和运算操作都会检查货币类型是否一致
2. **不可变性**：所有运算都返回新的 Money 对象，不修改原对象
3. **精度处理**：使用浮点数存储，输出时格式化为两位小数
4. **默认货币**：所有未指定货币的创建都默认为 CNY

## 文件结构

- `money.ts` - Money 类实现
- `money.test.ts` - 单元测试
- `money.example.ts` - 使用示例
- `MONEY_README.md` - 本文档


