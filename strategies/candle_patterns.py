"""
阴阳线策略模块
包含：基础阴阳线策略、增强版阴阳线策略、日线突破策略
"""
import backtrader as bt
import config


class CandlePatternStrategy(bt.Strategy):
    """
    阴阳线策略（Candle Pattern Strategy）

    原理：
    - 连续 N 根阳线（Close > Open）时买入
    - 连续 N 根阴线（Close < Open）时卖出
    - 支持固定止损金额

    适用场景：短线趋势跟踪
    """

    params = (
        ("consecutive_count", config.CANDLE_PATTERN_PARAMS["consecutive_count"]),
        ("trade_size", config.CANDLE_PATTERN_PARAMS["trade_size"]),
        ("stop_loss_amount", config.CANDLE_PATTERN_PARAMS["stop_loss_amount"]),
    )

    def __init__(self):
        self.order = None
        self.buy_price = None
        self.buy_total_cost = 0.0
        self.trade_count = 0

    def log(self, message):
        """日志函数"""
        datetime_str = self.datas[0].datetime.datetime(0).strftime("%Y-%m-%d %H:%M")
        print(f"  [{datetime_str}] {message}")

    def notify_order(self, order):
        """订单通知"""
        if order.status in [order.Completed]:
            if order.isbuy():
                self.buy_price = order.executed.price
                self.buy_total_cost = order.executed.price * order.executed.size
                self.log(f"🟢 买入: ${order.executed.price:.2f}, 数量: {order.executed.size:.0f}")
            else:
                sell_revenue = order.executed.price * abs(order.executed.size)
                profit = sell_revenue - self.buy_total_cost if self.buy_total_cost > 0 else 0
                emoji = "🔴" if profit < 0 else "🟢"
                self.log(f"{emoji} 卖出: ${order.executed.price:.2f}, "
                         f"数量: {abs(order.executed.size):.0f}, 盈亏: ${profit:.2f}")
                self.buy_price = None
                self.buy_total_cost = 0.0
            self.trade_count += 1
        self.order = None

    def _is_bullish(self, bars_ago=0):
        """判断某根 K 线是否为阳线（Close > Open）"""
        return self.data.close[bars_ago] > self.data.open[bars_ago]

    def _is_bearish(self, bars_ago=0):
        """判断某根 K 线是否为阴线（Close < Open）"""
        return self.data.close[bars_ago] < self.data.open[bars_ago]

    def _check_consecutive_bullish(self):
        """检查是否连续 N 根阳线"""
        # 确保有足够的数据
        if len(self.data) < self.params.consecutive_count:
            return False
        for i in range(self.params.consecutive_count):
            if not self._is_bullish(-i - 1):  # -1, -2, -3...
                return False
        return True

    def _check_consecutive_bearish(self):
        """检查是否连续 N 根阴线"""
        # 确保有足够的数据
        if len(self.data) < self.params.consecutive_count:
            return False
        for i in range(self.params.consecutive_count):
            if not self._is_bearish(-i - 1):  # -1, -2, -3...
                return False
        return True

    def _check_stop_loss(self):
        """检查是否触发止损（亏损超过止损金额）"""
        if self.position and self.buy_price:
            current_loss = (self.buy_price - self.data.close[0]) * abs(self.position.size)
            return current_loss >= self.params.stop_loss_amount
        return False

    def next(self):
        """策略核心逻辑"""
        if self.order:
            return

        # 止损检查（优先级最高）
        if self.position and self._check_stop_loss():
            sell_size = min(abs(self.position.size), self.params.trade_size)
            self.log(f"⛔ 触发止损! 当前价: ${self.data.close[0]:.2f}, "
                     f"买入价: ${self.buy_price:.2f}")
            self.order = self.sell(size=sell_size)
            return

        # 买入条件：连续 N 根阳线
        if self._check_consecutive_bullish():
            available_cash = self.broker.getcash()
            cost = self.data.close[0] * self.params.trade_size
            if available_cash >= cost:
                self.order = self.buy(size=self.params.trade_size)

        # 卖出条件：连续 N 根阴线（且有持仓）
        elif self.position and self._check_consecutive_bearish():
            sell_size = min(abs(self.position.size), self.params.trade_size)
            if sell_size > 0:
                self.order = self.sell(size=sell_size)


class EnhancedCandleStrategy(bt.Strategy):
    """
    增强版阴阳线策略（Enhanced Candle Pattern Strategy）

    在基础阴阳线策略上增加四重过滤：
    1. EMA 趋势过滤：价格在 EMA 上方才允许买入，下方才允许卖出
    2. 成交量确认：阳线放量（成交量 > 均量 × 倍数）才触发买入
    3. 冷却期：卖出后等待 N 根 K 线才能再次买入，避免频繁交易
    4. 移动止损：盈利达到阈值后，止损线上移到买入价（保本止损）
    """

    params = (
        ("consecutive_count", config.ENHANCED_CANDLE_PARAMS["consecutive_count"]),
        ("trade_size", config.ENHANCED_CANDLE_PARAMS["trade_size"]),
        ("stop_loss_amount", config.ENHANCED_CANDLE_PARAMS["stop_loss_amount"]),
        ("trailing_profit_threshold", config.ENHANCED_CANDLE_PARAMS["trailing_profit_threshold"]),
        ("ema_period", config.ENHANCED_CANDLE_PARAMS["ema_period"]),
        ("volume_ma_period", config.ENHANCED_CANDLE_PARAMS["volume_ma_period"]),
        ("volume_ratio", config.ENHANCED_CANDLE_PARAMS["volume_ratio"]),
        ("cooldown_bars", config.ENHANCED_CANDLE_PARAMS["cooldown_bars"]),
    )

    def __init__(self):
        # 技术指标
        self.ema = bt.indicators.EMA(self.data.close, period=self.params.ema_period)
        self.volume_ma = bt.indicators.SMA(self.data.volume, period=self.params.volume_ma_period)

        # 交易状态
        self.order = None
        self.buy_price = None
        self.buy_total_cost = 0.0
        self.trade_count = 0
        self.bars_since_sell = 999  # 距离上次卖出的 K 线数
        self.highest_profit = 0.0  # 持仓期间最高浮盈

    def log(self, message):
        """日志函数"""
        datetime_str = self.datas[0].datetime.datetime(0).strftime("%Y-%m-%d %H:%M")
        print(f"  [{datetime_str}] {message}")

    def notify_order(self, order):
        """订单通知"""
        if order.status in [order.Completed]:
            if order.isbuy():
                self.buy_price = order.executed.price
                self.buy_total_cost = order.executed.price * order.executed.size
                self.highest_profit = 0.0
                self.log(f"🟢 买入: ${order.executed.price:.2f}, 数量: {order.executed.size:.0f}")
            else:
                sell_revenue = order.executed.price * abs(order.executed.size)
                profit = sell_revenue - self.buy_total_cost if self.buy_total_cost > 0 else 0
                emoji = "🔴" if profit < 0 else "🟢"
                self.log(f"{emoji} 卖出: ${order.executed.price:.2f}, "
                         f"数量: {abs(order.executed.size):.0f}, 盈亏: ${profit:.2f}")
                self.buy_price = None
                self.buy_total_cost = 0.0
                self.bars_since_sell = 0
                self.highest_profit = 0.0
            self.trade_count += 1
        self.order = None

    def _is_bullish(self, bars_ago=0):
        return self.data.close[bars_ago] > self.data.open[bars_ago]

    def _is_bearish(self, bars_ago=0):
        return self.data.close[bars_ago] < self.data.open[bars_ago]

    def _check_consecutive_bullish(self):
        """检查是否连续 N 根阳线"""
        # 确保有足够的数据
        if len(self.data) < self.params.consecutive_count:
            return False
        for i in range(self.params.consecutive_count):
            if not self._is_bullish(-i - 1):  # -1, -2, -3...
                return False
        return True

    def _check_consecutive_bearish(self):
        """检查是否连续 N 根阴线"""
        # 确保有足够的数据
        if len(self.data) < self.params.consecutive_count:
            return False
        for i in range(self.params.consecutive_count):
            if not self._is_bearish(-i - 1):  # -1, -2, -3...
                return False
        return True

    def _is_above_ema(self):
        """价格是否在 EMA 上方（上升趋势）"""
        return self.data.close[0] > self.ema[0]

    def _is_below_ema(self):
        """价格是否在 EMA 下方（下降趋势）"""
        return self.data.close[0] < self.ema[0]

    def _is_volume_confirmed(self):
        """成交量是否放大（当前量 > 均量 × 倍数）"""
        return self.data.volume[0] > self.volume_ma[0] * self.params.volume_ratio

    def _is_cooldown_over(self):
        """冷却期是否已过"""
        return self.bars_since_sell >= self.params.cooldown_bars

    def _check_stop_loss(self):
        """检查止损：支持移动止损（盈利后保本）"""
        if not self.position or not self.buy_price:
            return False

        current_profit = (self.data.close[0] - self.buy_price) * abs(self.position.size)
        self.highest_profit = max(self.highest_profit, current_profit)

        # 移动止损：盈利曾超过阈值后，如果回撤到买入价以下则止损
        if self.highest_profit >= self.params.trailing_profit_threshold:
            if current_profit <= 0:
                return True

        # 固定止损：亏损超过止损金额
        current_loss = (self.buy_price - self.data.close[0]) * abs(self.position.size)
        return current_loss >= self.params.stop_loss_amount

    def next(self):
        """策略核心逻辑"""
        if self.order:
            return

        # 更新冷却计数器
        if not self.position:
            self.bars_since_sell += 1

        # 止损检查（优先级最高）
        if self.position and self._check_stop_loss():
            sell_size = min(abs(self.position.size), self.params.trade_size)
            current_profit = (self.data.close[0] - self.buy_price) * abs(self.position.size)
            if current_profit <= 0:
                self.log(f"⛔ 触发止损! 当前价: ${self.data.close[0]:.2f}, "
                         f"买入价: ${self.buy_price:.2f}")
            else:
                self.log(f"🔒 移动止损触发! 最高浮盈: ${self.highest_profit:.2f}, "
                         f"当前浮盈: ${current_profit:.2f}")
            self.order = self.sell(size=sell_size)
            return

        # 买入条件：连续阳线 + EMA 上方 + 放量 + 冷却期已过
        if (self._check_consecutive_bullish()
                and self._is_above_ema()
                and self._is_volume_confirmed()
                and self._is_cooldown_over()):
            available_cash = self.broker.getcash()
            cost = self.data.close[0] * self.params.trade_size
            if available_cash >= cost:
                self.order = self.buy(size=self.params.trade_size)

        # 卖出条件：连续阴线 + EMA 下方（且有持仓）
        elif (self.position
              and self._check_consecutive_bearish()
              and self._is_below_ema()):
            sell_size = min(abs(self.position.size), self.params.trade_size)
            if sell_size > 0:
                self.order = self.sell(size=sell_size)


class DailyBreakoutStrategy(bt.Strategy):
    """
    日线均线突破策略（Daily Breakout Strategy）

    专为上班族设计，每天收盘后检查一次信号即可，无需盯盘。

    买入条件（三重确认）：
    1. 收盘价突破 20 日均线（趋势确认）
    2. MACD 金叉（动量确认）
    3. 成交量放大（资金确认）

    卖出条件（任一触发）：
    1. 收盘价跌破 20 日均线
    2. MACD 死叉
    3. 止损：亏损超过 5%
    4. 止盈：盈利超过 15%
    """

    params = (
        ("sma_period", config.DAILY_BREAKOUT_PARAMS["sma_period"]),
        ("macd_fast", config.DAILY_BREAKOUT_PARAMS["macd_fast"]),
        ("macd_slow", config.DAILY_BREAKOUT_PARAMS["macd_slow"]),
        ("macd_signal", config.DAILY_BREAKOUT_PARAMS["macd_signal"]),
        ("volume_ma_period", config.DAILY_BREAKOUT_PARAMS["volume_ma_period"]),
        ("volume_ratio", config.DAILY_BREAKOUT_PARAMS["volume_ratio"]),
        ("stop_loss_pct", config.DAILY_BREAKOUT_PARAMS["stop_loss_pct"]),
        ("take_profit_pct", config.DAILY_BREAKOUT_PARAMS["take_profit_pct"]),
        ("trade_size", config.DAILY_BREAKOUT_PARAMS["trade_size"]),
    )

    def __init__(self):
        # 技术指标
        self.sma = bt.indicators.SMA(self.data.close, period=self.params.sma_period)
        self.macd = bt.indicators.MACD(
            self.data.close,
            period_me1=self.params.macd_fast,
            period_me2=self.params.macd_slow,
            period_signal=self.params.macd_signal,
        )
        self.macd_crossover = bt.indicators.CrossOver(self.macd.macd, self.macd.signal)
        self.volume_ma = bt.indicators.SMA(self.data.volume, period=self.params.volume_ma_period)

        # 交易状态
        self.order = None
        self.buy_price = None
        self.trade_count = 0

        # 记录前一天是否在均线下方（用于判断突破）
        self.was_below_sma = False

    def log(self, message):
        """日志函数"""
        date = self.datas[0].datetime.date(0)
        print(f"  [{date}] {message}")

    def notify_order(self, order):
        """订单通知"""
        if order.status in [order.Completed]:
            if order.isbuy():
                self.buy_price = order.executed.price
                self.log(f"🟢 买入: ${order.executed.price:.2f}, 数量: {order.executed.size:.0f}")
            else:
                profit = (order.executed.price - self.buy_price) * abs(order.executed.size) if self.buy_price else 0
                profit_pct = (order.executed.price / self.buy_price - 1) * 100 if self.buy_price else 0
                emoji = "🔴" if profit < 0 else "🟢"
                self.log(f"{emoji} 卖出: ${order.executed.price:.2f}, "
                         f"盈亏: ${profit:.2f} ({profit_pct:+.1f}%)")
                self.buy_price = None
            self.trade_count += 1
        self.order = None

    def next(self):
        """策略核心逻辑"""
        if self.order:
            return

        current_above_sma = self.data.close[0] > self.sma[0]

        if self.position:
            # === 持仓中：检查卖出条件 ===
            if self.buy_price and self.buy_price > 0:
                current_pct = (self.data.close[0] / self.buy_price) - 1

                # 止损：亏损超过 5%
                if current_pct <= -self.params.stop_loss_pct:
                    self.log(f"⛔ 触发止损! 亏损: {current_pct*100:.1f}%")
                    self.order = self.sell(size=abs(self.position.size))
                    return

                # 止盈：盈利超过 15%
                if current_pct >= self.params.take_profit_pct:
                    self.log(f"🎯 触发止盈! 盈利: {current_pct*100:.1f}%")
                    self.order = self.sell(size=abs(self.position.size))
                    return

            # 跌破均线卖出
            if not current_above_sma:
                self.log(f"📉 跌破 {self.params.sma_period} 日均线，卖出")
                self.order = self.sell(size=abs(self.position.size))
                return

            # MACD 死叉卖出
            if self.macd_crossover < 0:
                self.log(f"📉 MACD 死叉，卖出")
                self.order = self.sell(size=abs(self.position.size))
                return

        else:
            # === 空仓中：检查买入条件 ===
            # 三重确认：突破均线 + MACD 金叉 + 放量
            price_breakout = current_above_sma and self.was_below_sma
            macd_golden_cross = self.macd_crossover > 0
            volume_confirmed = self.data.volume[0] > self.volume_ma[0] * self.params.volume_ratio

            # 条件 1：价格突破均线 + 放量（最常见的入场信号）
            if price_breakout and volume_confirmed:
                available_cash = self.broker.getcash()
                cost = self.data.close[0] * self.params.trade_size
                if available_cash >= cost:
                    self.log(f"📈 突破 {self.params.sma_period} 日均线 + 放量，买入")
                    self.order = self.buy(size=self.params.trade_size)

            # 条件 2：MACD 金叉 + 价格在均线上方 + 放量
            elif macd_golden_cross and current_above_sma and volume_confirmed:
                available_cash = self.broker.getcash()
                cost = self.data.close[0] * self.params.trade_size
                if available_cash >= cost:
                    self.log(f"📈 MACD 金叉 + 均线上方 + 放量，买入")
                    self.order = self.buy(size=self.params.trade_size)

        # 记录当前是否在均线下方（供下一根 K 线判断突破用）
        self.was_below_sma = not current_above_sma
