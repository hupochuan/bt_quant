"""
RSI 相对强弱指标策略

RSI < 30: 超卖区域，买入信号
RSI > 70: 超买区域，卖出信号
"""
import math

import backtrader as bt
import config


class RsiStrategy(bt.Strategy):
    """
    RSI 策略

    Params:
        period: RSI 计算周期
        oversold: 超卖阈值
        overbought: 超买阈值
        order_percentage: 每次交易资金使用比例
    """

    params = (
        ('period', config.RSI_PARAMS['period']),
        ('oversold', config.RSI_PARAMS['oversold']),
        ('overbought', config.RSI_PARAMS['overbought']),
        ('order_percentage', config.RSI_PARAMS['order_percentage']),
    )

    def __init__(self):
        """初始化策略"""
        # 计算 RSI
        self.rsi = bt.indicators.RelativeStrengthIndex(
            self.data.close,
            period=self.params.period
        )

        # 记录订单
        self.order = None

        # 记录上次信号状态
        self.last_signal = None

    def log(self, txt, dt=None):
        """日志函数"""
        dt = dt or self.datas[0].datetime.date(0)
        print(f'{dt.isoformat()} {txt}')

    def notify_order(self, order):
        """订单状态通知"""
        if order.status in [order.Submitted, order.Accepted]:
            return

        if order.status in [order.Completed]:
            if order.isbuy():
                self.log(f'【买入执行】价格: {order.executed.price:.2f}, '
                        f'数量: {order.executed.size}, '
                        f'RSI: {self.rsi[0]:.2f}')
            else:
                self.log(f'【卖出执行】价格: {order.executed.price:.2f}, '
                        f'数量: {order.executed.size}, '
                        f'RSI: {self.rsi[0]:.2f}')

        elif order.status in [order.Canceled, order.Margin, order.Rejected]:
            self.log('【订单取消/保证金不足/被拒绝】')

        self.order = None

    def next(self):
        """策略核心逻辑"""
        if self.order:
            return

        current_rsi = self.rsi[0]

        # 检查数据有效性
        if math.isnan(current_rsi):
            return

        if not self.position:
            # 没有持仓，检查买入信号
            # RSI 从超卖区回升（<30 上升到 >=30）
            if self.rsi[-1] < self.params.oversold and current_rsi >= self.params.oversold:
                cash = self.broker.getcash()
                size = int((cash * self.params.order_percentage) / self.data.close[0])

                if size > 0:
                    self.log(f'【买入信号】价格: {self.data.close[0]:.2f}, '
                            f'RSI: {current_rsi:.2f} (超卖回升)')
                    self.order = self.buy(size=size)
        else:
            # 有持仓，检查卖出信号
            # RSI 从超买区回落（>70 下降到 <=70）
            if self.rsi[-1] > self.params.overbought and current_rsi <= self.params.overbought:
                self.log(f'【卖出信号】价格: {self.data.close[0]:.2f}, '
                        f'RSI: {current_rsi:.2f} (超买回落)')
                self.order = self.sell(size=self.position.size)

    def stop(self):
        """回测结束时调用"""
        final_value = self.broker.getvalue()
        initial_value = self.broker.startingcash
        return_pct = (final_value / initial_value - 1) * 100

        self.log(f'回测结束 - 初始资金: {initial_value:.2f}, '
                f'最终资金: {final_value:.2f}, '
                f'收益率: {return_pct:.2f}%')
