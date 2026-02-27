#!/usr/bin/env python3
"""
估值因子全量补全 - 补充2019-2024年数据
覆盖所有股票的估值数据
"""

import sys
import os
import pandas as pd
import sqlite3
from datetime import datetime
from concurrent.futures import ProcessPoolExecutor, as_completed

WORKSPACE = '/root/.openclaw/workspace'
DB_PATH = f'{WORKSPACE}/data/historical/historical.db'

def fetch_and_save_valuation(year):
    """获取并保存单年估值数据"""
    import tushare as ts
    
    # 从环境文件读取token
    token = ""
    env_file = f'{WORKSPACE}/.tushare.env'
    if os.path.exists(env_file):
        with open(env_file, 'r') as f:
            for line in f:
                if line.startswith('TUSHARE_TOKEN='):
                    token = line.split('=')[1].strip().strip('"')
                    break
    
    if not token:
        print(f"❌ 未找到Tushare token")
        return year, 0
    
    ts.set_token(token)
    pro = ts.pro_api()
    
    conn = sqlite3.connect(DB_PATH)
    
    try:
        # 获取该年所有交易日
        start_date = f'{year}0101'
        end_date = f'{year}1231'
        
        print(f"📅 处理 {year} 年数据...")
        
        # 获取交易日历
        df_cal = pro.trade_cal(exchange='SSE', start_date=start_date, end_date=end_date, is_open='1')
        trade_dates = df_cal['cal_date'].tolist()
        
        total_saved = 0
        
        for trade_date in trade_dates:
            try:
                # 获取当日所有股票估值数据
                df = pro.daily_basic(trade_date=trade_date)
                
                if df.empty:
                    continue
                
                # 选择需要的字段，添加pe和ps
                df = df[['ts_code', 'trade_date', 'pe', 'pe_ttm', 'pb', 'ps', 'ps_ttm', 
                         'dv_ratio', 'total_mv', 'circ_mv']].copy()
                
                # 处理空值
                df = df.fillna(0)
                
                # 保存到数据库
                cursor = conn.cursor()
                for _, row in df.iterrows():
                    cursor.execute("""
                        INSERT OR REPLACE INTO stock_valuation_factors 
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (row['ts_code'], str(row['trade_date']), 
                          float(row['pe']), float(row['pe_ttm']), 
                          float(row['pb']), float(row['ps']), float(row['ps_ttm']),
                          float(row['dv_ratio']), float(row['total_mv']), 
                          float(row['circ_mv']), datetime.now().isoformat()))
                
                conn.commit()
                total_saved += len(df)
                
                if int(trade_date) % 100 == 1:  # 每月1号打印进度
                    print(f"   {trade_date}: 已保存 {total_saved} 条")
                    
            except Exception as e:
                print(f"   {trade_date} 错误: {e}")
                continue
        
        conn.close()
        return year, total_saved
        
    except Exception as e:
        conn.close()
        return year, 0

def main():
    print("="*60)
    print("🚀 估值因子全量补全 (2019-2024)")
    print("="*60)
    
    years = [2019, 2020, 2021, 2022, 2023, 2024]
    
    # 串行处理（避免Tushare频率限制）
    total_records = 0
    for year in years:
        year, count = fetch_and_save_valuation(year)
        total_records += count
        print(f"✅ {year}年完成: {count} 条")
    
    print(f"\n{'='*60}")
    print(f"✅ 估值因子补全完成!")
    print(f"   共处理 {len(years)} 年")
    print(f"   共保存 {total_records} 条记录")
    print(f"{'='*60}\n")

if __name__ == "__main__":
    main()
