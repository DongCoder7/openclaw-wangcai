#!/usr/bin/env python3
"""
长桥API统一调用模块
用于获取美股、A股、港股实时行情
"""
import os
from typing import List, Dict, Optional
from longport.openapi import Config, QuoteContext

class LongbridgeAPI:
    """长桥API封装类"""
    
    def __init__(self):
        """初始化，从环境变量加载配置"""
        self.config = Config.from_env()
        self.ctx = QuoteContext(self.config)
    
    def get_quote(self, symbol: str) -> Optional[Dict]:
        """获取单个股票行情
        
        Args:
            symbol: 股票代码 (如 '002371.SZ', 'AAPL.US', '00700.HK')
            
        Returns:
            Dict: {
                'symbol': '002371.SZ',
                'name': '股票名称',
                'price': 496.00,
                'change': 1.78,  # 涨跌幅%
                'volume': 7889200,
                'turnover': 3883655146.45,
                'open': 488.47,
                'high': 499.68,
                'low': 480.77,
                'prev_close': 487.33
            }
        """
        try:
            resp = self.ctx.quote([symbol])
            if resp and len(resp) > 0:
                q = resp[0]
                return {
                    'symbol': symbol,
                    'price': float(q.last_done),
                    'prev_close': float(q.prev_close),
                    'change': (float(q.last_done) - float(q.prev_close)) / float(q.prev_close) * 100,
                    'open': float(q.open),
                    'high': float(q.high),
                    'low': float(q.low),
                    'volume': int(q.volume),
                    'turnover': float(q.turnover),
                    'timestamp': q.timestamp
                }
        except Exception as e:
            print(f"获取行情失败 {symbol}: {e}")
        return None
    
    def get_quotes(self, symbols: List[str]) -> List[Dict]:
        """批量获取股票行情"""
        results = []
        try:
            resp = self.ctx.quote(symbols)
            for i, q in enumerate(resp):
                results.append({
                    'symbol': symbols[i],
                    'price': float(q.last_done),
                    'prev_close': float(q.prev_close),
                    'change': (float(q.last_done) - float(q.prev_close)) / float(q.prev_close) * 100,
                    'open': float(q.open),
                    'high': float(q.high),
                    'low': float(q.low),
                    'volume': int(q.volume),
                    'turnover': float(q.turnover),
                    'timestamp': q.timestamp
                })
        except Exception as e:
            print(f"批量获取行情失败: {e}")
        return results
    
    def format_a_stock(self, code: str, market: str = 'SZ') -> str:
        """格式化A股代码"""
        return f"{code}.{market}"
    
    def format_hk_stock(self, code: str) -> str:
        """格式化港股代码"""
        return f"{code}.HK"
    
    def format_us_stock(self, code: str) -> str:
        """格式化美股代码"""
        return f"{code}.US"

# 便捷函数
def get_longbridge_api() -> LongbridgeAPI:
    """获取长桥API实例"""
    return LongbridgeAPI()

if __name__ == "__main__":
    # 测试
    api = get_longbridge_api()
    quote = api.get_quote("002371.SZ")
    if quote:
        print(f"{quote['symbol']}: {quote['price']} ({quote['change']:+.2f}%)")
