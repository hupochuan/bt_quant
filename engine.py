"""
回测引擎入口
基于 Backtrader 的回测框架
"""
import argparse
import sys
import os
from datetime import datetime
from typing import Dict, List, Optional

import backtrader as bt
import matplotlib
matplotlib.use("Agg")  # 使用非交互式后端

import config
from strategies import STRATEGY_REGISTRY, list_strategies
from utils import create_backtrader_data, FixedCommission


class BacktestEngine:
    """
    回测引擎

    封装 Backtrader 的核心功能，提供更简洁的接口
    """

    def __init__(
        self,
        strategy_name: str = "sma_cross",
        symbol: str = None,
        start_date: str = None,
        end_date: str = None,
        initial_cash: float = None,
        commission_rate: float = None,
        enable_plot: bool = True,
        plot_path: str = "./report",
        interval: str = None
    ):
        """
        初始化回测引擎

        Args:
            strategy_name: 策略名称
            symbol: 股票代码
            start_date: 开始日期
            end_date: 结束日期
            initial_cash: 初始资金
            commission_rate: 手续费率
            enable_plot: 是否生成图表
            plot_path: 图表保存路径
            interval: 数据周期 (1d, 10m等)，None则根据策略配置自动选择
        """
        self.strategy_name = strategy_name
        self.symbol = symbol or config.DEFAULT_SYMBOL
        self.start_date = start_date or config.START_DATE
        self.end_date = end_date or config.END_DATE
        self.initial_cash = initial_cash or config.INITIAL_CASH
        self.commission_rate = commission_rate or config.COMMISSION_RATE
        self.enable_plot = enable_plot
        self.plot_path = plot_path
        self.interval = interval

        # 创建输出目录
        os.makedirs(self.plot_path, exist_ok=True)

        # 获取策略信息
        self.strategy_info = STRATEGY_REGISTRY.get(strategy_name)
        if not self.strategy_info:
            available = ", ".join(STRATEGY_REGISTRY.keys())
            raise ValueError(f"未知策略: {strategy_name}，可用策略: {available}")

        self.strategy_class = self.strategy_info["class"]

        # 根据策略类型确定数据周期
        if self.interval is None:
            self.interval = self._get_strategy_interval()

        # 根据策略类型确定初始资金
        self._setup_strategy_config()
        
        # 特殊处理：带止盈的阴阳线策略
        self._setup_candle_profit_params()

        # 初始化 Backtrader Cerebro 引擎
        self.cerebro = bt.Cerebro()

    def _get_strategy_interval(self) -> str:
        """根据策略类型获取数据周期"""
        is_candle = self.strategy_name in ("candle", "enhanced_candle", "daily_breakout", "candle_trend", "candle_profit30")
        if is_candle:
            candle_params = config.STRATEGY_CONFIGS.get(self.strategy_name, {})
            return candle_params.get("interval", "1d")
        return "1d"

    def _setup_strategy_config(self):
        """根据策略类型设置配置"""
        is_candle = self.strategy_name in ("candle", "enhanced_candle", "daily_breakout", "candle_trend", "candle_profit30")
        if is_candle:
            candle_params = config.STRATEGY_CONFIGS.get(self.strategy_name, {})
            self.initial_cash = candle_params.get("initial_cash", self.initial_cash)
            self.commission_fixed = candle_params.get("commission_fixed", 5.0)
            self.base_position = candle_params.get("initial_position", 0)
        else:
            self.commission_fixed = None
            self.base_position = 0
    
    def _setup_candle_profit_params(self):
        """设置带止盈阴阳线策略的专属参数"""
        if self.strategy_name == "candle_profit30":
            candle_params = config.STRATEGY_CONFIGS.get(self.strategy_name, {})
            self.take_profit_amount = candle_params.get("take_profit_amount", 30.0)

    def setup(self):
        """设置回测环境"""
        # 添加策略
        self.cerebro.addstrategy(self.strategy_class)

        # 添加数据 - 使用策略对应的数据周期
        data_feed = create_backtrader_data(
            self.symbol,
            self.start_date,
            self.end_date,
            interval=self.interval
        )
        self.cerebro.adddata(data_feed, name=self.symbol)

        # 设置初始资金
        self.cerebro.broker.setcash(self.initial_cash)

        # 设置手续费
        self.cerebro.broker.setcommission(commission=self.commission_rate)

        # 添加分析器
        self._add_analyzers()

    def _add_analyzers(self):
        """添加分析器"""
        # 夏普比率
        self.cerebro.addanalyzer(
            bt.analyzers.SharpeRatio,
            _name="sharpe",
            riskfreerate=0.04,
            annualize=True
        )

        # 回撤分析
        self.cerebro.addanalyzer(bt.analyzers.DrawDown, _name="drawdown")

        # 交易分析
        self.cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name="trades")

        # 收益分析
        self.cerebro.addanalyzer(bt.analyzers.Returns, _name="returns")

        # 年度收益
        self.cerebro.addanalyzer(bt.analyzers.AnnualReturn, _name="annual")

        # 时间收益
        self.cerebro.addanalyzer(bt.analyzers.TimeReturn, _name="timereturn")

        # 自定义分析器
        from utils import CustomAnalyzer
        self.cerebro.addanalyzer(CustomAnalyzer, _name="custom")

    def run(self) -> Dict:
        """
        运行回测

        Returns:
            Dict: 回测结果
        """
        print("=" * 70)
        print(f"🚀 开始回测")
        print(f"   策略: {self.strategy_info['name']} ({self.strategy_name})")
        print(f"   描述: {self.strategy_info['description']}")
        print(f"   股票: {self.symbol}")
        print(f"   时间: {self.start_date} ~ {self.end_date}")
        
        # 根据策略类型显示专属配置
        is_candle = self.strategy_name in ("candle", "enhanced_candle", "daily_breakout", "candle_profit30")
        if is_candle:
            candle_params = config.STRATEGY_CONFIGS.get(self.strategy_name, {})
            print(f"   K线周期: {candle_params.get('interval', '1d')}")
            print(f"   初始现金: ${self.initial_cash:,.2f}")
            print(f"   初始持仓: {candle_params.get('initial_position', 0)} 股")
            print(f"   每笔手续费: ${candle_params.get('commission_fixed', 5.0):.2f}")
            print(f"   每次交易: {candle_params.get('trade_size', 100)} 股")
            if self.strategy_name == "daily_breakout":
                print(f"   均线周期: {candle_params.get('sma_period', 20)} 日")
                print(f"   MACD: {candle_params.get('macd_fast', 12)}/{candle_params.get('macd_slow', 26)}/{candle_params.get('macd_signal', 9)}")
                print(f"   放量倍数: {candle_params.get('volume_ratio', 1.2)}x")
                print(f"   止损: {candle_params.get('stop_loss_pct', 0.05)*100:.0f}%")
                print(f"   止盈: {candle_params.get('take_profit_pct', 0.15)*100:.0f}%")
            elif self.strategy_name == "candle_profit30":
                print(f"   止损金额: ${candle_params.get('stop_loss_amount', 100.0):.2f}")
                print(f"   止盈金额: ${candle_params.get('take_profit_amount', 30.0):.2f}")
            else:
                print(f"   止损金额: ${candle_params.get('stop_loss_amount', 100.0):.2f}")
            if self.strategy_name == "enhanced_candle":
                print(f"   EMA周期: {candle_params.get('ema_period', 20)}")
                print(f"   放量倍数: {candle_params.get('volume_ratio', 1.2)}x")
                print(f"   冷却期: {candle_params.get('cooldown_bars', 5)} 根K线")
                print(f"   移动止损阈值: ${candle_params.get('trailing_profit_threshold', 50.0):.2f}")
        else:
            print(f"   初始资金: ${self.initial_cash:,.2f}")
            print(f"   手续费率: {self.commission_rate * 100:.2f}%")
        print("=" * 70)

        # 设置环境
        self.setup()

        # 运行回测
        print("\n📈 开始运行回测...")
        results = self.cerebro.run()
        self.strategy_instance = results[0]

        # 生成结果
        results_dict = self._generate_results()

        # 生成图表
        if self.enable_plot:
            self._generate_plot()

        return results_dict

    def _generate_results(self) -> Dict:
        """生成回测结果"""
        # 获取分析结果
        sharpe_analysis = self.strategy_instance.analyzers.sharpe.get_analysis()
        drawdown_analysis = self.strategy_instance.analyzers.drawdown.get_analysis()
        trade_analysis = self.strategy_instance.analyzers.trades.get_analysis()
        returns_analysis = self.strategy_instance.analyzers.returns.get_analysis()
        timereturn_analysis = self.strategy_instance.analyzers.timereturn.get_analysis()
        custom_analysis = self.strategy_instance.analyzers.custom.get_analysis()

        # 计算关键指标
        final_value = self.cerebro.broker.getvalue()
        total_return = (final_value / self.initial_cash - 1) * 100

        sharpe_ratio = sharpe_analysis.get("sharperatio", 0) or 0
        max_drawdown = drawdown_analysis.get("max", {}).get("drawdown", 0) or 0
        max_drawdown_len = drawdown_analysis.get("max", {}).get("len", 0) or 0

        total_trades = trade_analysis.get("total", {}).get("total", 0) or 0
        won_trades = trade_analysis.get("won", {}).get("total", 0) or 0
        lost_trades = trade_analysis.get("lost", {}).get("total", 0) or 0
        win_rate = (won_trades / total_trades * 100) if total_trades > 0 else 0

        # 平均盈亏
        gross_pnl = trade_analysis.get("pnl", {}).get("gross", {}).get("total", 0) or 0
        net_pnl = trade_analysis.get("pnl", {}).get("net", {}).get("total", 0) or 0
        avg_trade_pnl = net_pnl / total_trades if total_trades > 0 else 0

        won_pnl = trade_analysis.get("won", {}).get("pnl", {}).get("total", 0) or 0
        lost_pnl = trade_analysis.get("lost", {}).get("pnl", {}).get("total", 0) or 0
        avg_won = won_pnl / won_trades if won_trades > 0 else 0
        avg_lost = lost_pnl / lost_trades if lost_trades > 0 else 0
        profit_factor = abs(won_pnl / lost_pnl) if lost_pnl != 0 else 0

        # 构建结果字典
        results = {
            "strategy": self.strategy_info['name'],
            "strategy_name": self.strategy_name,
            "symbol": self.symbol,
            "start_date": self.start_date,
            "end_date": self.end_date,
            "initial_cash": self.initial_cash,
            "final_value": final_value,
            "total_return": total_return,
            "sharpe_ratio": sharpe_ratio,
            "max_drawdown": max_drawdown,
            "max_drawdown_days": max_drawdown_len,
            "total_trades": int(total_trades),
            "won_trades": int(won_trades),
            "lost_trades": int(lost_trades),
            "win_rate": win_rate,
            "avg_trade_pnl": avg_trade_pnl,
            "avg_won": avg_won,
            "avg_lost": avg_lost,
            "profit_factor": profit_factor,
            "gross_pnl": gross_pnl,
            "net_pnl": net_pnl,
            "commission_paid": gross_pnl - net_pnl,
            "time_returns": timereturn_analysis,
            "daily_values": custom_analysis.get('daily_values'),
            "trades_df": custom_analysis.get('trades'),
        }

        # 打印结果
        self._print_results(results)

        return results

    def _print_results(self, results: Dict):
        """打印回测结果"""
        print("\n" + "=" * 70)
        print("📊 回测结果摘要")
        print("=" * 70)
        print(f"   初始现金:     ${results['initial_cash']:>15,.2f}")
        print(f"   最终总值:     ${results['final_value']:>15,.2f}")
        print(f"   总收益率:     {results['total_return']:>15.2f}%")
        print(f"   夏普比率:     {results['sharpe_ratio']:>15.4f}")
        print(f"   最大回撤:     {results['max_drawdown']:>15.2f}%")
        print(f"   回撤天数:     {results['max_drawdown_days']:>15} 天")
        print("-" * 70)
        print(f"   总交易次数:   {results['total_trades']:>15}")
        print(f"   盈利次数:     {results['won_trades']:>15}")
        print(f"   亏损次数:     {results['lost_trades']:>15}")
        print(f"   胜率:         {results['win_rate']:>15.2f}%")
        print("-" * 70)
        print(f"   平均每笔盈亏: ${results['avg_trade_pnl']:>15,.2f}")
        print(f"   平均盈利:     ${results['avg_won']:>15,.2f}")
        print(f"   平均亏损:     ${results['avg_lost']:>15,.2f}")
        print(f"   盈亏比:       {results['profit_factor']:>15.2f}")
        print("-" * 70)
        print(f"   毛盈亏:       ${results['gross_pnl']:>15,.2f}")
        print(f"   手续费:       ${results['commission_paid']:>15,.2f}")
        print(f"   净盈亏:       ${results['net_pnl']:>15,.2f}")
        print("=" * 70)

        profit_emoji = "🎉" if results['total_return'] > 0 else "😢"
        pnl = results['final_value'] - results['initial_cash']
        print(f"\n{profit_emoji} 最终盈亏: ${pnl:+,.2f} ({results['total_return']:+.2f}%)")

    def _generate_plot(self):
        """生成回测图表"""
        import matplotlib.pyplot as plt

        chart_filename = os.path.join(
            self.plot_path,
            f"backtest_{self.strategy_name}_{self.symbol}.png"
        )

        print(f"\n📉 正在生成回测图表...")
        try:
            figs = self.cerebro.plot(
                style="candlestick",
                barup="green",
                bardown="red",
                volup="green",
                voldown="red",
                width=config.PLOT_WIDTH,
                height=config.PLOT_HEIGHT,
                dpi=config.PLOT_DPI
            )

            # 保存图表
            if figs:
                fig = figs[0][0]
                fig.savefig(chart_filename, dpi=config.PLOT_DPI, bbox_inches="tight")
                plt.close("all")
                print(f"✅ 图表已保存: {chart_filename}")
        except Exception as e:
            print(f"⚠️  图表生成失败: {e}")
            plt.close("all")


def run_backtest(
    strategy_name: str = "sma_cross",
    symbol: str = None,
    start_date: str = None,
    end_date: str = None,
    initial_cash: float = None,
    commission_rate: float = None,
    enable_plot: bool = True
) -> Dict:
    """
    便捷函数：运行回测

    Args:
        strategy_name: 策略名称
        symbol: 股票代码
        start_date: 开始日期
        end_date: 结束日期
        initial_cash: 初始资金
        commission_rate: 手续费率
        enable_plot: 是否生成图表

    Returns:
        Dict: 回测结果
    """
    engine = BacktestEngine(
        strategy_name=strategy_name,
        symbol=symbol,
        start_date=start_date,
        end_date=end_date,
        initial_cash=initial_cash,
        commission_rate=commission_rate,
        enable_plot=enable_plot
    )

    return engine.run()


def compare_strategies(
    symbol: str = None,
    start_date: str = None,
    end_date: str = None,
    strategies: List[str] = None
) -> List[Dict]:
    """
    对比多个策略

    Args:
        symbol: 股票代码
        start_date: 开始日期
        end_date: 结束日期
        strategies: 策略列表 (None 表示所有策略)

    Returns:
        List[Dict]: 各策略的回测结果
    """
    symbol = symbol or config.DEFAULT_SYMBOL
    strategies = strategies or list(STRATEGY_REGISTRY.keys())

    print("\n" + "🔥" * 35)
    print(f"  策略对比模式 - 股票: {symbol}")
    print(f"  时间: {start_date or config.START_DATE} ~ {end_date or config.END_DATE}")
    print("🔥" * 35)

    all_results = []

    for strategy_name in strategies:
        if strategy_name not in STRATEGY_REGISTRY:
            print(f"⚠️  跳过未知策略: {strategy_name}")
            continue

        try:
            result = run_backtest(
                strategy_name=strategy_name,
                symbol=symbol,
                start_date=start_date,
                end_date=end_date,
                enable_plot=False  # 对比模式不生成图表
            )
            all_results.append(result)
            print("\n")
        except Exception as e:
            print(f"❌ 策略 {strategy_name} 运行失败: {e}\n")

    # 输出对比表格
    if all_results:
        print("=" * 90)
        print("📊 策略对比总结")
        print("=" * 90)
        print(f"{'策略':<20} {'收益率':>10} {'夏普':>8} {'最大回撤':>10} {'胜率':>8} {'交易次数':>8}")
        print("-" * 90)

        for result in all_results:
            print(f"{result['strategy']:<18} "
                  f"{result['total_return']:>9.2f}% "
                  f"{result['sharpe_ratio']:>8.2f} "
                  f"{result['max_drawdown']:>9.2f}% "
                  f"{result['win_rate']:>7.1f}% "
                  f"{result['total_trades']:>8}")

        print("=" * 90)

        # 找出最佳策略
        best_return = max(all_results, key=lambda x: x["total_return"])
        best_sharpe = max(all_results, key=lambda x: x["sharpe_ratio"])

        print(f"\n🏆 最高收益策略: {best_return['strategy']}，收益率: {best_return['total_return']:+.2f}%")
        print(f"🏆 最佳夏普策略: {best_sharpe['strategy']}，夏普比率: {best_sharpe['sharpe_ratio']:.2f}")

    return all_results


def validate_date(date_str: str) -> str:
    """
    验证日期格式

    Args:
        date_str: 日期字符串，格式应为 YYYY-MM-DD

    Returns:
        str: 验证后的日期字符串

    Raises:
        argparse.ArgumentTypeError: 日期格式错误
    """
    try:
        parsed = datetime.strptime(date_str, "%Y-%m-%d")
        return parsed.strftime("%Y-%m-%d")
    except ValueError:
        raise argparse.ArgumentTypeError(
            f"日期格式错误: {date_str}，应为 YYYY-MM-DD"
        )


def main():
    """命令行入口"""
    parser = argparse.ArgumentParser(
        description="美股量化回测工具 - 基于 Backtrader",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python engine.py -s sma_cross -t AAPL
  python engine.py -s rsi -t TSLA --start 2022-01-01 --end 2023-12-31
  python engine.py -c
  python engine.py -c -t MSFT
        """
    )

    parser.add_argument(
        "-s", "--strategy",
        default="sma_cross",
        choices=list(STRATEGY_REGISTRY.keys()),
        help=f"选择策略 (默认: sma_cross)"
    )

    parser.add_argument(
        "-t", "--ticker",
        default=None,
        help="股票代码，如 AAPL、MSFT、NVDA (默认: AAPL)"
    )

    parser.add_argument(
        "--start",
        type=validate_date,
        default=None,
        help="回测开始日期，格式 YYYY-MM-DD"
    )

    parser.add_argument(
        "--end",
        type=validate_date,
        default=None,
        help="回测结束日期，格式 YYYY-MM-DD"
    )

    parser.add_argument(
        "--cash",
        type=float,
        default=None,
        help="初始资金 (默认: 100000)"
    )

    parser.add_argument(
        "--commission",
        type=float,
        default=None,
        help="手续费率 (默认: 0.001)"
    )

    parser.add_argument(
        "-c", "--compare",
        action="store_true",
        help="对比所有策略的表现"
    )

    parser.add_argument(
        "--no-plot",
        action="store_true",
        help="不生成图表"
    )

    parser.add_argument(
        "--list-strategies",
        action="store_true",
        help="列出所有可用策略"
    )

    args = parser.parse_args()

    # 列出策略
    if args.list_strategies:
        print("\n" + "=" * 60)
        print("可用策略列表")
        print("=" * 60)
        for name, info in list_strategies().items():
            print(f"\n{name}:")
            print(f"  名称: {info['name']}")
            print(f"  描述: {info['description']}")
        print("=" * 60)
        return

    # 运行回测
    if args.compare:
        compare_strategies(args.ticker, args.start, args.end)
    else:
        run_backtest(
            strategy_name=args.strategy,
            symbol=args.ticker,
            start_date=args.start,
            end_date=args.end,
            initial_cash=args.cash,
            commission_rate=args.commission,
            enable_plot=not args.no_plot
        )


if __name__ == "__main__":
    main()
