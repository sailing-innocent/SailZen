/**
 * @file money.example.ts
 * @brief Money class usage examples
 * @author sailing-innocent
 * @date 2025-10-27
 */

import { Money } from './money'

// ============================================================
// 创建 Money 对象的各种方式
// ============================================================

// 方式 1: 从 "值 货币" 格式的字符串创建
const money1 = new Money('1000.00 CNY')
console.log(money1.toString()) // "1000.00 CNY"

// 方式 2: 从纯数字字符串创建（默认货币为 CNY）
const money2 = new Money('500.00')
console.log(money2.toString()) // "500.00 CNY"

// 方式 3: 从数字和货币代码创建
const money3 = new Money(750.50, 'USD')
console.log(money3.toString()) // "750.50 USD"

// 方式 4: 仅从数字创建（默认货币为 CNY）
const money4 = new Money(250)
console.log(money4.toString()) // "250.00 CNY"

// ============================================================
// 访问属性
// ============================================================

console.log(money1.value) // 1000.00
console.log(money1.currency) // "CNY"

// ============================================================
// 比较操作（仅支持相同货币）
// ============================================================

const price1 = new Money('100.00 CNY')
const price2 = new Money('200.00 CNY')

// 比较大小
console.log(price1.lessThan(price2)) // true
console.log(price2.greaterThan(price1)) // true
console.log(price1.equals(price1)) // true

// 通用比较方法
console.log(price1.compare(price2)) // 负数（price1 < price2）
console.log(price2.compare(price1)) // 正数（price2 > price1）
console.log(price1.compare(price1)) // 0（相等）

// 大于等于 / 小于等于
console.log(price1.lessThanOrEqual(price2)) // true
console.log(price2.greaterThanOrEqual(price1)) // true

// ============================================================
// 算术运算（仅支持相同货币）
// ============================================================

// 加法
const total = price1.add(price2)
console.log(total.toString()) // "300.00 CNY"

// 减法
const difference = price2.subtract(price1)
console.log(difference.toString()) // "100.00 CNY"

// 乘法（乘以标量）
const doubled = price1.multiply(2)
console.log(doubled.toString()) // "200.00 CNY"

// 除法（除以标量）
const half = price2.divide(2)
console.log(half.toString()) // "100.00 CNY"

// ============================================================
// 格式化输出
// ============================================================

const amount = new Money('1234.56 CNY')

// 标准格式
console.log(amount.toString()) // "1234.56 CNY"

// 本地化格式
console.log(amount.toFormattedString()) // "CN¥1,234.56" (取决于 Intl 设置)

// ============================================================
// 实际使用场景
// ============================================================

// 场景 1: 从后端 API 返回的字符串创建
const apiResponse = { amount: '999.99', currency: 'CNY' }
const productPrice = new Money(`${apiResponse.amount} ${apiResponse.currency}`)

// 场景 2: 计算购物车总价
const items = [
  new Money('100.00 CNY'),
  new Money('200.00 CNY'),
  new Money('150.50 CNY'),
]
const cartTotal = items.reduce((sum, item) => sum.add(item), new Money('0 CNY'))
console.log(cartTotal.toString()) // "450.50 CNY"

// 场景 3: 计算折扣
const originalPrice = new Money('1000.00 CNY')
const discount = 0.8 // 8折
const discountedPrice = originalPrice.multiply(discount)
console.log(discountedPrice.toString()) // "800.00 CNY"

// 场景 4: 检查是否有足够余额
const accountBalance = new Money('500.00 CNY')
const purchaseAmount = new Money('300.00 CNY')

if (accountBalance.greaterThanOrEqual(purchaseAmount)) {
  const remaining = accountBalance.subtract(purchaseAmount)
  console.log(`购买成功！剩余余额: ${remaining.toString()}`)
} else {
  console.log('余额不足')
}

// 场景 5: 排序价格列表
const prices = [
  new Money('500.00 CNY'),
  new Money('100.00 CNY'),
  new Money('300.00 CNY'),
]

const sortedPrices = prices.sort((a, b) => a.compare(b))
sortedPrices.forEach((price) => console.log(price.toString()))
// 输出:
// "100.00 CNY"
// "300.00 CNY"
// "500.00 CNY"

// ============================================================
// 错误处理
// ============================================================

try {
  // 错误: 比较不同货币
  const cny = new Money('100.00 CNY')
  const usd = new Money('100.00 USD')
  cny.greaterThan(usd) // 抛出错误
} catch (error) {
  console.error(error.message) // "Cannot compare different currencies: CNY and USD"
}

try {
  // 错误: 除以零
  const money = new Money('100.00 CNY')
  money.divide(0) // 抛出错误
} catch (error) {
  console.error(error.message) // "Cannot divide by zero"
}

try {
  // 错误: 无效的字符串格式
  const invalid = new Money('invalid') // 抛出错误
} catch (error) {
  console.error(error.message) // "Invalid money value"
}


