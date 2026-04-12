"""
动量策略

基于价格动量进行交易
"""
import math

import backtrader as bt
import config


class MomentumStrategy(bt.Strategy):
    """
    动量策略

    买入条件：价格动量超过正阈值（上涨趋势）
    卖出条件：价格动量低于负阈值（下跌趋势）

    Params:
        period: 动量计算周期
        threshold: 动量阈值
        order_percentage: 每次交易资金使用比例
    """

    params = (
        ('period', config.MOMENTUM_PARAMS['period']),
        ('threshold', config.MOMENTUM_PARAMS['threshold']),
        ('order_percentage', config.MOMENTUM_PARAMS['order_percentage']),
    )

    def __init__(self):
        """初始化策略"""
        # 计算动量指标 (当前价格 / N周期前价格 - 1)
        self.momentum = bt.indicators.Momentum(
            self.data.close, period=self.params.period
        )

        # 动量百分比
        self.momentum_pct = self.momentum / 100

        # 记录订单
        self.order = None

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
                        f'动量: {self.momentum_pct[0]:.2%}')
            else:
                self.log(f'【卖出执行】价格: {order.executed.price:.2f}, '
                        f'数量: {order.executed.size}, '
                        f'动量: {self.momentum_pct[0]:.2%}')

        elif order.status in [order.Canceled, order.Margin, order.Rejected]:
            self.log('【订单取消/保证金不足/被拒绝】')

        self.order = None

    def next(self):
        """策略核心逻辑"""
        if self.order:
            return

        current_momentum = self.momentum_pct[0]

        # 检查数据有效性
        if math.isnan(current_momentum):
            return

        if not self.position:
            # 没有持仓，检查买入信号
            # 动量超过正阈值（上涨趋势确认）
            if current_momentum > self.params.threshold:
                cash = self.broker.getcash()
                size = int((cash * self.params.order_percentage) / self.data.close[0])

                if size > 0:
                    self.log(f'【买入信号】价格: {self.data.close[0]:.2f}, '
                            f'动量: {current_momentum:.2%} (突破阈值)')
                    self.order = self.buy(size=size)
        else:
            # 有持仓，检查卖出信号
            # 动量转为负值（下跌趋势）
            if current_momentum < -self.params.threshold:
                self.log(f'【卖出信号】价格: {self.data.close[0]:.2f}, '
                        f'动量: {current_momentum:.2%} (跌破阈值)')
                self.order = self.sell(size=self.position.size)

            # 或者动量衰减（止盈）
            elif current_momentum < self.params.threshold / 2 and self.momentum_pct[-1] > self.params.threshold:
                self.log(f'【卖出信号】价格: {self.data.close[0]:.2f}, '
                        f'动量: {current_momentum:.2%} (动量衰减)')
                self.order = self.sell(size=self.position.size)

    def stop(self):
        """回测结束时调用"""
        final_value = self.broker.getvalue()
        initial_value = self.broker.startingcash
        return_pct = (final_value / initial_value - 1) * 100

        self.log(f'回测结束 - 初始资金: {initial_value:.2f}, '
                f'最终资金: {final_value:.2f}, '
                f'收益率: {return_pct:.2f}%')
