#!/root/.openclaw/workspace/venv/bin/python3
# 分段计算模块
import sqlite3, pandas as pd, numpy as np
from datetime import datetime, timedelta
import time

DB_PATH = '/root/.openclaw/workspace/data/historical/historical.db'

def calc_segment(start_date, end_date, seg_name):
    import tushare as ts
    ts.set_token('cd2c935050381b52c9849eb054d1b198c21b0f29be2f025f9a9ece30')
    pro = ts.pro_api()
    
    dates = pro.trade_cal(exchange='SSE', start_date=start_date, end_date=end_date)
    dates = dates[dates['is_open']==1]['cal_date'].tolist()
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # 检查已存在
    c.execute(f'SELECT DISTINCT trade_date FROM stock_factors WHERE trade_date BETWEEN "{start_date}" AND "{end_date}"')
    existing = set([r[0] for r in c.fetchall()])
    todo = [d for d in dates if d not in existing]
    
    print(f"[{seg_name}] 待计算: {len(todo)}天")
    total = 0
    
    for date in todo:
        count = calc_one_day(conn, date)
        total += count
        print(f"[{seg_name}] {date}: {count}只")
    
    conn.close()
    print(f"[{seg_name}] 完成! 共{total}只")

def calc_one_day(conn, calc_date):
    c = conn.cursor()
    query_start = (datetime.strptime(calc_date, '%Y%m%d') - timedelta(days=70)).strftime('%Y%m%d')
    
    df = pd.read_sql(f'''
        SELECT ts_code, trade_date, close, volume, high, low
        FROM daily_price WHERE trade_date BETWEEN "{query_start}" AND "{calc_date}"
        ORDER BY ts_code, trade_date
    ''', conn)
    
    if df.empty: return 0
    
    df['trade_date'] = pd.to_datetime(df['trade_date'])
    market = df.groupby('trade_date')['close'].last().pct_change().reset_index()
    market.columns = ['trade_date', 'market_ret']
    df = df.merge(market, on='trade_date', how='left')
    df['trade_date'] = df['trade_date'].dt.strftime('%Y%m%d')
    
    tech, defend, timing = [], [], []
    
    for code in df[df['trade_date']==calc_date]['ts_code'].unique():
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
    
    return len(tech)
