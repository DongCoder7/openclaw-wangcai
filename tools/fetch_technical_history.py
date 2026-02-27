#!/usr/bin/env python3
"""
技术指标历史数据回补 (2018-2026)
批量计算RSI、MACD等技术指标
"""

import sys
import os
import pandas as pd
import numpy as np
import sqlite3
from datetime import datetime, timedelta
import tushare as ts

WORKSPACE = '/root/.openclaw/workspace'
DB_PATH = f'{WORKSPACE}/data/historical/historical.db'

def init_tushare():
    token = ''
    env_file = f'{WORKSPACE}/.tushare.env'
    if os.path.exists(env_file):
        with open(env_file, 'r') as f:
            for line in f:
                if 'TUSHARE_TOKEN' in line and '=' in line:
                    token = line.split('=', 1)[1].strip().strip('"').strip("'")
    return ts.pro_api(token)

def calculate_technical_indicators(df):
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
    pro = init_tushare()
    conn = sqlite3.connect(DB_PATH)
    
    print("="*60)
    print("🚀 技术指标历史数据回补 (2018-2026)")
    print("="*60)
    
    # 获取股票列表（优先处理有估值因子的股票）
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT ts_code FROM stock_valuation_factors ORDER BY ts_code")
    stocks = [row[0] for row in cursor.fetchall()]
    
    print(f"\n📋 共 {len(stocks)} 只股票需要处理")
    print(f"   预估数据量: {len(stocks)} * ~1500天 = ~{len(stocks)*1500/10000:.0f}万条\n")
    
    total_saved = 0
    update_time = datetime.now().isoformat()
    
    for i, ts_code in enumerate(stocks, 1):
        if i % 100 == 0 or i == 1:
            print(f"   进度: {i}/{len(stocks)} - 已保存 {total_saved} 条")
        
        try:
            # 获取2018-2026日线数据
            df = pro.daily(ts_code=ts_code, start_date='20180101', end_date='20260226')
            if df is None or len(df) < 30:
                continue
            
            # 计算技术指标
            df = calculate_technical_indicators(df)
            
            # 选择需要的列
            df = df[['ts_code', 'trade_date', 'close', 'rsi_14', 'macd', 
                     'macd_signal', 'macd_hist', 'atr_14']].copy()
            df['update_time'] = update_time
            
            # 批量插入
            for _, row in df.iterrows():
                cursor.execute("""
                    INSERT OR REPLACE INTO stock_technical_factors 
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (row['ts_code'], row['trade_date'], row['close'], 
                      row['rsi_14'], row['macd'], row['macd_signal'], 
                      row['macd_hist'], row['atr_14'], row['update_time']))
            
            conn.commit()
            total_saved += len(df)
            
        except Exception as e:
            pass
    
    print(f"\n{'='*60}")
    print(f"✅ 技术指标回补完成!")
    print(f"   共保存 {total_saved} 条记录")
    print(f"{'='*60}\n")
    
    conn.close()

if __name__ == "__main__":
    main()
