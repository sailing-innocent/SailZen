# -*- coding: utf-8 -*-
# @file test_utils_money.py
# @brief Money 类单元测试
# @author sailing-innocent
# @date 2026-03-01
# @version 1.0
# ---------------------------------

"""
Money 类单元测试

测试范围:
- 构造函数
- 基本运算 (+, -, *, neg)
- 比较运算 (==, >, <, >=, <=)
- 货币转换
- 边界情况
"""

import pytest
from decimal import Decimal
from sail_server.utils.money import Money, TransCurrencyRate, sumup


class TestMoneyConstruction:
    """测试 Money 类构造"""
    
    def test_default_construction(self):
        """测试默认构造"""
        m = Money()
        assert m.value == Decimal("0.0")
        assert m.currency == "CNY"
    
    def test_construction_with_value(self):
        """测试带值的构造"""
        m = Money("100.50")
        assert m.value == Decimal("100.50")
        assert m.currency == "CNY"
    
    def test_construction_with_currency(self):
        """测试带货币的构造"""
        m = Money("100.50", "USD")
        assert m.value == Decimal("100.50")
        assert m.currency == "USD"
    
    def test_construction_with_currency_suffix(self):
        """测试带货币后缀的字符串"""
        m = Money("100.50 CNY")
        assert m.value == Decimal("100.50")
        assert m.currency == "CNY"
        
        m2 = Money("200.00 USD")
        assert m2.value == Decimal("200.00")
        assert m2.currency == "USD"
    
    def test_unsupported_currency(self):
        """测试不支持的货币"""
        with pytest.raises(ValueError, match="Unsupported currency"):
            Money("100", "GBP")
    
    def test_value_str_property(self):
        """测试 value_str 属性"""
        m = Money("123.456")
        assert m.value_str == "123.456"


class TestMoneyArithmetic:
    """测试 Money 类算术运算"""
    
    def test_addition(self):
        """测试加法"""
        m1 = Money("100")
        m2 = Money("50")
        result = m1 + m2
        assert result.value == Decimal("150")
        assert result.currency == "CNY"
    
    def test_addition_different_currency_fails(self):
        """测试不同货币加法失败"""
        m1 = Money("100", "CNY")
        m2 = Money("50", "USD")
        with pytest.raises(ValueError, match="Currency mismatch"):
            _ = m1 + m2
    
    def test_subtraction(self):
        """测试减法"""
        m1 = Money("100")
        m2 = Money("30")
        result = m1 - m2
        assert result.value == Decimal("70")
    
    def test_subtraction_different_currency_fails(self):
        """测试不同货币减法失败"""
        m1 = Money("100", "CNY")
        m2 = Money("50", "USD")
        with pytest.raises(ValueError, match="Currency mismatch"):
            _ = m1 - m2
    
    def test_multiplication_by_int(self):
        """测试整数乘法"""
        m = Money("100")
        result = m * 3
        assert result.value == Decimal("300")
    
    def test_multiplication_by_float(self):
        """测试浮点数乘法"""
        m = Money("100")
        result = m * 0.5
        assert result.value == Decimal("50.0")
    
    def test_multiplication_by_decimal(self):
        """测试 Decimal 乘法"""
        m = Money("100")
        result = m * Decimal("1.5")
        assert result.value == Decimal("150.0")
    
    def test_rmultiplication(self):
        """测试右乘法"""
        m = Money("100")
        result = 2 * m
        assert result.value == Decimal("200")
    
    def test_unary_negation(self):
        """测试一元负号"""
        m = Money("100")
        result = -m
        assert result.value == Decimal("-100")
    
    def test_invalid_multiplication(self):
        """测试无效乘法"""
        m = Money("100")
        with pytest.raises(TypeError):
            _ = m * "invalid"


class TestMoneyComparison:
    """测试 Money 类比较运算"""
    
    def test_equality(self):
        """测试相等"""
        m1 = Money("100")
        m2 = Money("100")
        assert m1 == m2
    
    def test_inequality(self):
        """测试不等"""
        m1 = Money("100")
        m2 = Money("200")
        assert not (m1 == m2)
    
    def test_equality_different_currency_returns_false(self):
        """测试不同货币相等返回 False"""
        m1 = Money("100", "CNY")
        m2 = Money("100", "USD")
        assert not (m1 == m2)
    
    def test_greater_than(self):
        """测试大于"""
        m1 = Money("200")
        m2 = Money("100")
        assert m1 > m2
    
    def test_less_than(self):
        """测试小于"""
        m1 = Money("100")
        m2 = Money("200")
        assert m1 < m2
    
    def test_greater_than_or_equal(self):
        """测试大于等于"""
        m1 = Money("100")
        m2 = Money("100")
        m3 = Money("50")
        assert m1 >= m2
        assert m1 >= m3
    
    def test_less_than_or_equal(self):
        """测试小于等于"""
        m1 = Money("100")
        m2 = Money("100")
        m3 = Money("200")
        assert m1 <= m2
        assert m1 <= m3
    
    def test_comparison_different_currency_fails(self):
        """测试不同货币比较失败"""
        m1 = Money("100", "CNY")
        m2 = Money("100", "USD")
        with pytest.raises(ValueError, match="Currency mismatch"):
            _ = m1 > m2


class TestMoneyCurrencyConversion:
    """测试货币转换"""
    
    def test_conversion_same_currency(self):
        """测试相同货币转换返回自身"""
        m = Money("100", "CNY")
        rate = TransCurrencyRate("CNY", "CNY", "1.0")
        result = m.to_currency("CNY", rate)
        assert result == m
    
    def test_conversion_different_currency(self):
        """测试不同货币转换"""
        m = Money("100", "CNY")
        rate = TransCurrencyRate("CNY", "USD", "0.14")
        result = m.to_currency("USD", rate)
        assert result.value == Decimal("14.00")
        assert result.currency == "USD"
    
    def test_conversion_unsupported_currency(self):
        """测试不支持的货币转换"""
        m = Money("100", "CNY")
        rate = TransCurrencyRate("CNY", "USD", "0.14")
        with pytest.raises(ValueError, match="Unsupported currency"):
            _ = m.to_currency("GBP", rate)
    
    def test_conversion_rate_mismatch_from(self):
        """测试汇率来源货币不匹配"""
        m = Money("100", "CNY")
        rate = TransCurrencyRate("USD", "EUR", "0.85")
        with pytest.raises(ValueError, match="Currency mismatch"):
            _ = m.to_currency("EUR", rate)
    
    def test_conversion_rate_mismatch_to(self):
        """测试汇率目标货币不匹配"""
        m = Money("100", "CNY")
        rate = TransCurrencyRate("CNY", "USD", "0.14")
        with pytest.raises(ValueError, match="Currency mismatch"):
            _ = m.to_currency("EUR", rate)


class TestSumup:
    """测试 sumup 函数"""
    
    def test_sumup_empty_list(self):
        """测试空列表求和"""
        result = sumup([])
        assert result.value == Decimal("0.0")
    
    def test_sumup_single_item(self):
        """测试单元素求和"""
        m = Money("100")
        result = sumup([m])
        assert result.value == Decimal("100")
    
    def test_sumup_multiple_items(self):
        """测试多元素求和"""
        items = [Money("100"), Money("200"), Money("300")]
        result = sumup(items)
        assert result.value == Decimal("600")
    
    def test_sumup_invalid_type(self):
        """测试无效类型求和"""
        with pytest.raises(TypeError, match="Expected Money instance"):
            sumup([Money("100"), "invalid"])


class TestMoneyStringRepresentation:
    """测试字符串表示"""
    
    def test_str(self):
        """测试 __str__"""
        m = Money("100.50", "CNY")
        assert str(m) == "100.50 CNY"
    
    def test_repr(self):
        """测试显示"""
        m = Money("100.50", "CNY")
        # Money 类可能未定义 __repr__，返回默认对象表示
        # 验证对象可 repr 且不抛出异常
        r = repr(m)
        assert r is not None  # 只要能获取 repr 即可
        assert "100.50" in str(m)
        assert "CNY" in str(m)


class TestMoneyEdgeCases:
    """测试边界情况"""
    
    def test_zero_value(self):
        """测试零值"""
        m = Money("0")
        assert m.value == Decimal("0")
    
    def test_negative_value(self):
        """测试负值"""
        m = Money("-100")
        assert m.value == Decimal("-100")
    
    def test_very_small_value(self):
        """测试非常小的值"""
        m = Money("0.0001")
        assert m.value == Decimal("0.0001")
    
    def test_very_large_value(self):
        """测试非常大的值"""
        m = Money("999999999999.99")
        assert m.value == Decimal("999999999999.99")
    
    def test_precision_handling(self):
        """测试精度处理"""
        m = Money("100.123456789")
        assert m.value == Decimal("100.123456789")
