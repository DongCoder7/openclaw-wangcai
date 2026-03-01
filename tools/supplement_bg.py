#!/usr/bin/env python3
"""
财务和估值数据补充 - 后台运行版
"""
import sqlite3
import pandas as pd
import time
import tushare as ts
from datetime import datetime

WORKSPACE = '/root/.openclaw/workspace'
DB_PATH = f'{WORKSPACE}/data/historical/historical.db'
LOG_PATH = f'{WORKSPACE}/reports/supplement_bg.log'
TS_TOKEN = 'cd2c935050381b52c9849eb054d1b198c21b0f29be2f025f9a9ece30'

def log(msg):
    line = f"[{datetime.now().strftime('%H:%M:%S')}] {msg}"
    print(line)
    with open(LOG_PATH, 'a') as f:
        f.write(line + '\n')

def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute('''
        CREATE TABLE IF NOT EXISTS stock_fina_tushare (
            ts_code TEXT, year INTEGER, quarter INTEGER, report_date TEXT,
            roe REAL, netprofit_yoy REAL, revenue_yoy REAL, grossprofit_margin REAL,
            netprofit_margin REAL, debt_to_assets REAL, update_time TEXT,
            PRIMARY KEY (ts_code, year, quarter)
        )
    ''')
    conn.commit()
    conn.close()

def get_stock_list():
    conn = sqlite3.connect(DB_PATH)
    # 注意：列名是ts_code（不是中文）
    cursor = conn.cursor()
    cursor.execute("SELECT ts_code FROM stock_basic")
    stocks = [r[0] for r in cursor.fetchall()]
    conn.close()
    log(f"获取到 {len(stocks)} 只股票")
    return stocks

def supplement(pro, stocks):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    fina_count = 0
    val_count = 0
    years = [2023, 2024, 2025]
    quarters = [(3, '0930'), (6, '0630'), (9, '0930'), (12, '1231')]
    
    for i, ts_code in enumerate(stocks):
        if i % 100 == 0:
            log(f"进度: {i}/{len(stocks)} | 财务:{fina_count} 估值:{val_count}")
        
        # 财务数据 - 近年
        for year in years:
            for q, suffix in quarters:
                period = f"{year}{suffix}"
                try:
                    df = pro.fina_indicator(ts_code=ts_code, period=period,
                        fields='ts_code,roe,netprofit_yoy,revenue_yoy,grossprofit_margin,netprofit_margin,debt_to_assets')
                    if df is not None and not df.empty:
                        row = df.iloc[0]
                        cursor.execute('''
                            INSERT OR REPLACE INTO stock_fina_tushare 
                            VALUES (?,?,?,?,?,?,?,?,?,?,?)
                        ''', (ts_code, year, q, period, row.get('roe'), row.get('netprofit_yoy'),
                              row.get('revenue_yoy'), row.get('grossprofit_margin'), 
                              row.get('netprofit_margin'), row.get('debt_to_assets'), datetime.now().isoformat()))
                        fina_count += 1
                    time.sleep(0.05)
                except:
                    time.sleep(0.05)
        
        # 估值数据 - 2024-2025
        try:
            df = pro.daily_basic(ts_code=ts_code, start_date='20240101', end_date='20251231',
                                fields='ts_code,trade_date,pe,pb')
            if df is not None and not df.empty:
                for _, row in df.iterrows():
                    cursor.execute('''
                        INSERT OR REPLACE INTO stock_valuation VALUES (?,?,?,?,?)
                    ''', (ts_code, row['trade_date'], row.get('pe'), row.get('pb'), datetime.now().isoformat()))
                val_count += len(df)
            time.sleep(0.05)
        except:
            time.sleep(0.05)
    
    conn.commit()
    conn.close()
    return fina_count, val_count

def main():
    with open(LOG_PATH, 'w') as f:
        f.write(f"开始: {datetime.now()}\n")
    
    log("="*50)
    log("财务估值补充开始")
    log("="*50)
    
    init_db()
    ts.set_token(TS_TOKEN)
    pro = ts.pro_api()
    
    stocks = get_stock_list()
    fina, val = supplement(pro, stocks)
    
    log(f"✅ 完成! 财务:{fina}条 估值:{val}条")
    log(f"结束: {datetime.now()}")

if __name__ == '__main__':
    main()
