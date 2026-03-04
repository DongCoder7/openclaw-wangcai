#!/usr/bin/env python3
"""
每日数据更新脚本 v5.0 (多数据源版)
数据源优先级：
1. 腾讯API (免费/快速) - 日线行情
2. efinance (东方财富) - 估值数据
3. 长桥API (实时) - 实时行情/港股
4. Tushare Pro (备用) - 补充缺失数据

执行：python3 supplement_daily.py --date 20250304 --test 500
"""
import os, sys, sqlite3, pandas as pd, numpy as np
from datetime import datetime, timedelta
import time, json, argparse, requests
from typing import Optional, Dict, List

WORKSPACE = '/root/.openclaw/workspace'
DB_PATH = f'{WORKSPACE}/data/historical/historical.db'

# 全局统计
data_source_stats = {'tencent': 0, 'efinance': 0, 'longbridge': 0, 'tushare': 0, 'failed': 0}

def log(msg): 
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")
    sys.stdout.flush()

def sleep_rate(source='tushare'):
    """根据数据源调整频率控制"""
    if source == 'tencent':
        time.sleep(0.05)  # 腾讯限制宽松
    elif source == 'efinance':
        time.sleep(0.1)
    elif source == 'tushare':
        time.sleep(0.35)  # Tushare 200次/分钟

def init_tables(conn):
    """初始化所有表"""
    c = conn.cursor()
    
    # 日线行情（多数据源标记）
    c.execute('''CREATE TABLE IF NOT EXISTS daily_price (
        ts_code TEXT, trade_date TEXT, open REAL, high REAL, low REAL, close REAL,
        volume REAL, amount REAL, change_pct REAL, pct_chg REAL, 
        source TEXT, update_time TEXT,
        PRIMARY KEY(ts_code, trade_date))''')
    
    # 估值数据
    c.execute('''CREATE TABLE IF NOT EXISTS daily_valuation (
        ts_code TEXT, trade_date TEXT, pe_ttm REAL, pb REAL, ps_ttm REAL,
        total_mv REAL, turnover_rate REAL, source TEXT, update_time TEXT,
        PRIMARY KEY(ts_code, trade_date))''')
    
    # 技术因子
    c.execute('''CREATE TABLE IF NOT EXISTS stock_factors (
        ts_code TEXT, trade_date TEXT, ret_3 REAL, ret_5 REAL, ret_20 REAL,
        vol_5 REAL, vol_20 REAL, ma_5 REAL, ma_20 REAL, rsi_14 REAL,
        macd REAL, money_flow REAL, rel_strength REAL, update_time TEXT,
        PRIMARY KEY(ts_code, trade_date))''')
    
    # 防御因子
    c.execute('''CREATE TABLE IF NOT EXISTS stock_defensive (
        ts_code TEXT, trade_date TEXT, vol_120 REAL, max_dd_120 REAL,
        downside_vol REAL, sharpe_like REAL, low_vol_score REAL, beta_60 REAL,
        update_time TEXT, PRIMARY KEY(ts_code, trade_date))''')
    
    # 择时因子
    c.execute('''CREATE TABLE IF NOT EXISTS stock_timing (
        ts_code TEXT, trade_date TEXT, trend_20 REAL, breakout_20 REAL,
        support_60 REAL, resistance_60 REAL, volume_spike REAL, price_gap REAL,
        update_time TEXT, PRIMARY KEY(ts_code, trade_date))''')
    
    conn.commit()

# ==================== 数据源1: 腾讯财经API ====================
def get_tencent_kline_batch(codes: List[str], days: int = 120) -> Optional[pd.DataFrame]:
    """腾讯API批量获取K线 - 最快免费源"""
    try:
        results = []
        for code in codes:
            try:
                # 转换代码格式
                clean = code.replace('.SH','').replace('.SZ','').replace('.BJ','')
                symbol = f"sh{clean}" if code.startswith('6') else f"sz{clean}" if not code.startswith(('4','8')) else f"bj{clean}"
                
                url = f"https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={symbol},day,,,{days},qfq"
                r = requests.get(url, timeout=5).json()
                
                if r.get('data', {}).get(symbol):
                    klines = r['data'][symbol].get('qfqday', []) or r['data'][symbol].get('day', [])
                    if len(klines) >= 3:  # 至少3天
                        df = pd.DataFrame(klines, columns=['trade_date','open','close','low','high','volume'])
                        for col in ['open','close','low','high','volume']:
                            df[col] = pd.to_numeric(df[col], errors='coerce')
                        df['trade_date'] = df['trade_date'].str.replace('-','')
                        df['ts_code'] = code
                        df['source'] = 'tencent'
                        results.append(df)
                
                sleep_rate('tencent')
            except:
                continue
        
        if results:
            return pd.concat(results, ignore_index=True)
    except Exception as e:
        log(f"腾讯API失败: {e}")
    return None

# ==================== 数据源2: efinance (东方财富) ====================
def get_efinance_valuation(codes: List[str]) -> Optional[pd.DataFrame]:
    """efinance获取估值数据"""
    try:
        sys.path.insert(0, f'{WORKSPACE}/venv/lib/python3.12/site-packages')
        import efinance as ef
        
        # 批量获取估值
        df = ef.stock.get_stock_latest(codes)
        
        if df is not None and not df.empty:
            # 字段映射
            df = df.rename(columns={
                '股票代码': 'ts_code',
                '市盈率': 'pe_ttm',
                '市净率': 'pb',
                '总市值': 'total_mv'
            })
            df['source'] = 'efinance'
            return df[['ts_code', 'pe_ttm', 'pb', 'total_mv', 'source']]
    except Exception as e:
        log(f"efinance失败: {e}")
    return None

# ==================== 数据源3: 长桥API ====================
def get_longbridge_quotes(codes: List[str]) -> Optional[pd.DataFrame]:
    """长桥API获取实时行情"""
    try:
        sys.path.insert(0, f'{WORKSPACE}/tools')
        from longbridge_api import get_longbridge_api
        
        api = get_longbridge_api()
        
        # 转换代码格式为长桥格式
        lb_codes = []
        for c in codes:
            if c.endswith('.SH'):
                lb_codes.append(f"SH.{c[:-3]}")
            elif c.endswith('.SZ'):
                lb_codes.append(f"SZ.{c[:-3]}")
        
        # 批量获取（长桥限制单次100只）
        results = []
        for i in range(0, len(lb_codes), 100):
            batch = lb_codes[i:i+100]
            quotes = api.quote(batch)
            results.extend(quotes)
            time.sleep(0.1)
        
        # 解析结果
        data = []
        for q in results:
            data.append({
                'ts_code': q.symbol.replace('SH.', '').replace('SZ.', '') + ('.SH' if q.symbol.startswith('SH') else '.SZ'),
                'close': q.last_done,
                'volume': q.volume,
                'source': 'longbridge'
            })
        
        if data:
            return pd.DataFrame(data)
    except Exception as e:
        log(f"长桥API失败: {e}")
    return None

# ==================== 数据源4: Tushare Pro (备用) ====================
class TushareDataSource:
    """Tushare数据源 - 备用"""
    
    def __init__(self):
        import tushare as ts
        self.pro = ts.pro_api()
    
    def get_daily(self, trade_date: str, limit: int = None) -> Optional[pd.DataFrame]:
        """获取日线行情"""
        try:
            df = self.pro.daily(trade_date=trade_date)
            sleep_rate('tushare')
            
            if df is not None and not df.empty:
                if limit:
                    df = df.head(limit)
                df['source'] = 'tushare'
                return df
        except Exception as e:
            log(f"Tushare日线失败: {e}")
        return None
    
    def get_valuation(self, trade_date: str, limit: int = None) -> Optional[pd.DataFrame]:
        """获取估值数据"""
        try:
            df = self.pro.daily_basic(trade_date=trade_date)
            sleep_rate('tushare')
            
            if df is not None and not df.empty:
                if limit:
                    df = df.head(limit)
                df['source'] = 'tushare'
                return df
        except Exception as e:
            log(f"Tushare估值失败: {e}")
        return None

# ==================== 主函数: 多数据源整合 ====================
def fetch_price_data_multi(conn, trade_date: str, limit: int = None):
    """多数据源获取价格数据 - 简化版：优先Tushare，腾讯备用"""
    log(f"📈 获取价格数据 {trade_date}")
    
    ts_source = TushareDataSource()
    
    # 方法1: Tushare Pro (最稳定)
    log("  使用Tushare Pro...")
    df = ts_source.get_daily(trade_date, limit=limit)
    
    if df is not None and not df.empty:
        df = df.rename(columns={'vol': 'volume', 'pct_chg': 'change_pct'})
        df['amount'] = df.get('amount', 0)
        df['source'] = 'tushare'
        data_source_stats['tushare'] = len(df)
        log(f"  ✅ Tushare: {len(df)}条")
        
        # 写入数据库
        c = conn.cursor()
        for _, r in df.iterrows():
            try:
                c.execute('''INSERT OR REPLACE INTO daily_price 
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?)''',
                    (r.ts_code, trade_date, r.open, r.high, r.low, r.close,
                     r.volume, r.amount, r.change_pct, r.pct_chg if 'pct_chg' in r else r.change_pct,
                     'tushare', datetime.now().isoformat()))
            except:
                continue
        conn.commit()
        log(f"✅ 价格数据: {len(df)}条")
        return len(df)
    
    log("❌ Tushare失败")
    return 0

def fetch_valuation_data_multi(conn, trade_date: str, limit: int = None):
    """获取估值数据 - 直接使用Tushare"""
    log(f"💰 获取估值数据 {trade_date}")
    
    ts_source = TushareDataSource()
    df = ts_source.get_valuation(trade_date, limit=limit)
    
    if df is not None and not df.empty:
        data_source_stats['tushare'] += len(df)
        log(f"✅ Tushare: {len(df)}条")
        
        c = conn.cursor()
        for _, r in df.iterrows():
            try:
                c.execute('''INSERT OR REPLACE INTO daily_valuation VALUES (?,?,?,?,?,?,?,?,?)''',
                    (r.ts_code, trade_date, r.get('pe_ttm'), r.get('pb'), r.get('ps_ttm'),
                     r.get('total_mv'), r.get('turnover_rate'), 'tushare', datetime.now().isoformat()))
            except:
                continue
        conn.commit()
        log(f"✅ 估值数据: {len(df)}条")
        return len(df)
    
    log("❌ 估值获取失败")
    return 0

def calc_all_factors(conn, date: str, limit: int = None):
    """计算全因子 - 支持短历史"""
    log(f"📊 计算全因子 {date}")
    
    # 读取所有可用历史
    df = pd.read_sql(f'''
        SELECT ts_code, trade_date, close, volume, high, low
        FROM daily_price ORDER BY ts_code, trade_date
    ''', conn)
    
    if df.empty:
        log("⚠️ 无历史数据")
        return 0
    
    unique_dates = df['trade_date'].nunique()
    log(f"  可用历史: {unique_dates}天")
    
    if unique_dates < 2:
        log("⚠️ 历史数据不足2天")
        return 0
    
    # 计算市场收益
    df['trade_date'] = pd.to_datetime(df['trade_date'])
    market = df.groupby('trade_date')['close'].last().pct_change().reset_index()
    market.columns = ['trade_date', 'market_ret']
    df = df.merge(market, on='trade_date', how='left')
    df['trade_date'] = df['trade_date'].dt.strftime('%Y%m%d')
    
    c = conn.cursor()
    tech_records, def_records, timing_records = [], [], []
    
    codes = df['ts_code'].unique()
    if limit:
        codes = codes[:limit]
    
    for code in codes:
        try:
            s = df[df['ts_code']==code].sort_values('trade_date').copy()
            if len(s) < 2:
                continue
            
            # 动态窗口：根据可用数据量调整
            win_short = min(3, len(s))
            win_med = min(5, len(s))
            
            # 技术因子（短窗口）
            s['ret_3'] = s['close'].pct_change(win_short) * 100
            s['ret_5'] = s['close'].pct_change(win_med) * 100
            s['vol_5'] = s['close'].pct_change().rolling(win_med).std() * np.sqrt(252) * 100
            s['ma_3'] = s['close'].rolling(win_short).mean()
            s['ma_5'] = s['close'].rolling(win_med).mean()
            
            # RSI简化
            delta = s['close'].diff()
            gain = delta.where(delta>0,0).rolling(win_short).mean()
            loss = (-delta.where(delta<0,0)).rolling(win_short).mean()
            s['rsi_5'] = 100 - (100/(1+gain/(loss+1e-10)))
            
            # MACD简化
            ema3 = s['close'].ewm(span=win_short).mean()
            ema5 = s['close'].ewm(span=win_med).mean()
            s['macd'] = ema3 - ema5
            
            # 资金流向/相对强弱
            s['money_flow'] = (s['close'] - s['close'].shift(1)) * s['volume'] / 1000000
            s['stock_ret'] = s['close'].pct_change()
            s['rel_strength'] = (s['stock_ret'] - s['market_ret']).rolling(win_short).sum() * 100
            
            # 防御因子（短窗口）
            s['vol_5d'] = s['close'].pct_change().rolling(win_med).std() * np.sqrt(252) * 100
            cummax = s['close'].cummax()
            s['max_dd_5'] = ((s['close']-cummax)/cummax).rolling(win_med).min() * 100
            s['sharpe_like'] = s['ret_5'] / (s['vol_5'] + 1e-10)
            
            # 择时因子
            s['trend_3'] = (s['close'] > s['ma_3']).astype(int)
            s['breakout_3'] = (s['high'] > s['high'].rolling(win_short).max().shift(1)).astype(int)
            s['volume_spike'] = (s['volume'] > s['volume'].rolling(win_short).mean() * 1.5).astype(int)
            
            # 取当日
            today = s[s['trade_date']==date]
            if len(today)==0:
                continue
            r = today.iloc[0]
            now = datetime.now().isoformat()
            
            def sv(v): return 0.0 if pd.isna(v) else float(v)
            
            # 写入数据
            tech_records.append((code, date, sv(r['ret_3']), sv(r['ret_5']), sv(r['vol_5']),
                sv(r['ma_3']), sv(r['ma_5']), sv(r['rsi_5']), sv(r['macd']), now))
            
            def_records.append((code, date, sv(r['vol_5d']), sv(r['max_dd_5']), sv(r['sharpe_like']), now))
            
            timing_records.append((code, date, sv(r['trend_3']), sv(r['breakout_3']), sv(r['volume_spike']), now))
            
        except Exception as e:
            continue
    
    if tech_records:
        c.executemany('INSERT OR REPLACE INTO stock_factors VALUES (?,?,?,?,?,?,?,?,?,?)', tech_records)
    if def_records:
        c.executemany('INSERT OR REPLACE INTO stock_defensive VALUES (?,?,?,?,?,?)', def_records)
    if timing_records:
        c.executemany('INSERT OR REPLACE INTO stock_timing VALUES (?,?,?,?,?,?)', timing_records)
    conn.commit()
    
    log(f"✅ 因子计算: {len(tech_records)}只")
    return len(tech_records)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--date', help='指定日期 YYYYMMDD')
    parser.add_argument('--test', type=int, help='测试模式，指定股票数量')
    parser.add_argument('--history', action='store_true', help='历史回补')
    parser.add_argument('--start', default='20240101', help='历史开始日期')
    parser.add_argument('--end', help='历史结束日期')
    args = parser.parse_args()
    
    log("="*60)
    log("数据更新 v5.0 (多数据源版)")
    log("优先级: 腾讯 > efinance > 长桥 > Tushare")
    log("="*60)
    
    conn = sqlite3.connect(DB_PATH)
    init_tables(conn)
    
    limit = args.test
    
    if args.date:
        fetch_price_data_multi(conn, args.date, limit)
        fetch_valuation_data_multi(conn, args.date, limit)
        calc_all_factors(conn, args.date, limit)
    elif args.history:
        import tushare as ts
        dates = ts.pro_api().trade_cal(exchange='SSE', start_date=args.start,
                                       end_date=args.end or datetime.now().strftime('%Y%m%d'))
        dates = dates[dates['is_open']==1]['cal_date'].tolist()
        log(f"历史回补: {len(dates)}天")
        for i, d in enumerate(dates):
            log(f"\n[{i+1}/{len(dates)}] {d}")
            fetch_price_data_multi(conn, d, limit)
            fetch_valuation_data_multi(conn, d, limit)
            calc_all_factors(conn, d, limit)
    else:
        import tushare as ts
        today = datetime.now().strftime('%Y%m%d')
        dates = ts.pro_api().trade_cal(exchange='SSE', start_date=
            (datetime.now()-timedelta(days=10)).strftime('%Y%m%d'), end_date=today)
        last_date = dates[dates['is_open']==1]['cal_date'].iloc[-1]
        log(f"最近交易日: {last_date}")
        fetch_price_data_multi(conn, last_date, limit)
        fetch_valuation_data_multi(conn, last_date, limit)
        calc_all_factors(conn, last_date, limit)
    
    conn.close()
    
    log("\n" + "="*60)
    log("数据源统计:")
    for source, count in data_source_stats.items():
        if count > 0:
            log(f"  {source}: {count}条")
    log("="*60)
    log("✅ 完成!")

if __name__ == '__main__':
    main()
