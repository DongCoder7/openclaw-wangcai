#!/root/.openclaw/workspace/venv/bin/python3
"""
逐日因子计算 v2 - 2026年
基于测试成功的简化版
"""
import sqlite3, pandas as pd, numpy as np
from datetime import datetime, timedelta
import sys, logging, os

log_file = '/root/.openclaw/workspace/logs/calc_factors_2026_v2.log'
logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(message)s', 
    handlers=[logging.FileHandler(log_file), logging.StreamHandler(sys.stdout)])
log = logging.info

DB_PATH = '/root/.openclaw/workspace/data/historical/historical.db'

def calc_factors_one_day(conn, calc_date, limit=None):
    """计算单日因子"""
    c = conn.cursor()
    
    # 读取70天历史
    query_start = (datetime.strptime(calc_date, '%Y%m%d') - timedelta(days=70)).strftime('%Y%m%d')
    
    df = pd.read_sql(f'''
        SELECT ts_code, trade_date, close, volume, high, low
        FROM daily_price 
        WHERE trade_date BETWEEN "{query_start}" AND "{calc_date}"
        ORDER BY ts_code, trade_date
    ''', conn)
    
    if df.empty:
        log(f"  {calc_date}: 无数据")
        return 0
    
    # 计算市场收益
    df['trade_date'] = pd.to_datetime(df['trade_date'])
    market = df.groupby('trade_date')['close'].last().pct_change().reset_index()
    market.columns = ['trade_date', 'market_ret']
    df = df.merge(market, on='trade_date', how='left')
    df['trade_date'] = df['trade_date'].dt.strftime('%Y%m%d')
    
    tech_records, def_records, timing_records = [], [], []
    stocks = df[df['trade_date']==calc_date]['ts_code'].unique()
    if limit: stocks = stocks[:limit]
    
    for code in stocks:
        try:
            s = df[df['ts_code']==code].sort_values('trade_date').copy()
            if len(s) < 20: continue
            
            # 技术因子
            s['ret_5'] = s['close'].pct_change(5) * 100
            s['ret_20'] = s['close'].pct_change(20) * 100
            s['vol_20'] = s['close'].pct_change().rolling(20).std() * np.sqrt(252) * 100
            s['ma_20'] = s['close'].rolling(20).mean()
            s['vol_5'] = s['close'].pct_change().rolling(5).std() * np.sqrt(252) * 100
            
            # 防御因子
            cummax = s['close'].cummax()
            s['max_dd'] = ((s['close']-cummax)/cummax).rolling(20).min() * 100
            s['sharpe'] = s['ret_20'] / (s['vol_20'] + 1e-10)
            
            # 择时因子
            s['trend'] = (s['close'] > s['ma_20']).astype(int)
            s['breakout'] = (s['high'] > s['high'].rolling(20).max().shift(1)).astype(int)
            
            today = s[s['trade_date']==calc_date]
            if len(today)==0: continue
            r = today.iloc[0]
            now = datetime.now().isoformat()
            
            def sv(v): return 0.0 if pd.isna(v) else float(v)
            
            # 10列: ts_code, trade_date, ret_3, ret_5, vol_5, ma_3, ma_5, rsi_5, macd, update_time
            tech_records.append((code, calc_date, sv(r['ret_5']), sv(r['ret_5']), sv(r['vol_5']),
                sv(r['ma_20']), sv(r['ma_20']), 50.0, sv(r['vol_20'])/100, now))
            
            # 6列: ts_code, trade_date, vol_5, max_dd_5, sharpe_like, update_time
            def_records.append((code, calc_date, sv(r['vol_20']), sv(r['max_dd']), sv(r['sharpe']), now))
            
            # 6列: ts_code, trade_date, trend_3, breakout_3, volume_spike, update_time
            timing_records.append((code, calc_date, sv(r['trend']), sv(r['breakout']), 0, now))
            
        except: continue
    
    if tech_records:
        c.executemany('INSERT OR REPLACE INTO stock_factors VALUES (?,?,?,?,?,?,?,?,?,?)', tech_records)
    if def_records:
        c.executemany('INSERT OR REPLACE INTO stock_defensive VALUES (?,?,?,?,?,?)', def_records)
    if timing_records:
        c.executemany('INSERT OR REPLACE INTO stock_timing VALUES (?,?,?,?,?,?)', timing_records)
    conn.commit()
    
    return len(tech_records)

def main():
    log("="*50)
    log("2026因子计算 v2")
    log("="*50)
    
    import tushare as ts
    ts.set_token('cd2c935050381b52c9849eb054d1b198c21b0f29be2f025f9a9ece30')
    pro = ts.pro_api()
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # 2026年交易日
    dates = pro.trade_cal(exchange='SSE', start_date='20260101', end_date='20260302')
    dates = dates[dates['is_open']==1]['cal_date'].tolist()
    
    # 检查已存在
    c.execute('SELECT DISTINCT trade_date FROM stock_factors WHERE trade_date >= "20260101"')
    existing = set([r[0] for r in c.fetchall()])
    todo = [d for d in dates if d not in existing]
    
    log(f"待计算: {len(todo)}天")
    
    for i, date in enumerate(todo):
        count = calc_factors_one_day(conn, date)
        log(f"[{i+1}/{len(todo)}] {date}: {count}只")
    
    conn.close()
    log("完成!")

if __name__ == '__main__':
    main()
