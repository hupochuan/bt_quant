"""
双均线交叉策略

当短期均线上穿长期均线时买入（金叉）
当短期均线下穿长期均线时卖出（死叉）
"""
import backtrader as bt
import config


class SmaCrossStrategy(bt.Strategy):
    """
    双均线交叉策略

    Params:
        fast_period: 短期均线周期
        slow_period: 长期均线周期
        order_percentage: 每次交易资金使用比例
    """

    params = (
        ('fast_period', config.SMA_CROSS_PARAMS['fast_period']),
        ('slow_period', config.SMA_CROSS_PARAMS['slow_period']),
        ('order_percentage', config.SMA_CROSS_PARAMS['order_percentage']),
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

        # 计算交叉信号
        self.crossover = bt.indicators.CrossOver(self.fast_sma, self.slow_sma)

        # 记录订单
        self.order = None

    def log(self, txt, dt=None):
        """日志函数"""
        dt = dt or self.datas[0].datetime.date(0)
        print(f'{dt.isoformat()} {txt}')

    def notify_order(self, order):
        """订单状态通知"""
        if order.status in [order.Submitted, order.Accepted]:
            # 订单已提交/接受，等待执行
            return

        if order.status in [order.Completed]:
            if order.isbuy():
                self.log(f'【买入执行】价格: {order.executed.price:.2f}, '
                        f'数量: {order.executed.size}, '
                        f'成本: {order.executed.value:.2f}, '
                        f'手续费: {order.executed.comm:.2f}')
            else:
                self.log(f'【卖出执行】价格: {order.executed.price:.2f}, '
                        f'数量: {order.executed.size}, '
                        f'成本: {order.executed.value:.2f}, '
                        f'手续费: {order.executed.comm:.2f}')

        elif order.status in [order.Canceled, order.Margin, order.Rejected]:
            self.log('【订单取消/保证金不足/被拒绝】')

        # 重置订单
        self.order = None

    def next(self):
        """策略核心逻辑 - 每个交易日调用"""
        # 如果有待执行订单，不执行新操作
        if self.order:
            return

        # 检查是否有持仓
        if not self.position:
            # 没有持仓，检查买入信号
            # 金叉：短期均线上穿长期均线
            if self.crossover > 0:
                # 计算可买入数量
                cash = self.broker.getcash()
                size = int((cash * self.params.order_percentage) / self.data.close[0])

                if size > 0:
                    self.log(f'【买入信号】价格: {self.data.close[0]:.2f}, 数量: {size}')
                    self.order = self.buy(size=size)
        else:
            # 有持仓，检查卖出信号
            # 死叉：短期均线下穿长期均线
            if self.crossover < 0:
                self.log(f'【卖出信号】价格: {self.data.close[0]:.2f}, 数量: {self.position.size}')
                self.order = self.sell(size=self.position.size)

    def stop(self):
        """回测结束时调用"""
        # 计算最终收益率
        final_value = self.broker.getvalue()
        initial_value = self.broker.startingcash
        return_pct = (final_value / initial_value - 1) * 100

        self.log(f'回测结束 - 初始资金: {initial_value:.2f}, '
                f'最终资金: {final_value:.2f}, '
                f'收益率: {return_pct:.2f}%')
