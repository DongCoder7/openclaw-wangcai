#!/usr/bin/env python3
"""
技术指标计算 - 使用本地日线数据
从daily_price表计算RSI、MACD等技术指标
"""

import sys
import os
import pandas as pd
import numpy as np
import sqlite3
from datetime import datetime

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
    
    # ATR
    df['tr1'] = df['high'] - df['low']
    df['tr2'] = abs(df['high'] - df['close'].shift())
    df['tr3'] = abs(df['low'] - df['close'].shift())
    df['tr'] = df[['tr1', 'tr2', 'tr3']].max(axis=1)
    df['atr_14'] = df['tr'].rolling(window=14, min_periods=1).mean()
    
    return df

def main():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    print("="*60)
    print("🚀 技术指标计算 - 使用本地日线数据")
    print("="*60)
    
    # 获取有估值因子的股票列表
    cursor.execute("SELECT DISTINCT ts_code FROM stock_valuation_factors ORDER BY ts_code")
    stocks = [row[0] for row in cursor.fetchall()]
    
    print(f"\n📋 共 {len(stocks)} 只股票需要处理\n")
    
    total_saved = 0
    update_time = datetime.now().isoformat()
    
    for i, ts_code in enumerate(stocks, 1):
        if i % 100 == 0 or i == 1:
            print(f"   进度: {i}/{len(stocks)} - 已保存 {total_saved} 条")
        
        try:
            # 从本地数据库获取日线数据
            df = pd.read_sql(f"""
                SELECT ts_code, trade_date, close, high, low 
                FROM daily_price 
                WHERE ts_code = '{ts_code}' 
                AND trade_date >= '20180101'
                ORDER BY trade_date
            """, conn)
            
            if len(df) < 30:
                continue
            
            # 计算技术指标
            df = calculate_technical(df)
            
            # 选择需要的列
            df = df[['ts_code', 'trade_date', 'close', 'rsi_14', 'macd', 
                     'macd_signal', 'macd_hist']].copy()
            
            # 批量插入
            for _, row in df.iterrows():
                cursor.execute("""
                    INSERT OR REPLACE INTO stock_technical_factors 
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (row['ts_code'], row['trade_date'], row['close'], 
                      row['rsi_14'], row['macd'], row['macd_signal'], 
                      row['macd_hist'], update_time))
            
            conn.commit()
            total_saved += len(df)
            
        except Exception as e:
            pass
    
    print(f"\n{'='*60}")
    print(f"✅ 技术指标计算完成!")
    print(f"   共保存 {total_saved} 条记录")
    print(f"{'='*60}\n")
    
    conn.close()

if __name__ == "__main__":
    main()
