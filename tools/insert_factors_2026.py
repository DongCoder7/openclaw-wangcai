#!/root/.openclaw/workspace/venv/bin/python3
"""
重新INSERT完整因子 - 2026年（收盘报告必需字段）
"""
import sqlite3, pandas as pd, numpy as np
from datetime import datetime, timedelta
import time

DB_PATH = '/root/.openclaw/workspace/data/historical/historical.db'

def calc_and_insert(date):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    query_start = (datetime.strptime(date, '%Y%m%d') - timedelta(days=70)).strftime('%Y%m%d')
    
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
            
            # 收盘报告必需字段
            s['ret_5'] = s['close'].pct_change(5) * 100
            s['ret_20'] = s['close'].pct_change(20) * 100
            s['vol_5'] = s['close'].pct_change().rolling(5).std() * np.sqrt(252) * 100
            s['vol_20'] = s['close'].pct_change().rolling(20).std() * np.sqrt(252) * 100
            s['ma_5'] = s['close'].rolling(5).mean()
            s['ma_20'] = s['close'].rolling(20).mean()
            roll20 = s['close'].rolling(20)
            s['price_pos_20'] = (s['close'] - roll20.min()) / (roll20.max() - roll20.min() + 1e-10)
            s['stock_ret'] = s['close'].pct_change()
            s['money_flow'] = (s['close'] - s['close'].shift(1)) * s['volume'] / 1000000
            s['rel_strength'] = (s['stock_ret'] - s['market_ret']).rolling(20).sum() * 100
            
            today = s[s['trade_date']==date]
            if len(today)==0: continue
            r = today.iloc[0]
            now = datetime.now().isoformat()
            
            def sv(v): return None if pd.isna(v) else float(v)
            
            records.append((
                code, date, sv(r['ret_3']), sv(r['ret_5']), sv(r['ret_20']),
                sv(r['vol_5']), sv(r['vol_20']),
                sv(r['ma_3']), sv(r['ma_5']), sv(r['ma_20']),
                sv(r['price_pos_20']), sv(r['money_flow']), sv(r['rel_strength']),
                now
            ))
        except: continue
    
    if records:
        c.executemany('''
            INSERT INTO stock_factors 
            (ts_code, trade_date, ret_3, ret_5, ret_20, vol_5, vol_20,
             ma_3, ma_5, ma_20, price_pos_20, money_flow, rel_strength, update_time)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        ''', records)
        conn.commit()
    
    conn.close()
    return len(records)

def main():
    print("重新INSERT因子数据 - 2026年")
    print("="*50)
    
    # 先计算最近5天让收盘报告可用
    dates = ['20260302', '20260227', '20260226', '20260225', '20260224']
    
    for i, date in enumerate(dates):
        count = calc_and_insert(date)
        print(f"[{i+1}/{len(dates)}] {date}: {count}只")
    
    print("\n✅ 前5天完成！收盘报告可生成")
    print("继续计算剩余30天...")
    
    # 继续剩余日期
    import tushare as ts
    ts.set_token('cd2c935050381b52c9849eb054d1b198c21b0f29be2f025f9a9ece30')
    pro = ts.pro_api()
    
    all_dates = pro.trade_cal(exchange='SSE', start_date='20260101', end_date='20260302')
    all_dates = all_dates[all_dates['is_open']==1]['cal_date'].tolist()
    remaining = [d for d in all_dates if d not in dates]
    
    for i, date in enumerate(remaining):
        count = calc_and_insert(date)
        if (i+1) % 5 == 0:
            print(f"[{i+1}/{len(remaining)}] {date}: {count}只")
    
    print("全部完成!")

if __name__ == '__main__':
    main()
