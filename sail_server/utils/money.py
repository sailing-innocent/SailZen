# -*- coding: utf-8 -*-
# @file money.py
# @brief The Money class for String-based Money calculation
# @author sailing-innocent
# @date 2024-12-21
# @version 1.0
# ---------------------------------

from decimal import Decimal
import logging


class TransCurrencyRate:
    _from_currency = "CNY"
    _to_currency = "USD"
    _rate = Decimal("1.0")

    def __init__(
        self, from_currency: str = "CNY", to_currency: str = "USD", rate: str = "1.0"
    ):
        self._from_currency = from_currency
        self._to_currency = to_currency
        self._rate = Decimal(rate)

    @property
    def rate(self):
        return self._rate

    @property
    def from_currency(self):
        return self._from_currency

    @property
    def to_currency(self):
        return self._to_currency


class Money:
    _supported_currency = [
        "CNY",
        "USD",
        "EUR",
    ]
    _value = Decimal("0.0")
    _currency = "CNY"

    def __init__(self, value: str = "0.0", currency: str = "CNY"):
        if currency not in Money._supported_currency:
            raise ValueError(f"Unsupported currency: {currency}")
        # print(value)
        self.value = Decimal(value)
        self.currency = currency

    @property
    def value(self):
        return self._value

    @property
    def value_str(self):
        return str(self.value)

    @value.setter
    def value(self, value):
        self._value = Decimal(value)

    def to_currency(self, _to_currency: str, rate: TransCurrencyRate):
        if _to_currency not in Money._supported_currency:
            raise ValueError(f"Unsupported currency: {_to_currency}")
        if self.currency == _to_currency:
            return self
        else:
            # check rate currency type
            if rate.from_currency != self.currency:
                raise ValueError(
                    f"Currency mismatch: {rate.from_currency} != {self.currency}"
                )
            if rate.to_currency != _to_currency:
                raise ValueError(
                    f"Currency mismatch: {rate.to_currency} != {_to_currency}"
                )

            return Money(self.value * rate.rate, _to_currency)

    # operator +-
    def __add__(self, other):
        if self.currency != other.currency:
            raise ValueError(f"Currency mismatch: {self.currency} != {other.currency}")
        return Money(self.value + other.value, self.currency)

    def __sub__(self, other):
        if self.currency != other.currency:
            raise ValueError(f"Currency mismatch: {self.currency} != {other.currency}")
        return Money(self.value - other.value, self.currency)

    # unary operator -
    def __neg__(self):
        return Money(-self.value, self.currency)

    # operator ==
    def __eq__(self, other):
        if self.currency != other.currency:
            logging.error(f"Currency mismatch: {self.currency} != {other.currency}")
            return False
        return self.value == other.value

    def __str__(self):
        return f"{self.value} {self.currency}"


def sumup(money_iter):
    total = Money("0.0", "CNY")
    for money in money_iter:
        if not isinstance(money, Money):
            raise TypeError(f"Expected Money instance, got {type(money)}")
        total += money
    return total
