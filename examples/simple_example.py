"""
简单示例 - 运行单个策略回测
"""
import os
import sys

# 动态添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine import run_backtest


def main():
    """运行简单回测示例"""

    print("=" * 70)
    print("           Backtrader 美股量化回测 - 简单示例")
    print("=" * 70)

    # 示例 1: 双均线策略
    print("\n" + "=" * 70)
    print("示例 1: 双均线交叉策略 (SMA Cross)")
    print("=" * 70)

    result1 = run_backtest(
        strategy_name="sma_cross",
        symbol="AAPL",
        start_date="2022-01-01",
        end_date="2023-12-31",
        initial_cash=100000,
        enable_plot=True
    )

    # 示例 2: RSI 策略
    print("\n" + "=" * 70)
    print("示例 2: RSI 策略")
    print("=" * 70)

    result2 = run_backtest(
        strategy_name="rsi",
        symbol="TSLA",
        start_date="2022-01-01",
        end_date="2023-12-31",
        initial_cash=100000,
        enable_plot=True
    )

    # 示例 3: MACD 策略
    print("\n" + "=" * 70)
    print("示例 3: MACD 策略")
    print("=" * 70)

    result3 = run_backtest(
        strategy_name="macd",
        symbol="NVDA",
        start_date="2022-01-01",
        end_date="2023-12-31",
        initial_cash=100000,
        enable_plot=True
    )

    print("\n" + "=" * 70)
    print("所有示例运行完成!")
    print("=" * 70)


if __name__ == "__main__":
    main()
