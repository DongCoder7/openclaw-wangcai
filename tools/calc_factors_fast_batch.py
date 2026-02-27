#!/usr/bin/env python3
"""
批量快速计算stock_factors (2022-2024) - 优化版
使用纯SQL批量计算，速度更快
"""
import sqlite3
import pandas as pd
import numpy as np
from datetime import datetime
import sys

DB_PATH = '/root/.openclaw/workspace/data/historical/historical.db'
BATCH_SIZE = 500  # 每批处理500只股票

def log(msg):
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f"[{timestamp}] {msg}")
    sys.stdout.flush()

def process_batch(conn, stock_batch, batch_num, total_batches):
    """处理一批股票"""
    success = 0
    
    for ts_code in stock_batch:
        try:
            # 获取日线数据
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
            df['ret_120'] = df['close'].pct_change(120)
            df['vol_20'] = df['close'].rolling(20).std() / df['close'].rolling(20).mean()
            df['ma_20'] = df['close'].rolling(20).mean()
            df['ma_60'] = df['close'].rolling(60).mean()
            df['price_pos_20'] = (df['close'] - df['low'].rolling(20).min()) / (df['high'].rolling(20).max() - df['low'].rolling(20).min() + 0.001)
            df['price_pos_60'] = (df['close'] - df['low'].rolling(60).min()) / (df['high'].rolling(60).max() - df['low'].rolling(60).min() + 0.001)
            df['price_pos_high'] = (df['close'] - df['high'].rolling(120).max()) / df['close']
            df['vol_ratio'] = df['volume'] / df['volume'].rolling(20).mean()
            df['vol_ratio_amt'] = df['vol_ratio']
            df['money_flow'] = np.where(df['close'] > df['open'], df['volume'], -df['volume']).rolling(20).sum()
            df['rel_strength'] = (df['close'] - df['ma_20']) / df['ma_20']
            df['mom_accel'] = df['ret_20'] - df['ret_20'].shift(20)
            df['profit_mom'] = df['ret_20'].rolling(20).mean()
            
            # 准备保存
            df['ts_code'] = ts_code
            df_save = df[['ts_code', 'trade_date', 'ret_20', 'ret_60', 'ret_120', 'vol_20', 
                         'vol_ratio', 'vol_ratio_amt', 'ma_20', 'ma_60', 'price_pos_20', 
                         'price_pos_60', 'price_pos_high', 'money_flow', 'rel_strength', 
                         'mom_accel', 'profit_mom']].dropna()
            
            if len(df_save) == 0:
                continue
            
            # 删除旧数据并插入
            conn.execute("DELETE FROM stock_factors WHERE ts_code = ? AND trade_date BETWEEN '20220101' AND '20241231'", [ts_code])
            df_save.to_sql('stock_factors', conn, if_exists='append', index=False)
            success += 1
            
        except Exception as e:
            pass  # 跳过错误
    
    return success

def main():
    log("="*70)
    log("🚀 批量快速计算stock_factors (2022-2024) - 优化版")
    log("="*70)
    
    conn = sqlite3.connect(DB_PATH, timeout=60)
    
    # 获取股票列表
    stocks = [s[0] for s in conn.execute('SELECT DISTINCT ts_code FROM daily_price WHERE trade_date BETWEEN "20220101" AND "20241231"').fetchall()]
    log(f"需要处理的股票: {len(stocks)}只")
    
    # 分批处理
    total_success = 0
    batches = [stocks[i:i+BATCH_SIZE] for i in range(0, len(stocks), BATCH_SIZE)]
    
    for i, batch in enumerate(batches, 1):
        success = process_batch(conn, batch, i, len(batches))
        total_success += success
        log(f"批次 {i}/{len(batches)}: {success}/{len(batch)} 成功 | 累计: {total_success}/{len(stocks)}")
        
        # 每5批提交一次
        if i % 5 == 0:
            conn.commit()
            log(f"  -> 已提交到数据库")
    
    conn.commit()
    conn.close()
    
    log(f"\n{'='*70}")
    log(f"✅ 完成! 成功处理: {total_success}/{len(stocks)}")
    log(f"{'='*70}")

if __name__ == '__main__':
    main()
