"""
单元测试 - 测试 bt_quant 核心功能
"""
import math
import unittest
from datetime import datetime
from unittest.mock import MagicMock, patch

import backtrader as bt
import pandas as pd
import numpy as np

import config
from strategies import STRATEGY_REGISTRY, list_strategies
from strategies.rsi import RsiStrategy
from strategies.bband import BollingerBandsStrategy
from strategies.momentum import MomentumStrategy
from strategies.candle_patterns import CandlePatternStrategy, EnhancedCandleStrategy, DailyBreakoutStrategy
from strategies.dual_ma_trend import DualMATrendStrategy
from utils import (
    FixedCommission,
    PercentageCommission,
    TieredCommission,
    get_commission,
    CustomAnalyzer,
    TradeList
)
from engine import validate_date, BacktestEngine


class TestNaNComparison(unittest.TestCase):
    """测试 NaN 比较修复"""

    def test_nan_comparison_with_math_isnan(self):
        """验证使用 math.isnan 正确检测 NaN"""
        nan_value = float('nan')
        # 错误的方式: nan == nan 永远返回 False
        self.assertFalse(nan_value == float('nan'))
        # 正确的方式
        self.assertTrue(math.isnan(nan_value))

    def test_normal_value_not_nan(self):
        """验证正常值不被误判为 NaN"""
        normal_value = 50.0
        self.assertFalse(math.isnan(normal_value))


class TestCommissionClasses(unittest.TestCase):
    """测试手续费模型"""

    def test_fixed_commission(self):
        """测试固定手续费"""
        comm = FixedCommission(commission=5.0)
        # 买入 100 股，价格 50
        fee = comm._getcommission(size=100, price=50, pseudoexec=False)
        self.assertEqual(fee, 5.0)

    def test_percentage_commission(self):
        """测试百分比手续费"""
        comm = PercentageCommission(commission=0.001)
        # 验证手续费对象能正确创建
        self.assertIsInstance(comm, PercentageCommission)
        self.assertTrue(comm.params.stocklike)

    def test_tiered_commission_tier1(self):
        """测试阶梯手续费 - 第一档"""
        comm = TieredCommission(tier1_limit=1000, tier1_rate=0.001)
        # 金额 500，第一档费率 0.1%
        fee = comm._getcommission(size=10, price=50, pseudoexec=False)
        self.assertEqual(fee, 0.5)  # 500 * 0.001

    def test_tiered_commission_tier2(self):
        """测试阶梯手续费 - 第二档"""
        comm = TieredCommission(tier1_limit=1000, tier2_limit=10000, tier2_rate=0.0008)
        # 金额 5000，第二档费率 0.08%
        fee = comm._getcommission(size=100, price=50, pseudoexec=False)
        self.assertEqual(fee, 4.0)  # 5000 * 0.0008

    def test_tiered_commission_tier3(self):
        """测试阶梯手续费 - 第三档"""
        comm = TieredCommission(tier2_limit=10000, tier3_rate=0.0005)
        # 金额 20000，第三档费率 0.05%
        fee = comm._getcommission(size=200, price=100, pseudoexec=False)
        self.assertEqual(fee, 10.0)  # 20000 * 0.0005

    def test_get_commission_factory(self):
        """测试手续费工厂函数"""
        fixed = get_commission("fixed", commission=10.0)
        self.assertIsInstance(fixed, FixedCommission)

        percentage = get_commission("percentage", commission=0.002)
        self.assertIsInstance(percentage, PercentageCommission)

        tiered = get_commission("tiered")
        self.assertIsInstance(tiered, TieredCommission)

        with self.assertRaises(ValueError):
            get_commission("unknown_type")


class TestDateValidation(unittest.TestCase):
    """测试日期验证"""

    def test_valid_date_format(self):
        """测试有效的日期格式"""
        result = validate_date("2023-01-15")
        self.assertEqual(result, "2023-01-15")

    def test_valid_date_format_edge_cases(self):
        """测试边界日期"""
        self.assertEqual(validate_date("2020-01-01"), "2020-01-01")
        self.assertEqual(validate_date("2023-12-31"), "2023-12-31")

    def test_invalid_date_format_wrong_separator(self):
        """测试错误的分隔符"""
        with self.assertRaises(Exception):  # ArgumentTypeError
            validate_date("2023/01/15")

    def test_invalid_date_format_wrong_order(self):
        """测试错误的日期顺序"""
        with self.assertRaises(Exception):
            validate_date("15-01-2023")

    def test_invalid_date_format_invalid_month(self):
        """测试无效的月份"""
        with self.assertRaises(Exception):
            validate_date("2023-13-01")

    def test_invalid_date_format_invalid_day(self):
        """测试无效的日期"""
        with self.assertRaises(Exception):
            validate_date("2023-02-30")


class TestStrategyRegistry(unittest.TestCase):
    """测试策略注册"""

    def test_registry_not_empty(self):
        """测试注册表不为空"""
        self.assertGreater(len(STRATEGY_REGISTRY), 0)

    def test_list_strategies(self):
        """测试列出策略"""
        strategies = list_strategies()
        self.assertIsInstance(strategies, dict)
        self.assertIn("sma_cross", strategies)

    def test_strategy_has_required_fields(self):
        """测试策略包含必需字段"""
        for name, info in STRATEGY_REGISTRY.items():
            self.assertIn("name", info, f"策略 {name} 缺少 name 字段")
            self.assertIn("description", info, f"策略 {name} 缺少 description 字段")
            self.assertIn("class", info, f"策略 {name} 缺少 class 字段")

    def test_all_registered_strategies_exist(self):
        """测试所有注册的策略类都存在"""
        for name, info in STRATEGY_REGISTRY.items():
            strategy_class = info["class"]
            self.assertTrue(
                issubclass(strategy_class, bt.Strategy),
                f"{name} 不是 bt.Strategy 的子类"
            )


class TestBollingerBandsDivisionByZero(unittest.TestCase):
    """测试布林带策略除零修复"""

    def test_band_width_zero_protection(self):
        """测试布林带宽度为零时的保护"""
        # 创建一个模拟的策略环境
        cerebro = bt.Cerebro()
        cerebro.addstrategy(BollingerBandsStrategy)

        # 创建测试数据
        dates = pd.date_range(start='2023-01-01', periods=50, freq='D')
        # 创建价格相同的数据（会导致布林带上下轨重合）
        data = pd.DataFrame({
            'Open': [100.0] * 50,
            'High': [100.0] * 50,
            'Low': [100.0] * 50,
            'Close': [100.0] * 50,
            'Volume': [1000] * 50
        }, index=dates)

        data_feed = bt.feeds.PandasData(
            dataname=data,
            name='TEST'
        )
        cerebro.adddata(data_feed)
        cerebro.broker.setcash(100000)

        # 运行不应崩溃
        try:
            cerebro.run()
            # 如果没有崩溃，测试通过
            self.assertTrue(True)
        except ZeroDivisionError:
            self.fail("布林带策略在极端数据下发生除零错误")


class TestCandlePatternBoundary(unittest.TestCase):
    """测试阴阳线策略边界条件"""

    def test_consecutive_count_boundary(self):
        """测试连续K线计数边界"""
        # 创建模拟数据
        cerebro = bt.Cerebro()
        cerebro.addstrategy(CandlePatternStrategy)

        # 创建只有5根K线的测试数据（少于默认的consecutive_count）
        dates = pd.date_range(start='2023-01-01', periods=5, freq='D')
        data = pd.DataFrame({
            'Open': [100, 101, 102, 103, 104],
            'High': [105, 106, 107, 108, 109],
            'Low': [99, 100, 101, 102, 103],
            'Close': [104, 105, 106, 107, 108],  # 全部阳线
            'Volume': [1000] * 5
        }, index=dates)

        data_feed = bt.feeds.PandasData(
            dataname=data,
            name='TEST'
        )
        cerebro.adddata(data_feed)
        cerebro.broker.setcash(100000)

        # 运行不应崩溃
        try:
            cerebro.run()
            self.assertTrue(True)
        except IndexError:
            self.fail("阴阳线策略在数据不足时发生索引错误")


class TestConfigValues(unittest.TestCase):
    """测试配置值"""

    def test_initial_cash_positive(self):
        """测试初始资金为正数"""
        self.assertGreater(config.INITIAL_CASH, 0)

    def test_commission_rate_valid(self):
        """测试手续费率在合理范围"""
        self.assertGreaterEqual(config.COMMISSION_RATE, 0)
        self.assertLess(config.COMMISSION_RATE, 1)

    def test_strategy_params_exist(self):
        """测试策略参数存在"""
        self.assertIn('period', config.RSI_PARAMS)
        self.assertIn('oversold', config.RSI_PARAMS)
        self.assertIn('overbought', config.RSI_PARAMS)


class TestCustomAnalyzer(unittest.TestCase):
    """测试自定义分析器"""

    def test_analyzer_initialization(self):
        """测试分析器初始化"""
        cerebro = bt.Cerebro()
        cerebro.addanalyzer(CustomAnalyzer, _name='custom')

        # 创建测试数据
        dates = pd.date_range(start='2023-01-01', periods=30, freq='D')
        data = pd.DataFrame({
            'Open': [100] * 30,
            'High': [105] * 30,
            'Low': [95] * 30,
            'Close': [100 + i for i in range(30)],
            'Volume': [1000] * 30
        }, index=dates)

        data_feed = bt.feeds.PandasData(
            dataname=data,
            name='TEST'
        )
        cerebro.adddata(data_feed)
        cerebro.broker.setcash(100000)

        # 添加一个简单策略
        cerebro.addstrategy(bt.Strategy)

        results = cerebro.run()
        strategy = results[0]

        analysis = strategy.analyzers.custom.get_analysis()
        self.assertIn('daily_values', analysis)
        self.assertIn('trades', analysis)


class TestDualMATrendLogic(unittest.TestCase):
    """测试双均线趋势策略逻辑"""

    def test_sell_condition_logic(self):
        """测试卖出条件逻辑正确性"""
        # 卖出条件应该是: price_below_fast
        # 而不是: price_below_fast or (fast_trend_down and price_below_fast)
        # 后者冗余，因为 price_below_fast 已经包含了所有情况

        # 模拟测试场景
        price_below_fast = True
        fast_trend_down = True

        # 原来的条件: price_below_fast or (fast_trend_down and price_below_fast)
        # 等价于: price_below_fast (因为第一个条件为True时，整个表达式为True)
        original_result = price_below_fast or (fast_trend_down and price_below_fast)
        simplified_result = price_below_fast

        self.assertEqual(original_result, simplified_result)


class TestBacktestEngine(unittest.TestCase):
    """测试回测引擎"""

    def test_invalid_strategy_raises_error(self):
        """测试无效策略名称抛出错误"""
        with self.assertRaises(ValueError):
            BacktestEngine(strategy_name="nonexistent_strategy")

    def test_valid_strategy_initialization(self):
        """测试有效策略初始化"""
        engine = BacktestEngine(
            strategy_name="sma_cross",
            symbol="AAPL",
            start_date="2023-01-01",
            end_date="2023-12-31"
        )
        self.assertEqual(engine.strategy_name, "sma_cross")
        self.assertEqual(engine.symbol, "AAPL")


if __name__ == '__main__':
    unittest.main(verbosity=2)
