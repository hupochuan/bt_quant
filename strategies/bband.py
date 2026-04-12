"""
布林带策略

价格触及下轨：买入信号
价格触及上轨：卖出信号
"""
import math

import backtrader as bt
import config


class BollingerBandsStrategy(bt.Strategy):
    """
    布林带策略

    Params:
        period: 布林带周期
        devfactor: 标准差倍数
        order_percentage: 每次交易资金使用比例
    """

    params = (
        ('period', config.BBAND_PARAMS['period']),
        ('devfactor', config.BBAND_PARAMS['devfactor']),
        ('order_percentage', config.BBAND_PARAMS['order_percentage']),
    )

    def __init__(self):
        """初始化策略"""
        # 计算布林带
        self.bband = bt.indicators.BollingerBands(
            self.data.close,
            period=self.params.period,
            devfactor=self.params.devfactor
        )

        # 上轨、中轨、下轨
        self.top = self.bband.top
        self.mid = self.bband.mid
        self.bot = self.bband.bot

        # 布林带宽度
        self.band_width = self.top - self.bot

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
                        f'%B: {self.percent_b[0]:.2f}')
            else:
                self.log(f'【卖出执行】价格: {order.executed.price:.2f}, '
                        f'数量: {order.executed.size}, '
                        f'%B: {self.percent_b[0]:.2f}')

        elif order.status in [order.Canceled, order.Margin, order.Rejected]:
            self.log('【订单取消/保证金不足/被拒绝】')

        self.order = None

    def next(self):
        """策略核心逻辑"""
        if self.order:
            return

        current_price = self.data.close[0]
        current_band_width = self.band_width[0]

        # 检查布林带宽度，防止除零
        if current_band_width == 0:
            return

        # %B 指标 (价格在布林带中的位置)
        current_percent_b = (current_price - self.bot[0]) / current_band_width

        # 检查数据有效性
        if math.isnan(current_percent_b):
            return

        if not self.position:
            # 没有持仓，检查买入信号
            # 价格从下轨下方回升（%B < 0.1 上升到 >= 0.1）
            prev_percent_b = (self.data.close[-1] - self.bot[-1]) / self.band_width[-1] if self.band_width[-1] != 0 else 0
            if prev_percent_b < 0.1 and current_percent_b >= 0.1:
                cash = self.broker.getcash()
                size = int((cash * self.params.order_percentage) / current_price)

                if size > 0:
                    self.log(f'【买入信号】价格: {current_price:.2f}, '
                            f'%B: {current_percent_b:.2f} (下轨反弹)')
                    self.order = self.buy(size=size)
        else:
            # 有持仓，检查卖出信号
            # 价格从上轨上方回落（%B > 0.9 下降到 <= 0.9）
            prev_percent_b = (self.data.close[-1] - self.bot[-1]) / self.band_width[-1] if self.band_width[-1] != 0 else 1
            if prev_percent_b > 0.9 and current_percent_b <= 0.9:
                self.log(f'【卖出信号】价格: {current_price:.2f}, '
                        f'%B: {current_percent_b:.2f} (上轨回落)')
                self.order = self.sell(size=self.position.size)

    def stop(self):
        """回测结束时调用"""
        final_value = self.broker.getvalue()
        initial_value = self.broker.startingcash
        return_pct = (final_value / initial_value - 1) * 100

        self.log(f'回测结束 - 初始资金: {initial_value:.2f}, '
                f'最终资金: {final_value:.2f}, '
                f'收益率: {return_pct:.2f}%')
