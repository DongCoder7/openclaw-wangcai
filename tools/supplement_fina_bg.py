#!/usr/bin/env python3
"""
后台财务和估值数据补充脚本
后台运行，记录日志到文件
"""
import sqlite3
import pandas as pd
import time
import tushare as ts
from datetime import datetime
import sys

WORKSPACE = '/root/.openclaw/workspace'
DB_PATH = f'{WORKSPACE}/data/historical/historical.db'
LOG_PATH = f'{WORKSPACE}/reports/supplement_fina_bg.log'
TS_TOKEN = 'cd2c935050381b52c9849eb054d1b198c21b0f29be2f025f9a9ece30'

def log(msg):
    line = f"[{datetime.now().strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    with open(LOG_PATH, 'a') as f:
        f.write(line + '\n')

# ============================================
# 财务因子补充
# ============================================

def create_fina_table():
    conn = sqlite3.connect(DB_PATH)
    conn.execute('''
        CREATE TABLE IF NOT EXISTS stock_fina_tushare (
            ts_code TEXT, year INTEGER, quarter INTEGER, report_date TEXT,
            roe REAL, roe_diluted REAL, roe_avg REAL,
            netprofit_yoy REAL, dt_netprofit_yoy REAL, revenue_yoy REAL,
            grossprofit_margin REAL, netprofit_margin REAL, assets_turn REAL,
            op_yoy REAL, ebit_yoy REAL, debt_to_assets REAL,
            current_ratio REAL, quick_ratio REAL, update_time TEXT,
            PRIMARY KEY (ts_code, year, quarter)
        )
    ''')
    conn.commit()
    conn.close()

def get_fina_for_stock(pro, ts_code, years, quarters):
    """获取单只股票多年的财务数据"""
    records = []
    for year in years:
        for q in quarters:
            period = f"{year}{q:02d}01"
            try:
                df = pro.fina_indicator(ts_code=ts_code, period=period, 
                    fields='ts_code,roe,roe_diluted,roe_avg,netprofit_yoy,dt_netprofit_yoy,revenue_yoy,grossprofit_margin,netprofit_margin,assets_turn,op_yoy,ebit_yoy,debt_to_assets,current_ratio,quick_ratio')
                if df is not None and not df.empty:
                    row = df.iloc[0]
                    records.append({
                        'ts_code': ts_code, 'year': year, 'quarter': q, 'report_date': period,
                        'roe': row.get('roe'), 'roe_diluted': row.get('roe_diluted'), 'roe_avg': row.get('roe_avg'),
                        'netprofit_yoy': row.get('netprofit_yoy'), 'dt_netprofit_yoy': row.get('dt_netprofit_yoy'),
                        'revenue_yoy': row.get('revenue_yoy'), 'grossprofit_margin': row.get('grossprofit_margin'),
                        'netprofit_margin': row.get('netprofit_margin'), 'assets_turn': row.get('assets_turn'),
                        'op_yoy': row.get('op_yoy'), 'ebit_yoy': row.get('ebit_yoy'),
                        'debt_to_assets': row.get('debt_to_assets'), 'current_ratio': row.get('current_ratio'),
                        'quick_ratio': row.get('quick_ratio'), 'update_time': datetime.now().isoformat()
                    })
                time.sleep(0.1)
            except Exception as e:
                time.sleep(0.1)
    return records

def supplement_fina():
    log("="*50)
    log("开始补充财务因子 (2018-2025)")
    log("="*50)
    
    create_fina_table()
    ts.set_token(TS_TOKEN)
    pro = ts.pro_api()
    conn = sqlite3.connect(DB_PATH)
    
    # 获取需要补充的股票
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT ts_code FROM stock_basic")
    stocks = [r[0] for r in cursor.fetchall()]
    
    # 获取已有数据
    cursor.execute("SELECT COUNT(*) FROM stock_fina_tushare")
    existing = cursor.fetchone()[0]
    log(f"已有财务数据: {existing}条, 待处理股票: {len(stocks)}只")
    
    years = list(range(2018, 2026))
    quarters = [3, 6, 9, 12]
    
    total_records = 0
    for i, ts_code in enumerate(stocks):
        if i % 100 == 0:
            log(f"进度: {i}/{len(stocks)} | 累计: {total_records}条")
            conn.commit()
        
        records = get_fina_for_stock(pro, ts_code, years, quarters)
        for r in records:
            cursor.execute('''
                INSERT OR REPLACE INTO stock_fina_tushare 
                (ts_code,year,quarter,report_date,roe,roe_diluted,roe_avg,netprofit_yoy,dt_netprofit_yoy,
                 revenue_yoy,grossprofit_margin,netprofit_margin,assets_turn,op_yoy,ebit_yoy,debt_to_assets,
                 current_ratio,quick_ratio,update_time)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ''', tuple(r.values()))
        total_records += len(records)
    
    conn.commit()
    conn.close()
    log(f"✅ 财务因子完成! 新增: {total_records}条")

# ============================================
# 估值因子补充
# ============================================

def create_val_table():
    conn = sqlite3.connect(DB_PATH)
    conn.execute('''
        CREATE TABLE IF NOT EXISTS stock_fina (
            ts_code TEXT, report_date TEXT, pe_ttm REAL, pb REAL, update_time TEXT,
            PRIMARY KEY (ts_code, report_date)
        )
    ''')
    conn.commit()
    conn.close()

def supplement_valuation():
    log("="*50)
    log("开始补充估值因子 (PE, PB)")
    log("="*50)
    
    create_val_table()
    ts.set_token(TS_TOKEN)
    pro = ts.pro_api()
    conn = sqlite3.connect(DB_PATH)
    
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT ts_code FROM stock_basic")
    stocks = [r[0] for r in cursor.fetchall()]
    
    cursor.execute("SELECT COUNT(*) FROM stock_fina")
    existing = cursor.fetchone()[0]
    log(f"已有估值数据: {existing}条, 待处理股票: {len(stocks)}只")
    
    total_records = 0
    for i, ts_code in enumerate(stocks):
        if i % 50 == 0:
            log(f"进度: {i}/{len(stocks)} | 累计: {total_records}条")
            conn.commit()
        
        try:
            df = pro.daily_basic(ts_code=ts_code, start_date='20180101', end_date='20251231',
                                fields='ts_code,trade_date,pe,pb')
            if df is not None and not df.empty:
                for _, row in df.iterrows():
                    cursor.execute('''
                        INSERT OR REPLACE INTO stock_fina (ts_code, report_date, pe_ttm, pb, update_time)
                        VALUES (?, ?, ?, ?, ?)
                    ''', (ts_code, row['trade_date'], row.get('pe'), row.get('pb'), datetime.now().isoformat()))
                total_records += len(df)
            time.sleep(0.1)
        except Exception as e:
            time.sleep(0.1)
    
    conn.commit()
    conn.close()
    log(f"✅ 估值因子完成! 新增: {total_records}条")

# ============================================
# 主入口
# ============================================

def main():
    with open(LOG_PATH, 'w') as f:
        f.write(f"[{datetime.now().strftime('%H:%M:%S')}] 后台数据补充开始\n")
    
    log("="*50)
    log("后台财务和估值数据补充")
    log("="*50)
    
    supplement_fina()
    supplement_valuation()
    
    log("="*50)
    log("✅ 全部完成!")
    log("="*50)

if __name__ == '__main__':
    main()
