"""
阴阳线策略 - 10分钟K线测试
"""
import os
import sys

# 动态添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import backtrader as bt
import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta

import config
from strategies import CandlePatternStrategy, EnhancedCandleStrategy
from utils import FixedCommission


def fetch_10m_data(symbol, start_date, end_date):
    """
    获取10分钟K线数据
    Yahoo Finance 限制: 只能获取最近60天的日内数据
    """
    print(f"[DataFetcher] 下载 {symbol} 10分钟K线数据...")
    print(f"              时间范围: {start_date} ~ {end_date}")

    ticker = yf.Ticker(symbol)

    # Yahoo Finance 不支持10分钟，使用5分钟K线（最接近的选项）
    # 5分钟数据限制为最近60天
    df = ticker.history(period="60d", interval="5m")

    if df.empty:
        raise ValueError(f"未获取到 {symbol} 的数据")

    # 过滤日期范围
    df.index = df.index.tz_localize(None)  # 移除时区
    mask = (df.index >= start_date) & (df.index <= end_date)
    df = df[mask]

    if df.empty:
        raise ValueError(f"指定日期范围内无数据")

    # 标准化列名
    df.columns = [col.capitalize() for col in df.columns]

    print(f"[DataFetcher] 获取到 {len(df)} 条5分钟K线数据")
    print(f"              数据范围: {df.index[0]} 至 {df.index[-1]}")

    return df


def run_candle_strategy_10m(strategy_name="candle"):
    """
    运行阴阳线策略（10分钟K线）
    """
    symbol = "BABA"

    # 由于Yahoo Finance限制，只能获取最近60天的10分钟数据
    # 使用最近30天的数据测试
    end_date = datetime.now()
    start_date = end_date - timedelta(days=30)

    start_str = start_date.strftime("%Y-%m-%d")
    end_str = end_date.strftime("%Y-%m-%d")

    print("=" * 70)
    print(f"🚀 阴阳线策略回测 (5分钟K线)")
    print(f"   股票: {symbol}")
    print(f"   时间: {start_str} ~ {end_str}")
    print(f"   策略: {strategy_name}")
    print("=" * 70)

    # 获取10分钟数据
    df = fetch_10m_data(symbol, start_str, end_str)

    # 创建Backtrader数据feed
    class PandasData10m(bt.feeds.PandasData):
        params = (
            ('datetime', None),
            ('open', 'Open'),
            ('high', 'High'),
            ('low', 'Low'),
            ('close', 'Close'),
            ('volume', 'Volume'),
            ('openinterest', -1),
        )

    data = PandasData10m(
        dataname=df,
        name=symbol,
        timeframe=bt.TimeFrame.Minutes,
        compression=5  # 5分钟
    )

    # 创建回测引擎
    cerebro = bt.Cerebro()

    # 添加策略
    if strategy_name == "candle":
        cerebro.addstrategy(CandlePatternStrategy)
    else:
        cerebro.addstrategy(EnhancedCandleStrategy)

    # 添加数据
    cerebro.adddata(data, name=symbol)

    # 设置初始资金
    initial_cash = config.CANDLE_PATTERN_PARAMS["initial_cash"]
    cerebro.broker.setcash(initial_cash)

    # 设置固定手续费
    fixed_comm = FixedCommission(
        commission=config.CANDLE_PATTERN_PARAMS["commission_fixed"]
    )
    cerebro.broker.addcommissioninfo(fixed_comm)

    # 添加分析器
    cerebro.addanalyzer(bt.analyzers.SharpeRatio, _name="sharpe", riskfreerate=0.04)
    cerebro.addanalyzer(bt.analyzers.DrawDown, _name="drawdown")
    cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name="trades")
    cerebro.addanalyzer(bt.analyzers.Returns, _name="returns")

    # 运行回测
    print(f"\n📈 开始运行回测...")
    print(f"   初始资金: ${initial_cash:,.2f}")
    print(f"   每笔手续费: ${config.CANDLE_PATTERN_PARAMS['commission_fixed']:.2f}")
    print(f"   每次交易: {config.CANDLE_PATTERN_PARAMS['trade_size']} 股")
    print(f"   止损金额: ${config.CANDLE_PATTERN_PARAMS['stop_loss_amount']:.2f}\n")

    results = cerebro.run()
    strategy = results[0]

    # 获取结果
    final_value = cerebro.broker.getvalue()
    total_return = (final_value / initial_cash - 1) * 100

    sharpe = strategy.analyzers.sharpe.get_analysis().get("sharperatio", 0) or 0
    drawdown = strategy.analyzers.drawdown.get_analysis().get("max", {}).get("drawdown", 0) or 0
    trades = strategy.analyzers.trades.get_analysis()

    total_trades = trades.get("total", {}).get("total", 0) or 0
    won_trades = trades.get("won", {}).get("total", 0) or 0
    win_rate = (won_trades / total_trades * 100) if total_trades > 0 else 0

    # 输出结果
    print("\n" + "=" * 70)
    print("📊 回测结果摘要")
    print("=" * 70)
    print(f"   初始资金:     ${initial_cash:>15,.2f}")
    print(f"   最终资金:     ${final_value:>15,.2f}")
    print(f"   总收益率:     {total_return:>15.2f}%")
    print(f"   夏普比率:     {sharpe:>15.4f}")
    print(f"   最大回撤:     {drawdown:>15.2f}%")
    print("-" * 70)
    print(f"   总交易次数:   {total_trades:>15}")
    print(f"   盈利次数:     {won_trades:>15}")
    print(f"   胜率:         {win_rate:>15.2f}%")
    print("=" * 70)

    profit_emoji = "🎉" if total_return > 0 else "😢"
    print(f"\n{profit_emoji} 最终盈亏: ${final_value - initial_cash:+,.2f} ({total_return:+.2f}%)")

    return {
        "total_return": total_return,
        "sharpe_ratio": sharpe,
        "max_drawdown": drawdown,
        "total_trades": total_trades,
        "win_rate": win_rate,
    }


if __name__ == "__main__":
    # 测试基础版阴阳线策略
    print("\n" + "🔥" * 35)
    print("测试 1: 基础版阴阳线策略 (5分钟K线)")
    print("🔥" * 35)
    result1 = run_candle_strategy_10m("candle")

    print("\n\n" + "🔥" * 35)
    print("测试 2: 增强版阴阳线策略 (5分钟K线)")
    print("🔥" * 35)
    result2 = run_candle_strategy_10m("enhanced_candle")

    print("\n\n" + "=" * 70)
    print("对比总结")
    print("=" * 70)
    print(f"{'策略':<25} {'收益率':>10} {'夏普':>8} {'最大回撤':>10} {'胜率':>8}")
    print("-" * 70)
    print(f"{'基础版阴阳线':<20} {result1['total_return']:>9.2f}% "
          f"{result1['sharpe_ratio']:>8.2f} {result1['max_drawdown']:>9.2f}% "
          f"{result1['win_rate']:>7.1f}%")
    print(f"{'增强版阴阳线':<20} {result2['total_return']:>9.2f}% "
          f"{result2['sharpe_ratio']:>8.2f} {result2['max_drawdown']:>9.2f}% "
          f"{result2['win_rate']:>7.1f}%")
    print("=" * 70)
