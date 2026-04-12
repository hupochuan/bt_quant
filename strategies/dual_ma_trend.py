"""
双均线趋势策略

结合价格与均线的关系以及均线趋势进行交易
"""
import backtrader as bt
import config


class DualMATrendStrategy(bt.Strategy):
    """
    双均线趋势跟踪策略

    买入条件：
    1. 价格在短期均线上方
    2. 短期均线在长期均线上方
    3. 短期均线向上倾斜

    卖出条件：
    1. 价格跌破短期均线
    2. 或短期均线向下倾斜且价格低于短期均线

    Params:
        fast_period: 短期均线周期
        slow_period: 长期均线周期
        trend_period: 趋势确认周期
        order_percentage: 每次交易资金使用比例
    """

    params = (
        ('fast_period', config.DUAL_MA_TREND_PARAMS['fast_period']),
        ('slow_period', config.DUAL_MA_TREND_PARAMS['slow_period']),
        ('trend_period', config.DUAL_MA_TREND_PARAMS['trend_period']),
        ('order_percentage', config.DUAL_MA_TREND_PARAMS['order_percentage']),
    )

    def __init__(self):
        """初始化策略"""
        # 计算短期和长期均线
        self.fast_sma = bt.indicators.SimpleMovingAverage(
            self.data.close, period=self.params.fast_period
        )
        self.slow_sma = bt.indicators.SimpleMovingAverage(
            self.data.close, period=self.params.slow_period
        )

        # 计算均线斜率（趋势）- 使用差分近似斜率
        # 正值表示向上倾斜，负值表示向下倾斜
        self.fast_sma_slope = self.fast_sma - self.fast_sma(-self.params.trend_period)

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
                        f'数量: {order.executed.size}')
            else:
                self.log(f'【卖出执行】价格: {order.executed.price:.2f}, '
                        f'数量: {order.executed.size}')

        elif order.status in [order.Canceled, order.Margin, order.Rejected]:
            self.log('【订单取消/保证金不足/被拒绝】')

        self.order = None

    def next(self):
        """策略核心逻辑"""
        if self.order:
            return

        current_price = self.data.close[0]

        # 检查数据有效性
        if len(self.fast_sma) < self.params.slow_period:
            return

        # 判断趋势
        price_above_fast = current_price > self.fast_sma[0]
        fast_above_slow = self.fast_sma[0] > self.slow_sma[0]
        fast_trend_up = self.fast_sma_slope[0] > 0

        if not self.position:
            # 没有持仓，检查买入信号
            # 条件：价格在短期均线上方 + 短期在长期上方 + 短期均线向上
            if price_above_fast and fast_above_slow and fast_trend_up:
                cash = self.broker.getcash()
                size = int((cash * self.params.order_percentage) / current_price)

                if size > 0:
                    self.log(f'【买入信号】价格: {current_price:.2f}, '
                            f'快MA: {self.fast_sma[0]:.2f}, '
                            f'慢MA: {self.slow_sma[0]:.2f}, '
                            f'趋势: 向上')
                    self.order = self.buy(size=size)
        else:
            # 有持仓，检查卖出信号
            # 条件：价格跌破短期均线 或 (短期均线向下且价格低于短期均线)
            price_below_fast = current_price < self.fast_sma[0]
            fast_trend_down = self.fast_sma_slope[0] < 0

            # 卖出条件：价格跌破短期均线
            if price_below_fast:
                self.log(f'【卖出信号】价格: {current_price:.2f}, '
                        f'快MA: {self.fast_sma[0]:.2f}, '
                        f'趋势: {"向下" if fast_trend_down else "向上"}')
                self.order = self.sell(size=self.position.size)

    def stop(self):
        """回测结束时调用"""
        final_value = self.broker.getvalue()
        initial_value = self.broker.startingcash
        return_pct = (final_value / initial_value - 1) * 100

        self.log(f'回测结束 - 初始资金: {initial_value:.2f}, '
                f'最终资金: {final_value:.2f}, '
                f'收益率: {return_pct:.2f}%')
