# Backtrader 美股量化回测框架

基于成熟的 Backtrader 库搭建的美股量化交易策略回测框架。

## 特性

- **成熟稳定**: 基于 Backtrader 开源回测框架
- **数据获取**: 自动从 Yahoo Finance 获取美股数据
- **多种策略**: 内置 6 种常用交易策略
- **完整分析**: 夏普比率、最大回撤、胜率等全面指标
- **可视化**: 自动生成回测图表
- **策略对比**: 支持多策略对比分析

## 项目结构

```
bt_quant/
├── strategies/          # 策略模块
│   ├── sma_cross.py     # 双均线交叉策略
│   ├── rsi.py           # RSI 策略
│   ├── macd.py          # MACD 策略
│   ├── bband.py         # 布林带策略
│   ├── dual_ma_trend.py # 双均线趋势策略
│   └── momentum.py      # 动量策略
├── utils/               # 工具模块
│   ├── data_fetcher.py  # 数据获取
│   ├── commission.py    # 手续费模型
│   └── analyzers.py     # 自定义分析器
├── examples/            # 示例代码
│   ├── simple_example.py    # 简单示例
│   └── compare_example.py   # 策略对比示例
├── config.py            # 配置文件
├── engine.py            # 回测引擎入口
├── requirements.txt     # 依赖列表
└── README.md            # 说明文档
```

## 安装依赖

```bash
cd /root/bt_quant
pip install -r requirements.txt
```

## 快速开始

### 1. 命令行运行

```bash
# 运行双均线策略
python engine.py -s sma_cross -t AAPL

# 运行 RSI 策略
python engine.py -s rsi -t TSLA

# 运行 MACD 策略，指定时间范围
python engine.py -s macd -t NVDA --start 2022-01-01 --end 2023-12-31

# 对比所有策略
python engine.py -c -t MSFT

# 列出所有策略
python engine.py --list-strategies
```

### 2. Python 代码调用

```python
from engine import run_backtest, compare_strategies

# 运行单个策略
result = run_backtest(
    strategy_name="sma_cross",
    symbol="AAPL",
    start_date="2022-01-01",
    end_date="2023-12-31",
    initial_cash=100000
)

# 对比多个策略
results = compare_strategies(
    symbol="MSFT",
    start_date="2022-01-01",
    end_date="2023-12-31"
)
```

### 3. 运行示例

```bash
# 简单示例
python examples/simple_example.py

# 策略对比示例
python examples/compare_example.py
```

## 内置策略

| 策略 | 名称 | 说明 |
|------|------|------|
| sma_cross | 双均线交叉 | 金叉买入，死叉卖出 |
| rsi | RSI 振荡器 | 超卖买入，超买卖出 |
| macd | MACD 信号 | MACD线上穿信号线买入 |
| bband | 布林带 | 触及下轨买入，触及上轨卖出 |
| dual_ma_trend | 双均线趋势 | 趋势跟踪策略 |
| momentum | 动量 | 基于价格动量交易 |

## 配置参数

在 `config.py` 中可以修改以下参数：

```python
# 基础配置
DEFAULT_SYMBOL = "AAPL"          # 默认股票
START_DATE = "2020-01-01"        # 默认开始日期
END_DATE = "2023-12-31"          # 默认结束日期

# 资金配置
INITIAL_CASH = 100000.0          # 初始资金
COMMISSION_RATE = 0.001          # 手续费率 (0.1%)

# 策略参数
SMA_CROSS_PARAMS = {
    "fast_period": 20,           # 短期均线
    "slow_period": 50,           # 长期均线
    "order_percentage": 0.95,    # 资金使用比例
}

RSI_PARAMS = {
    "period": 14,                # RSI 周期
    "oversold": 30,              # 超卖阈值
    "overbought": 70,            # 超买阈值
}

# ... 其他策略参数
```

## 回测结果

运行回测后会输出以下指标：

### 收益指标
- 初始资金 / 最终资金
- 总收益率
- 夏普比率

### 风险指标
- 最大回撤
- 回撤持续天数

### 交易统计
- 总交易次数
- 盈利 / 亏损次数
- 胜率
- 平均盈亏
- 盈亏比

### 图表
回测图表保存在 `./report/` 目录，包含：
- 价格走势
- 买卖信号
- 权益曲线
- 成交量

## 自定义策略

继承 `bt.Strategy` 创建自定义策略：

```python
import backtrader as bt

class MyStrategy(bt.Strategy):
    params = (
        ('period', 20),
    )

    def __init__(self):
        self.sma = bt.indicators.SimpleMovingAverage(
            self.data.close, period=self.params.period
        )

    def next(self):
        if not self.position:
            if self.data.close > self.sma:
                self.buy()
        else:
            if self.data.close < self.sma:
                self.sell()
```

然后在 `strategies/__init__.py` 中注册：

```python
STRATEGY_REGISTRY = {
    "my_strategy": {
        "class": MyStrategy,
        "name": "My Strategy",
        "description": "我的自定义策略",
    },
    # ...
}
```

## 注意事项

1. 数据通过 Yahoo Finance 获取，需要网络连接
2. 首次运行会下载数据并缓存到 `./cache/` 目录
3. 图表生成需要 matplotlib，如遇问题可添加 `--no-plot` 参数跳过
4. 回测结果仅供参考，不构成投资建议

## License

MIT License
