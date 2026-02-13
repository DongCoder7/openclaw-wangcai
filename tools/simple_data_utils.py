import pandas as pd
import numpy as np
import requests
from datetime import datetime, timedelta
from typing import Dict, Optional
import time

class SimpleStockData:
    """
    简化版股票数据获取工具
    主要使用腾讯API（稳定性高）
    """
    
    def __init__(self):
        self.cache = {}
        
    def get_daily_from_tencent(self, code: str, days: int = 60) -> Optional[pd.DataFrame]:
        """
        从腾讯API获取历史日线数据
        
        Args:
            code: 股票代码（如 '600519'）
            days: 获取天数
        """
        # 转换代码格式
        if code.startswith('6'):
            tencent_code = f'sh{code}'
        else:
            tencent_code = f'sz{code}'
        
        try:
            # 腾讯K线API
            url = f'http://web.ifzq.gtimg.cn/appstock/finance/dayquotestock/get'
            
            # 计算日期范围
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days*2)  # 多取一些避免节假日
            
            params = {
                'param': f'{tencent_code},day,{start_date.strftime("%Y%m%d")},{end_date.strftime("%Y%m%d")},640,qfq'
            }
            
            response = requests.get(url, params=params, timeout=15)
            data = response.json()
            
            if 'data' not in data or tencent_code not in data['data']:
                return None
            
            klines = data['data'][tencent_code].get('qfqday', []) or data['data'][tencent_code].get('day', [])
            
            if not klines:
                return None
            
            # 解析数据
            records = []
            for kline in klines[-days:]:  # 只取最近N天
                records.append({
                    'date': kline[0],
                    'open': float(kline[1]),
                    'close': float(kline[2]),
                    'low': float(kline[3]),
                    'high': float(kline[4]),
                    'volume': float(kline[5])
                })
            
            df = pd.DataFrame(records)
            df['date'] = pd.to_datetime(df['date'])
            df['amount'] = df['close'] * df['volume']
            
            return df.sort_values('date').reset_index(drop=True)
            
        except Exception as e:
            print(f'获取历史数据失败: {e}')
            return None
    
    def get_realtime(self, codes: list) -> Dict:
        """
        获取多只股票实时行情
        """
        try:
            # 转换代码格式
            tencent_codes = []
            for code in codes:
                if code.startswith('6'):
                    tencent_codes.append(f'sh{code}')
                else:
                    tencent_codes.append(f'sz{code}')
            
            codes_str = ','.join(tencent_codes)
            url = f'https://qt.gtimg.cn/q={codes_str}'
            
            response = requests.get(url, timeout=10)
            response.encoding = 'gbk'
            
            results = {}
            lines = response.text.strip().split(';')
            
            for line in lines:
                if '~' not in line:
                    continue
                
                parts = line.split('~')
                if len(parts) < 45:
                    continue
                
                code = parts[2]
                name = parts[1]
                price = float(parts[3]) if parts[3] else 0
                close = float(parts[4]) if parts[4] else 0
                change_pct = (price - close) / close * 100 if close else 0
                pe = float(parts[52]) if len(parts) > 52 and parts[52] else 0
                pb = float(parts[46]) if len(parts) > 46 and parts[46] else 0
                market_cap = float(parts[44]) if len(parts) > 44 and parts[44] else 0
                
                results[code] = {
                    'name': name,
                    'price': price,
                    'change_pct': change_pct,
                    'pe': pe,
                    'pb': pb,
                    'market_cap': market_cap
                }
            
            return results
            
        except Exception as e:
            print(f'获取实时行情失败: {e}')
            return {}
    
    def get_hs300_list(self) -> list:
        """
        获取沪深300成分股列表（简化版：使用常见大盘股）
        """
        # 简化版：使用一些常见的大盘股
        stocks = [
            '600519',  # 贵州茅台
            '000858',  # 五粮液
            '000333',  # 美的集团
            '600036',  # 招商银行
            '600900',  # 长江电力
            '601398',  # 工商银行
            '601318',  # 中国平安
            '600276',  # 恒瑞医药
            '002594',  # 比亚迪
            '300750',  # 宁德时代
            '600030',  # 中信证券
            '601888',  # 中国中免
            '603288',  # 海天味业
            '000002',  # 万科A
            '600000',  # 浦发银行
            '601166',  # 兴业银行
            '000001',  # 平安银行
            '600887',  # 伊利股份
            '601012',  # 隆基绿能
            '300760',  # 迈瑞医疗
        ]
        return stocks


# 便捷函数
def get_stock_data(code: str, days: int = 60) -> Optional[pd.DataFrame]:
    """获取股票日线数据"""
    provider = SimpleStockData()
    return provider.get_daily_from_tencent(code, days)

def get_batch_quotes(codes: list) -> Dict:
    """批量获取实时行情"""
    provider = SimpleStockData()
    return provider.get_realtime(codes)


if __name__ == '__main__':
    print('=== 简化版数据工具测试 ===')
    
    provider = SimpleStockData()
    
    # 测试获取历史数据
    print('\n1. 测试获取日线数据（贵州茅台600519）')
    df = provider.get_daily_from_tencent('600519', days=30)
    if df is not None:
        print(f'✅ 成功获取 {len(df)} 天数据')
        print(df.tail(3))
    else:
        print('❌ 获取失败')
    
    # 测试获取实时行情
    print('\n2. 测试批量获取实时行情')
    quotes = provider.get_realtime(['600519', '000858', '002600'])
    for code, data in quotes.items():
        print(f"{data['name']}({code}): 价格={data['price']:.2f}, PE={data['pe']:.2f}")
    
    print('\n=== 测试完成 ===')
