#!/root/.openclaw/workspace/venv/bin/python3
"""
后台数据回补脚本 - 2026年数据
日志: logs/supplement_2026.log
"""
import os, sys, sqlite3, pandas as pd, numpy as np
from datetime import datetime, timedelta
import time, json
import logging

# 日志配置
log_file = '/root/.openclaw/workspace/logs/supplement_2026.log'
os.makedirs(os.path.dirname(log_file), exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler(sys.stdout)
    ]
)
log = logging.info

WORKSPACE = '/root/.openclaw/workspace'
DB_PATH = f'{WORKSPACE}/data/historical/historical.db'

def init_tables(conn):
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS daily_price (
        ts_code TEXT, trade_date TEXT, open REAL, high REAL, low REAL, close REAL,
        volume REAL, amount REAL, change_pct REAL, pct_chg REAL, source TEXT,
        PRIMARY KEY(ts_code, trade_date))''')
    c.execute('''CREATE TABLE IF NOT EXISTS daily_valuation (
        ts_code TEXT, trade_date TEXT, pe_ttm REAL, pb REAL, ps_ttm REAL,
        total_mv REAL, turnover_rate REAL, source TEXT,
        PRIMARY KEY(ts_code, trade_date))''')
    conn.commit()

def main():
    log("="*60)
    log("2026年数据回补 - 后台任务")
    log("="*60)
    
    import tushare as ts
    ts.set_token('cd2c935050381b52c9849eb054d1b198c21b0f29be2f025f9a9ece30')
    pro = ts.pro_api()
    
    conn = sqlite3.connect(DB_PATH)
    init_tables(conn)
    c = conn.cursor()
    
    # 获取交易日
    dates = pro.trade_cal(exchange='SSE', start_date='20260101', end_date='20260302')
    dates = dates[dates['is_open']==1]['cal_date'].tolist()
    log(f"共{len(dates)}个交易日: {dates[0]} ~ {dates[-1]}")
    
    stats = {'price': 0, 'valuation': 0, 'errors': 0}
    
    for i, date in enumerate(dates):
        try:
            # 检查是否已存在
            c.execute('SELECT COUNT(*) FROM daily_price WHERE trade_date=?', (date,))
            if c.fetchone()[0] > 5000:
                log(f"[{i+1}/{len(dates)}] {date}: 已存在，跳过")
                continue
            
            # 价格数据
            df = pro.daily(trade_date=date)
            time.sleep(0.35)
            if df is not None and not df.empty:
                for _, r in df.iterrows():
                    c.execute('''INSERT OR REPLACE INTO daily_price VALUES (?,?,?,?,?,?,?,?,?,?,?)''',
                        (r.ts_code, date, r.open, r.high, r.low, r.close,
                         r.vol, r.amount, r.pct_chg, r.pct_chg, 'tushare'))
                conn.commit()
                stats['price'] += len(df)
                log(f"[{i+1}/{len(dates)}] {date}: 价格{len(df)}条")
            
            # 估值数据
            df = pro.daily_basic(trade_date=date)
            time.sleep(0.35)
            if df is not None and not df.empty:
                for _, r in df.iterrows():
                    c.execute('''INSERT OR REPLACE INTO daily_valuation VALUES (?,?,?,?,?,?,?,?)''',
                        (r.ts_code, date, r.pe_ttm, r.pb, r.ps_ttm, r.total_mv, r.turnover_rate, 'tushare'))
                conn.commit()
                stats['valuation'] += len(df)
                log(f"      {date}: 估值{len(df)}条")
            
        except Exception as e:
            stats['errors'] += 1
            log(f"[{i+1}/{len(dates)}] {date}: 错误 - {e}")
            time.sleep(1)
    
    conn.close()
    log("="*60)
    log(f"完成! 价格:{stats['price']}条 估值:{stats['valuation']}条 错误:{stats['errors']}")
    log("="*60)

if __name__ == '__main__':
    main()
