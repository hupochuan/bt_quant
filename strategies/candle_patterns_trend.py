"""
阴阳线策略模块 - 带趋势过滤的日内做T版

与原策略区别：
- 增加20日均线趋势过滤
- 下跌趋势（价格<MA20）：只反T（先卖后买）
- 上涨趋势（价格>MA20）：只正T（先买后卖）
"""
import backtrader as bt
import config


class CandlePatternTrendStrategy(bt.Strategy):
    """
    阴阳线策略 - 带趋势过滤的日内做T版

    规则：
    1. 每天最多一次做T交易
    2. 趋势过滤：
       - 价格 < MA20（下跌趋势）：只反T（先卖后买）
       - 价格 > MA20（上涨趋势）：只正T（先买后卖）
    3. 开仓后等不到信号，3小时后强制平仓
    4. 不持仓过夜

    价格取值逻辑（方案1）：
    - 开仓价：信号确认K线的收盘价（如连续2根阴线，用第2根收盘价开仓）
    - 平仓价：平仓信号K线的收盘价
    - 即：信号出现时立即以当前K线收盘价成交，不等待下一根K线开盘价
    """

    def stop(self):
        """回测结束时打印交易明细"""
        if not self.trade_records:
            print("\n" + "="*100)
            print("交易明细记录")
            print("="*100)
            print("无交易记录")
            print("="*100)
            return

        print("\n" + "="*100)
        print("交易明细记录")
        print("="*100)
        print(f"{'日期':<12} {'类型':<6} {'开仓时间':<10} {'开仓动作':<8} {'开仓价':>10} {'平仓时间':<10} {'平仓动作':<8} {'平仓价':>10} {'股数':>8} {'平仓原因':<10} {'毛盈亏':>12} {'手续费':>10} {'净盈亏':>12}")
        print("-"*100)

        total_gross = 0
        total_commission = 0
        total_net = 0

        for tr in self.trade_records:
            close_reason = tr.get('close_reason') or '未知'
            print(f"{tr['date']:<12} {tr['type']:<6} {tr['entry_time']:<10} {tr['entry_action']:<8} ${tr['entry_price']:>8.2f} {tr['exit_time']:<10} {tr['exit_action']:<8} ${tr['exit_price']:>8.2f} {tr['size']:>8} {close_reason:<10} ${tr['gross_pnl']:>10.2f} ${tr['commission']:>8.2f} ${tr['net_pnl']:>10.2f}")
            total_gross += tr['gross_pnl']
            total_commission += tr['commission']
            total_net += tr['net_pnl']

        print("-"*100)
        print(f"{'合计':<12} {'':<6} {'':<10} {'':<8} {'':>10} {'':<10} {'':<8} {'':>10} {'':>8} {'':<10} ${total_gross:>10.2f} ${total_commission:>8.2f} ${total_net:>10.2f}")
        print("="*100)

    params = (
        ("consecutive_count", config.CANDLE_TREND_PARAMS["consecutive_count"]),
        ("trade_size", config.CANDLE_TREND_PARAMS["trade_size"]),
        ("stop_loss_amount", config.CANDLE_TREND_PARAMS["stop_loss_amount"]),
        ("commission_fixed", config.CANDLE_TREND_PARAMS["commission_fixed"]),
        ("trend_ma_period", config.CANDLE_TREND_PARAMS["trend_ma_period"]),
        ("initial_position", config.CANDLE_TREND_PARAMS.get("initial_position", 100)),  # 做T底仓
    )

    def __init__(self):
        self.order = None
        self.buy_price = None
        self.sell_price = None
        self.trade_count = 0
        self.daily_trade_done = False  # 当日是否已完成做T
        self.daily_trade_type = None   # 'long'=先买后卖, 'short'=先卖后买
        self.current_date = None
        self.daily_bar_count = 0  # 当天已处理的bar数量
        self.daily_first_bar_idx = None  # 当天第一根bar在总数据中的索引
        self._base_position_set = False  # 底仓是否已建立

        # 详细交易记录
        self.trade_records = []  # 存储每笔完整做T交易的明细
        self.current_trade = None  # 当前进行中的交易

        # 趋势指标：20日均线
        self.sma20 = bt.indicators.SimpleMovingAverage(self.data.close, period=self.params.trend_ma_period)

        # 打印策略配置
        print(f"\n{'='*60}")
        print(f"策略配置: 阴阳线趋势过滤策略")
        print(f"  连续K线数量: {self.params.consecutive_count}")
        print(f"  每次交易股数: {self.params.trade_size}")
        print(f"  止损金额: ${self.params.stop_loss_amount}")
        print(f"  每笔手续费: ${self.params.commission_fixed}")
        print(f"  初始底仓: {self.params.initial_position} 股 (用于做T)")
        print(f"  趋势过滤: {self.params.trend_ma_period}日均线")
        print(f"    - 下跌趋势（价格<MA20）：只反T（先卖后买）")
        print(f"    - 上涨趋势（价格>MA20）：只正T（先买后卖）")
        print(f"{'='*60}\n")

    def log(self, message):
        """日志函数"""
        datetime_str = self.datas[0].datetime.datetime(0).strftime("%Y-%m-%d %H:%M")
        print(f"  [{datetime_str}] {message}")

    def _get_ny_time_str(self, dt=None):
        """将UTC时间转换为美东时间字符串 HH:MM"""
        from datetime import timedelta
        if dt is None:
            dt = self.datas[0].datetime.datetime(0)
        # UTC 转美东 (UTC-4)
        ny_dt = dt - timedelta(hours=4)
        return ny_dt.strftime("%H:%M")

    def _get_trend_direction(self):
        """获取当前趋势方向

        Returns:
            'uptrend': 上涨趋势（价格 > MA20）
            'downtrend': 下跌趋势（价格 < MA20）
            'neutral': 中性（价格 ≈ MA20）
        """
        current_price = self.data.close[0]
        ma_value = self.sma20[0]

        # 使用0.1%的容差避免频繁切换
        tolerance = ma_value * 0.001

        if current_price > ma_value + tolerance:
            return 'uptrend'
        elif current_price < ma_value - tolerance:
            return 'downtrend'
        else:
            return 'neutral'

    def notify_order(self, order):
        """订单通知"""
        if order.status in [order.Completed]:
            dt = self.datas[0].datetime.datetime(0)
            if order.isbuy():
                self.buy_price = order.executed.price
                self.log(f"买入: ${order.executed.price:.2f}, 数量: {order.executed.size:.0f}")
                # 判断是开仓还是平仓
                if self.current_trade and self.current_trade['type'] == '反T':
                    # 反T的第二笔：买入平仓
                    self.current_trade['exit_time'] = self._get_ny_time_str(dt)
                    self.current_trade['exit_price'] = order.executed.price
                    self.current_trade['exit_action'] = '买入'
                    self._finalize_trade_record()
                # 正T的第一笔买入已在next()中创建current_trade，这里不处理
            else:
                self.sell_price = order.executed.price
                profit = 0
                if self.daily_trade_type == 'long' and self.buy_price:
                    profit = (order.executed.price - self.buy_price) * order.executed.size - self.params.commission_fixed * 2
                elif self.daily_trade_type == 'short' and self.sell_price:
                    profit = (self.sell_price - order.executed.price) * order.executed.size - self.params.commission_fixed * 2
                self.log(f"卖出: ${order.executed.price:.2f}, 盈亏: ${profit:.2f}")
                # 判断是开仓还是平仓
                if self.current_trade and self.current_trade['type'] == '正T':
                    # 正T的第二笔：卖出平仓
                    self.current_trade['exit_time'] = self._get_ny_time_str(dt)
                    self.current_trade['exit_price'] = order.executed.price
                    self.current_trade['exit_action'] = '卖出'
                    self._finalize_trade_record()
                # 反T的第一笔卖出已在next()中创建current_trade，这里不处理
            self.trade_count += 1
        self.order = None

    def _finalize_trade_record(self):
        """完成交易记录并保存"""
        if not self.current_trade:
            return

        tr = self.current_trade
        # 确保有平仓信息
        if tr['exit_price'] is None:
            return

        # 计算盈亏
        if tr['type'] == '正T':
            # 先买后卖
            gross_pnl = (tr['exit_price'] - tr['entry_price']) * tr['size']
        else:  # 反T
            # 先卖后买
            gross_pnl = (tr['entry_price'] - tr['exit_price']) * tr['size']

        net_pnl = gross_pnl - self.params.commission_fixed * 2
        tr['gross_pnl'] = gross_pnl
        tr['commission'] = self.params.commission_fixed * 2
        tr['net_pnl'] = net_pnl

        self.trade_records.append(tr.copy())
        self.current_trade = None

    def _is_bullish(self, bars_ago=0):
        """判断某根 K 线是否为阳线"""
        return self.data.close[bars_ago] > self.data.open[bars_ago]

    def _is_bearish(self, bars_ago=0):
        """判断某根 K 线是否为阴线"""
        return self.data.close[bars_ago] < self.data.open[bars_ago]

    def _check_consecutive_bullish(self):
        """检查是否连续 N 根阳线（包含当前K线）

        真实交易逻辑：
        - 当前K线刚收盘时检查
        - 检查当前K线(索引0)和前N-1根K线
        """
        # 使用当天bar计数来判断
        if self.daily_bar_count < self.params.consecutive_count:
            return False

        # 将负数索引转换为绝对索引，确保只检查当天的bars
        current_idx = len(self.data)

        for i in range(self.params.consecutive_count):
            bar_idx = current_idx - i
            # 确保这根bar是当天的（索引 >= 当天第一根bar的索引）
            if bar_idx < self.daily_first_bar_idx:
                return False  # 跨天了
            if not self._is_bullish(-i):  # 检查 0, -1, -2...（当前K线+前N-1根）
                return False
        return True

    def _check_consecutive_bearish(self):
        """检查是否连续 N 根阴线（包含当前K线）

        真实交易逻辑：
        - 当前K线刚收盘时检查
        - 检查当前K线(索引0)和前N-1根K线
        """
        # 使用当天bar计数来判断
        if self.daily_bar_count < self.params.consecutive_count:
            return False

        # 将负数索引转换为绝对索引，确保只检查当天的bars
        current_idx = len(self.data)

        for i in range(self.params.consecutive_count):
            bar_idx = current_idx - i
            # 确保这根bar是当天的（索引 >= 当天第一根bar的索引）
            if bar_idx < self.daily_first_bar_idx:
                return False  # 跨天了
            if not self._is_bearish(-i):  # 检查 0, -1, -2...（当前K线+前N-1根）
                return False
        return True

    def _get_current_time(self):
        """获取当前时间"""
        return self.datas[0].datetime.time(0)

    def _get_current_date(self):
        """获取当前日期"""
        return self.datas[0].datetime.date(0)

    def _is_after_3h(self):
        """检查是否已过开仓3小时（强制平仓）。

        数据时间戳为UTC：
        - 10:30 EDT = UTC 14:30 可开仓
        - 3小时后 13:30 EDT = UTC 17:30 强制平仓
        """
        # 记录开仓时间，3小时后强制平仓
        if not hasattr(self, 'entry_time'):
            return False
        if self.entry_time is None:
            return False

        current_time = self._get_current_time()
        # 将时间转为分钟数比较
        current_minutes = current_time.hour * 60 + current_time.minute
        entry_minutes = self.entry_time.hour * 60 + self.entry_time.minute

        return (current_minutes - entry_minutes) >= 180  # 3小时 = 180分钟

    def _is_near_market_close(self):
        """检查是否接近收盘（15:30 EDT = UTC 19:30，不再开新仓）"""
        current_time = self._get_current_time()
        return current_time.hour > 19 or (current_time.hour == 19 and current_time.minute >= 30)

    def _is_within_first_60min(self):
        """检查是否在开盘后60分钟内（09:30-10:30 EDT = UTC 13:30-14:30）"""
        current_time = self._get_current_time()
        # UTC 13:30 = 美东 09:30 开盘
        # UTC 14:30 = 美东 10:30，60分钟结束
        return current_time.hour < 14 or (current_time.hour == 14 and current_time.minute < 30)

    def next(self):
        """策略核心逻辑"""
        if self.order:
            return

        # 初始化底仓（仅第一个bar执行一次）
        if not self._base_position_set and self.params.initial_position > 0:
            self.log(f"建立底仓: 以 ${self.data.open[0]:.2f} 买入 {self.params.initial_position} 股")
            self.order = self.buy(size=self.params.initial_position)
            self._base_position_set = True
            return

        current_date = self._get_current_date()
        current_time = self._get_current_time()

        # 新的一天，重置状态
        if self.current_date != current_date:
            self.current_date = current_date
            self.daily_trade_done = False
            self.daily_trade_type = None
            self.buy_price = None
            self.sell_price = None
            self.entry_time = None  # 重置开仓时间
            self.daily_bar_count = 0  # 重置当天bar计数
            self.daily_first_bar_idx = len(self.data)  # 记录当天第一根bar的索引
            self.log(f"新的一天开始: {current_date} (bar idx: {self.daily_first_bar_idx})")
            # 注意：这里不return，继续执行以处理第一根bar

        # 增加当天bar计数
        self.daily_bar_count += 1

        # 如果当日已完成做T，不再交易
        if self.daily_trade_done:
            return

        current_position = abs(self.position.size) if self.position else 0

        # 情况1：已开仓（先买后卖），等待卖出信号或强制平仓
        if self.daily_trade_type == 'long' and current_position > 0:
            # 检查是否触发止损
            if self.buy_price:
                current_loss = (self.buy_price - self.data.close[0]) * current_position
                if current_loss >= self.params.stop_loss_amount:
                    self.log(f"触发止损! 买入价: ${self.buy_price:.2f}, 当前价: ${self.data.close[0]:.2f}")
                    if self.current_trade:
                        self.current_trade['close_reason'] = '止损'
                    self.order = self.sell(size=current_position)
                    self.daily_trade_done = True
                    return

            # 检查卖出信号（连续阴线）或强制平仓时间
            if self._check_consecutive_bearish() or self._is_after_3h():
                if self._is_after_3h() and not self._check_consecutive_bearish():
                    self.log(f"强制平仓时间到，卖出 {current_position} 股")
                    if self.current_trade:
                        self.current_trade['close_reason'] = '强制平仓'
                else:
                    self.log(f"卖出信号: 连续{self.params.consecutive_count}根阴线")
                    if self.current_trade:
                        self.current_trade['close_reason'] = '信号平仓'
                self.order = self.sell(size=current_position)
                self.daily_trade_done = True
            return

        # 情况2：已开仓（先卖后买），等待买入信号或强制平仓
        if self.daily_trade_type == 'short' and current_position > 0:
            # 检查买入信号（连续阳线）或强制平仓时间
            if self._check_consecutive_bullish() or self._is_after_3h():
                if self._is_after_3h() and not self._check_consecutive_bullish():
                    self.log(f"强制平仓时间到，买入 {current_position} 股")
                    if self.current_trade:
                        self.current_trade['close_reason'] = '强制平仓'
                else:
                    self.log(f"买入信号: 连续{self.params.consecutive_count}根阳线")
                    if self.current_trade:
                        self.current_trade['close_reason'] = '信号平仓'
                self.order = self.buy(size=current_position)
                self.daily_trade_done = True
            return

        # 情况3：未开仓，寻找开仓信号
        # 开盘后60分钟内不交易
        if self._is_within_first_60min():
            return

        # 接近收盘不再开新仓
        if self._is_near_market_close():
            return

        # 获取当前趋势方向
        trend = self._get_trend_direction()
        current_price = self.data.close[0]
        ma_value = self.sma20[0]

        # 反T信号：连续阴线，先卖出（做空T）- 只在下跌趋势中
        if self._check_consecutive_bearish():
            if trend == 'downtrend':
                available_cash = self.broker.getcash()
                # 检查是否有足够资金买回
                cost = self.data.close[0] * self.params.trade_size
                if available_cash >= cost:
                    self.log(f"反T开仓信号: 连续{self.params.consecutive_count}根阴线，趋势下跌(价格${current_price:.2f}<MA20${ma_value:.2f})，先卖出 {self.params.trade_size} 股")
                    self.daily_trade_type = 'short'
                    # 记录开仓时间（UTC，用于3小时强制平仓）
                    self.entry_time = self._get_current_time()
                    # 创建新的交易记录
                    dt = self.datas[0].datetime.datetime(0)
                    self.current_trade = {
                        'date': dt.strftime("%Y-%m-%d"),
                        'type': '反T',
                        'entry_time': self._get_ny_time_str(dt),
                        'entry_price': self.data.close[0],
                        'entry_action': '卖出',
                        'size': self.params.trade_size,
                        'exit_time': None,
                        'exit_price': None,
                        'exit_action': None,
                        'close_reason': None,
                    }
                    self.order = self.sell(size=self.params.trade_size)
                return
            elif trend == 'uptrend':
                self.log(f"反T信号被过滤: 连续{self.params.consecutive_count}根阴线，但趋势上涨(价格${current_price:.2f}>MA20${ma_value:.2f})，不开仓")
            else:
                self.log(f"反T信号被过滤: 连续{self.params.consecutive_count}根阴线，但趋势中性，不开仓")
            return

        # 正T信号：连续阳线，先买入 - 只在上涨趋势中
        if self._check_consecutive_bullish():
            if trend == 'uptrend':
                available_cash = self.broker.getcash()
                cost = self.data.close[0] * self.params.trade_size
                if available_cash >= cost:
                    self.log(f"正T开仓信号: 连续{self.params.consecutive_count}根阳线，趋势上涨(价格${current_price:.2f}>MA20${ma_value:.2f})，先买入 {self.params.trade_size} 股")
                    self.daily_trade_type = 'long'
                    # 记录开仓时间（UTC，用于3小时强制平仓）
                    self.entry_time = self._get_current_time()
                    # 创建新的交易记录
                    dt = self.datas[0].datetime.datetime(0)
                    self.current_trade = {
                        'date': dt.strftime("%Y-%m-%d"),
                        'type': '正T',
                        'entry_time': self._get_ny_time_str(dt),
                        'entry_price': self.data.close[0],
                        'entry_action': '买入',
                        'size': self.params.trade_size,
                        'exit_time': None,
                        'exit_price': None,
                        'exit_action': None,
                        'close_reason': None,
                    }
                    self.order = self.buy(size=self.params.trade_size)
                return
            elif trend == 'downtrend':
                self.log(f"正T信号被过滤: 连续{self.params.consecutive_count}根阳线，但趋势下跌(价格${current_price:.2f}<MA20${ma_value:.2f})，不开仓")
            else:
                self.log(f"正T信号被过滤: 连续{self.params.consecutive_count}根阳线，但趋势中性，不开仓")
            return
