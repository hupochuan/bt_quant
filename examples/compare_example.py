"""
策略对比示例 - 对比多个策略在同一股票上的表现
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine import compare_strategies


def main():
    """运行策略对比示例"""

    print("=" * 70)
    print("           Backtrader 美股量化回测 - 策略对比示例")
    print("=" * 70)

    # 对比所有策略在 AAPL 上的表现
    print("\n对比所有策略在 AAPL 上的表现...")
    results = compare_strategies(
        symbol="AAPL",
        start_date="2022-01-01",
        end_date="2023-12-31"
    )

    print("\n" + "=" * 70)
    print("对比完成!")
    print("=" * 70)


if __name__ == "__main__":
    main()
