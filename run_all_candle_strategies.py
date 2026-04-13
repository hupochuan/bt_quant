"""
运行所有阴阳线策略进行回测对比 - 修复版
"""
import sys
import os
sys.path.insert(0, '/root/bt_quant')

import pandas as pd
import backtrader as bt
import config
from strategies import STRATEGY_REGISTRY
from backtrader.feeds import PandasData

# 要运行的阴阳线策略
candle_strategies = ['candle', 'candle_trend', 'candle_profit30']

# 数据文件
data_file = 'cache/BABA_2026-03-13_2026-04-12_15m.csv'

def load_data_from_csv(filepath):
    """直接从CSV文件加载Backtrader数据"""
    df = pd.read_csv(filepath, index_col=0, parse_dates=True)
    df.columns = [col.capitalize() for col in df.columns]
    return PandasData(dataname=df, name='BABA', timeframe=bt.TimeFrame.Minutes, compression=15)

# 收集所有策略结果
all_results = {}

for strategy_name in candle_strategies:
    import io
    
    # 捕获输出
    old_stdout = sys.stdout
    sys.stdout = io.StringIO()
    
    try:
        cerebro = bt.Cerebro()
        strategy_config = config.STRATEGY_CONFIGS.get(strategy_name, {})
        
        # 初始资金
        initial_cash = strategy_config.get('initial_cash', 30000.0)
        cerebro.broker.setcash(initial_cash)
        
        # 加载数据
        data = load_data_from_csv(data_file)
        cerebro.adddata(data)
        
        # 设置固定手续费 - 使用正确的 Backtrader 佣金设置
        commission_fixed = strategy_config.get('commission_fixed', 5.0)
        cerebro.broker.setcommission(commission=0.0)  # 先设置为0，后面用自定义
        
        # 添加自定义佣金类（固定每笔收费）
        class FixedCommission(bt.CommInfoBase):
            params = (
                ('commission', commission_fixed),
                ('stocklike', True),
                ('commtype', bt.CommInfoBase.COMM_FIXED),
            )
        
        cerebro.broker.addcommissioninfo(FixedCommission())
        
        # 设置执行模式
        cerebro.broker.set_coc(True)  # Close on Close
        cerebro.broker.set_coo(False)  # 不使用 Close on Open
        
        # 添加策略
        strategy_class = STRATEGY_REGISTRY[strategy_name]['class']
        cerebro.addstrategy(strategy_class)
        
        # 运行回测
        cerebro.run()
        
        # 获取策略实例
        strategy = cerebro.runningstrats[0] if cerebro.runningstrats else None
        
        final_value = cerebro.broker.getvalue()
        total_return = (final_value / initial_cash - 1) * 100
        
        # 获取交易记录
        trade_records = []
        if strategy is not None:
            trade_records = getattr(strategy, 'trade_records', [])
        
        all_results[strategy_name] = {
            'initial_cash': initial_cash,
            'final_value': final_value,
            'total_return': total_return,
            'trade_count': len(trade_records),
            'trade_records': trade_records,
            'status': 'success'
        }
        
    except Exception as e:
        import traceback
        all_results[strategy_name] = {
            'status': 'failed',
            'error': str(e) + '\n' + traceback.format_exc()
        }
    finally:
        sys.stdout = old_stdout

# 打印汇总报告
print("="*100)
print("阴阳线策略回测对比分析报告")
print("="*100)
print(f"回测标的: BABA (阿里巴巴)")
print(f"回测期间: 2026-03-13 至 2026-04-12 (约1个月)")
print(f"数据周期: 15分钟K线")
print("="*100)

# 策略对比表
print("\n【一、策略对比汇总】")
print("-"*100)
print(f"{'策略名称':<20} {'交易次数':>10} {'初始资金':>14} {'最终资金':>14} {'收益率':>12}")
print("-"*100)

for name, result in all_results.items():
    if result['status'] == 'success':
        print(f"{name:<20} {result['trade_count']:>10} ${result['initial_cash']:>12,.2f} ${result['final_value']:>12,.2f} {result['total_return']:>10.2f}%")
    else:
        print(f"{name:<20} {'执行失败':>10}")

print("-"*100)

# 详细分析每个策略
for name, result in all_results.items():
    if result['status'] != 'success':
        print(f"\n{name}: 执行失败 - {result.get('error', 'Unknown')[:200]}")
        continue
    
    print(f"\n{'='*100}")
    print(f"【{name} 策略详细分析】")
    print("="*100)
    
    trades = result.get('trade_records', [])
    
    if not trades:
        print("无交易记录")
        continue
    
    # 统计分析
    winning = [t for t in trades if t.get('net_pnl', 0) > 0]
    losing = [t for t in trades if t.get('net_pnl', 0) <= 0]
    
    total_net = sum(t.get('net_pnl', 0) for t in trades)
    total_commission = sum(t.get('commission', 0) for t in trades)
    
    won_pnl = sum(t.get('net_pnl', 0) for t in winning)
    lost_pnl = sum(t.get('net_pnl', 0) for t in losing)
    
    # 统计平仓原因
    close_reasons = {}
    for t in trades:
        reason = t.get('close_reason', '未知')
        close_reasons[reason] = close_reasons.get(reason, 0) + 1
    
    print(f"\n交易统计:")
    print(f"  总交易次数: {len(trades)} 笔")
    if len(trades) > 0:
        print(f"  盈利次数: {len(winning)} 笔 ({len(winning)/len(trades)*100:.1f}%)")
        print(f"  亏损次数: {len(losing)} 笔 ({len(losing)/len(trades)*100:.1f}%)")
        print(f"  胜率: {len(winning)/len(trades)*100:.1f}%")
    
    print(f"\n盈亏统计:")
    print(f"  总净盈亏: ${total_net:,.2f}")
    print(f"  总手续费: ${total_commission:,.2f}")
    if winning:
        print(f"  平均盈利: ${won_pnl/len(winning):,.2f}")
    if losing:
        print(f"  平均亏损: ${lost_pnl/len(losing):,.2f}")
    
    if lost_pnl != 0:
        profit_factor = abs(won_pnl / lost_pnl)
        print(f"  盈亏比: {profit_factor:.2f}")
    
    print(f"\n平仓原因分布:")
    for reason, count in close_reasons.items():
        print(f"  {reason}: {count} 笔")
    
    # 打印所有交易明细
    print(f"\n交易明细:")
    print(f"{'日期':<12} {'类型':<6} {'开仓价':>10} {'平仓价':>10} {'净盈亏':>10} {'平仓原因':<10}")
    print("-"*60)
    for t in trades:
        print(f"{t.get('date',''):<12} {t.get('type',''):<6} ${t.get('entry_price',0):>8.2f} ${t.get('exit_price',0):>8.2f} ${t.get('net_pnl',0):>8.2f} {t.get('close_reason',''):<10}")

# 总结
print(f"\n{'='*100}")
print("【总结】")
print("="*100)

successful = [n for n, r in all_results.items() if r['status'] == 'success']
if successful:
    results_with_trades = [n for n in successful if all_results[n]['trade_count'] > 0]
    
    if results_with_trades:
        best = max(results_with_trades, key=lambda n: all_results[n]['total_return'])
        worst = min(results_with_trades, key=lambda n: all_results[n]['total_return'])
        
        print(f"1. 共运行 {len(candle_strategies)} 个阴阳线策略，{len(successful)} 个成功执行")
        print(f"2. 有交易的策略: {len(results_with_trades)} 个")
        print(f"3. 表现最佳策略: {best} (收益率 {all_results[best]['total_return']:.2f}%)")
        print(f"4. 表现最差策略: {worst} (收益率 {all_results[worst]['total_return']:.2f}%)")
        
        # 各策略汇总
        print(f"\n策略收益率排名:")
        sorted_results = sorted(results_with_trades, key=lambda n: all_results[n]['total_return'], reverse=True)
        for i, n in enumerate(sorted_results, 1):
            r = all_results[n]
            print(f"  {i}. {n}: {r['total_return']:+.2f}% ({r['trade_count']} 笔交易)")
    else:
        print(f"共运行 {len(candle_strategies)} 个阴阳线策略，{len(successful)} 个成功执行，但无交易记录")
    
    # 各策略特点
    print(f"\n各策略特点:")
    print(f"  - candle (基础阴阳线): 无趋势过滤，每日最多一次做T，有止损")
    print(f"  - candle_trend (趋势过滤): 增加20日均线趋势过滤，下跌只反T，上涨只正T")
    print(f"  - candle_profit30 (止盈版): 增加50美元固定止盈，防止盈利回吐")
    
    # 修复说明
    print(f"\n已修复问题:")
    print(f"  1. K线索引偏移: 从检查 -1,-2,-3 改为 0,-1,-2 (包含当前K线)")
    print(f"  2. 初始底仓: 添加 initial_position 参数，策略启动时自动建立底仓")
    print(f"  3. 佣金设置: 使用固定每笔佣金模式 (COMM_FIXED)")
else:
    print("所有策略执行失败")

print("="*100)
