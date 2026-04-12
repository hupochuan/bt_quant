"""
自定义分析器
扩展 Backtrader 的分析功能
"""
import backtrader as bt
import pandas as pd
from datetime import datetime


class CustomAnalyzer(bt.Analyzer):
    """
    自定义分析器
    记录详细的交易信息和每日权益
    """

    def __init__(self):
        super(CustomAnalyzer, self).__init__()
        self.daily_values = []
        self.trades = []
        self.current_trade = None

    def start(self):
        """回测开始时调用"""
        self.daily_values = []
        self.trades = []

    def next(self):
        """每个交易日调用"""
        # 记录每日权益
        self.daily_values.append({
            'date': self.datas[0].datetime.date(0),
            'cash': self.strategy.broker.getcash(),
            'value': self.strategy.broker.getvalue(),
            'position': self.strategy.position.size if hasattr(self.strategy, 'position') else 0,
        })

    def notify_trade(self, trade):
        """交易通知"""
        if trade.isclosed:
            self.trades.append({
                'ref': trade.ref,
                'date': self.strategy.datetime.date(0),
                'size': trade.size,
                'price': trade.price,
                'value': trade.value,
                'commission': trade.commission,
                'pnl': trade.pnl,
                'pnlcomm': trade.pnlcomm,  # 扣除手续费后的盈亏
            })

    def get_analysis(self):
        """获取分析结果"""
        return {
            'daily_values': pd.DataFrame(self.daily_values),
            'trades': pd.DataFrame(self.trades) if self.trades else pd.DataFrame(),
        }


class TradeList(bt.Analyzer):
    """
    交易列表分析器
    详细记录每笔交易的信息
    """

    def __init__(self):
        super(TradeList, self).__init__()
        self.trades = []

    def notify_trade(self, trade):
        if trade.isclosed:
            dt = self.datas[0].datetime.date(0)

            self.trades.append({
                'date': dt,
                'ref': trade.ref,
                'ticker': trade.data._name,
                'size': trade.size,
                'price': trade.price,
                'value': trade.value,
                'commission': trade.commission,
                'pnl': trade.pnl,
                'pnlcomm': trade.pnlcomm,
            })

    def get_analysis(self):
        return self.trades


class DrawdownAnalyzer(bt.Analyzer):
    """
    回撤分析器
    详细记录回撤信息
    """

    def __init__(self):
        super(DrawdownAnalyzer, self).__init__()
        self.peak = 0
        self.max_drawdown = 0
        self.max_drawdown_date = None
        self.drawdowns = []

    def next(self):
        value = self.strategy.broker.getvalue()

        if value > self.peak:
            self.peak = value

        drawdown = (self.peak - value) / self.peak if self.peak > 0 else 0

        if drawdown > self.max_drawdown:
            self.max_drawdown = drawdown
            self.max_drawdown_date = self.datas[0].datetime.date(0)

        self.drawdowns.append({
            'date': self.datas[0].datetime.date(0),
            'value': value,
            'peak': self.peak,
            'drawdown': drawdown,
        })

    def get_analysis(self):
        return {
            'max_drawdown': self.max_drawdown,
            'max_drawdown_date': self.max_drawdown_date,
            'drawdowns': pd.DataFrame(self.drawdowns),
        }


class ReturnsAnalyzer(bt.Analyzer):
    """
    收益分析器
    计算各种收益指标
    """

    def __init__(self):
        super(ReturnsAnalyzer, self).__init__()
        self.returns = []
        self.initial_value = None

    def start(self):
        self.initial_value = self.strategy.broker.getvalue()

    def next(self):
        current_value = self.strategy.broker.getvalue()
        total_return = (current_value / self.initial_value - 1) if self.initial_value > 0 else 0

        self.returns.append({
            'date': self.datas[0].datetime.date(0),
            'value': current_value,
            'total_return': total_return,
        })

    def get_analysis(self):
        df = pd.DataFrame(self.returns)

        if len(df) > 1:
            df['daily_return'] = df['value'].pct_change()
            total_return = df['total_return'].iloc[-1]
            annualized_return = (1 + total_return) ** (252 / len(df)) - 1
            volatility = df['daily_return'].std() * (252 ** 0.5)
            sharpe_ratio = annualized_return / volatility if volatility > 0 else 0
        else:
            total_return = 0
            annualized_return = 0
            volatility = 0
            sharpe_ratio = 0

        return {
            'total_return': total_return,
            'annualized_return': annualized_return,
            'volatility': volatility,
            'sharpe_ratio': sharpe_ratio,
            'returns_df': df,
        }


class PositionAnalyzer(bt.Analyzer):
    """
    持仓分析器
    分析持仓变化和持仓时间
    """

    def __init__(self):
        super(PositionAnalyzer, self).__init__()
        self.positions = []
        self.current_position_start = None

    def next(self):
        position = self.strategy.position

        # 记录持仓状态变化
        if position.size != 0 and self.current_position_start is None:
            self.current_position_start = self.datas[0].datetime.date(0)
        elif position.size == 0 and self.current_position_start is not None:
            self.positions.append({
                'entry_date': self.current_position_start,
                'exit_date': self.datas[0].datetime.date(0),
                'duration': (self.datas[0].datetime.date(0) - self.current_position_start).days,
            })
            self.current_position_start = None

    def get_analysis(self):
        df = pd.DataFrame(self.positions)

        if not df.empty:
            avg_duration = df['duration'].mean()
            max_duration = df['duration'].max()
            min_duration = df['duration'].min()
        else:
            avg_duration = max_duration = min_duration = 0

        return {
            'positions': df,
            'avg_duration': avg_duration,
            'max_duration': max_duration,
            'min_duration': min_duration,
            'total_positions': len(df),
        }
