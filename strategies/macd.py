"""
MACD 策略

MACD 线上穿信号线：买入信号
MACD 线下穿信号线：卖出信号
"""
import backtrader as bt
import config


class MacdStrategy(bt.Strategy):
    """
    MACD 策略

    Params:
        fast_period: 快线周期
        slow_period: 慢线周期
        signal_period: 信号线周期
        order_percentage: 每次交易资金使用比例
    """

    params = (
        ('fast_period', config.MACD_PARAMS['fast_period']),
        ('slow_period', config.MACD_PARAMS['slow_period']),
        ('signal_period', config.MACD_PARAMS['signal_period']),
        ('order_percentage', config.MACD_PARAMS['order_percentage']),
    )

    def __init__(self):
        """初始化策略"""
        # 计算 MACD
        self.macd = bt.indicators.MACD(
            self.data.close,
            period_me1=self.params.fast_period,
            period_me2=self.params.slow_period,
            period_signal=self.params.signal_period
        )

        # MACD 线和信号线
        self.macd_line = self.macd.macd
        self.signal_line = self.macd.signal

        # MACD 柱状图 (MACD - Signal)
        self.histogram = self.macd_line - self.signal_line

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
                        f'MACD: {self.macd_line[0]:.4f}, '
                        f'信号: {self.signal_line[0]:.4f}')
            else:
                self.log(f'【卖出执行】价格: {order.executed.price:.2f}, '
                        f'数量: {order.executed.size}, '
                        f'MACD: {self.macd_line[0]:.4f}, '
                        f'信号: {self.signal_line[0]:.4f}')

        elif order.status in [order.Canceled, order.Margin, order.Rejected]:
            self.log('【订单取消/保证金不足/被拒绝】')

        self.order = None

    def next(self):
        """策略核心逻辑"""
        if self.order:
            return

        # 检查数据有效性
        if len(self.macd_line) < 2:
            return

        if not self.position:
            # 没有持仓，检查买入信号
            # MACD 线上穿信号线
            if self.macd_line[-1] <= self.signal_line[-1] and self.macd_line[0] > self.signal_line[0]:
                cash = self.broker.getcash()
                size = int((cash * self.params.order_percentage) / self.data.close[0])

                if size > 0:
                    self.log(f'【买入信号】价格: {self.data.close[0]:.2f}, '
                            f'MACD金叉: {self.macd_line[0]:.4f} > {self.signal_line[0]:.4f}')
                    self.order = self.buy(size=size)
        else:
            # 有持仓，检查卖出信号
            # MACD 线下穿信号线
            if self.macd_line[-1] >= self.signal_line[-1] and self.macd_line[0] < self.signal_line[0]:
                self.log(f'【卖出信号】价格: {self.data.close[0]:.2f}, '
                        f'MACD死叉: {self.macd_line[0]:.4f} < {self.signal_line[0]:.4f}')
                self.order = self.sell(size=self.position.size)

    def stop(self):
        """回测结束时调用"""
        final_value = self.broker.getvalue()
        initial_value = self.broker.startingcash
        return_pct = (final_value / initial_value - 1) * 100

        self.log(f'回测结束 - 初始资金: {initial_value:.2f}, '
                f'最终资金: {final_value:.2f}, '
                f'收益率: {return_pct:.2f}%')
