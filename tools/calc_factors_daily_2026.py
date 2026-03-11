#!/root/.openclaw/workspace/venv/bin/python3
"""
逐日因子计算 - 2026年（方案A）
每天单独计算，避免内存问题
日志: logs/calc_factors_daily_2026.log
"""
import os, sys, sqlite3, pandas as pd, numpy as np
from datetime import datetime, timedelta
import time
import logging

log_file = '/root/.openclaw/workspace/logs/calc_factors_daily_2026.log'
os.makedirs(os.path.dirname(log_file), exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(message)s',
    handlers=[logging.FileHandler(log_file), logging.StreamHandler(sys.stdout)]
)
log = logging.info

WORKSPACE = '/root/.openclaw/workspace'
DB_PATH = f'{WORKSPACE}/data/historical/historical.db'

def calc_factors_for_date(conn, calc_date):
    """计算单日的全因子"""
    c = conn.cursor()
    
    # 只读取该日期需要的60天历史
    query_start = (datetime.strptime(calc_date, '%Y%m%d') - timedelta(days=70)).strftime('%Y%m%d')
    
    df = pd.read_sql(f'''
        SELECT ts_code, trade_date, close, volume, high, low, open
        FROM daily_price 
        WHERE trade_date BETWEEN "{query_start}" AND "{calc_date}"
        ORDER BY ts_code, trade_date
    ''', conn)
    
    if df.empty or len(df) < 100:
        log(f"  {calc_date}: 原始数据不足")
        return 0
    
    # 计算市场收益
    df['trade_date'] = pd.to_datetime(df['trade_date'])
    market = df.groupby('trade_date')['close'].last().pct_change().reset_index()
    market.columns = ['trade_date', 'market_ret']
    df = df.merge(market, on='trade_date', how='left')
    df['trade_date'] = df['trade_date'].dt.strftime('%Y%m%d')
    
    tech_records, def_records, timing_records = [], [], []
    stocks = df[df['trade_date']==calc_date]['ts_code'].unique()
    
    for code in stocks:
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
            
            # 资金流向
            s['money_flow'] = (s['close'] - s['close'].shift(1)) * s['volume'] / 1000000
            s['stock_ret'] = s['close'].pct_change()
            s['rel_strength'] = (s['stock_ret'] - s['market_ret']).rolling(20).sum() * 100
            
            # 防御因子
            s['vol_120'] = s['close'].pct_change().rolling(60).std() * np.sqrt(252) * 100
            cummax = s['close'].cummax()
            s['max_dd_120'] = ((s['close']-cummax)/cummax).rolling(60).min() * 100
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
            
            # 匹配表结构: ts_code, trade_date, ret_3, ret_5, vol_5, ma_3, ma_5, rsi_5, macd, update_time
            rsi_5_val = sv(r['rsi_14']) if 'rsi_14' in r else 50.0
            tech_records.append((code, calc_date, sv(r['ret_3']), sv(r['ret_5']),
                sv(r['vol_5']), sv(r['ma_5']), sv(r['ma_20']), rsi_5_val, sv(r['macd']), now))
            
            # 防御因子表: ts_code, trade_date, vol_5, max_dd_5, sharpe_like, update_time (6列)
            def_records.append((code, calc_date, sv(r['vol_120']), sv(r['max_dd_120']),
                sv(r['sharpe_like']), now))
            
            # 择时因子表: ts_code, trade_date, trend_3, breakout_3, volume_spike, update_time (6列)
            timing_records.append((code, calc_date, sv(r['trend_20']), sv(r['breakout_20']),
                sv(r['volume_spike']), now))
            
        except:
            continue
    
    # 写入 - 匹配表结构
    if tech_records:
        c.executemany('INSERT OR REPLACE INTO stock_factors VALUES (?,?,?,?,?,?,?,?,?,?)', tech_records)
    if def_records:
        c.executemany('INSERT OR REPLACE INTO stock_defensive VALUES (?,?,?,?,?,?)', def_records)
    if timing_records:
        c.executemany('INSERT OR REPLACE INTO stock_timing VALUES (?,?,?,?,?,?)', timing_records)
    conn.commit()
    
    return len(tech_records)

def main():
    log("="*60)
    log("逐日因子计算 - 2026年")
    log("="*60)
    
    import tushare as ts
    ts.set_token('cd2c935050381b52c9849eb054d1b198c21b0f29be2f025f9a9ece30')
    pro = ts.pro_api()
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # 获取2026年交易日
    dates = pro.trade_cal(exchange='SSE', start_date='20260101', end_date='20260302')
    dates = dates[dates['is_open']==1]['cal_date'].tolist()
    
    # 检查已存在的因子
    c.execute('SELECT DISTINCT trade_date FROM stock_factors WHERE trade_date BETWEEN "20260101" AND "20261231"')
    existing = set([r[0] for r in c.fetchall()])
    
    todo = [d for d in dates if d not in existing]
    log(f"待计算: {len(todo)}天 (共{len(dates)}天, 已存在{len(existing)}天)")
    
    start_time = datetime.now()
    total = 0
    
    for i, date in enumerate(todo):
        count = calc_factors_for_date(conn, date)
        total += count
        elapsed = (datetime.now() - start_time).total_seconds()
        avg_time = elapsed / (i+1) if i > 0 else 0
        remain = avg_time * (len(todo)-i-1) / 60 if avg_time > 0 else 0
        log(f"[{i+1}/{len(todo)}] {date}: {count}只 | 累计:{total} | 预计剩余:{remain:.0f}min")
    
    conn.close()
    total_time = (datetime.now() - start_time).total_seconds()
    log("="*60)
    log(f"完成! {len(todo)}天, {total}只股票, 耗时{total_time/60:.1f}分钟")
    log("="*60)

if __name__ == '__main__':
    main()
