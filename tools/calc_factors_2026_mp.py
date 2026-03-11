#!/root/.openclaw/workspace/venv/bin/python3
"""
多进程因子计算 - 2026年（提速版）
按日期并行，利用多核CPU
"""
import sqlite3, pandas as pd, numpy as np
from datetime import datetime, timedelta
import sys, logging, os, time
from concurrent.futures import ProcessPoolExecutor, as_completed
import multiprocessing

DB_PATH = '/root/.openclaw/workspace/data/historical/historical.db'

def calc_one_day(args):
    """计算单日因子（独立函数，用于多进程）"""
    calc_date, db_path = args
    
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    query_start = (datetime.strptime(calc_date, '%Y%m%d') - timedelta(days=70)).strftime('%Y%m%d')
    
    df = pd.read_sql(f'''
        SELECT ts_code, trade_date, close, volume, high, low
        FROM daily_price WHERE trade_date BETWEEN "{query_start}" AND "{calc_date}"
        ORDER BY ts_code, trade_date
    ''', conn)
    
    if df.empty: 
        conn.close()
        return calc_date, 0
    
    # 市场收益
    df['trade_date'] = pd.to_datetime(df['trade_date'])
    market = df.groupby('trade_date')['close'].last().pct_change().reset_index()
    market.columns = ['trade_date', 'market_ret']
    df = df.merge(market, on='trade_date', how='left')
    df['trade_date'] = df['trade_date'].dt.strftime('%Y%m%d')
    
    tech, defend, timing = [], [], []
    stocks = df[df['trade_date']==calc_date]['ts_code'].unique()
    
    for code in stocks:
        try:
            s = df[df['ts_code']==code].sort_values('trade_date').copy()
            if len(s) < 20: continue
            
            s['ret_5'] = s['close'].pct_change(5) * 100
            s['vol_20'] = s['close'].pct_change().rolling(20).std() * np.sqrt(252) * 100
            s['ma_20'] = s['close'].rolling(20).mean()
            cummax = s['close'].cummax()
            s['max_dd'] = ((s['close']-cummax)/cummax).rolling(20).min() * 100
            s['sharpe'] = s['ret_5'] / (s['vol_20'] + 1e-10)
            s['trend'] = (s['close'] > s['ma_20']).astype(int)
            s['breakout'] = (s['high'] > s['high'].rolling(20).max().shift(1)).astype(int)
            
            today = s[s['trade_date']==calc_date]
            if len(today)==0: continue
            r = today.iloc[0]
            now = datetime.now().isoformat()
            
            def sv(v): return 0.0 if pd.isna(v) else float(v)
            
            tech.append((code, calc_date, sv(r['ret_5']), sv(r['ret_5']), sv(r['vol_20']), 
                sv(r['ma_20']), sv(r['ma_20']), 50.0, sv(r['vol_20'])/100, now))
            defend.append((code, calc_date, sv(r['vol_20']), sv(r['max_dd']), sv(r['sharpe']), now))
            timing.append((code, calc_date, sv(r['trend']), sv(r['breakout']), 0, now))
        except: continue
    
    if tech:
        c.executemany('INSERT OR REPLACE INTO stock_factors VALUES (?,?,?,?,?,?,?,?,?,?)', tech)
    if defend:
        c.executemany('INSERT OR REPLACE INTO stock_defensive VALUES (?,?,?,?,?,?)', defend)
    if timing:
        c.executemany('INSERT OR REPLACE INTO stock_timing VALUES (?,?,?,?,?,?)', timing)
    conn.commit()
    conn.close()
    
    return calc_date, len(tech)

def main():
    print("="*60)
    print("多进程因子计算 - 2026年 (4核并行)")
    print("="*60)
    
    import tushare as ts
    ts.set_token('cd2c935050381b52c9849eb054d1b198c21b0f29be2f025f9a9ece30')
    pro = ts.pro_api()
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    dates = pro.trade_cal(exchange='SSE', start_date='20260101', end_date='20260302')
    dates = dates[dates['is_open']==1]['cal_date'].tolist()
    
    c.execute('SELECT DISTINCT trade_date FROM stock_factors WHERE trade_date >= "20260101"')
    existing = set([r[0] for r in c.fetchall()])
    todo = [d for d in dates if d not in existing]
    conn.close()
    
    print(f"待计算: {len(todo)}天")
    print(f"CPU核心数: {multiprocessing.cpu_count()}")
    print(f"并行进程: 4")
    print("="*60)
    
    start = datetime.now()
    
    # 多进程并行（4个进程）
    with ProcessPoolExecutor(max_workers=4) as executor:
        # 提交所有任务
        args_list = [(d, DB_PATH) for d in todo]
        futures = {executor.submit(calc_one_day, args): args[0] for args in args_list}
        
        # 收集结果
        completed = 0
        for future in as_completed(futures):
            date, count = future.result()
            completed += 1
            elapsed = (datetime.now() - start).total_seconds()
            avg = elapsed / completed if completed > 0 else 0
            remain = avg * (len(todo) - completed) / 60 if avg > 0 else 0
            print(f"[{completed}/{len(todo)}] {date}: {count}只 | 预计剩余:{remain:.0f}min")
    
    total = (datetime.now() - start).total_seconds()
    print("="*60)
    print(f"完成! 总耗时: {total/60:.1f}分钟")

if __name__ == '__main__':
    main()
