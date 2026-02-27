#!/usr/bin/env python3
"""
高效历史因子回补 - 按年批量处理
快速补充2018-2026年数据
"""

import sys
import os
import pandas as pd
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

def create_tables(conn):
    """创建表"""
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS stock_valuation_factors (
        ts_code TEXT,
        trade_date TEXT,
        pe REAL,
        pe_ttm REAL,
        pb REAL,
        ps REAL,
        ps_ttm REAL,
        dv_ratio REAL,
        total_mv REAL,
        circ_mv REAL,
        update_time TEXT,
        PRIMARY KEY (ts_code, trade_date)
    )
    """)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS stock_technical_factors (
        ts_code TEXT,
        trade_date TEXT,
        close REAL,
        rsi_14 REAL,
        macd REAL,
        macd_signal REAL,
        macd_hist REAL,
        atr_14 REAL,
        update_time TEXT,
        PRIMARY KEY (ts_code, trade_date)
    )
    """)
    conn.commit()

def get_trade_dates(pro, start_date, end_date):
    """获取交易日"""
    try:
        df = pro.trade_cal(exchange='SSE', start_date=start_date, end_date=end_date, is_open='1')
        return df['cal_date'].tolist()
    except:
        return []

def fetch_year_valuation(pro, conn, year):
    """按年获取估值因子"""
    print(f"\n📊 处理 {year} 年...")
    
    start_date = f"{year}0101"
    end_date = f"{year}1231"
    
    trade_dates = get_trade_dates(pro, start_date, end_date)
    print(f"   交易日: {len(trade_dates)} 天")
    
    total = 0
    cursor = conn.cursor()
    update_time = datetime.now().isoformat()
    
    for i, date in enumerate(trade_dates):
        if (i + 1) % 50 == 0:
            print(f"   进度: {i+1}/{len(trade_dates)}")
        
        try:
            df = pro.daily_basic(trade_date=date)
            if df is None or df.empty:
                continue
            
            cols = ['ts_code', 'trade_date', 'pe', 'pe_ttm', 'pb', 'ps', 'ps_ttm', 'dv_ratio', 'total_mv', 'circ_mv']
            df = df[[c for c in cols if c in df.columns]].copy()
            
            for _, row in df.iterrows():
                cursor.execute("""
                    INSERT OR REPLACE INTO stock_valuation_factors 
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (row['ts_code'], row['trade_date'], 
                      row.get('pe'), row.get('pe_ttm'), row.get('pb'),
                      row.get('ps'), row.get('ps_ttm'), row.get('dv_ratio'),
                      row.get('total_mv'), row.get('circ_mv'), update_time))
            total += len(df)
            conn.commit()
            
        except Exception as e:
            pass
    
    print(f"   ✅ {year}年完成: {total} 条")
    return total

def main():
    """主函数"""
    pro = init_tushare()
    conn = sqlite3.connect(DB_PATH)
    
    print("="*60)
    print("🚀 高效历史因子回补 (2018-2026)")
    print("="*60)
    
    # 创建表
    create_tables(conn)
    
    # 检查当前数据
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM stock_valuation_factors")
    current = cursor.fetchone()[0]
    print(f"\n当前数据: {current} 条\n")
    
    # 按年回补
    total_all = 0
    for year in range(2018, 2027):
        count = fetch_year_valuation(pro, conn, year)
        total_all += count
    
    print(f"\n{'='*60}")
    print(f"✅ 全部完成! 共添加 {total_all} 条估值因子")
    print(f"   总计: {current + total_all} 条")
    print(f"{'='*60}\n")
    
    conn.close()

if __name__ == "__main__":
    main()
