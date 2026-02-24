#!/usr/bin/env python3
"""
获取全市场因子数据
用于构建多因子模型所需的数据
"""
import sys
import argparse
import json
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, '/root/.openclaw/workspace/skills/historical-data-fetcher')

from sources.local_source import LocalSource
from sources.tencent_source import TencentSource

DB_PATH = '/root/.openclaw/workspace/data/historical/historical.db'


class FactorDataFetcher:
    """因子数据获取器"""
    
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self.local = LocalSource(db_path)
        self.tencent = TencentSource()
        self.conn = sqlite3.connect(db_path)
    
    def get_latest_data_summary(self) -> dict:
        """获取最新数据概况"""
        cursor = self.conn.cursor()
        
        # Latest date
        cursor.execute("SELECT MAX(trade_date) FROM stock_factors")
        latest = cursor.fetchone()[0]
        
        # Stock count
        cursor.execute(f"SELECT COUNT(DISTINCT ts_code) FROM stock_factors WHERE trade_date = '{latest}'")
        count = cursor.fetchone()[0]
        
        # Available factors
        cursor.execute("PRAGMA table_info(stock_factors)")
        columns = [row[1] for row in cursor.fetchall() if row[1] not in ['ts_code', 'trade_date']]
        
        return {
            'latest_date': latest,
            'stock_count': count,
            'available_factors': columns,
            'factor_count': len(columns)
        }
    
    def fetch_from_tencent(self, batch_size: int = 100) -> dict:
        """从腾讯API获取全市场实时数据"""
        if not self.tencent.available:
            return {'error': 'Tencent API not available'}
        
        # Get stock list
        cursor = self.conn.cursor()
        cursor.execute("SELECT DISTINCT ts_code FROM stock_factors")
        codes = [row[0] for row in cursor.fetchall()]
        
        print(f"Fetching {len(codes)} stocks from Tencent API...")
        
        results = []
        errors = []
        
        for i in range(0, len(codes), batch_size):
            batch = codes[i:i+batch_size]
            
            try:
                df = self.tencent.get_realtime_quotes(batch)
                if df is not None:
                    results.append(df)
                    
                if (i // batch_size + 1) % 10 == 0:
                    print(f"  Progress: {min(i+batch_size, len(codes))}/{len(codes)}")
                    
            except Exception as e:
                errors.append(f"Batch {i//batch_size}: {e}")
        
        if results:
            combined = pd.concat(results, ignore_index=True)
            return {
                'success': True,
                'records': len(combined),
                'data': combined,
                'errors': errors
            }
        else:
            return {
                'success': False,
                'error': 'No data fetched',
                'errors': errors
            }
    
    def calculate_factors(self, price_data: dict) -> dict:
        """
        从价格数据计算因子
        
        Input: {code: DataFrame with price data}
        Output: {code: {factor_name: value}}
        """
        import pandas as pd
        import numpy as np
        
        factors = {}
        
        for code, df in price_data.items():
            if df is None or len(df) < 20:
                continue
            
            try:
                # Ensure sorted by date
                df = df.sort_values('date')
                
                # Calculate factors
                factor_values = {}
                
                # Returns
                factor_values['ret_5'] = df['close'].pct_change(5).iloc[-1]
                factor_values['ret_20'] = df['close'].pct_change(20).iloc[-1]
                factor_values['ret_60'] = df['close'].pct_change(60).iloc[-1] if len(df) >= 60 else np.nan
                
                # Volatility
                factor_values['vol_20'] = df['close'].pct_change().rolling(20).std().iloc[-1]
                
                # Moving averages
                factor_values['ma_20'] = df['close'].rolling(20).mean().iloc[-1]
                factor_values['ma_60'] = df['close'].rolling(60).mean().iloc[-1] if len(df) >= 60 else np.nan
                
                # Price position
                high_20 = df['high'].rolling(20).max().iloc[-1]
                low_20 = df['low'].rolling(20).min().iloc[-1]
                if high_20 > low_20:
                    factor_values['price_pos_20'] = (df['close'].iloc[-1] - low_20) / (high_20 - low_20)
                else:
                    factor_values['price_pos_20'] = 0.5
                
                # Volume ratio
                vol_ma_20 = df['volume'].rolling(20).mean().iloc[-1]
                if vol_ma_20 > 0:
                    factor_values['vol_ratio'] = df['volume'].iloc[-1] / vol_ma_20
                else:
                    factor_values['vol_ratio'] = 1.0
                
                # Money flow (simplified)
                factor_values['money_flow'] = np.sign(df['close'].iloc[-1] - df['open'].iloc[-1]) * df['volume'].iloc[-1]
                
                # Relative strength
                if factor_values['ma_20'] > 0:
                    factor_values['rel_strength'] = (df['close'].iloc[-1] / factor_values['ma_20']) - 1
                else:
                    factor_values['rel_strength'] = 0
                
                factors[code] = factor_values
                
            except Exception as e:
                print(f"Error calculating factors for {code}: {e}")
                continue
        
        return factors
    
    def save_factors_to_db(self, factors: dict, trade_date: str):
        """保存因子到数据库"""
        cursor = self.conn.cursor()
        
        inserted = 0
        for code, factor_values in factors.items():
            try:
                # Build insert query
                columns = ['ts_code', 'trade_date'] + list(factor_values.keys())
                placeholders = ['?'] * len(columns)
                
                query = f"""
                    INSERT OR REPLACE INTO stock_factors 
                    ({', '.join(columns)}) 
                    VALUES ({', '.join(placeholders)})
                """
                
                values = [code, trade_date] + list(factor_values.values())
                cursor.execute(query, values)
                inserted += 1
                
            except Exception as e:
                print(f"Error saving {code}: {e}")
        
        self.conn.commit()
        print(f"Saved {inserted} records to database")
        return inserted
    
    def close(self):
        """关闭连接"""
        self.conn.close()


def main():
    parser = argparse.ArgumentParser(description='Fetch factor data')
    parser.add_argument('--source', type=str, default='local', choices=['local', 'tencent', 'all'])
    parser.add_argument('--summary', action='store_true', help='Show data summary')
    parser.add_argument('--fetch-tencent', action='store_true', help='Fetch from Tencent API')
    parser.add_argument('--batch-size', type=int, default=100, help='Batch size for Tencent')
    
    args = parser.parse_args()
    
    fetcher = FactorDataFetcher()
    
    if args.summary:
        summary = fetcher.get_latest_data_summary()
        print("=" * 60)
        print("FACTOR DATA SUMMARY")
        print("=" * 60)
        print(f"Latest Date: {summary['latest_date']}")
        print(f"Stock Count: {summary['stock_count']}")
        print(f"Factor Count: {summary['factor_count']}")
        print(f"\nAvailable Factors:")
        for i, factor in enumerate(summary['available_factors'], 1):
            print(f"  {i:2d}. {factor}")
        print("=" * 60)
    
    if args.fetch_tencent:
        result = fetcher.fetch_from_tencent(args.batch_size)
        if result.get('success'):
            print(f"\n✅ Fetched {result['records']} records from Tencent")
            if 'data' in result:
                df = result['data']
                print(f"\nColumns: {list(df.columns)}")
                print(f"\nSample data:")
                print(df.head())
        else:
            print(f"\n❌ Failed: {result.get('error')}")
    
    fetcher.close()


if __name__ == '__main__':
    import pandas as pd
    import numpy as np
    main()
