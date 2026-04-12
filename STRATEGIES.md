# 策略说明文档

本文档详细介绍框架中所有可用的交易策略。

## 策略列表

### 1. 双均线交叉策略 (sma_cross)

**原理：**
- 当短期均线（默认20日）从下方穿越长期均线（默认50日）时买入（金叉）
- 当短期均线从上方穿越长期均线时卖出（死叉）

**适用场景：** 趋势行情

**配置参数：**
```python
SMA_CROSS_PARAMS = {
    "fast_period": 20,        # 短期均线周期
    "slow_period": 50,        # 长期均线周期
    "order_percentage": 0.95, # 资金使用比例
}
```

---

### 2. RSI 相对强弱策略 (rsi)

**原理：**
- RSI 低于超卖线（默认30）时，市场超卖，买入
- RSI 高于超买线（默认70）时，市场超买，卖出

**适用场景：** 震荡行情

**配置参数：**
```python
RSI_PARAMS = {
    "period": 14,             # RSI 计算周期
    "oversold": 30,           # 超卖阈值
    "overbought": 70,         # 超买阈值
    "order_percentage": 0.95,
}
```

---

### 3. MACD 信号策略 (macd)

**原理：**
- MACD 线上穿信号线时买入
- MACD 线下穿信号线时卖出

**适用场景：** 趋势确认

**配置参数：**
```python
MACD_PARAMS = {
    "fast_period": 12,        # 快线周期
    "slow_period": 26,        # 慢线周期
    "signal_period": 9,       # 信号线周期
    "order_percentage": 0.95,
}
```

---

### 4. 布林带策略 (bband)

**原理：**
- 价格触及下轨时买入
- 价格触及上轨时卖出

**适用场景：** 震荡行情

**配置参数：**
```python
BBAND_PARAMS = {
    "period": 20,             # 布林带周期
    "devfactor": 2.0,         # 标准差倍数
    "order_percentage": 0.95,
}
```

---

### 5. 双均线趋势策略 (dual_ma_trend)

**原理：**
- 价格在短期均线上方且均线向上时买入
- 价格跌破短期均线或均线向下时卖出

**适用场景：** 趋势跟踪

**配置参数：**
```python
DUAL_MA_TREND_PARAMS = {
    "fast_period": 10,
    "slow_period": 30,
    "trend_period": 5,
    "order_percentage": 0.95,
}
```

---

### 6. 动量策略 (momentum)

**原理：**
- 价格动量超过正阈值时买入
- 价格动量低于负阈值时卖出

**适用场景：** 动量交易

**配置参数：**
```python
MOMENTUM_PARAMS = {
    "period": 20,             # 动量计算周期
    "threshold": 0.05,        # 动量阈值 (5%)
    "order_percentage": 0.95,
}
```

---

### 7. 阴阳线策略 (candle)

**原理：**
- 连续 N 根阳线（Close > Open）时买入
- 连续 N 根阴线（Close < Open）时卖出
- 支持固定止损金额

**适用场景：** 短线趋势跟踪

**配置参数：**
```python
CANDLE_PATTERN_PARAMS = {
    "consecutive_count": 3,   # 连续 K 线数量
    "trade_size": 100,        # 每次交易股数
    "stop_loss_amount": 200.0,# 止损金额
}
```

---

### 8. 增强版阴阳线策略 (enhanced_candle)

**原理：**
在基础阴阳线策略上增加四重过滤：
1. **EMA 趋势过滤**：价格在 EMA 上方才允许买入
2. **成交量确认**：阳线放量才触发买入
3. **冷却期**：卖出后等待 N 根 K 线才能再次买入
4. **移动止损**：盈利达到阈值后，止损线上移到买入价

**适用场景：** 短线交易，过滤假信号

**配置参数：**
```python
ENHANCED_CANDLE_PARAMS = {
    "consecutive_count": 3,
    "trade_size": 100,
    "ema_period": 20,                    # EMA 周期
    "volume_ma_period": 20,              # 成交量均线周期
    "volume_ratio": 1.5,                 # 放量倍数
    "stop_loss_amount": 200.0,
    "cooldown_bars": 5,                  # 冷却期
    "trailing_profit_threshold": 500.0,  # 移动止盈阈值
}
```

---

### 9. 日线均线突破策略 (daily_breakout)

**原理：**
专为上班族设计，每天收盘后检查一次信号。

**买入条件（三重确认）：**
1. 收盘价突破 20 日均线（趋势确认）
2. MACD 金叉（动量确认）
3. 成交量放大（资金确认）

**卖出条件（任一触发）：**
1. 收盘价跌破 20 日均线
2. MACD 死叉
3. 止损：亏损超过 5%
4. 止盈：盈利超过 15%

**适用场景：** 中长线投资，无需盯盘

**配置参数：**
```python
DAILY_BREAKOUT_PARAMS = {
    "sma_period": 20,             # 均线周期
    "macd_fast": 12,              # MACD 快线
    "macd_slow": 26,              # MACD 慢线
    "macd_signal": 9,             # MACD 信号线
    "volume_ma_period": 20,
    "volume_ratio": 2.0,          # 放量倍数
    "stop_loss_pct": 0.05,        # 止损比例 (5%)
    "take_profit_pct": 0.15,      # 止盈比例 (15%)
    "trade_size": 100,
}
```

---

## 策略对比

| 策略 | 类型 | 适用场景 | 特点 |
|------|------|----------|------|
| sma_cross | 趋势 | 趋势行情 | 简单有效 |
| rsi | 震荡 | 震荡行情 | 逆势交易 |
| macd | 趋势 | 趋势确认 | 滞后但稳定 |
| bband | 震荡 | 震荡行情 | 均值回归 |
| dual_ma_trend | 趋势 | 趋势跟踪 | 多条件确认 |
| momentum | 趋势 | 动量交易 | 追涨杀跌 |
| candle | 短线 | 短线趋势 | K线形态 |
| enhanced_candle | 短线 | 短线过滤 | 多重过滤 |
| daily_breakout | 中长线 | 上班族 | 无需盯盘 |

## 使用建议

1. **趋势行情**：选择 `sma_cross`, `macd`, `dual_ma_trend`, `momentum`
2. **震荡行情**：选择 `rsi`, `bband`
3. **短线交易**：选择 `candle`, `enhanced_candle`
4. **中长线投资**：选择 `daily_breakout`

## 自定义策略

参考现有策略代码，继承 `bt.Strategy` 类实现自定义策略：

```python
import backtrader as bt

class MyStrategy(bt.Strategy):
    params = (
        ('param1', 20),
    )

    def __init__(self):
        self.indicator = bt.indicators.SMA(self.data.close, period=self.params.param1)

    def next(self):
        if not self.position:
            if self.data.close > self.indicator:
                self.buy()
        else:
            if self.data.close < self.indicator:
                self.sell()
```

然后在 `strategies/__init__.py` 中注册新策略。
