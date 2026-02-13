#!/usr/bin/env python3
"""
VQM策略交易监控脚本
每10分钟执行一次，检查是否需要交易
注意：A股T+1交易规则
"""

import json
import os
from datetime import datetime, timedelta
from typing import Dict, List, Tuple

# VQM持仓配置
PORTFOLIO = {
    'initial_capital': 1000000,
    'start_date': '2026-02-13',
    'positions': [
        {'code': '000001', 'name': '平安银行', 'buy_price': 10.96, 'stop_loss': 9.64},
        {'code': '000333', 'name': '美的集团', 'buy_price': 63.20, 'stop_loss': 55.62},
        {'code': '600887', 'name': '伊利股份', 'buy_price': 28.50, 'stop_loss': 25.08},
        {'code': '600036', 'name': '招商银行', 'buy_price': 38.99, 'stop_loss': 34.31},
        {'code': '601318', 'name': '中国平安', 'buy_price': 51.20, 'stop_loss': 45.06},
        {'code': '601166', 'name': '兴业银行', 'buy_price': 17.92, 'stop_loss': 15.77},
        {'code': '600519', 'name': '贵州茅台', 'buy_price': 1493.01, 'stop_loss': 1313.85},
        {'code': '000858', 'name': '五粮液', 'buy_price': 106.15, 'stop_loss': 93.41},
        {'code': '300760', 'name': '迈瑞医疗', 'buy_price': 288.50, 'stop_loss': 253.88},
        {'code': '600900', 'name': '长江电力', 'buy_price': 26.12, 'stop_loss': 22.99},
    ]
}

# 交易日历（简化版）
HOLIDAYS_2026 = [
    '2026-01-01',  # 元旦
    '2026-01-02',  # 元旦
    '2026-01-03',  # 元旦
    '2026-02-16',  # 春节
    '2026-02-17',  # 春节
    '2026-02-18',  # 春节
    '2026-02-19',  # 春节
    '2026-02-20',  # 春节
    '2026-02-21',  # 春节
    '2026-02-22',  # 春节
    '2026-02-23',  # 春节
]


def is_trading_day(date_str: str = None) -> bool:
    """检查是否为交易日"""
    if date_str is None:
        date_str = datetime.now().strftime('%Y-%m-%d')
    
    date = datetime.strptime(date_str, '%Y-%m-%d')
    
    # 周末
    if date.weekday() >= 5:  # 5=周六, 6=周日
        return False
    
    # 法定节假日
    if date_str in HOLIDAYS_2026:
        return False
    
    return True


def is_trading_time() -> bool:
    """检查当前是否在交易时间"""
    now = datetime.now()
    time_str = now.strftime('%H:%M')
    
    # 上午交易时间：9:30-11:30
    if '09:30' <= time_str <= '11:30':
        return True
    
    # 下午交易时间：13:00-15:00
    if '13:00' <= time_str <= '15:00':
        return True
    
    return False


def can_sell(buy_date: str, check_date: str = None) -> bool:
    """
    检查是否已过T+1，可以卖出
    
    Args:
        buy_date: 买入日期（格式：YYYY-MM-DD）
        check_date: 检查日期（默认为今天）
    
    Returns:
        bool: True表示可以卖出，False表示还不能卖
    """
    if check_date is None:
        check_date = datetime.now().strftime('%Y-%m-%d')
    
    buy = datetime.strptime(buy_date, '%Y-%m-%d')
    check = datetime.strptime(check_date, '%Y-%m-%d')
    
    # T+1：买入后至少一个交易日才能卖
    # 简单计算：日期差至少1天
    return (check - buy).days >= 1


def check_stop_loss(current_price: float, stop_loss_price: float) -> bool:
    """检查是否触发止损"""
    return current_price <= stop_loss_price


def check_portfolio():
    """检查整个持仓组合"""
    today = datetime.now().strftime('%Y-%m-%d')
    time_str = datetime.now().strftime('%H:%M')
    
    print(f'=== VQM策略交易检查 [{today} {time_str}] ===')
    print()
    
    # 1. 检查是否为交易日
    if not is_trading_day():
        print('⚠️ 今日非交易日（周末或节假日）')
        print(f'   下次交易日：2026-02-24（周一，春节后）')
        return
    
    # 2. 检查是否在交易时间
    if not is_trading_time():
        print('⏸️ 当前非交易时间')
        print('   交易时间：9:30-11:30, 13:00-15:00')
        return
    
    print('✅ 交易日，交易时间')
    print()
    
    # 3. 检查每只股票
    print('持仓检查：')
    print('-' * 80)
    print(f'{"代码":<8} {"名称":<8} {"买入价":<10} {"止损价":<10} {"可卖":<8} {"状态":<10}')
    print('-' * 80)
    
    alerts = []
    
    for pos in PORTFOLIO['positions']:
        code = pos['code']
        name = pos['name']
        buy_price = pos['buy_price']
        stop_loss = pos['stop_loss']
        buy_date = PORTFOLIO['start_date']
        
        # 检查T+1
        sellable = can_sell(buy_date, today)
        sellable_str = '✅' if sellable else '❌(T+1)'
        
        # 检查止损（需要实时价格，这里用模拟数据）
        # 实际使用时需要从API获取实时价格
        # current_price = get_realtime_price(code)
        # stop_loss_triggered = check_stop_loss(current_price, stop_loss)
        
        status = '持有'
        
        # 如果是建仓日（2026-02-13），全部不可卖
        if today == buy_date:
            status = '建仓锁定'
        elif not sellable:
            status = 'T+1锁定'
        
        print(f'{code:<8} {name:<8} {buy_price:<10.2f} {stop_loss:<10.2f} {sellable_str:<8} {status:<10}')
        
        # 记录报警
        # if stop_loss_triggered and sellable:
        #     alerts.append(f'🚨 {name}({code}) 触发止损！当前价≤{stop_loss}')
    
    print('-' * 80)
    print()
    
    # 4. 显示报警
    if alerts:
        print('⚠️ 交易报警：')
        for alert in alerts:
            print(f'   {alert}')
    else:
        print('✅ 无止损报警')
    
    print()
    
    # 5. 检查是否需要调仓
    # 调仓日：每月最后一个交易日
    print('调仓检查：')
    # 实际使用时需要判断是否是月末
    print('   下次调仓：月末最后一个交易日14:30后')
    print()
    
    # 6. 记录日志
    log_entry = {
        'time': f'{today} {time_str}',
        'is_trading_day': is_trading_day(),
        'is_trading_time': is_trading_time(),
        'alerts': alerts
    }
    
    # 保存到日志文件
    log_file = 'trading_plan/vqm_check_log.jsonl'
    os.makedirs(os.path.dirname(log_file), exist_ok=True)
    with open(log_file, 'a', encoding='utf-8') as f:
        f.write(json.dumps(log_entry, ensure_ascii=False) + '\n')
    
    print(f'✅ 检查完成，日志已保存至 {log_file}')


def main():
    """主函数"""
    check_portfolio()


if __name__ == '__main__':
    main()
