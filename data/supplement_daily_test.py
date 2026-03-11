#!/usr/bin/env python3
"""
数据更新脚本 v4.1 (测试版)
- 全因子计算（技术+防御+择时）
- 测试模式: --test 500
"""
import os, sys, sqlite3, pandas as pd, numpy as np
from datetime import datetime, timedelta
import time, json, argparse, requests

WORKSPACE = '/root/.openclaw/workspace'
DB_PATH = f'{WORKSPACE}/data/historical/historical.db'

def log(msg): 
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")
    sys.stdout.flush()

def init_tables(conn):
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS stock_factors (
        ts_code TEXT, trade_date TEXT, ret_3 REAL, ret_5 REAL, vol_5 REAL,
        ma_3 REAL, ma_5 REAL, rsi_5 REAL, macd REAL, update_time TEXT,
        PRIMARY KEY(ts_code,trade_date))''')
    c.execute('''CREATE TABLE IF NOT EXISTS stock_defensive (
        ts_code TEXT, trade_date TEXT, vol_5 REAL, max_dd_5 REAL,
        sharpe_like REAL, update_time TEXT, PRIMARY KEY(ts_code,trade_date))''')
    c.execute('''CREATE TABLE IF NOT EXISTS stock_timing (
        ts_code TEXT, trade_date TEXT, trend_3 REAL, breakout_3 REAL,
        volume_spike REAL, update_time TEXT, PRIMARY KEY(ts_code,trade_date))''')
    conn.commit()

def calc_all_factors(conn, date, limit=None):
    """计算全因子 - 简化版（只需3天数据）"""
    log(f"📊 计算全因子 {date}")
    
    start = (datetime.strptime(date,'%Y%m%d') - timedelta(days=7)).strftime('%Y%m%d')
    df = pd.read_sql(f'''
        SELECT ts_code, trade_date, close, volume, high, low
        FROM daily_price WHERE trade_date BETWEEN "{start}" AND "{date}"
        ORDER BY ts_code,trade_date
    ''', conn)
    
    if df.empty:
        log("⚠️ 无数据")
        return 0
    
    df['trade_date'] = pd.to_datetime(df['trade_date'])
    df['trade_date'] = df['trade_date'].dt.strftime('%Y%m%d')
    
    c = conn.cursor()
    tech_records, def_records, timing_records = [], [], []
    
    codes = df['ts_code'].unique()
    if limit: codes = codes[:limit]
    
    for code in codes:
        try:
            s = df[df['ts_code']==code].sort_values('trade_date').copy()
            if len(s) < 3: continue
            
            # 技术因子（3天/5天窗口）
            s['ret_3'] = s['close'].pct_change(3) * 100
            s['ret_5'] = s['close'].pct_change(5) * 100
            s['vol_5'] = s['close'].pct_change().rolling(5).std() * np.sqrt(252) * 100
            s['ma_3'] = s['close'].rolling(3).mean()
            s['ma_5'] = s['close'].rolling(5).mean()
            
            # RSI简化
            delta = s['close'].diff()
            gain = delta.where(delta>0,0).rolling(5).mean()
            loss = (-delta.where(delta<0,0)).rolling(5).mean()
            s['rsi_5'] = 100 - (100/(1+gain/(loss+1e-10)))
            
            # MACD简化
            ema3 = s['close'].ewm(span=3).mean()
            ema5 = s['close'].ewm(span=5).mean()
            s['macd'] = ema3 - ema5
            
            # 防御因子
            s['vol_5d'] = s['close'].pct_change().rolling(5).std() * np.sqrt(252) * 100
            cummax = s['close'].cummax()
            s['max_dd_5'] = ((s['close']-cummax)/cummax).rolling(5).min() * 100
            s['sharpe_like'] = s['ret_5'] / (s['vol_5'] + 1e-10)
            
            # 择时因子
            s['trend_3'] = (s['close'] > s['ma_3']).astype(int)
            s['breakout_3'] = (s['high'] > s['high'].rolling(3).max().shift(1)).astype(int)
            s['volume_spike'] = (s['volume'] > s['volume'].rolling(3).mean() * 1.5).astype(int)
            
            # 取当日
            today = s[s['trade_date']==date]
            if len(today)==0: continue
            r = today.iloc[0]
            now = datetime.now().isoformat()
            
            def sv(v): return 0.0 if pd.isna(v) else float(v)
            
            tech_records.append((code, date, sv(r['ret_3']), sv(r['ret_5']), sv(r['vol_5']),
                sv(r['ma_3']), sv(r['ma_5']), sv(r['rsi_5']), sv(r['macd']), now))
            
            def_records.append((code, date, sv(r['vol_5d']), sv(r['max_dd_5']),
                sv(r['sharpe_like']), now))
            
            timing_records.append((code, date, sv(r['trend_3']), sv(r['breakout_3']),
                sv(r['volume_spike']), now))
            
        except Exception as e:
            pass
    
    if tech_records:
        c.executemany('INSERT OR REPLACE INTO stock_factors VALUES (?,?,?,?,?,?,?,?,?,?)', tech_records)
    if def_records:
        c.executemany('INSERT OR REPLACE INTO stock_defensive VALUES (?,?,?,?,?,?)', def_records)
    if timing_records:
        c.executemany('INSERT OR REPLACE INTO stock_timing VALUES (?,?,?,?,?,?)', timing_records)
    conn.commit()
    
    log(f"✅ 因子: {len(tech_records)}只 (技术+防御+择时)")
    return len(tech_records)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--date', default='20250304')
    parser.add_argument('--test', type=int, default=500)
    args = parser.parse_args()
    
    log("="*50)
    log("数据更新 v4.1 (测试版)")
    log("="*50)
    
    conn = sqlite3.connect(DB_PATH)
    init_tables(conn)
    
    calc_all_factors(conn, args.date, args.test)
    
    conn.close()
    log("✅ 完成!")

if __name__ == '__main__':
    main()
