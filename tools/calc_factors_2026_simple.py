#!/root/.openclaw/workspace/venv/bin/python3
"""
2026年因子计算 - 分批次版本
每批5天，避免长时间运行中断
"""
import tushare as ts
import sqlite3
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import sys

TUSHARE_TOKEN = 'cd2c935050381b52c9849eb054d1b198c21b0f29be2f025f9a9ece30'
DB_PATH = '/root/.openclaw/workspace/data/historical/historical.db'

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")
    sys.stdout.flush()

def calc_one_day(conn, pro, calc_date):
    """计算单日因子"""
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
    
    records = []
    stocks = df[df['trade_date']==calc_date]['ts_code'].unique()
    
    for code in stocks:
        try:
            s = df[df['ts_code']==code].sort_values('trade_date').copy()
            if len(s) < 60:
                continue
            
            # 简化因子计算（核心字段）
            ret_20 = s['close'].pct_change(20).iloc[-1] * 100
            ret_60 = s['close'].pct_change(60).iloc[-1] * 100
            vol_20 = s['close'].pct_change().rolling(20).std().iloc[-1] * np.sqrt(252) * 100
            
            if pd.isna(ret_20) or pd.isna(vol_20):
                continue
            
            now = datetime.now().isoformat()
            records.append((code, calc_date, float(ret_20), float(ret_60), float(vol_20), now))
            
        except:
            continue
    
    if records:
        c.executemany('''
            INSERT OR REPLACE INTO stock_factors 
            (ts_code, trade_date, ret_20, ret_60, vol_20, update_time)
            VALUES (?,?,?,?,?,?)
        ''', records)
        conn.commit()
    
    return len(records)

def main():
    log("="*60)
    log("2026年因子计算 - 简化版")
    log("="*60)
    
    ts.set_token(TUSHARE_TOKEN)
    pro = ts.pro_api()
    
    conn = sqlite3.connect(DB_PATH)
    
    # 获取交易日
    dates = pro.trade_cal(exchange='SSE', start_date='20260101', end_date='20260302')
    dates = dates[dates['is_open']==1]['cal_date'].tolist()
    
    log(f"总天数: {len(dates)}")
    
    for i, date in enumerate(dates):
        count = calc_one_day(conn, pro, date)
        log(f"[{i+1}/{len(dates)}] {date}: {count}只")
    
    conn.close()
    log("完成!")

if __name__ == '__main__':
    main()
