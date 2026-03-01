#!/usr/bin/env python3
"""
财务和估值数据补充 - 修复版
匹配实际表结构
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
    print(line, flush=True)
    with open(LOG_PATH, 'a') as f:
        f.write(line + '\n')

def get_stock_list():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    # 获取未处理的股票
    cursor.execute("""
        SELECT ts_code FROM stock_basic 
        WHERE ts_code NOT IN (SELECT DISTINCT ts_code FROM fina_tushare WHERE period LIKE '2024%')
    """)
    stocks = [r[0] for r in cursor.fetchall()]
    conn.close()
    log(f"待处理股票: {len(stocks)} 只")
    return stocks

def supplement(pro, stocks):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    fina_count = 0
    val_count = 0
    
    # 财务数据周期：2023-2025年，每季度
    periods = []
    for year in [2023, 2024, 2025]:
        for suffix in ['0331', '0630', '0930', '1231']:
            periods.append(f"{year}{suffix}")
    
    for i, ts_code in enumerate(stocks):
        if i % 100 == 0:
            log(f"进度: {i}/{len(stocks)} | 财务:{fina_count} 估值:{val_count}")
            conn.commit()  # 定期提交
        
        # 财务数据 - 写入 fina_tushare 表
        for period in periods:
            try:
                df = pro.fina_indicator(ts_code=ts_code, period=period,
                    fields='ts_code,roe,roe_waa,roe_dt,roa,roic,netprofit_yoy,dt_netprofit_yoy,revenue_yoy,grossprofit_margin,netprofit_margin,assets_turn,op_yoy,debt_to_assets,current_ratio')
                if df is not None and not df.empty:
                    row = df.iloc[0]
                    cursor.execute('''
                        INSERT OR REPLACE INTO fina_tushare 
                        (ts_code, period, roe, roe_waa, roe_dt, roa, roic, 
                         netprofit_yoy, dt_netprofit_yoy, revenue_yoy, 
                         grossprofit_margin, netprofit_margin, assets_turn, op_yoy, 
                         debt_to_assets, current_ratio, update_time)
                        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    ''', (
                        ts_code, period, row.get('roe'), row.get('roe_waa'), row.get('roe_dt'),
                        row.get('roa'), row.get('roic'), row.get('netprofit_yoy'), 
                        row.get('dt_netprofit_yoy'), row.get('revenue_yoy'),
                        row.get('grossprofit_margin'), row.get('netprofit_margin'),
                        row.get('assets_turn'), row.get('op_yoy'), row.get('debt_to_assets'),
                        row.get('current_ratio'), datetime.now().isoformat()
                    ))
                    fina_count += 1
                time.sleep(0.06)  # API限速
            except Exception as e:
                time.sleep(0.06)
        
        # 估值数据 - 写入 stock_valuation 表（2024-2025）
        try:
            df = pro.daily_basic(ts_code=ts_code, start_date='20240101', end_date='20251231',
                                fields='ts_code,trade_date,pe,pb')
            if df is not None and not df.empty:
                for _, row in df.iterrows():
                    # 检查是否已存在
                    cursor.execute("SELECT 1 FROM stock_valuation WHERE ts_code=? AND trade_date=?", 
                                  (ts_code, row['trade_date']))
                    if cursor.fetchone() is None:
                        cursor.execute('''
                            INSERT INTO stock_valuation (ts_code, trade_date, pe, pb)
                            VALUES (?,?,?,?)
                        ''', (ts_code, row['trade_date'], row.get('pe'), row.get('pb')))
                        val_count += 1
            time.sleep(0.06)
        except Exception as e:
            time.sleep(0.06)
    
    conn.commit()
    conn.close()
    return fina_count, val_count

def main():
    with open(LOG_PATH, 'w') as f:
        f.write(f"开始: {datetime.now()}\n")
    
    log("="*50)
    log("财务估值补充开始")
    log("="*50)
    
    ts.set_token(TS_TOKEN)
    pro = ts.pro_api()
    
    stocks = get_stock_list()
    fina, val = supplement(pro, stocks)
    
    log(f"✅ 完成! 财务:{fina}条 估值:{val}条")
    log(f"结束: {datetime.now()}")

if __name__ == '__main__':
    main()
