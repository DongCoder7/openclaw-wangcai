#!/usr/bin/env python3
"""
技术指标扩量 - 分批处理避免锁定
"""
import sys
import os
import pandas as pd
import sqlite3
from datetime import datetime
import numpy as np
import time

WORKSPACE = '/root/.openclaw/workspace'
DB_PATH = f'{WORKSPACE}/data/historical/historical.db'

def calculate_technical(df):
    """计算技术指标"""
    df = df.sort_values('trade_date')
    
    # RSI_14
    delta = df['close'].diff()
    gain = delta.where(delta > 0, 0).rolling(window=14, min_periods=1).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14, min_periods=1).mean()
    rs = gain / (loss + 0.0001)
    df['rsi_14'] = 100 - (100 / (1 + rs))
    
    # MACD
    exp1 = df['close'].ewm(span=12, adjust=False).mean()
    exp2 = df['close'].ewm(span=26, adjust=False).mean()
    df['macd'] = exp1 - exp2
    df['macd_signal'] = df['macd'].ewm(span=9, adjust=False).mean()
    df['macd_hist'] = df['macd'] - df['macd_signal']
    
    return df

def process_batch(stock_codes, batch_id):
    """处理一批股票"""
    conn = sqlite3.connect(DB_PATH)
    total_saved = 0
    
    for ts_code in stock_codes:
        try:
            df = pd.read_sql(f"""
                SELECT ts_code, trade_date, close, high, low 
                FROM daily_price 
                WHERE ts_code='{ts_code}' AND trade_date >= '20180101'
                ORDER BY trade_date
            """, conn)
            
            if len(df) < 30:
                continue
            
            df = calculate_technical(df)
            
            cursor = conn.cursor()
            for _, row in df.iterrows():
                cursor.execute("""
                    INSERT OR REPLACE INTO stock_technical_factors 
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (row['ts_code'], row['trade_date'], row['close'], 
                      row['rsi_14'], row['macd'], row['macd_signal'], 
                      row['macd_hist'], datetime.now().isoformat()))
            
            conn.commit()
            total_saved += len(df)
            
        except Exception as e:
            print(f"   {ts_code} 错误: {e}")
            continue
    
    conn.close()
    return batch_id, total_saved

def main():
    print("="*60)
    print("🚀 技术指标扩量补全 (分批版)")
    print("="*60)
    
    # 先获取股票列表
    conn = sqlite3.connect(DB_PATH)
    df_stocks = pd.read_sql("""
        SELECT DISTINCT ts_code 
        FROM daily_price 
        WHERE trade_date >= '20180101'
    """, conn)
    conn.close()
    
    stock_list = df_stocks['ts_code'].tolist()
    print(f"📋 共 {len(stock_list)} 只股票需要处理\n")
    
    # 分批处理，每批500只
    batch_size = 500
    batches = [stock_list[i:i+batch_size] for i in range(0, len(stock_list), batch_size)]
    
    total_saved = 0
    for i, batch in enumerate(batches):
        print(f"   处理第 {i+1}/{len(batches)} 批 ({len(batch)} 只)...")
        _, saved = process_batch(batch, i+1)
        total_saved += saved
        print(f"   累计保存: {total_saved} 条")
        time.sleep(1)  # 避免锁定
    
    print(f"\n{'='*60}")
    print(f"✅ 技术指标扩量完成!")
    print(f"   共处理 {len(stock_list)} 只股票")
    print(f"   共保存 {total_saved} 条记录")
    print(f"{'='*60}\n")

if __name__ == "__main__":
    main()
