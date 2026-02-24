#!/usr/bin/env python3
"""
本地数据库数据源
优点: 快速，离线可用，已清洗
缺点: 需要预先填充数据
"""
import sqlite3
import pandas as pd
from typing import Optional, List
from datetime import datetime
from . import DataSource

DB_PATH = '/root/.openclaw/workspace/data/historical/historical.db'

class LocalSource(DataSource):
    """本地数据库数据源"""
    
    def __init__(self, db_path: str = DB_PATH):
        super().__init__('local')
        self.db_path = db_path
        self.test_connection()
    
    def test_connection(self) -> bool:
        """测试连接"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            conn.close()
            self.available = True
            return True
        except:
            self.available = False
            return False
    
    def get_daily_data(self, code: str, start: str, end: str) -> Optional[pd.DataFrame]:
        """
        从本地数据库获取日线数据
        
        Args:
            code: 股票代码 (如: 000001.SZ)
            start: 开始日期 (YYYYMMDD)
            end: 结束日期 (YYYYMMDD)
        
        Returns:
            DataFrame or None
        """
        if not self.available:
            return None
        
        try:
            conn = sqlite3.connect(self.db_path)
            
            # Try stock_factors table first
            query = f"""
            SELECT 
                trade_date as date,
                ma_20 as close,
                ret_20,
                ret_60,
                ret_120,
                vol_20,
                vol_ratio,
                price_pos_20,
                price_pos_60,
                money_flow,
                rel_strength,
                mom_accel,
                profit_mom
            FROM stock_factors
            WHERE ts_code = '{code}'
            AND trade_date BETWEEN '{start}' AND '{end}'
            ORDER BY trade_date
            """
            
            df = pd.read_sql(query, conn)
            conn.close()
            
            if df.empty:
                return None
            
            # Convert date
            df['date'] = pd.to_datetime(df['date'])
            
            return df
            
        except Exception as e:
            print(f"Error fetching from local DB: {e}")
            return None
    
    def get_stock_list(self) -> Optional[pd.DataFrame]:
        """获取本地股票列表"""
        if not self.available:
            return None
        
        try:
            conn = sqlite3.connect(self.db_path)
            
            query = """
            SELECT DISTINCT ts_code 
            FROM stock_factors
            ORDER BY ts_code
            """
            
            df = pd.read_sql(query, conn)
            conn.close()
            
            return df
            
        except Exception as e:
            print(f"Error fetching stock list: {e}")
            return None
    
    def get_latest_date(self) -> Optional[str]:
        """获取最新数据日期"""
        if not self.available:
            return None
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT MAX(trade_date) FROM stock_factors")
            result = cursor.fetchone()
            conn.close()
            return result[0] if result else None
        except:
            return None
    
    def get_date_coverage(self) -> dict:
        """获取数据覆盖情况"""
        if not self.available:
            return {}
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Overall coverage
            cursor.execute("""
                SELECT COUNT(DISTINCT ts_code), MIN(trade_date), MAX(trade_date), COUNT(*) 
                FROM stock_factors
            """)
            row = cursor.fetchone()
            
            # Coverage by date (recent)
            cursor.execute("""
                SELECT trade_date, COUNT(DISTINCT ts_code) as stock_count
                FROM stock_factors
                WHERE trade_date >= date('now', '-30 days')
                GROUP BY trade_date
                ORDER BY trade_date DESC
                LIMIT 10
            """)
            recent = cursor.fetchall()
            
            conn.close()
            
            return {
                'total_stocks': row[0],
                'start_date': row[1],
                'end_date': row[2],
                'total_records': row[3],
                'recent_coverage': recent
            }
            
        except Exception as e:
            print(f"Error getting coverage: {e}")
            return {}


if __name__ == '__main__':
    # Test
    source = LocalSource()
    print(f"Local DB available: {source.available}")
    
    if source.available:
        # Test stock list
        stocks = source.get_stock_list()
        if stocks is not None:
            print(f"\nTotal stocks: {len(stocks)}")
        
        # Test data coverage
        coverage = source.get_date_coverage()
        print(f"\nCoverage: {coverage.get('total_stocks')} stocks")
        print(f"Date range: {coverage.get('start_date')} to {coverage.get('end_date')}")
        
        # Test daily data
        df = source.get_daily_data('000001.SZ', '20240101', '20240131')
        if df is not None:
            print(f"\nFetched {len(df)} days for 000001.SZ")
            print(df.head())
