#!/root/.openclaw/workspace/venv/bin/python3
"""
后台因子计算脚本 - 2026年数据
日志: logs/calc_factors_2026.log
"""
import os, sys, sqlite3, pandas as pd, numpy as np
from datetime import datetime, timedelta
import time
import logging

log_file = '/root/.openclaw/workspace/logs/calc_factors_2026.log'
os.makedirs(os.path.dirname(log_file), exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(message)s',
    handlers=[logging.FileHandler(log_file), logging.StreamHandler(sys.stdout)]
)
log = logging.info

WORKSPACE = '/root/.openclaw/workspace'
DB_PATH = f'{WORKSPACE}/data/historical/historical.db'

def init_tables(conn):
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS stock_factors (
        ts_code TEXT, trade_date TEXT, ret_3 REAL, ret_5 REAL, ret_20 REAL,
        vol_5 REAL, vol_20 REAL, ma_5 REAL, ma_20 REAL, rsi_14 REAL,
        macd REAL, money_flow REAL, rel_strength REAL, update_time TEXT,
        PRIMARY KEY(ts_code, trade_date))''')
    c.execute('''CREATE TABLE IF NOT EXISTS stock_defensive (
        ts_code TEXT, trade_date TEXT, vol_120 REAL, max_dd_120 REAL,
        downside_vol REAL, sharpe_like REAL, low_vol_score REAL, beta_60 REAL,
        update_time TEXT, PRIMARY KEY(ts_code, trade_date))''')
    c.execute('''CREATE TABLE IF NOT EXISTS stock_timing (
        ts_code TEXT, trade_date TEXT, trend_20 REAL, breakout_20 REAL,
        support_60 REAL, resistance_60 REAL, volume_spike REAL, price_gap REAL,
        update_time TEXT, PRIMARY KEY(ts_code, trade_date))''')
    conn.commit()

def calc_all_factors(conn, dates_to_calc):
    """计算指定日期的全因子"""
    c = conn.cursor()
    
    # 读取所有需要的原始数据
    start_date = min(dates_to_calc)
    end_date = max(dates_to_calc)
    # 扩展范围以获取足够历史
    query_start = (datetime.strptime(start_date, '%Y%m%d') - timedelta(days=130)).strftime('%Y%m%d')
    
    log(f"读取原始数据: {query_start} ~ {end_date}")
    df = pd.read_sql(f'''
        SELECT ts_code, trade_date, close, volume, high, low, open
        FROM daily_price 
        WHERE trade_date BETWEEN "{query_start}" AND "{end_date}"
        ORDER BY ts_code, trade_date
    ''', conn)
    
    if df.empty:
        log("⚠️ 无原始数据")
        return 0
    
    log(f"原始数据: {len(df)}条, {df['trade_date'].nunique()}天")
    
    # 计算市场收益
    df['trade_date'] = pd.to_datetime(df['trade_date'])
    market = df.groupby('trade_date')['close'].last().pct_change().reset_index()
    market.columns = ['trade_date', 'market_ret']
    df = df.merge(market, on='trade_date', how='left')
    df['trade_date'] = df['trade_date'].dt.strftime('%Y%m%d')
    
    total_factors = 0
    
    for calc_date in dates_to_calc:
        log(f"📊 计算因子: {calc_date}")
        
        # 获取该日期需要的股票列表
        stocks_today = df[df['trade_date'] == calc_date]['ts_code'].unique()
        
        tech_records, def_records, timing_records = [], [], []
        
        for code in stocks_today:
            try:
                s = df[df['ts_code']==code].sort_values('trade_date').copy()
                if len(s) < 20:
                    continue
                
                # 技术因子
                s['ret_3'] = s['close'].pct_change(3) * 100
                s['ret_5'] = s['close'].pct_change(5) * 100
                s['ret_20'] = s['close'].pct_change(20) * 100
                s['vol_5'] = s['close'].pct_change().rolling(5).std() * np.sqrt(252) * 100
                s['vol_20'] = s['close'].pct_change().rolling(20).std() * np.sqrt(252) * 100
                s['ma_5'] = s['close'].rolling(5).mean()
                s['ma_20'] = s['close'].rolling(20).mean()
                
                # RSI
                delta = s['close'].diff()
                gain = delta.where(delta>0,0).rolling(14).mean()
                loss = (-delta.where(delta<0,0)).rolling(14).mean()
                s['rsi_14'] = 100 - (100/(1+gain/(loss+1e-10)))
                
                # MACD
                ema12 = s['close'].ewm(span=12).mean()
                ema26 = s['close'].ewm(span=26).mean()
                s['macd'] = ema12 - ema26
                
                # 资金流向/相对强弱
                s['money_flow'] = (s['close'] - s['close'].shift(1)) * s['volume'] / 1000000
                s['stock_ret'] = s['close'].pct_change()
                s['rel_strength'] = (s['stock_ret'] - s['market_ret']).rolling(20).sum() * 100
                
                # 防御因子
                s['vol_120'] = s['close'].pct_change().rolling(120).std() * np.sqrt(252) * 100
                cummax = s['close'].cummax()
                s['max_dd_120'] = ((s['close']-cummax)/cummax).rolling(120).min() * 100
                neg_ret = s['close'].pct_change().where(s['close'].pct_change()<0, np.nan)
                s['downside_vol'] = neg_ret.rolling(120).std() * np.sqrt(252) * 100
                s['sharpe_like'] = s['ret_20'] / (s['vol_20'] + 1e-10)
                
                # 择时因子
                s['trend_20'] = (s['close'] > s['ma_20']).astype(int)
                s['breakout_20'] = (s['high'] > s['high'].rolling(20).max().shift(1)).astype(int)
                s['support_60'] = s['low'].rolling(60).min()
                s['resistance_60'] = s['high'].rolling(60).max()
                s['volume_spike'] = (s['volume'] > s['volume'].rolling(20).mean() * 2).astype(int)
                s['price_gap'] = ((s['open'] - s['close'].shift(1)) / s['close'].shift(1) * 100).abs()
                
                # 取当日
                today = s[s['trade_date']==calc_date]
                if len(today)==0:
                    continue
                r = today.iloc[0]
                now = datetime.now().isoformat()
                
                def sv(v): return 0.0 if pd.isna(v) else float(v)
                
                tech_records.append((code, calc_date, sv(r['ret_3']), sv(r['ret_5']), sv(r['ret_20']),
                    sv(r['vol_5']), sv(r['vol_20']), sv(r['ma_5']), sv(r['ma_20']),
                    sv(r['rsi_14']), sv(r['macd']), sv(r['money_flow']), sv(r['rel_strength']), now))
                
                def_records.append((code, calc_date, sv(r['vol_120']), sv(r['max_dd_120']),
                    sv(r['downside_vol']), sv(r['sharpe_like']), 0.5, 1.0, now))
                
                timing_records.append((code, calc_date, sv(r['trend_20']), sv(r['breakout_20']),
                    sv(r['support_60']), sv(r['resistance_60']), sv(r['volume_spike']), sv(r['price_gap']), now))
                
            except Exception as e:
                continue
        
        # 批量写入
        if tech_records:
            c.executemany('INSERT OR REPLACE INTO stock_factors VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)', tech_records)
        if def_records:
            c.executemany('INSERT OR REPLACE INTO stock_defensive VALUES (?,?,?,?,?,?,?,?,?)', def_records)
        if timing_records:
            c.executemany('INSERT OR REPLACE INTO stock_timing VALUES (?,?,?,?,?,?,?,?,?)', timing_records)
        conn.commit()
        
        total_factors += len(tech_records)
        log(f"✅ {calc_date}: {len(tech_records)}只 (技术+防御+择时)")
    
    return total_factors

def main():
    log("="*70)
    log("2026年因子计算 - 后台任务")
    log("="*70)
    
    import tushare as ts
    ts.set_token('cd2c935050381b52c9849eb054d1b198c21b0f29be2f025f9a9ece30')
    pro = ts.pro_api()
    
    conn = sqlite3.connect(DB_PATH)
    init_tables(conn)
    
    # 获取2026年所有交易日
    dates = pro.trade_cal(exchange='SSE', start_date='20260101', end_date='20260302')
    dates = dates[dates['is_open']==1]['cal_date'].tolist()
    log(f"共{len(dates)}个交易日需要计算因子")
    
    # 检查已存在的因子
    c = conn.cursor()
    c.execute('SELECT DISTINCT trade_date FROM stock_factors WHERE trade_date BETWEEN "20260101" AND "20261231"')
    existing = set([r[0] for r in c.fetchall()])
    log(f"已存在因子: {len(existing)}天")
    
    todo = [d for d in dates if d not in existing]
    log(f"待计算: {len(todo)}天")
    
    if not todo:
        log("无需计算，全部已存在!")
        conn.close()
        return
    
    # 批量计算（每批5天，避免内存问题）
    batch_size = 5
    total = 0
    
    for i in range(0, len(todo), batch_size):
        batch = todo[i:i+batch_size]
        log(f"\n批次 [{i//batch_size + 1}/{(len(todo)+batch_size-1)//batch_size}]: {batch[0]} ~ {batch[-1]}")
        count = calc_all_factors(conn, batch)
        total += count
        log(f"累计: {total}只")
    
    conn.close()
    log("="*70)
    log(f"完成! 总计算: {total}只股票的因子")
    log("="*70)

if __name__ == '__main__':
    main()
