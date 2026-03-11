#!/root/.openclaw/workspace/venv/bin/python3
"""
简化版完整因子计算 - 只计算收盘报告必需字段
必需: ret_20, vol_20, money_flow, rel_strength, price_pos_20
"""
import sqlite3, pandas as pd, numpy as np
from datetime import datetime, timedelta
import time

DB_PATH = '/root/.openclaw/workspace/data/historical/historical.db'

def calc_one_day(date):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    query_start = (datetime.strptime(date, '%Y%m%d') - timedelta(days=70)).strftime('%Y%m%d')
    
    # 读取数据
    df = pd.read_sql(f'''
        SELECT ts_code, trade_date, close, volume, high, low
        FROM daily_price WHERE trade_date BETWEEN "{query_start}" AND "{date}"
        ORDER BY ts_code, trade_date
    ''', conn)
    
    if df.empty:
        conn.close()
        return 0
    
    # 市场收益
    df['trade_date'] = pd.to_datetime(df['trade_date'])
    market = df.groupby('trade_date')['close'].last().pct_change().reset_index()
    market.columns = ['trade_date', 'market_ret']
    df = df.merge(market, on='trade_date', how='left')
    df['trade_date'] = df['trade_date'].dt.strftime('%Y%m%d')
    
    records = []
    stocks = df[df['trade_date']==date]['ts_code'].unique()
    
    for code in stocks:
        try:
            s = df[df['ts_code']==code].sort_values('trade_date').copy()
            if len(s) < 20: continue
            
            # 只计算收盘报告必需字段
            s['ret_20'] = s['close'].pct_change(20) * 100
            s['vol_20'] = s['close'].pct_change().rolling(20).std() * np.sqrt(252) * 100
            roll20 = s['close'].rolling(20)
            s['price_pos_20'] = (s['close'] - roll20.min()) / (roll20.max() - roll20.min() + 1e-10)
            s['stock_ret'] = s['close'].pct_change()
            s['money_flow'] = (s['close'] - s['close'].shift(1)) * s['volume'] / 1000000
            s['rel_strength'] = (s['stock_ret'] - s['market_ret']).rolling(20).sum() * 100
            
            today = s[s['trade_date']==date]
            if len(today)==0: continue
            r = today.iloc[0]
            
            def sv(v): return None if pd.isna(v) else float(v)
            
            records.append((
                sv(r['ret_20']), sv(r['vol_20']), sv(r['price_pos_20']),
                sv(r['money_flow']), sv(r['rel_strength']),
                code, date
            ))
        except: continue
    
    if records:
        c.executemany('''
            UPDATE stock_factors SET
                ret_20=?, vol_20=?, price_pos_20=?, money_flow=?, rel_strength=?
            WHERE ts_code=? AND trade_date=?
        ''', records)
        conn.commit()
    
    conn.close()
    return len(records)

def main():
    print("简化版因子计算 - 补充收盘报告字段")
    print("="*50)
    
    dates = ['20260302', '20260227', '20260226', '20260225', '20260224']
    
    for i, date in enumerate(dates):
        count = calc_one_day(date)
        print(f"[{i+1}/{len(dates)}] {date}: {count}只")
        time.sleep(1)
    
    print("完成!")

if __name__ == '__main__':
    main()
