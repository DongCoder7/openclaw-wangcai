#!/usr/bin/env python3
"""
长桥API (Longbridge) 数据获取模块
文档: https://open.longbridge.com/zh-CN/docs

使用说明：
1. 先在长桥开放平台获取 App Key 和 App Secret
2. 设置环境变量：LONGBRIDGE_APP_KEY 和 LONGBRIDGE_APP_SECRET
3. 可选：LONGBRIDGE_ACCESS_TOKEN（如有）

支持功能：
- 实时行情订阅
- 历史K线数据
- 股票基础信息
- 实时成交明细
"""

import os
import json
import time
import base64
import hmac
import hashlib
import requests
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import warnings
warnings.filterwarnings('ignore')


@dataclass
class LongbridgeConfig:
    """长桥API配置"""
    app_key: str
    app_secret: str
    access_token: Optional[str] = None
    base_url: str = "https://openapi.longbridgeapp.com"
    
    @classmethod
    def from_env(cls) -> 'LongbridgeConfig':
        """从环境变量或配置文件加载配置"""
        # 首先尝试从环境变量读取
        app_key = os.getenv('LONGBRIDGE_APP_KEY', '')
        app_secret = os.getenv('LONGBRIDGE_APP_SECRET', '')
        access_token = os.getenv('LONGBRIDGE_ACCESS_TOKEN', None)
        
        # 如果环境变量未设置，尝试从配置文件读取
        if not app_key or not app_secret:
            config_paths = [
                os.path.expanduser('~/.openclaw/workspace/.longbridge.env'),
                os.path.expanduser('~/.longbridge.env'),
                '.longbridge.env',
            ]
            
            for config_path in config_paths:
                if os.path.exists(config_path):
                    with open(config_path, 'r') as f:
                        for line in f:
                            line = line.strip()
                            if '=' in line and not line.startswith('#'):
                                key, value = line.split('=', 1)
                                key = key.strip()
                                value = value.strip().strip('"\'')  # 去除引号
                                
                                if key == 'LONGBRIDGE_APP_KEY':
                                    app_key = value
                                elif key == 'LONGBRIDGE_APP_SECRET':
                                    app_secret = value
                                elif key == 'LONGBRIDGE_ACCESS_TOKEN':
                                    access_token = value
                    break
        
        if not app_key or not app_secret:
            raise ValueError("请设置 LONGBRIDGE_APP_KEY 和 LONGBRIDGE_APP_SECRET 环境变量或配置文件")
        
        return cls(app_key=app_key, app_secret=app_secret, access_token=access_token)


class LongbridgeAuth:
    """长桥API认证处理"""
    
    def __init__(self, config: LongbridgeConfig):
        self.config = config
        self._token = None
        self._token_expire = 0
    
    def _generate_sign(self, timestamp: str) -> str:
        """生成签名"""
        # 按照长桥文档的签名规则
        message = f"{timestamp}\n{self.config.app_key}"
        sign = base64.b64encode(
            hmac.new(
                self.config.app_secret.encode('utf-8'),
                message.encode('utf-8'),
                hashlib.sha256
            ).digest()
        ).decode('utf-8')
        return sign
    
    def get_headers(self) -> Dict[str, str]:
        """获取请求头"""
        timestamp = str(int(time.time()))
        sign = self._generate_sign(timestamp)
        
        headers = {
            'X-Api-Key': self.config.app_key,
            'X-Api-Signature': sign,
            'X-Api-Timestamp': timestamp,
            'Content-Type': 'application/json'
        }
        
        # 如果有access token，添加到header
        if self.config.access_token:
            headers['Authorization'] = f'Bearer {self.config.access_token}'
        
        return headers


class LongbridgeDataProvider:
    """
    长桥API数据提供者
    支持A股、港股、美股实时行情
    """
    
    def __init__(self, config: Optional[LongbridgeConfig] = None):
        if config is None:
            config = LongbridgeConfig.from_env()
        self.config = config
        self.auth = LongbridgeAuth(config)
        self.base_url = config.base_url
        self._cache = {}
        self._cache_timeout = 30  # 实时数据缓存30秒
    
    def _request(self, method: str, endpoint: str, params: Dict = None, data: Dict = None) -> Dict:
        """发送API请求"""
        url = f"{self.base_url}{endpoint}"
        headers = self.auth.get_headers()
        
        try:
            if method.upper() == 'GET':
                response = requests.get(url, headers=headers, params=params, timeout=10)
            else:
                response = requests.post(url, headers=headers, json=data, timeout=10)
            
            response.raise_for_status()
            return response.json()
            
        except requests.exceptions.RequestException as e:
            raise Exception(f"API请求失败: {str(e)}")
    
    def _format_symbol(self, code: str, market: str = 'CN') -> str:
        """
        转换股票代码为长桥格式
        
        A股格式:
        - 上海: 600519.SH
        - 深圳: 000858.SZ
        
        港股格式:
        - 00700.HK
        
        美股格式:
        - AAPL.US
        """
        code = code.strip().upper()
        
        # 如果已经是标准格式，直接返回
        if '.' in code:
            return code
        
        if market == 'CN':
            # A股判断
            if code.startswith('6') or code.startswith('5'):
                return f"{code}.SH"  # 上海
            else:
                return f"{code}.SZ"  # 深圳
        elif market == 'HK':
            return f"{code}.HK"
        elif market == 'US':
            return f"{code}.US"
        else:
            return code
    
    def get_realtime_quote(self, code: str, market: str = 'CN') -> Optional[Dict]:
        """
        获取实时行情
        
        Args:
            code: 股票代码（如 '600519' 或 '00700'）
            market: 市场 'CN'(A股) / 'HK'(港股) / 'US'(美股)
            
        Returns:
            {
                'code': '600519',
                'name': '贵州茅台',
                'price': 1500.00,
                'open': 1490.00,
                'high': 1510.00,
                'low': 1485.00,
                'prev_close': 1480.00,
                'change': 20.00,
                'change_pct': 1.35,
                'volume': 10000,
                'turnover': 15000000,
                'timestamp': 1708326400
            }
        """
        # 检查缓存
        cache_key = f"quote_{code}_{market}"
        if cache_key in self._cache:
            cache_time, data = self._cache[cache_key]
            if time.time() - cache_time < self._cache_timeout:
                return data
        
        symbol = self._format_symbol(code, market)
        
        try:
            # 长桥实时行情接口
            # 注意：实际接口路径请参考最新文档
            endpoint = "/v1/quote/realtime"
            params = {'symbol': symbol}
            
            result = self._request('GET', endpoint, params=params)
            
            if result.get('code') != 0:
                print(f"⚠️ 获取行情失败: {result.get('message', '未知错误')}")
                return None
            
            data = result.get('data', {})
            
            quote = {
                'code': code,
                'symbol': symbol,
                'name': data.get('name', ''),
                'price': float(data.get('last_done', 0)),
                'open': float(data.get('open', 0)),
                'high': float(data.get('high', 0)),
                'low': float(data.get('low', 0)),
                'prev_close': float(data.get('prev_close', 0)),
                'change': float(data.get('change', 0)),
                'change_pct': float(data.get('change_rate', 0)) * 100,
                'volume': int(data.get('volume', 0)),
                'turnover': float(data.get('turnover', 0)),
                'timestamp': data.get('timestamp', int(time.time()))
            }
            
            # 存入缓存
            self._cache[cache_key] = (time.time(), quote)
            return quote
            
        except Exception as e:
            print(f"❌ 获取实时行情失败 {code}: {e}")
            return None
    
    def get_realtime_quotes(self, codes: List[str], market: str = 'CN') -> List[Dict]:
        """
        批量获取实时行情
        
        Args:
            codes: 股票代码列表
            market: 市场
            
        Returns:
            List[Dict] 行情列表
        """
        results = []
        for code in codes:
            quote = self.get_realtime_quote(code, market)
            if quote:
                results.append(quote)
            time.sleep(0.05)  # 限速保护
        return results
    
    def get_klines(self, code: str, period: str = 'day', count: int = 100, 
                   market: str = 'CN') -> List[Dict]:
        """
        获取K线数据
        
        Args:
            code: 股票代码
            period: 周期 'day'/'week'/'month'/'min' (分钟)
            count: 获取条数
            market: 市场
            
        Returns:
            [
                {
                    'timestamp': 1708326400,
                    'open': 1490.00,
                    'high': 1510.00,
                    'low': 1485.00,
                    'close': 1500.00,
                    'volume': 10000
                },
                ...
            ]
        """
        symbol = self._format_symbol(code, market)
        
        try:
            # K线数据接口
            endpoint = "/v1/quote/candles"
            params = {
                'symbol': symbol,
                'period': period,
                'count': count
            }
            
            result = self._request('GET', endpoint, params=params)
            
            if result.get('code') != 0:
                return []
            
            candles = result.get('data', {}).get('candles', [])
            
            klines = []
            for candle in candles:
                klines.append({
                    'timestamp': candle.get('timestamp'),
                    'open': float(candle.get('open', 0)),
                    'high': float(candle.get('high', 0)),
                    'low': float(candle.get('low', 0)),
                    'close': float(candle.get('close', 0)),
                    'volume': int(candle.get('volume', 0))
                })
            
            return klines
            
        except Exception as e:
            print(f"❌ 获取K线失败 {code}: {e}")
            return []
    
    def get_stock_info(self, code: str, market: str = 'CN') -> Optional[Dict]:
        """
        获取股票基础信息
        
        Returns:
            {
                'name': '贵州茅台',
                'exchange': 'SH',
                'currency': 'CNY',
                'lot_size': 100,
                'total_shares': 1256197800,
                'circulating_shares': 1256197800
            }
        """
        symbol = self._format_symbol(code, market)
        
        try:
            endpoint = "/v1/quote/static"
            params = {'symbol': symbol}
            
            result = self._request('GET', endpoint, params=params)
            
            if result.get('code') != 0:
                return None
            
            data = result.get('data', {})
            
            return {
                'code': code,
                'symbol': symbol,
                'name': data.get('name', ''),
                'exchange': data.get('exchange', ''),
                'currency': data.get('currency', 'CNY'),
                'lot_size': data.get('lot_size', 100),
                'total_shares': data.get('total_shares', 0),
                'circulating_shares': data.get('circulating_shares', 0)
            }
            
        except Exception as e:
            print(f"❌ 获取股票信息失败 {code}: {e}")
            return None
    
    def is_trading_time(self, market: str = 'CN') -> bool:
        """
        检查当前是否在交易时间
        
        A股交易时间: 9:30-11:30, 13:00-15:00 (北京时间)
        港股交易时间: 9:30-12:00, 13:00-16:00 (香港时间)
        """
        now = datetime.now()
        time_str = now.strftime('%H:%M')
        weekday = now.weekday()
        
        # 周末不交易
        if weekday >= 5:
            return False
        
        if market == 'CN':
            # A股
            if '09:30' <= time_str <= '11:30':
                return True
            if '13:00' <= time_str <= '15:00':
                return True
        elif market == 'HK':
            # 港股
            if '09:30' <= time_str <= '12:00':
                return True
            if '13:00' <= time_str <= '16:00':
                return True
        
        return False
    
    def clear_cache(self):
        """清除缓存"""
        self._cache.clear()
        print('✅ 缓存已清除')


# ==================== 兼容层：保持与原有接口一致 ====================

class StockDataProviderLongbridge(LongbridgeDataProvider):
    """
    兼容原有StockDataProvider接口的长桥数据提供者
    可以直接替换原有数据源
    """
    
    def __init__(self, config: Optional[LongbridgeConfig] = None):
        super().__init__(config)
        self.data_sources = ['longbridge']
        self.current_source = 'longbridge'
    
    def get_daily_data(self, code: str, start_date: str = None, end_date: str = None) -> 'pd.DataFrame':
        """
        获取日线数据（兼容原有接口）
        
        Args:
            code: 股票代码
            start_date: 开始日期（YYYY-MM-DD）
            end_date: 结束日期（YYYY-MM-DD）
        """
        import pandas as pd
        
        # 获取K线数据
        klines = self.get_klines(code, period='day', count=500)
        
        if not klines:
            return pd.DataFrame()
        
        # 转换为DataFrame
        df = pd.DataFrame(klines)
        df['date'] = pd.to_datetime(df['timestamp'], unit='s')
        
        # 日期过滤
        if start_date:
            start_dt = pd.to_datetime(start_date)
            df = df[df['date'] >= start_dt]
        
        if end_date:
            end_dt = pd.to_datetime(end_date)
            df = df[df['date'] <= end_dt]
        
        # 标准化列名
        df['amount'] = df['close'] * df['volume']
        
        return df[['date', 'open', 'high', 'low', 'close', 'volume', 'amount']]
    
    def get_realtime_quote_compat(self, code: str) -> Dict:
        """兼容原有接口的实时行情"""
        quote = self.get_realtime_quote(code, market='CN')
        
        if not quote:
            return None
        
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


# ==================== 便捷函数 ====================

def get_longbridge_provider() -> LongbridgeDataProvider:
    """获取长桥数据提供者实例"""
    return LongbridgeDataProvider()


def get_realtime_price(code: str, market: str = 'CN') -> Optional[float]:
    """便捷函数：获取实时价格"""
    provider = LongbridgeDataProvider()
    quote = provider.get_realtime_quote(code, market)
    return quote['price'] if quote else None


def get_realtime_prices(codes: List[str], market: str = 'CN') -> Dict[str, float]:
    """便捷函数：批量获取实时价格"""
    provider = LongbridgeDataProvider()
    quotes = provider.get_realtime_quotes(codes, market)
    return {q['code']: q['price'] for q in quotes}


# ==================== 测试 ====================

if __name__ == '__main__':
    print('=== 长桥API数据获取工具测试 ===')
    print()
    
    # 检查环境变量
    if not os.getenv('LONGBRIDGE_APP_KEY'):
        print('⚠️ 请设置环境变量:')
        print('  export LONGBRIDGE_APP_KEY="your_app_key"')
        print('  export LONGBRIDGE_APP_SECRET="your_app_secret"')
        print()
        print('注意：没有配置的情况下，部分功能可能不可用')
        print()
    
    try:
        provider = LongbridgeDataProvider()
        
        # 测试1: 获取实时行情
        print('1. 测试获取实时行情（贵州茅台600519）')
        quote = provider.get_realtime_quote('600519', market='CN')
        if quote:
            print(f"  股票: {quote['name']} ({quote['code']})")
            print(f"  价格: ¥{quote['price']:.2f}")
            print(f"  涨跌: {quote['change_pct']:+.2f}%")
        else:
            print('  ⚠️ 未获取到数据（可能未配置API密钥）')
        
        print()
        
        # 测试2: 批量获取
        print('2. 测试批量获取（平安银行、招商银行）')
        quotes = provider.get_realtime_quotes(['000001', '600036'], market='CN')
        for q in quotes:
            print(f"  {q['name']}: ¥{q['price']:.2f} ({q['change_pct']:+.2f}%)")
        
        print()
        
        # 测试3: 检查交易时间
        print('3. 检查当前是否在A股交易时间')
        is_trading = provider.is_trading_time('CN')
        print(f"  交易时间: {'✅ 是' if is_trading else '❌ 否'}")
        
        print()
        print('=== 测试完成 ===')
        
    except Exception as e:
        print(f'❌ 测试失败: {e}')
