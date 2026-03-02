#!/usr/bin/env python3
"""
qteasy集成示例 - 演示如何与现有量化系统协同工作
"""

import sys
sys.path.insert(0, '/root/.openclaw/workspace/skills/quant-integration/scripts')
sys.path.insert(0, '/root/.openclaw/workspace/skills/quant-data-system/scripts')
sys.path.insert(0, '/root/.openclaw/workspace/skills/dounai-investment-system/scripts')

from qteasy_wrapper import FastBacktest, Benchmark, LiveTrader, check_qteasy_installation


def demo1_quick_backtest():
    """示例1: 快速回测验证策略想法"""
    print("="*80)
    print("🚀 示例1: 快速回测验证")
    print("="*80)
    
    # 检查安装
    if not check_qteasy_installation():
        print("\n请先安装qteasy:")
        print("python3 -m venv ~/.openclaw/workspace/.venv/qteasy")
        print("source ~/.openclaw/workspace/.venv/qteasy/bin/activate")
        print("pip install qteasy")
        return
    
    # 初始化快速回测器
    fb = FastBacktest()
    
    # 测试标的
    symbols = ['000001.SZ', '000002.SZ', '600519.SH']  # 平安银行、万科、茅台
    
    # 测试多个经典策略
    strategies = [
        {'name': 'SMA', 'params': (20, 60)},    # 双均线
        {'name': 'EMA', 'params': (12, 26)},   # 指数均线
        {'name': 'MACD', 'params': (12, 26, 9)},  # MACD
    ]
    
    print(f"\n测试标的: {symbols}")
    print(f"测试策略: {[s['name'] for s in strategies]}")
    print(f"回测期间: 20240101 - 20241231")
    
    # 批量回测
    results = fb.batch_test(
        symbols=symbols,
        strategies=strategies,
        start='20240101',
        end='20241231'
    )
    
    # 显示结果
    print("\n📊 回测结果排名:")
    print("-" * 80)
    for i, r in enumerate(results, 1):
        if 'error' not in r:
            print(f"{i}. {r['strategy']}{r['params']}")
            print(f"   总收益: {r['total_return']:.2%}")
            print(f"   夏普比率: {r['sharpe']:.2f}")
            print(f"   最大回撤: {r['max_drawdown']:.2%}")
            print()


def demo2_benchmark_comparison():
    """示例2: 对比我们的策略与经典策略"""
    print("="*80)
    print("🚀 示例2: 策略基准对比")
    print("="*80)
    
    if not check_qteasy_installation():
        return
    
    # 模拟我们的AI策略结果（实际应从WFO系统获取）
    our_strategy = {
        'strategy': 'AI_Factor_v26',
        'total_return': 0.35,      # 35%收益
        'annual_return': 0.38,
        'sharpe': 1.5,
        'max_drawdown': -0.12,
        'win_rate': 0.65
    }
    
    print(f"\n我们的策略: {our_strategy['strategy']}")
    print(f"总收益: {our_strategy['total_return']:.2%}")
    print(f"夏普比率: {our_strategy['sharpe']:.2f}")
    
    # 对比基准
    bm = Benchmark()
    comparison = bm.compare(
        our_strategy_result=our_strategy,
        benchmarks=['SMA', 'MACD', 'RSI', 'BOLL'],
        symbols=['000001.SZ', '000002.SZ'],
        period='20240101-20241231'
    )
    
    # 生成报告
    print("\n" + "="*80)
    report = bm.generate_report(comparison)
    print(report)


def demo3_live_trading():
    """示例3: 实盘交易执行（模拟）"""
    print("="*80)
    print("🚀 示例3: 实盘交易执行（模拟模式）")
    print("="*80)
    
    # 初始化交易器
    trader = LiveTrader(
        broker='ths',
        account='8888888888'  # 示例账号
    )
    
    # 模拟从我们系统生成的交易信号
    signals = [
        {'symbol': '000001.SZ', 'action': 'buy', 'amount': 1000, 'price': 10.5},
        {'symbol': '002843.SZ', 'action': 'buy', 'amount': 500, 'price': 25.8},   # 泰嘉股份
        {'symbol': '300308.SZ', 'action': 'sell', 'amount': 200, 'price': 570.0}, # 中际旭创
    ]
    
    print(f"\n交易信号 ({len(signals)}条):")
    for s in signals:
        print(f"  {s['action']:4} {s['symbol']} {s['amount']:4}股 @ {s['price']:.2f}")
    
    # 模拟执行（dry_run=True）
    print("\n📋 模拟执行结果:")
    results = trader.execute_signals(signals, dry_run=True)
    
    for r in results:
        if 'error' in r:
            print(f"  ❌ {r.get('symbol', 'Unknown')}: {r['error']}")
        else:
            print(f"  ✅ {r['symbol']}: {r['action']} {r['amount']}股 - {r['message']}")
    
    print("\n⚠️  如需实盘执行，请:")
    print("  1. 配置真实券商账号")
    print("  2. 设置环境变量: export BROKER_PASSWORD=xxx")
    print("  3. 将 dry_run=False")


def demo4_workflow():
    """示例4: 完整工作流演示"""
    print("="*80)
    print("🚀 示例4: 完整工作流 - 从想法到实盘")
    print("="*80)
    
    if not check_qteasy_installation():
        return
    
    print("""
    工作流步骤:
    
    Step 1: 产生想法
    → "双均线策略在AI概念股上表现如何？"
    
    Step 2: qteasy快速验证 (5分钟)
    → 测试SMA(20,60)在光芯片板块的表现
    → 结果: +15%收益，夏普1.2
    → 结论: 值得深入验证
    
    Step 3: 我们的WFO深度验证 (5小时)
    → 滚动窗口优化参数
    → 结果: +12%收益，最大回撤8%
    → 结论: 可以上模拟盘
    
    Step 4: 模拟盘跟踪 (1个月)
    → 实际收益: +3%
    → 结论: 表现符合预期
    
    Step 5: 实盘交易
    → 通过qteasy执行交易
    → 持续跟踪收益
    """)
    
    # 实际演示Step 2
    print("\n" + "="*60)
    print("实际演示 Step 2: qteasy快速验证")
    print("="*60)
    
    fb = FastBacktest()
    result = fb.test_strategy(
        symbols=['300308.SZ', '300502.SZ', '002281.SZ'],  # 光芯片三剑客
        strategy='SMA',
        params=(20, 60),
        start='20240101',
        end='20241231'
    )
    
    if 'error' not in result:
        print(f"✅ 快速验证结果:")
        print(f"   策略: {result['strategy']}{result['params']}")
        print(f"   总收益: {result['total_return']:.2%}")
        print(f"   夏普: {result['sharpe']:.2f}")
        
        if result['total_return'] > 0.1:
            print(f"\n   👍 收益>10%，建议进行WFO深度验证")
        else:
            print(f"\n   👎 收益<10%，放弃或修改策略")


if __name__ == "__main__":
    import sys
    
    print("🎯 qteasy集成示例演示")
    print("="*80)
    
    # 选择要运行的示例
    demos = {
        '1': ('快速回测验证', demo1_quick_backtest),
        '2': ('策略基准对比', demo2_benchmark_comparison),
        '3': ('实盘交易执行', demo3_live_trading),
        '4': ('完整工作流', demo4_workflow),
        'all': ('运行所有示例', None)
    }
    
    print("\n可用示例:")
    for k, (name, _) in demos.items():
        print(f"  {k}. {name}")
    
    choice = input("\n选择要运行的示例 (1/2/3/4/all): ").strip() or 'all'
    
    if choice == 'all':
        for k, (_, func) in demos.items():
            if k != 'all' and func:
                print(f"\n{'='*80}")
                func()
    elif choice in demos:
        demos[choice][1]()
    else:
        print(f"无效选择: {choice}")
