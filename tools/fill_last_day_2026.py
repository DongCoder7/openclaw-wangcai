#!/root/.openclaw/workspace/venv/bin/python3
"""
补充2026-03-02最后一天的防御和择时因子
"""
import sqlite3, pandas as pd, numpy as np
from datetime import datetime, timedelta

DB_PATH = '/root/.openclaw/workspace/data/historical/historical.db'
calc_date = '20260302'

print(f"补充 {calc_date} 的防御和择时因子...")

conn = sqlite3.connect(DB_PATH)
c = conn.cursor()

# 读取70天历史
query_start = (datetime.strptime(calc_date, '%Y%m%d') - timedelta(days=70)).strftime('%Y%m%d')

df = pd.read_sql(f'''
    SELECT ts_code, trade_date, close, volume, high, low
    FROM daily_price WHERE trade_date BETWEEN "{query_start}" AND "{calc_date}"
    ORDER BY ts_code, trade_date
''', conn)

print(f"读取数据: {len(df)}条")

if df.empty:
    print("无数据，退出")
    conn.close()
    exit(1)

# 计算市场收益
df['trade_date'] = pd.to_datetime(df['trade_date'])
market = df.groupby('trade_date')['close'].last().pct_change().reset_index()
market.columns = ['trade_date', 'market_ret']
df = df.merge(market, on='trade_date', how='left')
df['trade_date'] = df['trade_date'].dt.strftime('%Y%m%d')

defend, timing = [], []
stocks = df[df['trade_date']==calc_date]['ts_code'].unique()
print(f"待计算股票: {len(stocks)}只")

for i, code in enumerate(stocks):
    try:
        s = df[df['ts_code']==code].sort_values('trade_date').copy()
        if len(s) < 20:
            continue
        
        # 计算因子
        s['ret_5'] = s['close'].pct_change(5) * 100
        s['vol_20'] = s['close'].pct_change().rolling(20).std() * np.sqrt(252) * 100
        s['ma_20'] = s['close'].rolling(20).mean()
        cummax = s['close'].cummax()
        s['max_dd'] = ((s['close']-cummax)/cummax).rolling(20).min() * 100
        s['sharpe'] = s['ret_5'] / (s['vol_20'] + 1e-10)
        s['trend'] = (s['close'] > s['ma_20']).astype(int)
        s['breakout'] = (s['high'] > s['high'].rolling(20).max().shift(1)).astype(int)
        
        today = s[s['trade_date']==calc_date]
        if len(today)==0:
            continue
        r = today.iloc[0]
        now = datetime.now().isoformat()
        
        def sv(v): return 0.0 if pd.isna(v) else float(v)
        
        defend.append((code, calc_date, sv(r['vol_20']), sv(r['max_dd']), sv(r['sharpe']), now))
        timing.append((code, calc_date, sv(r['trend']), sv(r['breakout']), 0, now))
        
        if (i+1) % 1000 == 0:
            print(f"  已处理 {i+1}/{len(stocks)}只...")
            
    except Exception as e:
        continue

print(f"计算完成: 防御{len(defend)}条, 择时{len(timing)}条")

# 写入数据库
if defend:
    c.executemany('INSERT OR REPLACE INTO stock_defensive VALUES (?,?,?,?,?,?)', defend)
if timing:
    c.executemany('INSERT OR REPLACE INTO stock_timing VALUES (?,?,?,?,?,?)', timing)
conn.commit()
conn.close()

print(f"✅ 完成! {calc_date} 因子已补充")
