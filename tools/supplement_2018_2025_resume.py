#!/root/.openclaw/workspace/venv/bin/python3
"""
2018-2025年历史数据回补 - 断点续传版
只补充缺失的日期，避免重复
日志: logs/supplement_2018_2025_resume.log
"""
import os, sys, sqlite3, pandas as pd
from datetime import datetime
import time
import logging

log_file = '/root/.openclaw/workspace/logs/supplement_2018_2025_resume.log'
os.makedirs(os.path.dirname(log_file), exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(message)s',
    handlers=[logging.FileHandler(log_file), logging.StreamHandler(sys.stdout)]
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
    log("="*70)
    log("2018-2025年历史数据回补 - 断点续传版")
    log("="*70)
    
    import tushare as ts
    ts.set_token('cd2c935050381b52c9849eb054d1b198c21b0f29be2f025f9a9ece30')
    pro = ts.pro_api()
    
    conn = sqlite3.connect(DB_PATH)
    init_tables(conn)
    c = conn.cursor()
    
    # 获取2018-2025年所有交易日
    dates = pro.trade_cal(exchange='SSE', start_date='20180101', end_date='20251231')
    all_dates = dates[dates['is_open']==1]['cal_date'].tolist()
    log(f"2018-2025年总交易日: {len(all_dates)}天")
    
    # 检查已存在的日期（价格数据）
    c.execute('SELECT DISTINCT trade_date FROM daily_price WHERE trade_date BETWEEN "20180101" AND "20251231"')
    existing = set([r[0] for r in c.fetchall()])
    log(f"已存在: {len(existing)}天")
    
    # 过滤待回补的日期
    todo = [d for d in all_dates if d not in existing]
    log(f"待回补: {len(todo)}天")
    
    if not todo:
        log("无需回补，全部已存在!")
        conn.close()
        return
    
    # 显示前5个和后5个待回补日期
    log(f"最早待回补: {todo[0]}, 最晚待回补: {todo[-1]}")
    
    stats = {'price': 0, 'valuation': 0, 'errors': 0}
    start_time = datetime.now()
    
    for i, date in enumerate(todo):
        try:
            # 检查是否已存在（双重检查）
            c.execute('SELECT COUNT(*) FROM daily_price WHERE trade_date=?', (date,))
            if c.fetchone()[0] > 5000:
                log(f"[{i+1}/{len(todo)}] {date}: 已存在，跳过")
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
            
            # 估值数据
            df = pro.daily_basic(trade_date=date)
            time.sleep(0.35)
            if df is not None and not df.empty:
                for _, r in df.iterrows():
                    c.execute('''INSERT OR REPLACE INTO daily_valuation VALUES (?,?,?,?,?,?,?,?)''',
                        (r.ts_code, date, r.pe_ttm, r.pb, r.ps_ttm, r.total_mv, r.turnover_rate, 'tushare'))
                conn.commit()
                stats['valuation'] += len(df)
            
            # 每10天汇报一次进度
            if (i+1) % 10 == 0 or i == 0 or i == len(todo)-1:
                elapsed = (datetime.now() - start_time).total_seconds()
                speed = (i+1) / (elapsed/60) if elapsed > 0 else 0
                remain = (len(todo)-(i+1)) / speed if speed > 0 else 0
                log(f"[{i+1}/{len(todo)}] {date} | 已用时:{elapsed/60:.1f}min 速度:{speed:.1f}天/min 预计剩余:{remain:.0f}min")
            
        except Exception as e:
            stats['errors'] += 1
            log(f"[{i+1}/{len(todo)}] {date}: 错误 - {e}")
            time.sleep(1)
    
    conn.close()
    total_time = (datetime.now() - start_time).total_seconds()
    log("="*70)
    log(f"完成! 价格:{stats['price']}条 估值:{stats['valuation']}条 错误:{stats['errors']} 总耗时:{total_time/60:.1f}min")
    log("="*70)

if __name__ == '__main__':
    main()
