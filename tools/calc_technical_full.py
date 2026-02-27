#!/usr/bin/env python3
"""
技术指标全量补全 - 覆盖所有有估值因子的股票
补齐所有股票2018-2026年的技术指标
"""

import sys
import os
import pandas as pd
import sqlite3
from datetime import datetime
from concurrent.futures import ProcessPoolExecutor, as_completed
import multiprocessing

WORKSPACE = '/root/.openclaw/workspace'
DB_PATH = f'{WORKSPACE}/data/historical/historical.db'

def calculate_technical_for_stock(args):
    """计算单只股票的技术指标"""
    ts_code, db_path = args
    
    try:
        conn = sqlite3.connect(db_path)
        
        # 获取日线数据
        df = pd.read_sql(f"""
            SELECT ts_code, trade_date, close, high, low 
            FROM daily_price 
            WHERE ts_code='{ts_code}' AND trade_date >= '20180101'
            ORDER BY trade_date
        """, conn)
        
        if len(df) < 30:
            conn.close()
            return ts_code, 0
        
        # 计算技术指标
        df = df.sort_values('trade_date')
        
        # RSI_14
        delta = df['close'].diff()
        gain = delta.where(delta > 0, 0).rolling(window=14, min_periods=1).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14, min_periods=1).mean()
        rs = gain / loss
        df['rsi_14'] = 100 - (100 / (1 + rs))
        
        # MACD
        exp1 = df['close'].ewm(span=12, adjust=False).mean()
        exp2 = df['close'].ewm(span=26, adjust=False).mean()
        df['macd'] = exp1 - exp2
        df['macd_signal'] = df['macd'].ewm(span=9, adjust=False).mean()
        df['macd_hist'] = df['macd'] - df['macd_signal']
        
        # 保存到数据库
        df = df[['ts_code', 'trade_date', 'close', 'rsi_14', 'macd', 
                 'macd_signal', 'macd_hist']].copy()
        df['update_time'] = datetime.now().isoformat()
        
        cursor = conn.cursor()
        for _, row in df.iterrows():
            cursor.execute("""
                INSERT OR REPLACE INTO stock_technical_factors 
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (row['ts_code'], row['trade_date'], row['close'], 
                  row['rsi_14'], row['macd'], row['macd_signal'], 
                  row['macd_hist'], row['update_time']))
        
        conn.commit()
        conn.close()
        
        return ts_code, len(df)
        
    except Exception as e:
        return ts_code, 0

def main():
    conn = sqlite3.connect(DB_PATH)
    
    print("="*60)
    print("🚀 技术指标全量补全")
    print("="*60)
    
    # 获取所有有日线数据的股票
    df_stocks = pd.read_sql("""
        SELECT DISTINCT ts_code 
        FROM daily_price 
        WHERE trade_date >= '20180101'
    """, conn)
    
    stock_list = df_stocks['ts_code'].tolist()
    print(f"\n📋 共 {len(stock_list)} 只股票需要处理\n")
    
    conn.close()
    
    # 准备参数
    args_list = [(code, DB_PATH) for code in stock_list]
    
    # 多进程处理
    total_saved = 0
    completed = 0
    
    with ProcessPoolExecutor(max_workers=8) as executor:
        futures = {executor.submit(calculate_technical_for_stock, args): args[0] 
                   for args in args_list}
        
        for future in as_completed(futures):
            ts_code, count = future.result()
            completed += 1
            total_saved += count
            
            if completed % 100 == 0 or completed == len(stock_list):
                print(f"   进度: {completed}/{len(stock_list)} - 已保存 {total_saved} 条")
    
    print(f"\n{'='*60}")
    print(f"✅ 技术指标全量补全完成!")
    print(f"   共处理 {completed} 只股票")
    print(f"   共保存 {total_saved} 条记录")
    print(f"{'='*60}\n")

if __name__ == "__main__":
    main()
