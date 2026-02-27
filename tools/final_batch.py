#!/usr/bin/env python3
"""
最终轮补充 - 达到4,000+
"""
import sqlite3
import pandas as pd
import numpy as np
from datetime import datetime
import sys

DB_PATH = '/root/.openclaw/workspace/data/historical/historical.db'

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")
    sys.stdout.flush()

def main():
    log("="*70)
    log("🚀 最终轮补充 - 目标4,000+")
    log("="*70)
    
    conn = sqlite3.connect(DB_PATH, timeout=60)
    
    # 获取未处理的股票
    processed = set(s[0] for s in conn.execute('SELECT DISTINCT ts_code FROM stock_factors WHERE trade_date BETWEEN "20220101" AND "20241231"').fetchall())
    all_stocks = set(s[0] for s in conn.execute('SELECT DISTINCT ts_code FROM daily_price WHERE trade_date BETWEEN "20220101" AND "20241231"').fetchall())
    remaining = list(all_stocks - processed)
    
    log(f"剩余股票: {len(remaining)}只")
    log(f"预计最终: {len(processed) + len(remaining)}只")
    
    success = 0
    
    for i, ts_code in enumerate(remaining, 1):
        if i % 100 == 0:
            log(f"进度: {i}/{len(remaining)} | 成功: {success}")
            conn.commit()
        
        try:
            df = pd.read_sql_query('''
                SELECT trade_date, open, high, low, close, volume
                FROM daily_price
                WHERE ts_code = ? AND trade_date BETWEEN "20220101" AND "20241231"
                ORDER BY trade_date
            ''', conn, params=[ts_code])
            
            if len(df) < 60:
                continue
            
            # 计算因子
            df['ret_20'] = df['close'].pct_change(20)
            df['ret_60'] = df['close'].pct_change(60)
            df['vol_20'] = df['close'].rolling(20).std() / df['close'].rolling(20).mean()
            df['ma_20'] = df['close'].rolling(20).mean()
            df['price_pos_20'] = (df['close'] - df['low'].rolling(20).min()) / (df['high'].rolling(20).max() - df['low'].rolling(20).min() + 0.001)
            df['vol_ratio'] = df['volume'] / df['volume'].rolling(20).mean()
            
            df['ts_code'] = ts_code
            df_save = df[['ts_code', 'trade_date', 'ret_20', 'ret_60', 'vol_20', 'ma_20', 'price_pos_20', 'vol_ratio']].dropna()
            
            if len(df_save) > 0:
                df_save.to_sql('stock_factors', conn, if_exists='append', index=False)
                success += 1
            
        except Exception as e:
            pass
    
    conn.commit()
    conn.close()
    
    log(f"\n✅ 完成! 本次成功: {success}/{len(remaining)}")
    
    # 最终结果
    conn2 = sqlite3.connect(DB_PATH)
    count = conn2.execute('SELECT COUNT(DISTINCT ts_code) FROM stock_factors WHERE trade_date BETWEEN "20220101" AND "20241231"').fetchone()[0]
    log(f"2022-2024最终: {count}只股票")
    conn2.close()

if __name__ == '__main__':
    main()
