#!/usr/bin/env python3
"""
分批次财务数据补充 - 每次处理500只
"""
import sqlite3
import pandas as pd
import time
import tushare as ts
from datetime import datetime

WORKSPACE = '/root/.openclaw/workspace'
DB_PATH = f'{WORKSPACE}/data/historical/historical.db'
LOG_PATH = f'{WORKSPACE}/reports/supplement_batch.log'
TS_TOKEN = 'cd2c935050381b52c9849eb054d1b198c21b0f29be2f025f9a9ece30'
BATCH_SIZE = 500  # 每批处理500只

def log(msg):
    line = f"[{datetime.now().strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    with open(LOG_PATH, 'a') as f:
        f.write(line + '\n')

def get_pending_stocks():
    """获取待处理的股票（未完整2024年数据的）"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT ts_code FROM stock_basic 
        WHERE ts_code NOT IN (
            SELECT DISTINCT ts_code FROM fina_tushare 
            WHERE period LIKE '2024%'
        )
        LIMIT ?
    """, (BATCH_SIZE,))
    stocks = [r[0] for r in cursor.fetchall()]
    
    # 获取总数
    cursor.execute("""
        SELECT COUNT(*) FROM stock_basic 
        WHERE ts_code NOT IN (
            SELECT DISTINCT ts_code FROM fina_tushare 
            WHERE period LIKE '2024%'
        )
    """)
    remaining = cursor.fetchone()[0]
    conn.close()
    return stocks, remaining

def supplement_batch(pro, stocks):
    """处理一批股票"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    fina_count = 0
    periods = ['20240331', '20240630', '20240930', '20241231',
               '20230331', '20230630', '20230930', '20231231',
               '20250331', '20250630', '20250930', '20251231']
    
    for i, ts_code in enumerate(stocks):
        if i % 50 == 0:
            log(f"  进度: {i}/{len(stocks)} | 财务:{fina_count}")
        
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
                time.sleep(0.06)
            except Exception as e:
                time.sleep(0.06)
        
        # 每10只提交一次
        if i % 10 == 0:
            conn.commit()
    
    conn.commit()
    conn.close()
    return fina_count

def main():
    with open(LOG_PATH, 'a') as f:
        f.write(f"\n[{datetime.now()}] 新批次开始\n")
    
    log("="*50)
    log("分批次财务数据补充")
    log("="*50)
    
    ts.set_token(TS_TOKEN)
    pro = ts.pro_api()
    
    stocks, remaining = get_pending_stocks()
    log(f"本批次处理: {len(stocks)}只, 剩余待处理: {remaining}只")
    
    if len(stocks) == 0:
        log("✅ 所有股票财务数据已补充完成!")
        return
    
    fina_count = supplement_batch(pro, stocks)
    
    log(f"✅ 本批次完成! 新增财务数据: {fina_count}条")
    log(f"剩余待处理: {remaining - len(stocks)}只")
    log("="*50)

if __name__ == '__main__':
    main()
