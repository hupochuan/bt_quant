"""
阴阳线策略模块 - 日内做T版
"""
import backtrader as bt
import config


class CandlePatternStrategy(bt.Strategy):
    """
    阴阳线策略 - 日内做T版
    
    规则：
    1. 每天最多一次做T交易
    2. 三种情况：先买后卖 / 先卖后买 / 无交易
    3. 开仓后等不到信号，收盘前3小时强制平仓
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
        ("consecutive_count", config.CANDLE_PATTERN_PARAMS["consecutive_count"]),
        ("trade_size", config.CANDLE_PATTERN_PARAMS["trade_size"]),
        ("stop_loss_amount", config.CANDLE_PATTERN_PARAMS["stop_loss_amount"]),
        ("commission_fixed", config.CANDLE_PATTERN_PARAMS["commission_fixed"]),
        ("initial_position", config.CANDLE_PATTERN_PARAMS.get("initial_position", 100)),  # 做T底仓
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

        # 打印策略配置
        print(f"\n{'='*60}")
        print(f"策略配置:")
        print(f"  连续K线数量: {self.params.consecutive_count}")
        print(f"  每次交易股数: {self.params.trade_size}")
        print(f"  止损金额: ${self.params.stop_loss_amount}")
        print(f"  每笔手续费: ${self.params.commission_fixed}")
        print(f"  初始底仓: {self.params.initial_position} 股 (用于做T)")
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
        # 原策略无趋势过滤，始终返回neutral
        return 'neutral'

    def notify_order(self, order):
        """订单通知"""
        if order.status in [order.Completed]:
            dt = self.datas[0].datetime.datetime(0)
            if order.isbuy():
                self.buy_price = order.executed.price
                self.log(f"🟢 买入: ${order.executed.price:.2f}, 数量: {order.executed.size:.0f}")
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
                emoji = "🔴" if profit < 0 else "🟢"
                self.log(f"{emoji} 卖出: ${order.executed.price:.2f}, 盈亏: ${profit:.2f}")
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
        if self.daily_bar_count < self.params.consecutive_count:
            return False
        
        current_idx = len(self.data)
        
        for i in range(self.params.consecutive_count):
            bar_idx = current_idx - i
            if bar_idx < self.daily_first_bar_idx:
                return False
            if not self._is_bullish(-i):  # 检查 0, -1, -2...
                return False
        return True

    def _check_consecutive_bearish(self):
        """检查是否连续 N 根阴线（包含当前K线）
        
        真实交易逻辑：
        - 当前K线刚收盘时检查
        - 检查当前K线(索引0)和前N-1根K线
        """
        if self.daily_bar_count < self.params.consecutive_count:
            return False
        
        current_idx = len(self.data)
        
        for i in range(self.params.consecutive_count):
            bar_idx = current_idx - i
            if bar_idx < self.daily_first_bar_idx:
                return False
            if not self._is_bearish(-i):  # 检查 0, -1, -2...
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
            self.log(f"🏦 建立底仓: 以 ${self.data.open[0]:.2f} 买入 {self.params.initial_position} 股")
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
            self.log(f"📅 新的一天开始: {current_date} (bar idx: {self.daily_first_bar_idx})")
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
                    self.log(f"⛔ 触发止损! 买入价: ${self.buy_price:.2f}, 当前价: ${self.data.close[0]:.2f}")
                    if self.current_trade:
                        self.current_trade['close_reason'] = '止损'
                    self.order = self.sell(size=current_position)
                    self.daily_trade_done = True
                    return

            # 检查卖出信号（连续阴线）或强制平仓时间
            if self._check_consecutive_bearish() or self._is_after_3h():
                if self._is_after_3h() and not self._check_consecutive_bearish():
                    self.log(f"⏰ 强制平仓时间到，卖出 {current_position} 股")
                    if self.current_trade:
                        self.current_trade['close_reason'] = '强制平仓'
                else:
                    self.log(f"📉 卖出信号: 连续{self.params.consecutive_count}根阴线")
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
                    self.log(f"⏰ 强制平仓时间到，买入 {current_position} 股")
                    if self.current_trade:
                        self.current_trade['close_reason'] = '强制平仓'
                else:
                    self.log(f"📈 买入信号: 连续{self.params.consecutive_count}根阳线")
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

        # 反T信号：连续阴线，先卖出（做空T）
        if self._check_consecutive_bearish():
            available_cash = self.broker.getcash()
            # 检查是否有足够资金买回
            cost = self.data.close[0] * self.params.trade_size
            if available_cash >= cost:
                self.log(f"📉 反T开仓信号: 连续{self.params.consecutive_count}根阴线，先卖出 {self.params.trade_size} 股")
                self.daily_trade_type = 'short'
                # 记录开仓时间（UTC，用于4小时强制平仓）
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

        # 正T信号：连续阳线，先买入
        if self._check_consecutive_bullish():
            available_cash = self.broker.getcash()
            cost = self.data.close[0] * self.params.trade_size
            if available_cash >= cost:
                self.log(f"📈 正T开仓信号: 连续{self.params.consecutive_count}根阳线，先买入 {self.params.trade_size} 股")
                self.daily_trade_type = 'long'
                # 记录开仓时间（UTC，用于4小时强制平仓）
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


class EnhancedCandleStrategy(bt.Strategy):
    """占位符 - 增强版阴阳线策略"""
    params = (
        ("consecutive_count", 3),
        ("trade_size", 100),
        ("stop_loss_amount", 200.0),
        ("commission_fixed", 5.0),
    )
    def __init__(self):
        pass
    def next(self):
        pass


class DailyBreakoutStrategy(bt.Strategy):
    """占位符 - 日线突破策略"""
    params = (
        ("sma_period", 20),
        ("trade_size", 100),
        ("commission_fixed", 5.0),
    )
    def __init__(self):
        pass
    def next(self):
        pass


class CandlePatternWithProfitTarget(bt.Strategy):
    """
    阴阳线策略 - 带固定金额止盈版

    规则：
    1. 开仓条件与原策略相同（连续N根阳线/阴线）
    2. 平仓条件增加：盈利达到50美元时止盈
    3. 其他平仓条件保留：止损、信号平仓、强制平仓
    4. 不持仓过夜

    价格取值逻辑：
    - 信号价：信号确认K线的收盘价（如连续2根阴线，第2根收盘价）
    - 成交价：下一根K线开盘价（Backtrader自动执行）
    - 报告中同时显示信号价和实际成交价
    """
    
    params = (
        ("consecutive_count", config.CANDLE_PATTERN_PARAMS["consecutive_count"]),
        ("trade_size", config.CANDLE_PATTERN_PARAMS["trade_size"]),
        ("stop_loss_amount", config.CANDLE_PATTERN_PARAMS["stop_loss_amount"]),
        ("take_profit_amount", 50.0),  # 新增：止盈金额50美元
        ("commission_fixed", config.CANDLE_PATTERN_PARAMS["commission_fixed"]),
        ("initial_position", config.CANDLE_PATTERN_PARAMS.get("initial_position", 100)),  # 做T底仓
    )

    def __init__(self):
        self.order = None
        self.buy_price = None
        self.sell_price = None
        self.trade_count = 0
        self.daily_trade_done = False
        self.daily_trade_type = None
        self.current_date = None
        self.daily_bar_count = 0
        self.daily_first_bar_idx = None
        self.entry_time = None
        self._base_position_set = False  # 底仓是否已建立
        
        # 交易记录
        self.trade_records = []
        self.current_trade = None
        
        # 打印策略配置
        self._print_config()

    def _print_config(self):
        """打印策略配置"""
        print("\n" + "="*70)
        print("策略配置: 阴阳线策略 - 带固定金额止盈版")
        print("="*70)
        print(f"  连续K线数量:     {self.params.consecutive_count}")
        print(f"  每次交易股数:    {self.params.trade_size}")
        print(f"  止损金额:        ${self.params.stop_loss_amount:.2f}")
        print(f"  止盈金额:        ${self.params.take_profit_amount:.2f} (新增50美元止盈)")
        print(f"  每笔手续费:      ${self.params.commission_fixed:.2f}")
        print(f"  初始底仓:        {self.params.initial_position} 股 (用于做T)")
        print("="*70)

    def stop(self):
        """回测结束时打印详细报告"""
        self._print_final_report()

    def _print_final_report(self):
        """打印最终回测报告"""
        print("\n" + "="*100)
        print("回测详细报告 - 阴阳线策略（带50美元止盈）")
        print("="*100)
        
        # 1. 初始参数
        print("\n【一、初始参数】")
        print("-"*100)
        print(f"  策略名称:        阴阳线策略 - 带固定金额止盈版")
        print(f"  连续K线数量:     {self.params.consecutive_count} 根")
        print(f"  每次交易股数:    {self.params.trade_size} 股")
        print(f"  止损金额:        ${self.params.stop_loss_amount:.2f}")
        print(f"  止盈金额:        ${self.params.take_profit_amount:.2f}")
        print(f"  每笔手续费:      ${self.params.commission_fixed:.2f}")
        print(f"  总手续费/笔交易: ${self.params.commission_fixed * 2:.2f} (开仓+平仓)")
        print(f"  开盘不交易时段:  开盘后60分钟内 (09:30-10:30 美东时间)")
        print("-"*100)
        print("  价格取值逻辑：")
        print("    - 信号价：信号确认K线的收盘价（如连续2根阴线，第2根收盘价）")
        print("    - 成交价：实际成交价格（下一根K线开盘价，由Backtrader自动执行）")
        print("    - 报告中的开仓价/平仓价均为实际成交价")
        
        # 2. 交易明细
        print("\n【二、交易明细】")
        print("-"*140)
        
        if not self.trade_records:
            print("无交易记录")
        else:
            # 表头 - 区分信号价和成交价
            header = (f"{'序号':<4} {'日期':<12} {'类型':<6} {'开仓时间(ET)':<14} {'开仓动作':<8} "
                     f"{'信号价':>10} {'成交价':>10} {'平仓时间(ET)':<14} {'平仓动作':<8} {'平仓价':>10} "
                     f"{'股数':>6} {'平仓原因':<10} {'毛盈亏':>10} {'手续费':>8} {'净盈亏':>10}")
            print(header)
            print("-"*140)
            
            total_gross = 0
            total_commission = 0
            total_net = 0
            
            for idx, tr in enumerate(self.trade_records, 1):
                signal_price = tr.get('signal_price', tr['entry_price'])
                print(f"{idx:<4} {tr['date']:<12} {tr['type']:<6} {tr['entry_time']:<14} {tr['entry_action']:<8} "
                      f"${signal_price:>8.2f} ${tr['entry_price']:>8.2f} {tr['exit_time']:<14} {tr['exit_action']:<8} "
                      f"${tr['exit_price']:>8.2f} {tr['size']:>6} {tr['close_reason']:<10} "
                      f"${tr['gross_pnl']:>8.2f} ${tr['commission']:>6.2f} ${tr['net_pnl']:>8.2f}")
                total_gross += tr['gross_pnl']
                total_commission += tr['commission']
                total_net += tr['net_pnl']
            
            print("-"*140)
            print(f"{'合计':<4} {'':<12} {'':<6} {'':<14} {'':<8} {'':>10} {'':>10} {'':<14} {'':<8} "
                  f"{'':>10} {'':>6} {'':<10} ${total_gross:>8.2f} ${total_commission:>6.2f} ${total_net:>8.2f}")
        
        # 3. 最终输出
        print("\n【三、最终输出】")
        print("-"*100)
        
        final_value = self.broker.getvalue()
        initial_cash = config.CANDLE_PATTERN_PARAMS.get("initial_cash", 30000.0)
        total_return = (final_value / initial_cash - 1) * 100 if initial_cash > 0 else 0
        
        # 统计各类型平仓次数
        stop_loss_count = sum(1 for tr in self.trade_records if tr['close_reason'] == '止损')
        take_profit_count = sum(1 for tr in self.trade_records if tr['close_reason'] == '止盈')
        signal_count = sum(1 for tr in self.trade_records if tr['close_reason'] == '信号平仓')
        force_close_count = sum(1 for tr in self.trade_records if tr['close_reason'] == '强制平仓')
        
        # 统计盈亏
        winning_trades = [tr for tr in self.trade_records if tr['net_pnl'] > 0]
        losing_trades = [tr for tr in self.trade_records if tr['net_pnl'] <= 0]
        
        total_trades = len(self.trade_records)
        win_count = len(winning_trades)
        loss_count = len(losing_trades)
        win_rate = (win_count / total_trades * 100) if total_trades > 0 else 0
        
        total_gross = sum(tr['gross_pnl'] for tr in self.trade_records)
        total_commission = sum(tr['commission'] for tr in self.trade_records)
        total_net = sum(tr['net_pnl'] for tr in self.trade_records)
        
        avg_gross = total_gross / total_trades if total_trades > 0 else 0
        avg_net = total_net / total_trades if total_trades > 0 else 0
        
        won_pnl = sum(tr['net_pnl'] for tr in winning_trades)
        lost_pnl = sum(tr['net_pnl'] for tr in losing_trades)
        avg_won = won_pnl / win_count if win_count > 0 else 0
        avg_lost = lost_pnl / loss_count if loss_count > 0 else 0
        profit_factor = abs(won_pnl / lost_pnl) if lost_pnl != 0 else float('inf')
        
        print(f"  初始资金:        ${initial_cash:,.2f}")
        print(f"  最终资金:        ${final_value:,.2f}")
        print(f"  总收益率:        {total_return:+.2f}%")
        print(f"  总盈亏(净):      ${total_net:+,.2f}")
        print()
        print(f"  总交易次数:      {total_trades} 笔")
        print(f"  盈利次数:        {win_count} 笔 ({win_rate:.1f}%)")
        print(f"  亏损次数:        {loss_count} 笔 ({100-win_rate:.1f}%)")
        print()
        print(f"  止盈触发次数:    {take_profit_count} 笔")
        print(f"  止损触发次数:    {stop_loss_count} 笔")
        print(f"  信号平仓次数:    {signal_count} 笔")
        print(f"  强制平仓次数:    {force_close_count} 笔")
        print()
        print(f"  平均每笔毛盈亏:  ${avg_gross:,.2f}")
        print(f"  平均每笔净盈亏:  ${avg_net:,.2f}")
        print(f"  平均盈利:        ${avg_won:,.2f}")
        print(f"  平均亏损:        ${avg_lost:,.2f}")
        print(f"  盈亏比:          {profit_factor:.2f}")
        print(f"  总手续费:        ${total_commission:,.2f}")
        
        # 4. 总结
        print("\n【四、总结】")
        print("-"*100)
        
        if total_trades == 0:
            print("  本次回测期间未产生任何交易信号。")
        else:
            profit_emoji = "🎉" if total_net > 0 else "😢"
            print(f"  {profit_emoji} 策略在回测期间共执行 {total_trades} 笔交易，")
            print(f"     其中 {win_count} 笔盈利，{loss_count} 笔亏损，胜率 {win_rate:.1f}%。")
            print(f"     净盈亏为 ${total_net:+,.2f}，总收益率 {total_return:+.2f}%。")
            print()
            print(f"  止盈机制触发 {take_profit_count} 次，止损机制触发 {stop_loss_count} 次。")
            if take_profit_count > 0 or stop_loss_count > 0:
                print(f"     止盈/止损比为 {take_profit_count}:{stop_loss_count}，", end="")
                if take_profit_count >= stop_loss_count:
                    print("止盈次数大于等于止损次数，风控效果良好。")
                else:
                    print("止损次数多于止盈次数，建议优化开仓条件。")
            print()
            if total_net > 0:
                print(f"  策略整体盈利，但需扣除 ${total_commission:,.2f} 手续费。")
                print(f"     扣除手续费后净收益率为 {total_return:+.2f}%。")
            else:
                print(f"  策略整体亏损 ${abs(total_net):,.2f}，建议调整参数或更换标的。")
        
        print("="*100)

    def log(self, message):
        """日志函数"""
        datetime_str = self.datas[0].datetime.datetime(0).strftime("%Y-%m-%d %H:%M")
        print(f"  [{datetime_str}] {message}")

    def _get_ny_time_str(self, dt=None):
        """将UTC时间转换为美东时间字符串 HH:MM"""
        from datetime import timedelta
        if dt is None:
            dt = self.datas[0].datetime.datetime(0)
        ny_dt = dt - timedelta(hours=4)
        return ny_dt.strftime("%H:%M")

    def notify_order(self, order):
        """订单通知 - 记录实际成交价"""
        if order.status in [order.Completed]:
            dt = self.datas[0].datetime.datetime(0)
            if order.isbuy():
                self.buy_price = order.executed.price
                self.log(f"🟢 买入: ${order.executed.price:.2f}, 数量: {order.executed.size:.0f}")
                if self.current_trade and self.current_trade['type'] == '反T':
                    # 反T平仓：买入
                    self.current_trade['exit_time'] = self._get_ny_time_str(dt)
                    self.current_trade['exit_price'] = order.executed.price  # 实际成交价
                    self.current_trade['exit_action'] = '买入'
                    self._finalize_trade_record()
                elif self.current_trade and self.current_trade['type'] == '正T':
                    # 正T开仓：买入 - 更新实际成交价
                    self.current_trade['entry_price'] = order.executed.price  # 实际成交价
            else:
                self.sell_price = order.executed.price
                profit = 0
                if self.daily_trade_type == 'long' and self.buy_price:
                    profit = (order.executed.price - self.buy_price) * order.executed.size - self.params.commission_fixed * 2
                elif self.daily_trade_type == 'short' and self.sell_price:
                    profit = (self.sell_price - order.executed.price) * order.executed.size - self.params.commission_fixed * 2
                emoji = "🔴" if profit < 0 else "🟢"
                self.log(f"{emoji} 卖出: ${order.executed.price:.2f}, 盈亏: ${profit:.2f}")
                if self.current_trade and self.current_trade['type'] == '正T':
                    # 正T平仓：卖出
                    self.current_trade['exit_time'] = self._get_ny_time_str(dt)
                    self.current_trade['exit_price'] = order.executed.price  # 实际成交价
                    self.current_trade['exit_action'] = '卖出'
                    self._finalize_trade_record()
                elif self.current_trade and self.current_trade['type'] == '反T':
                    # 反T开仓：卖出 - 更新实际成交价
                    self.current_trade['entry_price'] = order.executed.price  # 实际成交价
            self.trade_count += 1
        self.order = None

    def _finalize_trade_record(self):
        """完成交易记录并保存"""
        if not self.current_trade:
            return
        
        tr = self.current_trade
        if tr['exit_price'] is None:
            return
            
        if tr['type'] == '正T':
            gross_pnl = (tr['exit_price'] - tr['entry_price']) * tr['size']
        else:  # 反T
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
        - 例如N=2：检查当前K线+上一根K线
        """
        if self.daily_bar_count < self.params.consecutive_count:
            return False
        
        current_idx = len(self.data)
        
        for i in range(self.params.consecutive_count):
            bar_idx = current_idx - i
            if bar_idx < self.daily_first_bar_idx:
                return False
            if not self._is_bullish(-i):  # 检查 0, -1, -2...（当前K线+前N-1根）
                return False
        return True

    def _check_consecutive_bearish(self):
        """检查是否连续 N 根阴线（包含当前K线）
        
        真实交易逻辑：
        - 当前K线刚收盘时检查
        - 检查当前K线(索引0)和前N-1根K线
        - 例如N=2：检查当前K线+上一根K线
        """
        if self.daily_bar_count < self.params.consecutive_count:
            return False
        
        current_idx = len(self.data)
        
        for i in range(self.params.consecutive_count):
            bar_idx = current_idx - i
            if bar_idx < self.daily_first_bar_idx:
                return False
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
        """检查是否已过开仓3小时（强制平仓）"""
        if not hasattr(self, 'entry_time') or self.entry_time is None:
            return False
        
        current_time = self._get_current_time()
        current_minutes = current_time.hour * 60 + current_time.minute
        entry_minutes = self.entry_time.hour * 60 + self.entry_time.minute
        
        return (current_minutes - entry_minutes) >= 180

    def _is_near_market_close(self):
        """检查是否接近收盘（15:30 EDT = UTC 19:30）"""
        current_time = self._get_current_time()
        return current_time.hour > 19 or (current_time.hour == 19 and current_time.minute >= 30)

    def _is_within_first_60min(self):
        """检查是否在开盘后60分钟内"""
        current_time = self._get_current_time()
        return current_time.hour < 14 or (current_time.hour == 14 and current_time.minute < 30)

    def _check_take_profit(self, current_position):
        """检查是否触发止盈（新增）"""
        if self.daily_trade_type == 'long' and self.buy_price:
            current_profit = (self.data.close[0] - self.buy_price) * current_position
            return current_profit >= self.params.take_profit_amount
        elif self.daily_trade_type == 'short' and self.sell_price:
            current_profit = (self.sell_price - self.data.close[0]) * current_position
            return current_profit >= self.params.take_profit_amount
        return False

    def next(self):
        """策略核心逻辑"""
        if self.order:
            return

        # 初始化底仓（仅第一个bar执行一次）
        if not self._base_position_set and self.params.initial_position > 0:
            self.log(f"🏦 建立底仓: 以 ${self.data.open[0]:.2f} 买入 {self.params.initial_position} 股")
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
            self.entry_time = None
            self.daily_bar_count = 0
            self.daily_first_bar_idx = len(self.data)
            self.log(f"📅 新的一天开始: {current_date}")
        
        self.daily_bar_count += 1

        if self.daily_trade_done:
            return

        current_position = abs(self.position.size) if self.position else 0

        # 情况1：已开仓（先买后卖），等待卖出信号、止盈、止损或强制平仓
        # 平仓价取值逻辑（方案1）：使用信号确认K线的收盘价
        if self.daily_trade_type == 'long' and current_position > 0:
            # 检查是否触发止盈（新增）
            if self._check_take_profit(current_position):
                self.log(f"💰 触发止盈! 盈利达到 ${self.params.take_profit_amount:.2f}")
                if self.current_trade:
                    self.current_trade['close_reason'] = '止盈'
                self.order = self.sell(size=current_position)
                self.daily_trade_done = True
                return
            
            # 检查是否触发止损
            if self.buy_price:
                current_loss = (self.buy_price - self.data.close[0]) * current_position
                if current_loss >= self.params.stop_loss_amount:
                    self.log(f"⛔ 触发止损! 买入价: ${self.buy_price:.2f}, 当前价: ${self.data.close[0]:.2f}")
                    if self.current_trade:
                        self.current_trade['close_reason'] = '止损'
                    self.order = self.sell(size=current_position)
                    self.daily_trade_done = True
                    return

            # 检查卖出信号或强制平仓时间
            if self._check_consecutive_bearish() or self._is_after_3h():
                if self._is_after_3h() and not self._check_consecutive_bearish():
                    self.log(f"⏰ 强制平仓时间到，卖出 {current_position} 股")
                    if self.current_trade:
                        self.current_trade['close_reason'] = '强制平仓'
                else:
                    self.log(f"📉 卖出信号: 连续{self.params.consecutive_count}根阴线")
                    if self.current_trade:
                        self.current_trade['close_reason'] = '信号平仓'
                self.order = self.sell(size=current_position)
                self.daily_trade_done = True
            return

        # 情况2：已开仓（先卖后买），等待买入信号、止盈、止损或强制平仓
        # 平仓价取值逻辑（方案1）：使用信号确认K线的收盘价
        if self.daily_trade_type == 'short' and current_position > 0:
            # 检查是否触发止盈（新增）
            if self._check_take_profit(current_position):
                self.log(f"💰 触发止盈! 盈利达到 ${self.params.take_profit_amount:.2f}")
                if self.current_trade:
                    self.current_trade['close_reason'] = '止盈'
                self.order = self.buy(size=current_position)
                self.daily_trade_done = True
                return
            
            # 检查买入信号或强制平仓时间
            if self._check_consecutive_bullish() or self._is_after_3h():
                if self._is_after_3h() and not self._check_consecutive_bullish():
                    self.log(f"⏰ 强制平仓时间到，买入 {current_position} 股")
                    if self.current_trade:
                        self.current_trade['close_reason'] = '强制平仓'
                else:
                    self.log(f"📈 买入信号: 连续{self.params.consecutive_count}根阳线")
                    if self.current_trade:
                        self.current_trade['close_reason'] = '信号平仓'
                self.order = self.buy(size=current_position)
                self.daily_trade_done = True
            return

        # 情况3：未开仓，寻找开仓信号
        if self._is_within_first_60min():
            return
        
        if self._is_near_market_close():
            return

        # 反T信号：连续阴线，先卖出
        # 价格取值逻辑：
        # - signal_price: 信号确认K线的收盘价（如连续2根阴线，第2根收盘价）
        # - entry_price: 实际成交价（下一根K线开盘价，在notify_order中更新）
        if self._check_consecutive_bearish():
            available_cash = self.broker.getcash()
            cost = self.data.close[0] * self.params.trade_size
            if available_cash >= cost:
                self.log(f"📉 反T开仓信号: 连续{self.params.consecutive_count}根阴线，先卖出 {self.params.trade_size} 股")
                self.daily_trade_type = 'short'
                self.entry_time = self._get_current_time()
                dt = self.datas[0].datetime.datetime(0)
                self.current_trade = {
                    'date': dt.strftime("%Y-%m-%d"),
                    'type': '反T',
                    'entry_time': self._get_ny_time_str(dt),
                    'signal_price': self.data.close[0],  # 信号价：信号K线收盘价
                    'entry_price': None,  # 实际成交价：在notify_order中更新
                    'entry_action': '卖出',
                    'size': self.params.trade_size,
                    'exit_time': None,
                    'exit_price': None,
                    'exit_action': None,
                    'close_reason': None,
                }
                self.order = self.sell(size=self.params.trade_size)
            return

        # 正T信号：连续阳线，先买入
        # 价格取值逻辑：
        # - signal_price: 信号确认K线的收盘价
        # - entry_price: 实际成交价（下一根K线开盘价，在notify_order中更新）
        if self._check_consecutive_bullish():
            available_cash = self.broker.getcash()
            cost = self.data.close[0] * self.params.trade_size
            if available_cash >= cost:
                self.log(f"📈 正T开仓信号: 连续{self.params.consecutive_count}根阳线，先买入 {self.params.trade_size} 股")
                self.daily_trade_type = 'long'
                self.entry_time = self._get_current_time()
                dt = self.datas[0].datetime.datetime(0)
                self.current_trade = {
                    'date': dt.strftime("%Y-%m-%d"),
                    'type': '正T',
                    'entry_time': self._get_ny_time_str(dt),
                    'signal_price': self.data.close[0],  # 信号价：信号K线收盘价
                    'entry_price': None,  # 实际成交价：在notify_order中更新
                    'entry_action': '买入',
                    'size': self.params.trade_size,
                    'exit_time': None,
                    'exit_price': None,
                    'exit_action': None,
                    'close_reason': None,
                }
                self.order = self.buy(size=self.params.trade_size)
            return
