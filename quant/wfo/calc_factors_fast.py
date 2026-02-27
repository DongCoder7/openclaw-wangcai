#!/usr/bin/env python3
"""
快速因子计算器 - 批量处理版
"""
import os
import sys
import sqlite3
import pandas as pd
import numpy as np
from datetime import datetime

DB_PATH = '/root/.openclaw/workspace/data/historical/historical.db'

# 连接数据库
conn = sqlite3.connect(DB_PATH)

print("="*70)
print("🚀 批量因子计算 (2018-2024)")
print("="*70)

# 获取所有股票
stocks = [r[0] for r in conn.execute('''
    SELECT DISTINCT ts_code FROM stock_efinance
    WHERE trade_date BETWEEN '20180101' AND '20241231'
''').fetchall()]

print(f"总股票数: {len(stocks)}")

# 分批处理
batch_size = 50
processed = 0
errors = 0

for batch_idx in range(0, len(stocks), batch_size):
    batch = stocks[batch_idx:batch_idx+batch_size]
    
    for ts_code in batch:
        try:
            # 获取价格数据
            df = pd.read_sql('''
                SELECT trade_date as date, close, volume, amount
                FROM stock_efinance
                WHERE ts_code = ? AND trade_date BETWEEN '20180101' AND '20241231'
                ORDER BY trade_date
            ''', conn, params=[ts_code])
            
            if len(df) < 120:
                continue
            
            # 计算因子
            df['ret_20'] = df['close'].pct_change(20)
            df['ret_60'] = df['close'].pct_change(60)
            df['ret_120'] = df['close'].pct_change(120)
            df['vol_20'] = df['close'].pct_change().rolling(20).std() * np.sqrt(252)
            df['vol_ratio'] = df['volume'] / df['volume'].rolling(20).mean()
            df['price_pos_20'] = (df['close'] - df['close'].rolling(20).min()) / (df['close'].rolling(20).max() - df['close'].rolling(20).min() + 1e-6)
            df['price_pos_60'] = (df['close'] - df['close'].rolling(60).min()) / (df['close'].rolling(60).max() - df['close'].rolling(60).min() + 1e-6)
            df['price_pos_high'] = df['close'] / df['close'].rolling(252).max()
            df['mom_accel'] = df['close'].pct_change(20) - df['close'].pct_change(20).shift(20)
            
            # 保存 (只保存有效数据)
            df_valid = df.dropna(subset=['ret_20', 'vol_20'])
            
            for _, row in df_valid.iterrows():
                try:
                    conn.execute('''
                        INSERT OR REPLACE INTO stock_factors
                        (ts_code, trade_date, ret_20, ret_60, ret_120, vol_20, vol_ratio,
                         price_pos_20, price_pos_60, price_pos_high, mom_accel)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        ts_code, row['date'],
                        row.get('ret_20'), row.get('ret_60'), row.get('ret_120'),
                        row.get('vol_20'), row.get('vol_ratio'),
                        row.get('price_pos_20'), row.get('price_pos_60'), row.get('price_pos_high'),
                        row.get('mom_accel')
                    ))
                except:
                    pass
            
            conn.commit()
            processed += 1
            
        except Exception as e:
            errors += 1
    
    # 进度报告
    if (batch_idx // batch_size + 1) % 10 == 0:
        print(f"进度: {processed}/{len(stocks)} 只处理完成, 错误: {errors}")

print(f"\n✅ 完成! 处理 {processed} 只股票, 错误 {errors}")
conn.close()
