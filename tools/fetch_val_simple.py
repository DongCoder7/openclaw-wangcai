#!/usr/bin/env python3
"""
估值因子补全 - 从Tushare获取2019-2024年数据
"""
import os
import sys
import tushare as ts
import sqlite3
from datetime import datetime

WORKSPACE = '/root/.openclaw/workspace'
DB_PATH = f'{WORKSPACE}/data/historical/historical.db'

# 读取token
token = ""
with open(f'{WORKSPACE}/.tushare.env', 'r') as f:
    for line in f:
        if line.startswith('TUSHARE_TOKEN='):
            token = line.split('=')[1].strip().strip('"')
            break

ts.set_token(token)
pro = ts.pro_api()

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

years = [2019, 2020, 2021, 2022, 2023, 2024]
total = 0

for year in years:
    print(f"📅 处理 {year} 年...")
    start = f'{year}0101'
    end = f'{year}1231'
    
    try:
        df_cal = pro.trade_cal(exchange='SSE', start_date=start, end_date=end, is_open='1')
        dates = df_cal['cal_date'].tolist()
        
        year_total = 0
        for i, d in enumerate(dates):
            try:
                df = pro.daily_basic(trade_date=d)
                if df.empty:
                    continue
                
                for _, row in df.iterrows():
                    cursor.execute("""
                        INSERT OR REPLACE INTO stock_valuation_factors 
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (row['ts_code'], str(d), 
                          row.get('pe', 0), row.get('pe_ttm', 0),
                          row.get('pb', 0), row.get('ps', 0),
                          row.get('ps_ttm', 0), row.get('dv_ratio', 0),
                          row.get('total_mv', 0), row.get('circ_mv', 0),
                          datetime.now().isoformat()))
                conn.commit()
                year_total += len(df)
                
            except Exception as e:
                if '限制' not in str(e):
                    print(f"   {d} 错误: {e}")
                continue
        
        print(f"   {year}: {year_total} 条")
        total += year_total
        
    except Exception as e:
        print(f"   {year} 年错误: {e}")
        continue

conn.close()
print(f"\n✅ 完成! 共保存 {total} 条")
