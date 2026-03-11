#!/root/.openclaw/workspace/venv/bin/python3
"""
qteasy集成使用示例
展示如何将qteasy与现有量化系统结合使用
"""

import sys
sys.path.insert(0, '/root/.openclaw/workspace/skills/quant-data-system/scripts')

import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# 导入集成模块
try:
    from qteasy_integration import (
        QteasyIntegration, 
        QteasySignalBridge,
        quick_backtest,
        compare_with_benchmark,
        optimize_weights
    )
    QTEASY_AVAILABLE = True
except ImportError as e:
    print(f"⚠️ 导入失败: {e}")
    QTEASY_AVAILABLE = False


def example_1_quick_backtest():
    """示例1: 快速策略验证 - 5分钟出结果"""
    print("\n" + "="*80)
    print("📊 示例1: 快速策略验证")
    print("="*80)
    
    if not QTEASY_AVAILABLE:
        print("qteasy未安装，跳过")
        return
    
    # 测试多只股票
    stocks = ['000001.SZ', '000002.SZ', '600519.SH']
    
    # 快速回测3个经典策略
    strategies = ['sma_cross', 'macd', 'rsi']
    
    results = []
    for strategy in strategies:
        print(f"\n测试策略: {strategy}")
        try:
            result = quick_backtest(
                strategy=strategy,
                stocks=stocks,
                start='20240101',
                end='20241231'
            )
            results.append({
                'strategy': strategy,
                'annual_return': result['annual_return'],
                'sharpe': result['sharpe_ratio'],
                'max_dd': result['max_drawdown']
            })
            print(f"  年化收益: {result['annual_return']:.2%}")
            print(f"  夏普比率: {result['sharpe_ratio']:.2f}")
            print(f"  最大回撤: {result['max_drawdown']:.2%}")
        except Exception as e:
            print(f"  失败: {e}")
    
    # 选出最佳策略
    if results:
        best = max(results, key=lambda x: x['sharpe'])
        print(f"\n🏆 最佳策略: {best['strategy']} (夏普{best['sharpe']:.2f})")
    
    return results


def example_2_benchmark_comparison():
    """示例2: 我们的策略 vs qteasy基准对照"""
    print("\n" + "="*80)
    print("📈 示例2: 策略基准对照")
    print("="*80)
    
    if not QTEASY_AVAILABLE:
        print("qteasy未安装，跳过")
        return
    
    # 模拟我们策略的收益率序列
    dates = pd.date_range('2024-01-01', '2024-12-31', freq='B')
    np.random.seed(42)
    our_returns = pd.Series(
        np.random.normal(0.0008, 0.02, len(dates)),  # 日均0.08%，波动2%
        index=dates
    )
    
    print(f"我们的策略模拟数据:")
    print(f"  日均收益: {our_returns.mean():.4f}")
    print(f"  年化收益: {our_returns.mean() * 252:.2%}")
    
    # 与qteasy基准对照
    try:
        comparison = compare_with_benchmark(
            our_returns=our_returns,
            stocks=['000001.SZ', '000002.SZ'],
            start='20240101',
            end='20241231'
        )
        
        print(f"\n基准对照结果:")
        for name, metrics in comparison['benchmarks'].items():
            excess = comparison['comparison'][name]['excess_return']
            print(f"  {name}: 年化{metrics['annual_return']:.2%} (我们超额{excess:.2%})")
    except Exception as e:
        print(f"  对照失败: {e}")


def example_3_portfolio_optimization():
    """示例3: 组合优化对比"""
    print("\n" + "="*80)
    print("💼 示例3: 组合优化")
    print("="*80)
    
    if not QTEASY_AVAILABLE:
        print("qteasy未安装，跳过")
        return
    
    stocks = ['000001.SZ', '000002.SZ', '600519.SH', '000858.SZ']
    
    # 对比不同优化方法
    methods = ['markowitz', 'risk_parity', 'equal_weight']
    
    for method in methods:
        print(f"\n方法: {method}")
        try:
            result = optimize_weights(stocks, method=method)
            print(f"  权重: {result['weights']}")
            print(f"  预期收益: {result['expected_return']:.2%}")
            print(f"  预期风险: {result['expected_risk']:.2%}")
            print(f"  夏普比率: {result['sharpe_ratio']:.2f}")
        except Exception as e:
            print(f"  失败: {e}")


def example_4_signal_bridge():
    """示例4: 信号桥接 - 我们的信号转qteasy格式"""
    print("\n" + "="*80)
    print("🔄 示例4: 信号桥接")
    print("="*80)
    
    # 模拟我们的策略信号
    our_signals = pd.DataFrame({
        'date': ['2024-03-01', '2024-03-01', '2024-03-02'],
        'code': ['000001.SZ', '000002.SZ', '000001.SZ'],
        'signal_weight': [0.3, 0.2, -0.1]  # 正=买入，负=卖出
    })
    
    print("我们的原始信号:")
    print(our_signals)
    
    # 转换为qteasy格式
    qt_signals = QteasySignalBridge.convert_signals(our_signals)
    
    print("\nqteasy格式信号:")
    print(qt_signals)


def example_5_full_workflow():
    """示例5: 完整工作流 - 从筛选到执行"""
    print("\n" + "="*80)
    print("🚀 示例5: 完整工作流")
    print("="*80)
    
    if not QTEASY_AVAILABLE:
        print("qteasy未安装，跳过")
        return
    
    print("Step 1: 快速筛选策略...")
    # 用qteasy快速测试多个策略
    stocks = ['000001.SZ', '000002.SZ', '600519.SH']
    
    best_strategy = None
    best_sharpe = 0
    
    for strategy in ['sma_cross', 'macd']:
        try:
            result = quick_backtest(strategy, stocks, '20240101', '20241231')
            if result['sharpe_ratio'] > best_sharpe:
                best_sharpe = result['sharpe_ratio']
                best_strategy = strategy
            print(f"  {strategy}: 夏普{result['sharpe_ratio']:.2f}")
        except:
            pass
    
    print(f"\n选中策略: {best_strategy}")
    
    print("\nStep 2: 组合优化...")
    opt_result = optimize_weights(stocks, method='markowitz')
    print(f"  优化权重: {opt_result['weights']}")
    
    print("\nStep 3: 生成交易信号...")
    # 模拟信号
    signals = pd.DataFrame({
        'date': [datetime.now().strftime('%Y-%m-%d')] * len(stocks),
        'code': stocks,
        'signal_weight': [0.4, 0.35, 0.25]
    })
    
    print("\nStep 4: 执行信号...")
    integrator = QteasyIntegration()
    execution = integrator.execute_signals(signals, broker='simulator')
    print(f"  执行了 {execution['executed_count']} 笔订单")


if __name__ == "__main__":
    print("🎯 qteasy集成使用示例")
    print("="*80)
    
    if not QTEASY_AVAILABLE:
        print("\n⚠️ qteasy未安装，请先运行:")
        print("  pip3 install qteasy --user")
        print("\n以下展示代码结构，实际运行需安装qteasy")
    
    # 运行示例
    example_1_quick_backtest()
    example_2_benchmark_comparison()
    example_3_portfolio_optimization()
    example_4_signal_bridge()
    example_5_full_workflow()
    
    print("\n" + "="*80)
    print("✅ 示例完成!")
    print("="*80)
    print("\n使用建议:")
    print("1. 快速筛选策略idea → qteasy向量化回测")
    print("2. 深度优化 → 我们的WFO系统")
    print("3. 基准对照 → qteasy内置经典策略")
    print("4. 实盘执行 → qteasy交易接口")
