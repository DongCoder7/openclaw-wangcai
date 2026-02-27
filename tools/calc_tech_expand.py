#!/usr/bin/env python3
"""
技术指标扩量 - 覆盖所有日线数据股票
从daily_price表重新计算技术指标
"""
import sys
import os
import pandas as pd
import sqlite3
from datetime import datetime
import numpy as np

WORKSPACE = '/root/.openclaw/workspace'
DB_PATH = f'{WORKSPACE}/data/historical/historical.db'

def calculate_technical(df):
    """计算技术指标"""
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
    
    return df

def main():
    print("="*60)
    print("🚀 技术指标扩量补全")
    print("="*60)
    
    conn = sqlite3.connect(DB_PATH)
    
    # 获取所有有日线数据的股票
    df_stocks = pd.read_sql("""
        SELECT DISTINCT ts_code 
        FROM daily_price 
        WHERE trade_date >= '20180101'
    """, conn)
    
    stock_list = df_stocks['ts_code'].tolist()
    print(f"📋 共 {len(stock_list)} 只股票需要处理\n")
    
    total_saved = 0
    
    for idx, ts_code in enumerate(stock_list):
        try:
            # 获取日线数据
            df = pd.read_sql(f"""
                SELECT ts_code, trade_date, close, high, low 
                FROM daily_price 
                WHERE ts_code='{ts_code}' AND trade_date >= '20180101'
                ORDER BY trade_date
            """, conn)
            
            if len(df) < 30:
                continue
            
            # 计算技术指标
            df = calculate_technical(df)
            
            # 保存到数据库
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
            
            if (idx + 1) % 100 == 0:
                print(f"   进度: {idx+1}/{len(stock_list)} - 已保存 {total_saved} 条")
                
        except Exception as e:
            print(f"   {ts_code} 错误: {e}")
            continue
    
    conn.close()
    
    print(f"\n{'='*60}")
    print(f"✅ 技术指标扩量完成!")
    print(f"   共处理 {len(stock_list)} 只股票")
    print(f"   共保存 {total_saved} 条记录")
    print(f"{'='*60}\n")

if __name__ == "__main__":
    main()
