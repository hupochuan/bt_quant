"""
配置文件 - 回测参数设置
"""

# ==================== 基础配置 ====================
DEFAULT_SYMBOL = "AAPL"          # 默认股票代码
START_DATE = "2020-01-01"        # 默认开始日期
END_DATE = "2023-12-31"          # 默认结束日期

# ==================== 资金配置 ====================
INITIAL_CASH = 100000.0          # 初始资金
COMMISSION_RATE = 0.001          # 手续费率 (0.1%)
FIXED_COMMISSION = 5.0           # 固定手续费 (用于某些策略)

# ==================== 图表配置 ====================
PLOT_RESULTS = True              # 是否生成图表
PLOT_WIDTH = 16                  # 图表宽度
PLOT_HEIGHT = 9                  # 图表高度
PLOT_DPI = 150                   # 图表分辨率

# ==================== SMA 交叉策略配置 ====================
SMA_CROSS_PARAMS = {
    "fast_period": 20,           # 短期均线周期
    "slow_period": 50,           # 长期均线周期
    "order_percentage": 0.95,    # 每次交易资金使用比例
}

# ==================== RSI 策略配置 ====================
RSI_PARAMS = {
    "period": 14,                # RSI 计算周期
    "oversold": 30,              # 超卖阈值
    "overbought": 70,            # 超买阈值
    "order_percentage": 0.95,    # 每次交易资金使用比例
}

# ==================== MACD 策略配置 ====================
MACD_PARAMS = {
    "fast_period": 12,           # 快线周期
    "slow_period": 26,           # 慢线周期
    "signal_period": 9,          # 信号线周期
    "order_percentage": 0.95,    # 每次交易资金使用比例
}

# ==================== 布林带策略配置 ====================
BBAND_PARAMS = {
    "period": 20,                # 布林带周期
    "devfactor": 2.0,            # 标准差倍数
    "order_percentage": 0.95,    # 每次交易资金使用比例
}

# ==================== 双均线趋势策略配置 ====================
DUAL_MA_TREND_PARAMS = {
    "fast_period": 10,           # 短期均线
    "slow_period": 30,           # 长期均线
    "trend_period": 5,           # 趋势确认周期
    "order_percentage": 0.95,    # 每次交易资金使用比例
}

# ==================== 动量策略配置 ====================
MOMENTUM_PARAMS = {
    "period": 20,                # 动量计算周期
    "threshold": 0.05,           # 动量阈值 (5%)
    "order_percentage": 0.95,    # 每次交易资金使用比例
}

# ==================== 阴阳线策略配置 (Candle) ====================
CANDLE_PATTERN_PARAMS = {
    "symbol": "BABA",            # 默认股票
    "initial_cash": 100000.0,    # 初始资金
    "initial_position": 0,       # 初始持仓
    "commission_fixed": 5.0,     # 固定手续费
    "trade_size": 100,           # 每次交易股数
    "consecutive_count": 3,      # 连续 K 线数量
    "stop_loss_amount": 200.0,   # 止损金额
    "interval": "10m",           # K线周期 (10分钟)
}

# ==================== 增强阴阳线策略配置 ====================
ENHANCED_CANDLE_PARAMS = {
    "symbol": "BABA",
    "initial_cash": 100000.0,
    "initial_position": 0,
    "commission_fixed": 5.0,
    "trade_size": 100,
    "consecutive_count": 3,      # 连续 K 线数量
    "ema_period": 20,            # EMA 周期
    "volume_ma_period": 20,      # 成交量均线周期
    "volume_ratio": 1.5,         # 放量倍数
    "stop_loss_amount": 200.0,
    "cooldown_bars": 5,          # 冷却期 (K线根数)
    "trailing_profit_threshold": 500.0,  # 移动止盈阈值
    "interval": "10m",
}

# ==================== 日线突破策略配置 ====================
DAILY_BREAKOUT_PARAMS = {
    "symbol": "BABA",
    "initial_cash": 100000.0,
    "initial_position": 0,
    "commission_fixed": 5.0,
    "trade_size": 100,
    "sma_period": 20,            # 均线周期
    "macd_fast": 12,             # MACD 快线
    "macd_slow": 26,             # MACD 慢线
    "macd_signal": 9,            # MACD 信号线
    "volume_ma_period": 20,      # 成交量均线周期
    "volume_ratio": 2.0,         # 放量倍数
    "stop_loss_pct": 0.05,       # 止损比例 (5%)
    "take_profit_pct": 0.15,     # 止盈比例 (15%)
    "interval": "1d",
}

# ==================== 策略注册表 ====================
STRATEGY_CONFIGS = {
    "sma_cross": SMA_CROSS_PARAMS,
    "rsi": RSI_PARAMS,
    "macd": MACD_PARAMS,
    "bband": BBAND_PARAMS,
    "dual_ma_trend": DUAL_MA_TREND_PARAMS,
    "momentum": MOMENTUM_PARAMS,
    "candle": CANDLE_PATTERN_PARAMS,
    "enhanced_candle": ENHANCED_CANDLE_PARAMS,
    "daily_breakout": DAILY_BREAKOUT_PARAMS,
}
