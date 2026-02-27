#!/usr/bin/env python3
"""
WFO快速测试脚本 - 验证框架正确性
"""
import sys
sys.path.insert(0, '/root/.openclaw/workspace/quant/wfo')

from wfo_backtest import WFOEngine

def main():
    print("="*70)
    print("🚀 WFO 框架测试")
    print("="*70)
    
    # 初始化引擎
    engine = WFOEngine()
    
    # 生成窗口
    windows = engine.generate_windows()
    print(f"\n✅ 成功生成 {len(windows)} 个WFO窗口")
    
    # 验证窗口
    valid = engine.validate_windows()
    
    if valid:
        print("\n✅ 所有窗口验证通过，可以执行完整WFO流程")
        print("\n要执行完整WFO回测，请运行:")
        print("  cd ~/.openclaw/workspace/quant/wfo")
        print("  python3 wfo_backtest.py")
    else:
        print("\n⚠️ 窗口验证失败，请检查数据范围")
    
    print("\n" + "="*70)
    print("配置信息:")
    print(f"  训练窗口: {engine.config['wfo']['train_window_years']}年")
    print(f"  测试窗口: {engine.config['wfo']['test_window_years']}年")
    print(f"  滚动步长: {engine.config['wfo']['roll_step_years']}年")
    print(f"  优化方法: {engine.config['optimization']['method']}")
    print(f"  种群大小: {engine.config['optimization']['population_size']}")
    print(f"  进化代数: {engine.config['optimization']['generations']}")
    print("="*70)

if __name__ == '__main__':
    main()
