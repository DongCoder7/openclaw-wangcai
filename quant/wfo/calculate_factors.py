#!/usr/bin/env python3
"""
因子数据补充器
用价格数据计算完整技术指标因子
"""
import os
import sys
import sqlite3
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

sys.path.insert(0, '/root/.openclaw/workspace')

DB_PATH = '/root/.openclaw/workspace/data/historical/historical.db'


class FactorCalculator:
    """从价格计算技术指标因子"""
    
    def __init__(self):
        self.conn = sqlite3.connect(DB_PATH)
        
    def __del__(self):
        if hasattr(self, 'conn'):
            self.conn.close()
    
    def get_price_data(self, ts_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        """获取价格数据"""
        # 优先从stock_efinance获取(2018-2021)
        df = pd.read_sql('''
            SELECT trade_date as date, close, volume, amount, change_pct
            FROM stock_efinance
            WHERE ts_code = ? AND trade_date BETWEEN ? AND ?
            ORDER BY trade_date
        ''', self.conn, params=[ts_code, start_date, end_date])
        
        if len(df) == 0:
            # 从daily_price获取(2022+)
            df = pd.read_sql('''
                SELECT trade_date as date, close, volume, amount, change_pct
                FROM daily_price
                WHERE ts_code = ? AND trade_date BETWEEN ? AND ?
                ORDER BY trade_date
            ''', self.conn, params=[ts_code, start_date, end_date])
        
        return df
    
    def calculate_factors(self, df: pd.DataFrame) -> pd.DataFrame:
        """计算技术指标因子"""
        if len(df) < 120:
            return None
        
        df = df.copy()
        df['date'] = pd.to_datetime(df['date'])
        df = df.sort_values('date')
        
        # 1. 收益率因子
        df['ret_5'] = df['close'].pct_change(5)
        df['ret_10'] = df['close'].pct_change(10)
        df['ret_20'] = df['close'].pct_change(20)
        df['ret_60'] = df['close'].pct_change(60)
        df['ret_120'] = df['close'].pct_change(120)
        
        # 2. 波动率因子
        df['vol_5'] = df['close'].pct_change().rolling(5).std() * np.sqrt(252)
        df['vol_10'] = df['close'].pct_change().rolling(10).std() * np.sqrt(252)
        df['vol_20'] = df['close'].pct_change().rolling(20).std() * np.sqrt(252)
        df['vol_60'] = df['close'].pct_change().rolling(60).std() * np.sqrt(252)
        df['vol_120'] = df['close'].pct_change().rolling(120).std() * np.sqrt(252)
        
        # 3. 价格位置因子
        df['price_pos_5'] = (df['close'] - df['close'].rolling(5).min()) / (df['close'].rolling(5).max() - df['close'].rolling(5).min() + 1e-6)
        df['price_pos_20'] = (df['close'] - df['close'].rolling(20).min()) / (df['close'].rolling(20).max() - df['close'].rolling(20).min() + 1e-6)
        df['price_pos_60'] = (df['close'] - df['close'].rolling(60).min()) / (df['close'].rolling(60).max() - df['close'].rolling(60).min() + 1e-6)
        df['price_pos_120'] = (df['close'] - df['close'].rolling(120).min()) / (df['close'].rolling(120).max() - df['close'].rolling(120).min() + 1e-6)
        df['price_pos_high'] = df['close'] / df['close'].rolling(252).max()
        
        # 4. 均线因子
        df['ma_5'] = df['close'].rolling(5).mean()
        df['ma_10'] = df['close'].rolling(10).mean()
        df['ma_20'] = df['close'].rolling(20).mean()
        df['ma_60'] = df['close'].rolling(60).mean()
        df['ma_120'] = df['close'].rolling(120).mean()
        
        # 5. 动量因子
        df['mom_5'] = df['close'] / df['close'].shift(5) - 1
        df['mom_10'] = df['close'] / df['close'].shift(10) - 1
        df['mom_20'] = df['close'] / df['close'].shift(20) - 1
        df['mom_accel'] = df['mom_20'] - df['mom_20'].shift(20)
        
        # 6. 量价因子
        df['vol_ratio'] = df['volume'] / df['volume'].rolling(20).mean()
        df['vol_ratio_amt'] = df['amount'] / df['amount'].rolling(20).mean()
        df['turnover_rate'] = df['volume'] / df['volume'].rolling(20).mean()
        
        # 7. 夏普类因子
        returns = df['close'].pct_change()
        df['sharpe_like'] = (returns.rolling(20).mean() * 252) / (returns.rolling(20).std() * np.sqrt(252) + 1e-6)
        
        # 8. 最大回撤因子
        rolling_max = df['close'].rolling(120).max()
        df['max_drawdown_120'] = (df['close'] - rolling_max) / rolling_max
        
        # 9. 相对强度 (对比市场)
        # 简化版: 使用涨跌幅
        df['rel_strength'] = df['change_pct'] if 'change_pct' in df.columns else 0
        
        # 10. 资金流向 (简化)
        df['money_flow'] = df['amount'] * np.where(df['close'] >= df['close'].shift(1), 1, -1)
        df['money_flow'] = df['money_flow'].rolling(20).sum()
        
        return df
    
    def save_factors_to_db(self, ts_code: str, df: pd.DataFrame):
        """保存计算好的因子到数据库"""
        if df is None or len(df) == 0:
            return
        
        # 选择需要保存的列
        factor_cols = [
            'date', 'ret_5', 'ret_10', 'ret_20', 'ret_60', 'ret_120',
            'vol_5', 'vol_10', 'vol_20', 'vol_60', 'vol_120',
            'price_pos_5', 'price_pos_20', 'price_pos_60', 'price_pos_120', 'price_pos_high',
            'mom_5', 'mom_10', 'mom_20', 'mom_accel',
            'vol_ratio', 'sharpe_like', 'max_drawdown_120',
            'rel_strength', 'money_flow'
        ]
        
        available_cols = [c for c in factor_cols if c in df.columns]
        df_save = df[available_cols].copy()
        df_save['ts_code'] = ts_code
        df_save['date'] = df_save['date'].dt.strftime('%Y%m%d')
        
        # 只保存有效数据 (去掉NaN过多的行)
        df_save = df_save.dropna(subset=['ret_20', 'vol_20'], how='any')
        
        if len(df_save) == 0:
            return
        
        # 保存到stock_factors表 (INSERT OR REPLACE)
        for _, row in df_save.iterrows():
            try:
                self.conn.execute('''
                    INSERT OR REPLACE INTO stock_factors (
                        ts_code, trade_date, ret_5, ret_10, ret_20, ret_60, ret_120,
                        vol_20, vol_ratio, price_pos_20, price_pos_60, price_pos_high,
                        mom_accel, sharpe_like, rel_strength, money_flow
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    row['ts_code'], row['date'],
                    row.get('ret_5'), row.get('ret_10'), row.get('ret_20'), 
                    row.get('ret_60'), row.get('ret_120'),
                    row.get('vol_20'), row.get('vol_ratio'),
                    row.get('price_pos_20'), row.get('price_pos_60'), row.get('price_pos_high'),
                    row.get('mom_accel'), row.get('sharpe_like'),
                    row.get('rel_strength'), row.get('money_flow')
                ))
            except Exception as e:
                pass
        
        self.conn.commit()
    
    def batch_calculate_factors(self, start_year: int = 2018, end_year: int = 2024):
        """批量计算因子"""
        print("="*70)
        print(f"🚀 批量计算因子 ({start_year}-{end_year})")
        print("="*70)
        
        # 获取股票列表
        stocks = self.conn.execute('''
            SELECT DISTINCT ts_code FROM stock_efinance
            WHERE trade_date BETWEEN ? AND ?
        ''', [f'{start_year}0101', f'{end_year}1231']).fetchall()
        
        stocks = [s[0] for s in stocks]
        print(f"总股票数: {len(stocks)}")
        
        # 分批处理
        batch_size = 100
        total_processed = 0
        
        for i in range(0, len(stocks), batch_size):
            batch = stocks[i:i+batch_size]
            print(f"\n处理批次 {i//batch_size + 1}/{(len(stocks)-1)//batch_size + 1}: {len(batch)}只股票")
            
            for ts_code in batch:
                try:
                    # 获取价格数据
                    df = self.get_price_data(ts_code, f'{start_year}0101', f'{end_year}1231')
                    
                    if len(df) < 120:
                        continue
                    
                    # 计算因子
                    df_factors = self.calculate_factors(df)
                    
                    if df_factors is not None:
                        # 保存
                        self.save_factors_to_db(ts_code, df_factors)
                        total_processed += 1
                        
                except Exception as e:
                    pass
            
            if (i // batch_size + 1) % 10 == 0:
                print(f"   已处理: {total_processed}只")
        
        print(f"\n✅ 完成! 共处理 {total_processed} 只股票")


if __name__ == '__main__':
    calc = FactorCalculator()
    
    # 计算2018-2024年的因子
    calc.batch_calculate_factors(2018, 2024)
    
    print("\n✅ 因子计算完成!")
