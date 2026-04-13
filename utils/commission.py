"""
手续费模型
"""
import backtrader as bt


class FixedCommission(bt.CommInfoBase):
    """
    固定手续费模型
    每笔交易收取固定金额

    适用于某些特定策略，如阴阳线策略
    """
    params = (
        ('commission', 5.0),      # 固定手续费金额
        ('stocklike', True),      # 股票类资产
        ('commtype', bt.CommInfoBase.COMM_FIXED),  # 固定费用类型
    )

    def _getcommission(self, size, price, pseudoexec):
        """
        计算手续费

        Args:
            size: 交易数量
            price: 交易价格
            pseudoexec: 是否为预执行

        Returns:
            float: 手续费金额
        """
        return self.params.commission


class PercentageCommission(bt.CommInfoBase):
    """
    百分比手续费模型
    按交易金额的一定比例收取

    适用于大多数美股交易策略
    """
    params = (
        ('commission', 0.001),    # 手续费率 (0.1%)
        ('stocklike', True),
        ('commtype', bt.CommInfoBase.COMM_PERC),  # 百分比模式，框架自动计算
    )

    # 使用 COMM_PERC 模式，Backtrader 框架会自动按百分比计算手续费
    # 无需重写 _getcommission 方法


class TieredCommission(bt.CommInfoBase):
    """
    阶梯手续费模型
    根据交易量设置不同费率
    """
    params = (
        ('tier1_limit', 1000),     # 第一档限额
        ('tier1_rate', 0.001),     # 第一档费率
        ('tier2_limit', 10000),    # 第二档限额
        ('tier2_rate', 0.0008),    # 第二档费率
        ('tier3_rate', 0.0005),    # 第三档费率
        ('stocklike', True),
        ('commtype', bt.CommInfoBase.COMM_FIXED),  # 使用 FIXED 模式
    )

    def _getcommission(self, size, price, pseudoexec):
        """
        计算阶梯手续费

        Args:
            size: 交易数量
            price: 交易价格
            pseudoexec: 是否为预执行

        Returns:
            float: 手续费金额
        """
        amount = abs(size) * price

        if amount <= self.params.tier1_limit:
            rate = self.params.tier1_rate
        elif amount <= self.params.tier2_limit:
            rate = self.params.tier2_rate
        else:
            rate = self.params.tier3_rate

        return amount * rate


def get_commission(commission_type: str = "percentage", **kwargs):
    """
    获取手续费模型

    Args:
        commission_type: 手续费类型 ('fixed', 'percentage', 'tiered')
        **kwargs: 手续费参数

    Returns:
        Commission 实例
    """
    if commission_type == "fixed":
        return FixedCommission(**kwargs)
    elif commission_type == "percentage":
        return PercentageCommission(**kwargs)
    elif commission_type == "tiered":
        return TieredCommission(**kwargs)
    else:
        raise ValueError(f"未知的手续费类型: {commission_type}")
