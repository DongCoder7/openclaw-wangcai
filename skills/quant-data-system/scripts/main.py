#!/usr/bin/env python3
"""
量化数据系统 - 主入口
整合数据补充、WFO回测、模拟盘功能
"""
import sys
import argparse
from datetime import datetime

def main():
    parser = argparse.ArgumentParser(description='量化数据系统')
    parser.add_argument('command', choices=['supplement', 'wfo', 'sim', 'all'], 
                       help='执行命令: supplement(数据补充), wfo(WFO回测), sim(模拟盘), all(全部)')
    
    args = parser.parse_args()
    
    print(f"🚀 量化数据系统 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60)
    
    if args.command == 'supplement' or args.command == 'all':
        print("\n📊 执行数据补充...")
        import supplement_data
        supplement_data.main()
    
    if args.command == 'wfo' or args.command == 'all':
        print("\n📈 执行WFO回测...")
        import wfo_backtest
        wfo_backtest.main()
    
    if args.command == 'sim' or args.command == 'all':
        print("\n💼 执行模拟盘...")
        import sim_portfolio
        sim_portfolio.main()
    
    print("\n" + "="*60)
    print("✅ 执行完成!")
    print("="*60)

if __name__ == '__main__':
    main()
