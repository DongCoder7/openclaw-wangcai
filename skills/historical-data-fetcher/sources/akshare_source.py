#!/usr/bin/env python3
"""
AKShare数据源实现
优点: 免费，数据全面，A股专业
缺点: 需要网络，偶有稳定性问题
"""
import pandas as pd
from typing import Optional, List
from datetime import datetime
from . import DataSource

class AKShareSource(DataSource):
    """AKShare数据源"""
    
    def __init__(self):
        super().__init__('akshare')
        self.test_connection()
    
    def test_connection(self) -> bool:
        """测试连接"""
        try:
            import akshare as ak
            # Try a simple request
            _ = ak.stock_zh_a_spot_em()
            self.available = True
            return True
        except Exception as e:
            print(f"AKShare test failed: {e}")
            self.available = False
            return False
    
    def _convert_code_to_akshare(self, code: str) -> str:
        """
        转换代码格式到AKShare格式
        000001.SZ -> 000001
        """
        if '.' in code:
            return code.split('.')[0]
        return code
    
    def get_stock_list(self) -> Optional[pd.DataFrame]:
        """获取A股列表"""
        if not self.available:
            return None
        
        try:
            import akshare as ak
            df = ak.stock_zh_a_spot_em()
            
            # Rename columns to standard format
            df = df.rename(columns={
                '代码': 'code',
                '名称': 'name',
                '最新价': 'price',
                '涨跌幅': 'change_pct',
            })
            
            # Add ts_code column
            df['ts_code'] = df['code'].apply(
                lambda x: x + '.SH' if x.startswith('6') else x + '.SZ'
            )
            
            return df[['ts_code', 'code', 'name', 'price', 'change_pct']]
            
        except Exception as e:
            print(f"Error fetching stock list: {e}")
            return None
    
    def get_daily_data(self, code: str, start: str, end: str) -> Optional[pd.DataFrame]:
        """
        获取日线数据
        
        Args:
            code: 股票代码 (如: 000001.SZ)
            start: 开始日期 (YYYYMMDD)
            end: 结束日期 (YYYYMMDD)
        
        Returns:
            DataFrame with columns: date, open, high, low, close, volume, amount
        """
        if not self.available:
            return None
        
        try:
            import akshare as ak
            
            symbol = self._convert_code_to_akshare(code)
            
            df = ak.stock_zh_a_hist(
                symbol=symbol,
                period="daily",
                start_date=start,
                end_date=end,
                adjust="qfq"  # 前复权
            )
            
            if df.empty:
                return None
            
            # Rename columns to standard format
            df = df.rename(columns={
                '日期': 'date',
                '开盘': 'open',
                '最高': 'high',
                '最低': 'low',
                '收盘': 'close',
                '成交量': 'volume',
                '成交额': 'amount',
                '振幅': 'amplitude',
                '涨跌幅': 'change_pct',
                '涨跌额': 'change',
                '换手率': 'turnover',
            })
            
            df['date'] = pd.to_datetime(df['date'])
            
            return df
            
        except Exception as e:
            print(f"Error fetching daily data: {e}")
            return None
    
    def get_fundamental_data(self, code: str) -> Optional[pd.DataFrame]:
        """
        获取基本面数据
        """
        if not self.available:
            return None
        
        try:
            import akshare as ak
            symbol = self._convert_code_to_akshare(code)
            
            # Get financial data
            df = ak.stock_financial_report_sina(stock=symbol, symbol="资产负债表")
            
            return df
            
        except Exception as e:
            print(f"Error fetching fundamental data: {e}")
            return None
    
    def get_all_stocks_daily(self, start: str, end: str, 
                            progress_callback=None) -> dict:
        """
        批量获取所有股票日线数据
        
        Args:
            start: 开始日期
            end: 结束日期
            progress_callback: 进度回调函数 (current, total, code)
        
        Returns:
            Dict mapping code to DataFrame
        """
        if not self.available:
            return {}
        
        # Get stock list
        stock_list = self.get_stock_list()
        if stock_list is None:
            return {}
        
        results = {}
        total = len(stock_list)
        
        for i, row in stock_list.iterrows():
            code = row['ts_code']
            
            try:
                df = self.get_daily_data(code, start, end)
                if df is not None:
                    results[code] = df
            except Exception as e:
                print(f"Error fetching {code}: {e}")
            
            if progress_callback:
                progress_callback(i + 1, total, code)
        
        return results


if __name__ == '__main__':
    # Test
    source = AKShareSource()
    print(f"AKShare available: {source.available}")
    
    if source.available:
        # Test stock list
        stocks = source.get_stock_list()
        if stocks is not None:
            print(f"\nTotal stocks: {len(stocks)}")
            print(stocks.head())
        
        # Test daily data
        df = source.get_daily_data('000001.SZ', '20240101', '20240131')
        if df is not None:
            print(f"\nFetched {len(df)} days")
            print(df.head())
