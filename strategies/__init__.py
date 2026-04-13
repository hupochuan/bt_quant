"""
策略模块
注册所有可用策略
"""
from .sma_cross import SmaCrossStrategy
from .rsi import RsiStrategy
from .macd import MacdStrategy
from .bband import BollingerBandsStrategy
from .dual_ma_trend import DualMATrendStrategy
from .momentum import MomentumStrategy
from .candle_patterns import (
    CandlePatternStrategy,
    EnhancedCandleStrategy,
    DailyBreakoutStrategy,
    CandlePatternWithProfitTarget
)
from .candle_patterns_trend import CandlePatternTrendStrategy

# 策略注册表
STRATEGY_REGISTRY = {
    "sma_cross": {
        "class": SmaCrossStrategy,
        "name": "双均线交叉策略",
        "description": "快线上穿慢线买入，快线下穿慢线卖出",
    },
    "rsi": {
        "class": RsiStrategy,
        "name": "RSI 相对强弱策略",
        "description": "RSI 低于超卖线买入，高于超买线卖出",
    },
    "macd": {
        "class": MacdStrategy,
        "name": "MACD 信号策略",
        "description": "MACD线上穿信号线买入，下穿卖出",
    },
    "bband": {
        "class": BollingerBandsStrategy,
        "name": "布林带策略",
        "description": "触及下轨买入，触及上轨卖出",
    },
    "dual_ma_trend": {
        "class": DualMATrendStrategy,
        "name": "双均线趋势策略",
        "description": "趋势跟踪策略",
    },
    "momentum": {
        "class": MomentumStrategy,
        "name": "动量策略",
        "description": "基于价格动量交易",
    },
    "candle": {
        "class": CandlePatternStrategy,
        "name": "阴阳线策略",
        "description": "连续阳线买入，连续阴线卖出，支持止损",
    },
    "enhanced_candle": {
        "class": EnhancedCandleStrategy,
        "name": "增强版阴阳线策略",
        "description": "阴阳线 + EMA趋势过滤 + 放量确认 + 冷却期 + 移动止损",
    },
    "daily_breakout": {
        "class": DailyBreakoutStrategy,
        "name": "日线均线突破策略",
        "description": "均线突破 + MACD + 放量确认，适合上班族",
    },
    "candle_trend": {
        "class": CandlePatternTrendStrategy,
        "name": "阴阳线趋势过滤策略",
        "description": "阴阳线 + 20日均线趋势过滤，下跌只反T，上涨只正T",
    },
    "candle_profit30": {
        "class": CandlePatternWithProfitTarget,
        "name": "阴阳线策略-30美元止盈版",
        "description": "阴阳线策略，增加30美元固定金额止盈条件",
    },
}


def get_strategy(name: str):
    """
    获取策略类

    Args:
        name: 策略名称

    Returns:
        策略类或 None
    """
    strategy_info = STRATEGY_REGISTRY.get(name)
    return strategy_info["class"] if strategy_info else None


def list_strategies():
    """列出所有可用策略"""
    return {
        name: {
            "name": info["name"],
            "description": info["description"],
        }
        for name, info in STRATEGY_REGISTRY.items()
    }


__all__ = [
    'SmaCrossStrategy',
    'RsiStrategy',
    'MacdStrategy',
    'BollingerBandsStrategy',
    'DualMATrendStrategy',
    'MomentumStrategy',
    'CandlePatternStrategy',
    'EnhancedCandleStrategy',
    'DailyBreakoutStrategy',
    'CandlePatternTrendStrategy',
    'CandlePatternWithProfitTarget',
    'STRATEGY_REGISTRY',
    'get_strategy',
    'list_strategies',
]
