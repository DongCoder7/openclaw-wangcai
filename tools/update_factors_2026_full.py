#!/root/.openclaw/workspace/venv/bin/python3
"""
更新2026年因子数据 - 补充完整字段
"""
import sqlite3, pandas as pd, numpy as np
from datetime import datetime, timedelta
import sys

DB_PATH = '/root/.openclaw/workspace/data/historical/historical.db'

def update_factors_for_date(conn, calc_date):
    """更新单日因子（包含所有字段）"""
    c = conn.cursor()
    
    query_start = (datetime.strptime(calc_date, '%Y%m%d') - timedelta(days=130)).strftime('%Y%m%d')
    
    df = pd.read_sql(f'''
        SELECT ts_code, trade_date, close, volume, high, low
        FROM daily_price WHERE trade_date BETWEEN "{query_start}" AND "{calc_date}"
        ORDER BY ts_code, trade_date
    ''', conn)
    
    if df.empty:
        return 0
    
    # 市场收益
    df['trade_date'] = pd.to_datetime(df['trade_date'])
    market = df.groupby('trade_date')['close'].last().pct_change().reset_index()
    market.columns = ['trade_date', 'market_ret']
    df = df.merge(market, on='trade_date', how='left')
    df['trade_date'] = df['trade_date'].dt.strftime('%Y%m%d')
    
    updates = []
    stocks = df[df['trade_date']==calc_date]['ts_code'].unique()
    
    for code in stocks:
        try:
            s = df[df['ts_code']==code].sort_values('trade_date').copy()
            if len(s) < 60:  # 需要至少60天
                continue
            
            # 计算完整因子
            s['ret_20'] = s['close'].pct_change(20) * 100
            s['ret_60'] = s['close'].pct_change(60) * 100
            s['vol_20'] = s['close'].pct_change().rolling(20).std() * np.sqrt(252) * 100
            s['ma_20'] = s['close'].rolling(20).mean()
            s['ma_60'] = s['close'].rolling(60).mean()
            
            # 价格位置
            roll20 = s['close'].rolling(20)
            s['price_pos_20'] = (s['close'] - roll20.min()) / (roll20.max() - roll20.min() + 1e-10)
            
            # 资金流向和相对强弱
            s['stock_ret'] = s['close'].pct_change()
            s['money_flow'] = (s['close'] - s['close'].shift(1)) * s['volume'] / 1000000
            s['rel_strength'] = (s['stock_ret'] - s['market_ret']).rolling(20).sum() * 100
            
            today = s[s['trade_date']==calc_date]
            if len(today)==0:
                continue
            r = today.iloc[0]
            
            def sv(v): return None if pd.isna(v) else float(v)
            
            updates.append((sv(r['ret_20']), sv(r['ret_60']), sv(r['vol_20']), sv(r['ma_20']),
                sv(r['ma_60']), sv(r['price_pos_20']), sv(r['money_flow']), sv(r['rel_strength']),
                code, calc_date))
            
        except: continue
    
    if updates:
        c.executemany('''
            UPDATE stock_factors 
            SET ret_20=?, ret_60=?, vol_20=?, ma_20=?, ma_60=?, 
                price_pos_20=?, money_flow=?, rel_strength=?
            WHERE ts_code=? AND trade_date=?
        ''', updates)
        conn.commit()
    
    return len(updates)

def main():
    print("="*60)
    print("更新2026年因子数据 - 补充完整字段")
    print("="*60)
    
    import tushare as ts
    ts.set_token('cd2c935050381b52c9849eb054d1b198c21b0f29be2f025f9a9ece30')
    pro = ts.pro_api()
    
    conn = sqlite3.connect(DB_PATH)
    
    # 获取2026年交易日
    dates = pro.trade_cal(exchange='SSE', start_date='20260101', end_date='20260302')
    dates = dates[dates['is_open']==1]['cal_date'].tolist()
    
    print(f"待更新: {len(dates)}天")
    
    for i, date in enumerate(dates):
        count = update_factors_for_date(conn, date)
        print(f"[{i+1}/{len(dates)}] {date}: 更新{count}只")
    
    conn.close()
    print("完成!")

if __name__ == '__main__':
    main()
