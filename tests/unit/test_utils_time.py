# -*- coding: utf-8 -*-
# @file test_utils_time.py
# @brief time_utils 单元测试
# @author sailing-innocent
# @date 2026-03-01
# @version 1.0
# ---------------------------------

"""
time_utils 单元测试

测试范围:
- 季度计算
- 周计算
- 双周计算
- QuarterBiWeekTime 类
- 边界情况
"""

import pytest
from datetime import datetime, timedelta
from sail_server.utils.time_utils import (
    getQuarterFromMonth,
    getQuarterStartEnd,
    startOfISOWeek,
    endOfISOWeek,
    isWithIn,
    listFullWeeksInQuarter,
    listFullBiweeksInQuarter,
    QuarterBiWeekTime,
    Week,
    QuarterBiWeek,
)


class TestQuarterFromMonth:
    """测试 getQuarterFromMonth 函数"""
    
    @pytest.mark.parametrize("month,expected", [
        (1, 1), (2, 1), (3, 1),
        (4, 2), (5, 2), (6, 2),
        (7, 3), (8, 3), (9, 3),
        (10, 4), (11, 4), (12, 4),
    ])
    def test_all_months(self, month, expected):
        """测试所有月份"""
        assert getQuarterFromMonth(month) == expected


class TestQuarterStartEnd:
    """测试 getQuarterStartEnd 函数"""
    
    def test_q1_2024(self):
        """测试 2024 年 Q1"""
        start, end = getQuarterStartEnd(2024, 1)
        assert start == datetime(2024, 1, 1)
        assert end == datetime(2024, 3, 1)
    
    def test_q2_2024(self):
        """测试 2024 年 Q2"""
        start, end = getQuarterStartEnd(2024, 2)
        assert start == datetime(2024, 4, 1)
        assert end == datetime(2024, 6, 1)
    
    def test_q3_2024(self):
        """测试 2024 年 Q3"""
        start, end = getQuarterStartEnd(2024, 3)
        assert start == datetime(2024, 7, 1)
        assert end == datetime(2024, 9, 1)
    
    def test_q4_2024(self):
        """测试 2024 年 Q4"""
        start, end = getQuarterStartEnd(2024, 4)
        assert start == datetime(2024, 10, 1)
        assert end == datetime(2024, 12, 1)
    
    def test_invalid_quarter_low(self):
        """测试无效季度（太小）"""
        with pytest.raises(ValueError, match="Quarter must be in"):
            getQuarterStartEnd(2024, 0)
    
    def test_invalid_quarter_high(self):
        """测试无效季度（太大）"""
        with pytest.raises(ValueError, match="Quarter must be in"):
            getQuarterStartEnd(2024, 5)


class TestISOWeek:
    """测试 ISO 周计算"""
    
    def test_start_of_iso_week_monday(self):
        """测试周一的 ISO 周开始"""
        # 2024-01-01 是周一
        date = datetime(2024, 1, 1)
        start = startOfISOWeek(date)
        assert start == datetime(2024, 1, 1)
    
    def test_start_of_iso_week_sunday(self):
        """测试周日的 ISO 周开始"""
        # 2024-01-07 是周日
        date = datetime(2024, 1, 7)
        start = startOfISOWeek(date)
        assert start == datetime(2024, 1, 1)
    
    def test_end_of_iso_week_monday(self):
        """测试周一的 ISO 周结束"""
        date = datetime(2024, 1, 1)
        end = endOfISOWeek(date)
        assert end == datetime(2024, 1, 7)
    
    def test_end_of_iso_week_sunday(self):
        """测试周日的 ISO 周结束"""
        date = datetime(2024, 1, 7)
        end = endOfISOWeek(date)
        assert end == datetime(2024, 1, 7)


class TestIsWithIn:
    """测试 isWithIn 函数"""
    
    def test_date_within_range(self):
        """测试日期在范围内"""
        date = datetime(2024, 6, 15)
        start = datetime(2024, 6, 1)
        end = datetime(2024, 6, 30)
        assert isWithIn(date, start, end)
    
    def test_date_at_start(self):
        """测试日期在开始边界"""
        date = datetime(2024, 6, 1)
        start = datetime(2024, 6, 1)
        end = datetime(2024, 6, 30)
        assert isWithIn(date, start, end)
    
    def test_date_at_end(self):
        """测试日期在结束边界"""
        date = datetime(2024, 6, 30)
        start = datetime(2024, 6, 1)
        end = datetime(2024, 6, 30)
        assert isWithIn(date, start, end)
    
    def test_date_before_range(self):
        """测试日期在范围前"""
        date = datetime(2024, 5, 31)
        start = datetime(2024, 6, 1)
        end = datetime(2024, 6, 30)
        assert not isWithIn(date, start, end)
    
    def test_date_after_range(self):
        """测试日期在范围后"""
        date = datetime(2024, 7, 1)
        start = datetime(2024, 6, 1)
        end = datetime(2024, 6, 30)
        assert not isWithIn(date, start, end)


class TestListFullWeeksInQuarter:
    """测试 listFullWeeksInQuarter 函数"""
    
    def test_q1_2024_weeks(self):
        """测试 2024 年 Q1 的完整周"""
        weeks = listFullWeeksInQuarter(2024, 1)
        # Q1 通常有 13 周左右，但完整周数量取决于具体日期
        assert len(weeks) > 0
        
        # 验证每个周都是完整周（开始和结束都在季度内）
        q_start, q_end = getQuarterStartEnd(2024, 1)
        for week in weeks:
            assert isWithIn(week.start, q_start, q_end)
            assert isWithIn(week.end, q_start, q_end)
            # 验证是 ISO 周
            assert week.start.weekday() == 0  # 周一开始
            assert week.end.weekday() == 6     # 周日结束
    
    def test_week_structure(self):
        """测试周结构"""
        weeks = listFullWeeksInQuarter(2024, 1)
        if weeks:
            week = weeks[0]
            assert isinstance(week, Week)
            assert hasattr(week, 'start')
            assert hasattr(week, 'end')
            # 周开始和结束相差 6 天
            assert (week.end - week.start).days == 6


class TestListFullBiweeksInQuarter:
    """测试 listFullBiweeksInQuarter 函数"""
    
    def test_biweek_structure(self):
        """测试双周结构"""
        biweeks = listFullBiweeksInQuarter(2024, 1)
        assert len(biweeks) > 0
        
        for i, biweek in enumerate(biweeks):
            assert isinstance(biweek, QuarterBiWeek)
            assert biweek.index == i + 1
            assert isinstance(biweek.first_w, Week)
            assert isinstance(biweek.next_w, Week)
            # 两周连续
            assert (biweek.next_w.start - biweek.first_w.end).days == 1
    
    def test_biweek_count(self):
        """测试双周数量（取决于季度完整周数，通常为 4-6 个双周）"""
        biweeks = listFullBiweeksInQuarter(2024, 1)
        # 每个季度应有偶数个完整周，双周数量为周数的一半
        # 实际数量取决于季度天数和 ISO 周对齐
        assert len(biweeks) >= 4
        assert len(biweeks) <= 6


class TestQuarterBiWeekTime:
    """测试 QuarterBiWeekTime 类"""
    
    def test_construction(self):
        """测试构造"""
        qbwt = QuarterBiWeekTime(2024, 1, 1)
        assert qbwt.year == 2024
        assert qbwt.quarter == 1
        assert qbwt.biweek == 1
    
    def test_to_db_int(self):
        """测试转换为数据库整数"""
        qbwt = QuarterBiWeekTime(2024, 1, 1)
        db_int = qbwt.to_db_int()
        assert db_int == 20240101
    
    def test_from_db_int(self):
        """测试从数据库整数转换"""
        qbwt = QuarterBiWeekTime.from_db_int(20240102)
        assert qbwt.year == 2024
        assert qbwt.quarter == 1
        assert qbwt.biweek == 2
    
    def test_str_representation(self):
        """测试字符串表示"""
        qbwt = QuarterBiWeekTime(2024, 2, 3)
        assert str(qbwt) == "2024-2-3"
    
    def test_equality(self):
        """测试相等性"""
        qbwt1 = QuarterBiWeekTime(2024, 1, 1)
        qbwt2 = QuarterBiWeekTime(2024, 1, 1)
        assert qbwt1 == qbwt2
    
    def test_inequality(self):
        """测试不等"""
        qbwt1 = QuarterBiWeekTime(2024, 1, 1)
        qbwt2 = QuarterBiWeekTime(2024, 1, 2)
        assert qbwt1 != qbwt2
    
    def test_hash(self):
        """测试哈希"""
        qbwt = QuarterBiWeekTime(2024, 1, 1)
        hash_val = hash(qbwt)
        assert isinstance(hash_val, int)
    
    def test_from_timestamp(self):
        """测试从时间戳转换"""
        # 2024-01-15 的时间戳 (在 Q1 第一个双周内)
        timestamp = int(datetime(2024, 1, 15).timestamp())
        qbwt = QuarterBiWeekTime.from_timestamp(timestamp)
        assert qbwt.year == 2024
        # 双周索引应该合理
        assert 1 <= qbwt.biweek <= 6


class TestTimeUtilsEdgeCases:
    """测试边界情况"""
    
    def test_leap_year_q1(self):
        """测试闰年第一季度"""
        # 2024 是闰年，2月有 29 天
        start, end = getQuarterStartEnd(2024, 1)
        assert start == datetime(2024, 1, 1)
        assert end == datetime(2024, 3, 1)
    
    def test_year_boundary(self):
        """测试年份边界"""
        # Q4 结束和 Q1 开始
        q4_end = getQuarterStartEnd(2023, 4)[1]
        q1_start = getQuarterStartEnd(2024, 1)[0]
        assert (q1_start - q4_end).days > 0
    
    def test_week_consistency(self):
        """测试周一致性"""
        for quarter in range(1, 5):
            weeks = listFullWeeksInQuarter(2024, quarter)
            if len(weeks) >= 2:
                # 连续周之间相差 7 天
                for i in range(len(weeks) - 1):
                    diff = weeks[i + 1].start - weeks[i].start
                    assert diff.days == 7
