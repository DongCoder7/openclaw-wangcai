#!/root/.openclaw/workspace/venv/bin/python3
"""
完整因子计算 - 2026年（含收盘报告所需全部字段）
字段: ret_3, ret_5, ret_20, ret_60, vol_5, vol_20, ma_3, ma_5, ma_20, ma_60, 
      rsi_14, macd, price_pos_20, money_flow, rel_strength
"""
import sqlite3, pandas as pd, numpy as np
from datetime import datetime, timedelta
import sys

DB_PATH = '/root/.openclaw/workspace/data/historical/historical.db'

def calc_full_factors(conn, calc_date):
    c = conn.cursor()
    query_start = (datetime.strptime(calc_date, '%Y%m%d') - timedelta(days=130)).strftime('%Y%m%d')
    
    df = pd.read_sql(f'''
        SELECT ts_code, trade_date, close, volume, high, low, open
        FROM daily_price WHERE trade_date BETWEEN "{query_start}" AND "{calc_date}"
        ORDER BY ts_code, trade_date
    ''', conn)
    
    if df.empty: return 0
    
    # 市场收益
    df['trade_date'] = pd.to_datetime(df['trade_date'])
    market = df.groupby('trade_date')['close'].last().pct_change().reset_index()
    market.columns = ['trade_date', 'market_ret']
    df = df.merge(market, on='trade_date', how='left')
    df['trade_date'] = df['trade_date'].dt.strftime('%Y%m%d')
    
    tech_records = []
    stocks = df[df['trade_date']==calc_date]['ts_code'].unique()
    
    for code in stocks:
        try:
            s = df[df['ts_code']==code].sort_values('trade_date').copy()
            if len(s) < 60: continue
            
            # 收益率
            s['ret_3'] = s['close'].pct_change(3) * 100
            s['ret_5'] = s['close'].pct_change(5) * 100
            s['ret_20'] = s['close'].pct_change(20) * 100
            s['ret_60'] = s['close'].pct_change(60) * 100
            
            # 波动率
            s['vol_5'] = s['close'].pct_change().rolling(5).std() * np.sqrt(252) * 100
            s['vol_20'] = s['close'].pct_change().rolling(20).std() * np.sqrt(252) * 100
            
            # 均线
            s['ma_3'] = s['close'].rolling(3).mean()
            s['ma_5'] = s['close'].rolling(5).mean()
            s['ma_20'] = s['close'].rolling(20).mean()
            s['ma_60'] = s['close'].rolling(60).mean()
            
            # RSI
            delta = s['close'].diff()
            gain = delta.where(delta>0, 0).rolling(14).mean()
            loss = (-delta.where(delta<0, 0)).rolling(14).mean()
            rs = gain / (loss + 1e-10)
            s['rsi_14'] = 100 - (100 / (1 + rs))
            
            # MACD
            ema12 = s['close'].ewm(span=12).mean()
            ema26 = s['close'].ewm(span=26).mean()
            s['macd'] = ema12 - ema26
            
            # 价格位置
            roll20 = s['close'].rolling(20)
            s['price_pos_20'] = (s['close'] - roll20.min()) / (roll20.max() - roll20.min() + 1e-10)
            
            # 资金流向和相对强弱
            s['stock_ret'] = s['close'].pct_change()
            s['money_flow'] = (s['close'] - s['close'].shift(1)) * s['volume'] / 1000000
            s['rel_strength'] = (s['stock_ret'] - s['market_ret']).rolling(20).sum() * 100
            
            today = s[s['trade_date']==calc_date]
            if len(today)==0: continue
            r = today.iloc[0]
            now = datetime.now().isoformat()
            
            def sv(v): return None if pd.isna(v) else float(v)
            
            tech_records.append((
                code, calc_date,
                sv(r['ret_3']), sv(r['ret_5']), sv(r['ret_20']), sv(r['ret_60']),
                sv(r['vol_5']), sv(r['vol_20']),
                sv(r['ma_3']), sv(r['ma_5']), sv(r['ma_20']), sv(r['ma_60']),
                sv(r['rsi_14']), sv(r['macd']),
                sv(r['price_pos_20']), sv(r['money_flow']), sv(r['rel_strength']),
                now
            ))
        except: continue
    
    if tech_records:
        c.executemany('''
            INSERT OR REPLACE INTO stock_factors 
            (ts_code, trade_date, ret_3, ret_5, ret_20, ret_60, vol_5, vol_20,
             ma_3, ma_5, ma_20, ma_60, rsi_14, macd, price_pos_20, money_flow, rel_strength, update_time)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        ''', tech_records)
        conn.commit()
    
    return len(tech_records)

def main():
    print("="*60)
    print("完整因子计算 - 2026年")
    print("="*60)
    
    import tushare as ts
    ts.set_token('cd2c935050381b52c9849eb054d1b198c21b0f29be2f025f9a9ece30')
    pro = ts.pro_api()
    
    conn = sqlite3.connect(DB_PATH)
    
    dates = pro.trade_cal(exchange='SSE', start_date='20260101', end_date='20260302')
    dates = dates[dates['is_open']==1]['cal_date'].tolist()
    
    print(f"待计算: {len(dates)}天")
    
    for i, date in enumerate(dates):
        count = calc_full_factors(conn, date)
        print(f"[{i+1}/{len(dates)}] {date}: {count}只")
    
    conn.close()
    print("完成!")

if __name__ == '__main__':
    main()
