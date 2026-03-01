// helper function to format money value to string

export function formatMoney(value: number) {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'CNY',
  }).format(value)
}

export class Money {
  private _value: number
  private _currency: string

  // Constructor supports multiple formats:
  // - Money("1000.00 CNY")
  // - Money("1000.00") - defaults to CNY
  // - Money(1000.00, "CNY")
  // - Money(1000.00) - defaults to CNY
  // - Money(null/undefined/"") - defaults to 0
  constructor(value: string | number | null | undefined, currency?: string) {
    // Handle null/undefined
    if (value === null || value === undefined) {
      this._value = 0
      this._currency = currency || 'CNY'
      return
    }

    if (typeof value === 'string') {
      const trimmed = value.trim()
      // Handle empty string
      if (trimmed === '') {
        this._value = 0
        this._currency = currency || 'CNY'
        return
      }
      const parts = trimmed.split(/\s+/)
      if (parts.length === 2) {
        // Format: "1000.00 CNY"
        this._value = parseFloat(parts[0])
        this._currency = parts[1]
      } else if (parts.length === 1) {
        // Format: "1000.00" - defaults to CNY
        this._value = parseFloat(parts[0])
        this._currency = currency || 'CNY'
      } else {
        throw new Error('Invalid money string format')
      }
    } else {
      // Format: Money(1000.00, "CNY") or Money(1000.00)
      this._value = value
      this._currency = currency || 'CNY'
    }

    if (isNaN(this._value)) {
      this._value = 0
    }
  }

  get value(): number {
    return this._value
  }

  get currency(): string {
    return this._currency
  }

  // Check if two money objects have the same currency
  private assertSameCurrency(other: Money): void {
    if (this._currency !== other._currency) {
      throw new Error(`Cannot compare different currencies: ${this._currency} and ${other._currency}`)
    }
  }

  // Compare two money objects (returns negative if this < other, 0 if equal, positive if this > other)
  compare(other: Money): number {
    this.assertSameCurrency(other)
    return this._value - other._value
  }

  // Check if two money objects are equal
  equals(other: Money): boolean {
    return this._currency === other._currency && this._value === other._value
  }

  // Check if this money is greater than other
  greaterThan(other: Money): boolean {
    this.assertSameCurrency(other)
    return this._value > other._value
  }

  // Check if this money is greater than or equal to other
  greaterThanOrEqual(other: Money): boolean {
    this.assertSameCurrency(other)
    return this._value >= other._value
  }

  // Check if this money is less than other
  lessThan(other: Money): boolean {
    this.assertSameCurrency(other)
    return this._value < other._value
  }

  // Check if this money is less than or equal to other
  lessThanOrEqual(other: Money): boolean {
    this.assertSameCurrency(other)
    return this._value <= other._value
  }

  // Add two money objects
  add(other: Money): Money {
    this.assertSameCurrency(other)
    return new Money(this._value + other._value, this._currency)
  }

  // Subtract two money objects
  subtract(other: Money): Money {
    this.assertSameCurrency(other)
    return new Money(this._value - other._value, this._currency)
  }

  // Multiply money by a scalar
  multiply(scalar: number): Money {
    return new Money(this._value * scalar, this._currency)
  }

  // Divide money by a scalar
  divide(scalar: number): Money {
    if (scalar === 0) {
      throw new Error('Cannot divide by zero')
    }
    return new Money(this._value / scalar, this._currency)
  }

  // Convert to string format "1000.00 CNY"
  toString(): string {
    return `${this._value.toFixed(2)} ${this._currency}`
  }

  // Convert to formatted string using Intl
  toFormattedString(): string {
    return formatMoney(this._value)
  }

  // Alias for toFormattedString() for convenience
  format(): string {
    return this.toFormattedString()
  }
}