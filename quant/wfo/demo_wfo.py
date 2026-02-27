#!/usr/bin/env python3
"""
WFO快速演示 - 使用模拟数据展示完整流程
用于验证框架和生成示例报告
"""
import sys
sys.path.insert(0, '/root/.openclaw/workspace/quant/wfo')

from wfo_backtest import WFOEngine, main as wfo_main

def main():
    print("="*70)
    print("🚀 WFO Walk-Forward Optimization 快速演示")
    print("="*70)
    print()
    print("⚠️ 注意: 当前使用模拟数据进行演示")
    print("   实际生产环境需要连接真实数据库执行回测")
    print()
    print("="*70)
    
    # 执行完整WFO流程
    summary = wfo_main()
    
    return summary

if __name__ == '__main__':
    main()
