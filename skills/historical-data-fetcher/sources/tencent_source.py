#!/usr/bin/env python3
"""
腾讯API数据源实现
优点: 无需认证，实时数据，批量查询
缺点: 历史数据有限，字段较少
"""
import requests
import pandas as pd
import re
from typing import Optional, List
from datetime import datetime
from . import DataSource

class TencentSource(DataSource):
    """腾讯API数据源"""
    
    def __init__(self):
        super().__init__('tencent')
        self.base_url = "https://qt.gtimg.cn/q="
        self.test_connection()
    
    def test_connection(self) -> bool:
        """测试连接"""
        try:
            response = requests.get(f"{self.base_url}sh600519", timeout=5)
            self.available = response.status_code == 200 and '600519' in response.text
            return self.available
        except:
            self.available = False
            return False
    
    def _convert_code(self, code: str) -> str:
        """
        转换代码格式
        000001.SZ -> sz000001
        600519.SH -> sh600519
        """
        if '.' in code:
            parts = code.split('.')
            if parts[1] == 'SZ':
                return f"sz{parts[0]}"
            elif parts[1] == 'SH':
                return f"sh{parts[0]}"
            elif parts[1] == 'BJ':
                return f"bj{parts[0]}"
        return code.lower()
    
    def _parse_response(self, response_text: str) -> dict:
        """解析腾讯API响应"""
        result = {}
        lines = response_text.strip().split(';')
        
        for line in lines:
            if not line.strip():
                continue
            
            # Match v_xxx="...";
            match = re.search(r'v_(\w+)="([^"]*)"', line)
            if match:
                code_key = match.group(1)
                data = match.group(2)
                result[code_key] = data.split('~')
        
        return result
    
    def get_realtime_quotes(self, codes: List[str]) -> Optional[pd.DataFrame]:
        """
        获取实时行情
        
        Args:
            codes: 股票代码列表 (如 ['000001.SZ', '600519.SH'])
        
        Returns:
            DataFrame with realtime quotes
        """
        if not self.available:
            return None
        
        # Convert codes
        tencent_codes = [self._convert_code(c) for c in codes]
        
        # Batch in groups of 100
        all_data = []
        batch_size = 100
        
        for i in range(0, len(tencent_codes), batch_size):
            batch = tencent_codes[i:i+batch_size]
            url = f"{self.base_url}{','.join(batch)}"
            
            try:
                response = requests.get(url, timeout=30)
                data = self._parse_response(response.text)
                
                for code_key, values in data.items():
                    if len(values) > 44:
                        all_data.append({
                            'code': code_key,
                            'name': values[1],
                            'price': float(values[3]) if values[3] else 0,
                            'yesterday_close': float(values[4]) if values[4] else 0,
                            'open': float(values[5]) if values[5] else 0,
                            'high': float(values[33]) if values[33] else 0,
                            'low': float(values[34]) if values[34] else 0,
                            'volume': int(values[36]) if values[36] else 0,
                            'amount': float(values[37]) if values[37] else 0,
                            'change_pct': float(values[32]) if values[32] else 0,
                            'pe': float(values[39]) if values[39] else 0,
                            'pb': float(values[46]) if values[46] else 0,
                            'market_cap': float(values[44]) if values[44] else 0,
                            'turnover_rate': float(values[38]) if values[38] else 0,
                        })
            except Exception as e:
                print(f"Error fetching batch: {e}")
                continue
        
        if not all_data:
            return None
        
        df = pd.DataFrame(all_data)
        
        # Convert back to ts_code format
        df['ts_code'] = df['code'].apply(lambda x: x[2:] + '.' + x[:2].upper().replace('SH', 'SH').replace('SZ', 'SZ'))
        
        return df
    
    def get_daily_data(self, code: str, start: str, end: str) -> Optional[pd.DataFrame]:
        """
        腾讯API不支持历史数据，返回None
        仅支持实时行情
        """
        # Tencent API doesn't provide historical data
        return None
    
    def get_stock_list(self) -> Optional[pd.DataFrame]:
        """
        腾讯API没有股票列表接口
        需要配合其他数据源使用
        """
        return None
    
    def get_all_stocks_realtime(self, max_stocks: int = 5000) -> Optional[pd.DataFrame]:
        """
        获取全市场实时行情
        
        Note: 需要配合股票列表使用
        """
        # This requires a stock list from another source
        return None


if __name__ == '__main__':
    # Test
    source = TencentSource()
    print(f"Tencent API available: {source.available}")
    
    if source.available:
        # Test realtime quotes
        df = source.get_realtime_quotes(['000001.SZ', '600519.SH'])
        if df is not None:
            print(f"\nFetched {len(df)} stocks")
            print(df[['ts_code', 'name', 'price', 'change_pct', 'pe', 'pb']])
