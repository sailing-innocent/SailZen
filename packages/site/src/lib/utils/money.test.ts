/**
 * @file money.test.ts
 * @brief Money class unit tests
 * @author sailing-innocent
 * @date 2025-10-27
 */

import { Money } from './money'

describe('Money Class', () => {
  describe('Constructor', () => {
    test('should create Money from string with currency', () => {
      const money = new Money('1000.00 CNY')
      expect(money.value).toBe(1000.00)
      expect(money.currency).toBe('CNY')
    })

    test('should create Money from string without currency (defaults to CNY)', () => {
      const money = new Money('1000.00')
      expect(money.value).toBe(1000.00)
      expect(money.currency).toBe('CNY')
    })

    test('should create Money from number with currency', () => {
      const money = new Money(1000.00, 'USD')
      expect(money.value).toBe(1000.00)
      expect(money.currency).toBe('USD')
    })

    test('should create Money from number without currency (defaults to CNY)', () => {
      const money = new Money(1000.00)
      expect(money.value).toBe(1000.00)
      expect(money.currency).toBe('CNY')
    })

    test('should handle different string formats', () => {
      const money1 = new Money('500.50 USD')
      expect(money1.value).toBe(500.50)
      expect(money1.currency).toBe('USD')

      const money2 = new Money('  250.25  EUR  ')
      expect(money2.value).toBe(250.25)
      expect(money2.currency).toBe('EUR')
    })

    test('should throw error for invalid string format', () => {
      expect(() => new Money('invalid')).toThrow('Invalid money value')
      expect(() => new Money('100 CNY EUR')).toThrow('Invalid money string format')
    })
  })

  describe('Comparison Methods', () => {
    test('should compare same currency values', () => {
      const money1 = new Money('1000.00 CNY')
      const money2 = new Money('500.00 CNY')
      const money3 = new Money('1000.00 CNY')

      expect(money1.compare(money2)).toBeGreaterThan(0)
      expect(money2.compare(money1)).toBeLessThan(0)
      expect(money1.compare(money3)).toBe(0)
    })

    test('should check equality', () => {
      const money1 = new Money('1000.00 CNY')
      const money2 = new Money('1000.00 CNY')
      const money3 = new Money('500.00 CNY')
      const money4 = new Money('1000.00 USD')

      expect(money1.equals(money2)).toBe(true)
      expect(money1.equals(money3)).toBe(false)
      expect(money1.equals(money4)).toBe(false)
    })

    test('should check greater than', () => {
      const money1 = new Money('1000.00 CNY')
      const money2 = new Money('500.00 CNY')

      expect(money1.greaterThan(money2)).toBe(true)
      expect(money2.greaterThan(money1)).toBe(false)
    })

    test('should check greater than or equal', () => {
      const money1 = new Money('1000.00 CNY')
      const money2 = new Money('500.00 CNY')
      const money3 = new Money('1000.00 CNY')

      expect(money1.greaterThanOrEqual(money2)).toBe(true)
      expect(money1.greaterThanOrEqual(money3)).toBe(true)
      expect(money2.greaterThanOrEqual(money1)).toBe(false)
    })

    test('should check less than', () => {
      const money1 = new Money('500.00 CNY')
      const money2 = new Money('1000.00 CNY')

      expect(money1.lessThan(money2)).toBe(true)
      expect(money2.lessThan(money1)).toBe(false)
    })

    test('should check less than or equal', () => {
      const money1 = new Money('500.00 CNY')
      const money2 = new Money('1000.00 CNY')
      const money3 = new Money('500.00 CNY')

      expect(money1.lessThanOrEqual(money2)).toBe(true)
      expect(money1.lessThanOrEqual(money3)).toBe(true)
      expect(money2.lessThanOrEqual(money1)).toBe(false)
    })

    test('should throw error when comparing different currencies', () => {
      const money1 = new Money('1000.00 CNY')
      const money2 = new Money('500.00 USD')

      expect(() => money1.compare(money2)).toThrow('Cannot compare different currencies')
      expect(() => money1.greaterThan(money2)).toThrow('Cannot compare different currencies')
      expect(() => money1.lessThan(money2)).toThrow('Cannot compare different currencies')
    })
  })

  describe('Arithmetic Operations', () => {
    test('should add two money objects', () => {
      const money1 = new Money('1000.00 CNY')
      const money2 = new Money('500.00 CNY')
      const result = money1.add(money2)

      expect(result.value).toBe(1500.00)
      expect(result.currency).toBe('CNY')
    })

    test('should subtract two money objects', () => {
      const money1 = new Money('1000.00 CNY')
      const money2 = new Money('300.00 CNY')
      const result = money1.subtract(money2)

      expect(result.value).toBe(700.00)
      expect(result.currency).toBe('CNY')
    })

    test('should multiply money by scalar', () => {
      const money = new Money('100.00 CNY')
      const result = money.multiply(3)

      expect(result.value).toBe(300.00)
      expect(result.currency).toBe('CNY')
    })

    test('should divide money by scalar', () => {
      const money = new Money('300.00 CNY')
      const result = money.divide(3)

      expect(result.value).toBe(100.00)
      expect(result.currency).toBe('CNY')
    })

    test('should throw error when dividing by zero', () => {
      const money = new Money('100.00 CNY')
      expect(() => money.divide(0)).toThrow('Cannot divide by zero')
    })

    test('should throw error when operating on different currencies', () => {
      const money1 = new Money('1000.00 CNY')
      const money2 = new Money('500.00 USD')

      expect(() => money1.add(money2)).toThrow('Cannot compare different currencies')
      expect(() => money1.subtract(money2)).toThrow('Cannot compare different currencies')
    })
  })

  describe('String Conversion', () => {
    test('should convert to string format', () => {
      const money = new Money('1000.50 CNY')
      expect(money.toString()).toBe('1000.50 CNY')
    })

    test('should format with toFixed(2)', () => {
      const money = new Money(1000, 'CNY')
      expect(money.toString()).toBe('1000.00 CNY')
    })

    test('should convert to formatted string', () => {
      const money = new Money('1000.00 CNY')
      const formatted = money.toFormattedString()
      expect(formatted).toContain('1,000')
    })
  })

  describe('Edge Cases', () => {
    test('should handle zero values', () => {
      const money = new Money('0.00 CNY')
      expect(money.value).toBe(0)
      expect(money.currency).toBe('CNY')
    })

    test('should handle negative values', () => {
      const money = new Money('-500.00 CNY')
      expect(money.value).toBe(-500.00)
      expect(money.currency).toBe('CNY')
    })

    test('should handle very large values', () => {
      const money = new Money('9999999999.99 CNY')
      expect(money.value).toBe(9999999999.99)
      expect(money.currency).toBe('CNY')
    })

    test('should handle very small decimal values', () => {
      const money = new Money('0.01 CNY')
      expect(money.value).toBe(0.01)
      expect(money.currency).toBe('CNY')
    })
  })
})

