# 量化投资数据获取工具 (data_utils.py)
# Day 2 学习任务 - 数据源封装

import pandas as pd
import numpy as np
import requests
import json
import time
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Tuple
import warnings
warnings.filterwarnings('ignore')

class StockDataProvider:
    """
    股票数据获取工具类
    支持多数据源：长桥API / AKShare / 腾讯API / 新浪API
    自动切换机制：主数据源失败时自动切换到备用源
    
    优先级：
    1. 长桥API（实时性最好，需配置API Key）
    2. 腾讯API（免费，稳定性好）
    3. AKShare（数据全面，但速度较慢）
    4. 新浪API（备用）
    """
    
    def __init__(self, use_longbridge: bool = False):
        self.data_sources = ['tencent', 'akshare', 'sina']
        self.current_source = 'tencent'
        self.cache = {}
        self.cache_timeout = 300  # 缓存5分钟
        
        # 长桥API支持
        self.longbridge = None
        if use_longbridge:
            self._init_longbridge()
    
    def _init_longbridge(self):
        """初始化长桥API（如配置可用）"""
        try:
            from longbridge_provider import LongbridgeDataProvider
            self.longbridge = LongbridgeDataProvider()
            # 测试连接
            test = self.longbridge.get_realtime_quote('000001', market='CN')
            if test:
                print('✅ 长桥API已启用')
                # 将长桥添加到数据源列表首位
                self.data_sources.insert(0, 'longbridge')
            else:
                self.longbridge = None
        except Exception as e:
            print(f'⚠️ 长桥API未启用: {e}')
            self.longbridge = None
        
    def _get_stock_code_format(self, code: str, source: str) -> str:
        """
        转换股票代码格式
        """
        # 去除空格和扩展名
        code = code.strip().upper().replace('.SZ', '').replace('.SH', '')
        
        if source == 'tencent':
            # 腾讯格式：sh600519 / sz000858
            if code.startswith('6'):
                return f'sh{code}'
            else:
                return f'sz{code}'
        elif source == 'sina':
            # 新浪格式与腾讯相同
            if code.startswith('6'):
                return f'sh{code}'
            else:
                return f'sz{code}'
        else:
            # AKShare格式：原始代码
            return code
    
    def get_daily_data(self, code: str, start_date: str = None, end_date: str = None) -> pd.DataFrame:
        """
        获取日线数据（自动切换数据源）
        
        Args:
            code: 股票代码（如 '600519' 或 '000858'）
            start_date: 开始日期（格式：YYYY-MM-DD）
            end_date: 结束日期（格式：YYYY-MM-DD）
            
        Returns:
            DataFrame with columns: date, open, high, low, close, volume, amount
        """
        # 检查缓存
        cache_key = f'{code}_{start_date}_{end_date}'
        if cache_key in self.cache:
            cache_time, data = self.cache[cache_key]
            if time.time() - cache_time < self.cache_timeout:
                return data.copy()
        
        # 设置默认日期
        if end_date is None:
            end_date = datetime.now().strftime('%Y%m%d')
        if start_date is None:
            start_dt = datetime.now() - timedelta(days=365)
            start_date = start_dt.strftime('%Y%m%d')
        
        # 尝试各数据源
        for source in self.data_sources:
            try:
                if source == 'akshare':
                    data = self._get_daily_akshare(code, start_date, end_date)
                elif source == 'tencent':
                    data = self._get_daily_tencent(code, start_date, end_date)
                elif source == 'sina':
                    data = self._get_daily_sina(code, start_date, end_date)
                
                if data is not None and not data.empty:
                    # 存入缓存
                    self.cache[cache_key] = (time.time(), data.copy())
                    self.current_source = source
                    print(f'✅ 成功从 {source} 获取 {code} 数据，共 {len(data)} 条')
                    return data
                    
            except Exception as e:
                print(f'⚠️ {source} 数据源失败: {str(e)[:50]}')
                continue
        
        raise Exception(f'所有数据源均失败: {code}')
    
    def _get_daily_akshare(self, code: str, start_date: str, end_date: str) -> pd.DataFrame:
        """使用AKShare获取日线数据"""
        import akshare as ak
        
        df = ak.stock_zh_a_hist(
            symbol=code,
            period='daily',
            start_date=start_date,
            end_date=end_date,
            adjust='qfq'  # 前复权
        )
        
        if df.empty:
            return None
            
        # 标准化列名
        df = df.rename(columns={
            '日期': 'date',
            '开盘': 'open',
            '收盘': 'close',
            '最高': 'high',
            '最低': 'low',
            '成交量': 'volume',
            '成交额': 'amount'
        })
        
        df['date'] = pd.to_datetime(df['date'])
        return df[['date', 'open', 'high', 'low', 'close', 'volume', 'amount']]
    
    def _get_daily_tencent(self, code: str, start_date: str, end_date: str) -> pd.DataFrame:
        """使用腾讯API获取日线数据"""
        # 腾讯API代码格式
        tencent_code = self._get_stock_code_format(code, 'tencent')
        
        url = f'http://web.ifzq.gtimg.cn/appstock/finance/dayquotestock/get'
        params = {
            'param': f'{tencent_code},day,{start_date},{end_date},640,qfq'
        }
        
        response = requests.get(url, params=params, timeout=10)
        data = response.json()
        
        if 'data' not in data or tencent_code not in data['data']:
            return None
            
        klines = data['data'][tencent_code].get('day', [])
        
        if not klines:
            return None
        
        # 解析数据
        records = []
        for kline in klines:
            # 格式: [日期, 开盘, 收盘, 最低, 最高, 成交量]
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
        df['amount'] = df['close'] * df['volume']  # 估算成交额
        
        return df[['date', 'open', 'high', 'low', 'close', 'volume', 'amount']]
    
    def _get_daily_sina(self, code: str, start_date: str, end_date: str) -> pd.DataFrame:
        """使用新浪API获取日线数据"""
        # 新浪API代码格式
        sina_code = self._get_stock_code_format(code, 'sina')
        
        url = f'https://quotes.sina.cn/cn/api/quotes.php'
        params = {
            'symbol': sina_code,
            'from': start_date,
            'to': end_date
        }
        
        # 新浪API限制较多，这里使用备用方案
        # 实际使用时可以实现更完整的数据获取
        return None  # 暂时返回None，使用其他数据源
    
    def _get_realtime_longbridge(self, code: str) -> Dict:
        """使用长桥API获取实时行情"""
        if not self.longbridge:
            return None
        
        try:
            quote = self.longbridge.get_realtime_quote(code, market='CN')
            if quote:
                return {
                    'code': quote['code'],
                    'name': quote['name'],
                    'price': quote['price'],
                    'yesterday_close': quote['prev_close'],
                    'open': quote['open'],
                    'high': quote['high'],
                    'low': quote['low'],
                    'change': quote['change'],
                    'change_pct': quote['change_pct'],
                    'volume': quote['volume'],
                    'turnover': quote['turnover']
                }
        except Exception as e:
            print(f'⚠️ 长桥API获取失败 {code}: {e}')
        return None
    
    def get_realtime_quote(self, code: str) -> Dict:
        """
        获取实时行情
        优先使用长桥API（如已启用），否则使用腾讯API
        
        Returns:
            dict: {code, name, price, change, change_pct, volume, turnover}
        """
        # 1. 优先尝试长桥API
        if self.longbridge:
            result = self._get_realtime_longbridge(code)
            if result:
                return result
        
        # 2. 回退到腾讯API
        try:
            # 使用腾讯实时行情API
            tencent_code = self._get_stock_code_format(code, 'tencent')
            url = f'https://qt.gtimg.cn/q={tencent_code}'
            
            response = requests.get(url, timeout=5)
            response.encoding = 'gbk'
            
            # 解析腾讯数据格式
            data_str = response.text
            if not data_str or '~' not in data_str:
                return None
            
            parts = data_str.split('~')
            if len(parts) < 45:
                return None
            
            return {
                'code': code,
                'name': parts[1],
                'price': float(parts[3]),
                'yesterday_close': float(parts[4]),
                'open': float(parts[5]),
                'high': float(parts[33]),
                'low': float(parts[34]),
                'change': float(parts[3]) - float(parts[4]),
                'change_pct': (float(parts[3]) - float(parts[4])) / float(parts[4]) * 100,
                'volume': float(parts[36]),
                'turnover': float(parts[37])
            }
            
        except Exception as e:
            print(f'获取实时行情失败: {e}')
            return None
    
    def get_stock_list(self, market: str = 'all') -> pd.DataFrame:
        """
        获取股票列表
        
        Args:
            market: 'sh'/'sz'/'all'
        """
        try:
            import akshare as ak
            
            if market in ['all', 'sh']:
                df_sh = ak.stock_sh_a_spot_em()
            else:
                df_sh = pd.DataFrame()
                
            if market in ['all', 'sz']:
                df_sz = ak.stock_sz_a_spot_em()
            else:
                df_sz = pd.DataFrame()
            
            df = pd.concat([df_sh, df_sz], ignore_index=True)
            
            # 标准化列名
            df = df.rename(columns={
                '代码': 'code',
                '名称': 'name',
                '最新价': 'price',
                '涨跌幅': 'change_pct',
                '总市值': 'market_cap'
            })
            
            return df[['code', 'name', 'price', 'change_pct', 'market_cap']]
            
        except Exception as e:
            print(f'获取股票列表失败: {e}')
            return pd.DataFrame()
    
    def get_index_data(self, index_code: str = '000300') -> pd.DataFrame:
        """
        获取指数数据（如沪深300）
        """
        try:
            import akshare as ak
            
            if index_code == '000300':
                df = ak.index_zh_a_hist(symbol='000300', period='daily')
            elif index_code == '000001':
                df = ak.index_zh_a_hist(symbol='000001', period='daily')
            else:
                df = ak.index_zh_a_hist(symbol=index_code, period='daily')
            
            return df
            
        except Exception as e:
            print(f'获取指数数据失败: {e}')
            return pd.DataFrame()
    
    def clear_cache(self):
        """清除缓存"""
        self.cache.clear()
        print('✅ 缓存已清除')


# 便捷函数接口
def get_stock_data(code: str, start_date: str = None, end_date: str = None) -> pd.DataFrame:
    """便捷函数：获取股票日线数据"""
    provider = StockDataProvider()
    return provider.get_daily_data(code, start_date, end_date)

def get_realtime_price(code: str) -> Dict:
    """便捷函数：获取实时价格"""
    provider = StockDataProvider()
    return provider.get_realtime_quote(code)


# 测试代码
if __name__ == '__main__':
    print('=== 数据获取工具测试 ===')
    
    # 测试获取日线数据
    provider = StockDataProvider()
    
    # 获取贵州茅台最近30天数据
    print('\n1. 测试获取日线数据（贵州茅台600519）')
    try:
        df = provider.get_daily_data('600519', '20250101', '20260213')
        print(df.tail())
    except Exception as e:
        print(f'❌ 失败: {e}')
    
    # 测试获取实时行情
    print('\n2. 测试获取实时行情（领益智造002600）')
    try:
        quote = provider.get_realtime_quote('002600')
        if quote:
            print(f"股票: {quote['name']} ({quote['code']})")
            print(f"价格: {quote['price']:.2f}")
            print(f"涨跌: {quote['change_pct']:.2f}%")
    except Exception as e:
        print(f'❌ 失败: {e}')
    
    print('\n=== 测试完成 ===')
