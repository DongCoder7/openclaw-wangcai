#!/root/.openclaw/workspace/venv/bin/python3
"""
VQM策略交易监控脚本 - 长桥API版本
每10分钟执行一次，检查是否需要交易
注意：A股T+1交易规则

环境变量:
    LONGBRIDGE_APP_KEY: 长桥App Key
    LONGBRIDGE_APP_SECRET: 长桥App Secret
"""

import json
import os
import sys
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional

# 添加tools目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 优先使用长桥API，失败时回退到腾讯API
from longbridge_provider import LongbridgeDataProvider, LongbridgeConfig
from data_utils import StockDataProvider

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

# 交易日历（2026年节假日）
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


class DataSourceManager:
    """
    数据源管理器
    优先使用长桥API，失败时回退到腾讯API
    """
    
    def __init__(self):
        self.longbridge = None
        self.tencent = None
        self._init_datasource()
    
    def _init_datasource(self):
        """初始化数据源"""
        # 尝试初始化长桥
        try:
            self.longbridge = LongbridgeDataProvider()
            # 测试一下是否能正常工作
            test_quote = self.longbridge.get_realtime_quote('000001', market='CN')
            if test_quote:
                print('✅ 长桥API连接成功')
            else:
                print('⚠️ 长桥API测试失败，将使用腾讯API作为回退')
                self.longbridge = None
        except Exception as e:
            print(f'⚠️ 长桥API初始化失败: {e}')
            print('   将使用腾讯API作为回退')
            self.longbridge = None
        
        # 初始化腾讯API作为回退
        self.tencent = StockDataProvider()
    
    def get_realtime_quotes(self, codes: List[str]) -> Dict[str, Dict]:
        """
        获取实时行情，优先长桥，失败回退腾讯
        
        Returns:
            {code: {'price': float, 'change_pct': float, 'name': str, ...}}
        """
        results = {}
        failed_codes = []
        
        # 1. 尝试长桥API
        if self.longbridge:
            try:
                quotes = self.longbridge.get_realtime_quotes(codes, market='CN')
                for q in quotes:
                    results[q['code']] = {
                        'price': q['price'],
                        'change_pct': q['change_pct'],
                        'change': q['change'],
                        'name': q['name'],
                        'high': q['high'],
                        'low': q['low'],
                        'open': q['open'],
                        'prev_close': q['prev_close'],
                        'volume': q['volume'],
                        'source': 'longbridge'
                    }
                print(f'✅ 长桥API获取成功: {len(results)}/{len(codes)} 只股票')
            except Exception as e:
                print(f'⚠️ 长桥API获取失败: {e}')
        
        # 2. 检查失败的股票，使用腾讯API回退
        failed_codes = [c for c in codes if c not in results]
        if failed_codes:
            print(f'🔄 使用腾讯API获取剩余 {len(failed_codes)} 只股票...')
            for code in failed_codes:
                try:
                    quote = self.tencent.get_realtime_quote(code)
                    if quote:
                        results[code] = {
                            'price': quote['price'],
                            'change_pct': quote['change_pct'],
                            'change': quote['change'],
                            'name': quote['name'],
                            'high': quote['high'],
                            'low': quote['low'],
                            'open': quote['open'],
                            'prev_close': quote['yesterday_close'],
                            'volume': quote['volume'],
                            'source': 'tencent'
                        }
                except Exception as e:
                    print(f'   ❌ 获取 {code} 失败: {e}')
        
        return results


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
    return (check - buy).days >= 1


def check_stop_loss(current_price: float, buy_price: float, threshold: float = -0.08) -> Tuple[bool, float]:
    """
    检查是否触发止损
    
    Args:
        current_price: 当前价格
        buy_price: 买入价格
        threshold: 止损阈值（默认-8%）
    
    Returns:
        (是否触发止损, 当前盈亏率)
    """
    pnl_pct = (current_price - buy_price) / buy_price
    return pnl_pct <= threshold, pnl_pct


def check_portfolio():
    """检查整个持仓组合"""
    today = datetime.now().strftime('%Y-%m-%d')
    time_str = datetime.now().strftime('%H:%M')
    
    print(f'=== VQM策略交易检查 [{today} {time_str}] ===')
    print()
    
    # 1. 检查是否为交易日
    if not is_trading_day():
        print('⚠️ 今日非交易日（周末或节假日）')
        return
    
    # 2. 检查是否在交易时间
    if not is_trading_time():
        print('⏸️ 当前非交易时间')
        print('   交易时间：9:30-11:30, 13:00-15:00')
        return
    
    print('✅ 交易日，交易时间')
    print()
    
    # 3. 初始化数据源
    print('🔄 初始化数据源...')
    ds = DataSourceManager()
    print()
    
    # 4. 获取所有持仓的实时行情
    codes = [pos['code'] for pos in PORTFOLIO['positions']]
    quotes = ds.get_realtime_quotes(codes)
    
    if not quotes:
        print('❌ 无法获取行情数据，检查网络连接')
        return
    
    # 5. 检查每只股票
    print()
    print('持仓检查：')
    print('-' * 100)
    print(f'{"代码":<8} {"名称":<8} {"买入价":<10} {"现价":<10} {"盈亏":<10} {"止损价":<10} {"可卖":<8} {"状态":<10}')
    print('-' * 100)
    
    alerts = []
    total_pnl = 0
    total_value = 0
    
    for pos in PORTFOLIO['positions']:
        code = pos['code']
        name = pos['name']
        buy_price = pos['buy_price']
        stop_loss_price = buy_price * 0.92  # -8%止损
        warning_price = buy_price * 0.95    # -5%预警
        buy_date = PORTFOLIO['start_date']
        
        # 获取实时价格
        quote = quotes.get(code, {})
        current_price = quote.get('price', 0)
        
        # 检查T+1
        sellable = can_sell(buy_date, today)
        sellable_str = '✅' if sellable else '❌(T+1)'
        
        # 计算盈亏
        if current_price > 0:
            pnl_pct = (current_price - buy_price) / buy_price * 100
            pnl_str = f'{pnl_pct:+.2f}%'
        else:
            pnl_pct = 0
            pnl_str = 'N/A'
        
        # 确定状态
        status = '持有'
        if today == buy_date:
            status = '建仓锁定'
        elif not sellable:
            status = 'T+1锁定'
        elif current_price > 0:
            if current_price <= stop_loss_price:
                status = '🔴止损'
                if sellable:
                    alerts.append(f'🚨 {name}({code}) 触发止损！现价¥{current_price:.2f} ≤ 止损价¥{stop_loss_price:.2f}')
            elif current_price <= warning_price:
                status = '🟡预警'
                alerts.append(f'⚠️ {name}({code}) 接近止损！现价¥{current_price:.2f}，距止损{(current_price/stop_loss_price-1)*100:.1f}%')
        
        print(f'{code:<8} {name:<8} ¥{buy_price:<9.2f} ¥{current_price:<9.2f} {pnl_str:<10} ¥{stop_loss_price:<9.2f} {sellable_str:<8} {status:<10}')
    
    print('-' * 100)
    print()
    
    # 6. 显示报警
    if alerts:
        print('⚠️ 交易报警：')
        for alert in alerts:
            print(f'   {alert}')
    else:
        print('✅ 无止损报警')
    
    print()
    
    # 7. 组合统计
    print('组合统计：')
    total_cost = sum(pos['buy_price'] for pos in PORTFOLIO['positions']) * 100000 / PORTFOLIO['initial_capital']
    print(f'   持仓数量: {len(PORTFOLIO["positions"])} 只')
    print(f'   初始资金: ¥{PORTFOLIO["initial_capital"]:,.0f}')
    print()
    
    # 8. 检查是否需要调仓
    print('调仓检查：')
    # 调仓日：每月最后一个交易日
    print('   下次调仓：月末最后一个交易日14:30后')
    print()
    
    # 9. 记录日志
    log_entry = {
        'time': f'{today} {time_str}',
        'is_trading_day': is_trading_day(),
        'is_trading_time': is_trading_time(),
        'quotes': {k: {'price': v['price'], 'change_pct': v['change_pct']} for k, v in quotes.items()},
        'alerts': alerts
    }
    
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
