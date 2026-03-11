#!/root/.openclaw/workspace/venv/bin/python3
"""
量化数据系统 - 全量数据补充脚本
补充2018-2024年完整数据用于WFO回测

补充内容:
1. 技术指标 (RSI, MACD) - stock_technical_factors
2. 财务因子 (ROE, 杜邦分析) - stock_fina_tushare
3. 估值因子 (PE, PB) - stock_fina

数据源:
- 本地: daily_price (日线)
- Tushare Pro: 财务数据、估值数据
"""
import os
import sys
import sqlite3
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from concurrent.futures import ProcessPoolExecutor, as_completed
import multiprocessing
import time
import tushare as ts

WORKSPACE = '/root/.openclaw/workspace'
DB_PATH = f'{WORKSPACE}/data/historical/historical.db'
TS_TOKEN = 'cd2c935050381b52c9849eb054d1b198c21b0f29be2f025f9a9ece30'

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

def init_tushare():
    """初始化Tushare"""
    ts.set_token(TS_TOKEN)
    return ts.pro_api()

# ============================================
# 1. 技术指标补充 (RSI, MACD)
# ============================================

def calc_rsi(prices, window=14):
    """计算RSI"""
    delta = prices.diff()
    gain = delta.where(delta > 0, 0).rolling(window=window, min_periods=1).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=window, min_periods=1).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def calc_macd(prices, fast=12, slow=26, signal=9):
    """计算MACD"""
    exp1 = prices.ewm(span=fast, adjust=False).mean()
    exp2 = prices.ewm(span=slow, adjust=False).mean()
    macd = exp1 - exp2
    macd_signal = macd.ewm(span=signal, adjust=False).mean()
    macd_hist = macd - macd_signal
    return macd, macd_signal, macd_hist

def supplement_technical_for_stock(args):
    """为单只股票补充技术指标"""
    ts_code, db_path = args
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # 检查是否已有数据
        cursor.execute(
            "SELECT COUNT(*) FROM stock_technical_factors WHERE ts_code=? AND trade_date BETWEEN '20180101' AND '20241231'",
            (ts_code,)
        )
        existing = cursor.fetchone()[0]
        
        if existing > 500:  # 假设已有足够数据
            conn.close()
            return ts_code, 'skipped', existing
        
        # 获取日线数据
        df = pd.read_sql(f"""
            SELECT ts_code, trade_date, close, high, low, vol, amount
            FROM daily_price 
            WHERE ts_code='{ts_code}' AND trade_date BETWEEN '20180101' AND '20241231'
            ORDER BY trade_date
        """, conn)
        
        if len(df) < 60:
            conn.close()
            return ts_code, 'insufficient_data', 0
        
        df = df.sort_values('trade_date')
        
        # 计算RSI
        df['rsi_14'] = calc_rsi(df['close'], 14)
        
        # 计算MACD
        df['macd'], df['macd_signal'], df['macd_hist'] = calc_macd(df['close'])
        
        # 计算额外技术指标
        df['rsi_6'] = calc_rsi(df['close'], 6)
        df['rsi_24'] = calc_rsi(df['close'], 24)
        
        # 保存到数据库
        df['update_time'] = datetime.now().isoformat()
        records = df[['ts_code', 'trade_date', 'close', 'rsi_14', 'rsi_6', 'rsi_24',
                      'macd', 'macd_signal', 'macd_hist', 'update_time']].copy()
        
        for _, row in records.iterrows():
            cursor.execute("""
                INSERT OR REPLACE INTO stock_technical_factors 
                (ts_code, trade_date, close, rsi_14, rsi_6, rsi_24,
                 macd, macd_signal, macd_hist, update_time)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, tuple(row))
        
        conn.commit()
        conn.close()
        
        return ts_code, 'success', len(records)
        
    except Exception as e:
        return ts_code, f'error: {str(e)[:50]}', 0

def supplement_technical_factors():
    """补充所有股票的技术指标"""
    log("="*60)
    log("🚀 开始补充技术指标 (2018-2024)")
    log("="*60)
    
    conn = sqlite3.connect(DB_PATH)
    
    # 获取需要补充的股票列表
    df_stocks = pd.read_sql("""
        SELECT DISTINCT ts_code 
        FROM daily_price 
        WHERE trade_date BETWEEN '20180101' AND '20241231'
        AND ts_code NOT IN (
            SELECT ts_code FROM stock_technical_factors 
            WHERE trade_date BETWEEN '20180101' AND '20241231'
            GROUP BY ts_code HAVING COUNT(*) > 500
        )
    """, conn)
    
    stock_list = df_stocks['ts_code'].tolist()
    conn.close()
    
    log(f"需要补充的股票: {len(stock_list)}只")
    
    if len(stock_list) == 0:
        log("✅ 技术指标数据已完整")
        return
    
    # 多进程处理
    args_list = [(code, DB_PATH) for code in stock_list]
    success_count = 0
    skip_count = 0
    error_count = 0
    total_records = 0
    
    with ProcessPoolExecutor(max_workers=16) as executor:
        futures = {executor.submit(supplement_technical_for_stock, args): args[0] 
                   for args in args_list}
        
        for i, future in enumerate(as_completed(futures), 1):
            ts_code, status, count = future.result()
            
            if status == 'success':
                success_count += 1
                total_records += count
            elif status == 'skipped':
                skip_count += 1
            else:
                error_count += 1
            
            if i % 100 == 0 or i == len(stock_list):
                log(f"进度: {i}/{len(stock_list)} | 成功:{success_count} 跳过:{skip_count} 失败:{error_count} | 新增:{total_records}条")
    
    log(f"\n{'='*60}")
    log(f"✅ 技术指标补充完成!")
    log(f"   成功: {success_count}只")
    log(f"   跳过: {skip_count}只")
    log(f"   失败: {error_count}只")
    log(f"   新增记录: {total_records}条")
    log(f"{'='*60}\n")

# ============================================
# 2. 财务因子补充 (Tushare)
# ============================================

def get_fina_data_from_tushare(pro, ts_code, year, quarter):
    """从Tushare获取财务数据"""
    try:
        period = f"{year}{quarter:02d}01"
        
        # 获取财务指标
        indicator = pro.fina_indicator(ts_code=ts_code, period=period)
        
        if indicator.empty:
            return None
        
        row = indicator.iloc[0]
        
        result = {
            'ts_code': ts_code,
            'year': year,
            'quarter': quarter,
            'report_date': period,
            'roe': row.get('roe'),
            'roe_diluted': row.get('roe_diluted'),
            'roe_avg': row.get('roe_avg'),
            'netprofit_yoy': row.get('netprofit_yoy'),
            'dt_netprofit_yoy': row.get('dt_netprofit_yoy'),
            'revenue_yoy': row.get('revenue_yoy'),
            'grossprofit_margin': row.get('grossprofit_margin'),
            'netprofit_margin': row.get('netprofit_margin'),
            'assets_turn': row.get('assets_turn'),
            'op_yoy': row.get('op_yoy'),
            'ebit_yoy': row.get('ebit_yoy'),
            'debt_to_assets': row.get('debt_to_assets'),
            'current_ratio': row.get('current_ratio'),
            'quick_ratio': row.get('quick_ratio'),
        }
        
        return result
        
    except Exception as e:
        return None

def save_fina_data(conn, data):
    """保存财务数据"""
    try:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO stock_fina_tushare 
            (ts_code, year, quarter, report_date, roe, roe_diluted, roe_avg,
             netprofit_yoy, dt_netprofit_yoy, revenue_yoy,
             grossprofit_margin, netprofit_margin, assets_turn,
             op_yoy, ebit_yoy, debt_to_assets, current_ratio, quick_ratio,
             update_time)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
        ''', [
            data['ts_code'], data['year'], data['quarter'], data['report_date'],
            data['roe'], data['roe_diluted'], data['roe_avg'],
            data['netprofit_yoy'], data['dt_netprofit_yoy'], data['revenue_yoy'],
            data['grossprofit_margin'], data['netprofit_margin'], data['assets_turn'],
            data['op_yoy'], data['ebit_yoy'], data['debt_to_assets'], 
            data['current_ratio'], data['quick_ratio']
        ])
        return True
    except Exception as e:
        return False

def create_fina_tushare_table():
    """创建财务数据表"""
    conn = sqlite3.connect(DB_PATH)
    conn.execute('''
        CREATE TABLE IF NOT EXISTS stock_fina_tushare (
            ts_code TEXT,
            year INTEGER,
            quarter INTEGER,
            report_date TEXT,
            roe REAL,
            roe_diluted REAL,
            roe_avg REAL,
            netprofit_yoy REAL,
            dt_netprofit_yoy REAL,
            revenue_yoy REAL,
            grossprofit_margin REAL,
            netprofit_margin REAL,
            assets_turn REAL,
            op_yoy REAL,
            ebit_yoy REAL,
            debt_to_assets REAL,
            current_ratio REAL,
            quick_ratio REAL,
            update_time TEXT,
            PRIMARY KEY (ts_code, year, quarter)
        )
    ''')
    conn.commit()
    conn.close()

def supplement_fina_factors():
    """补充财务因子"""
    log("="*60)
    log("🚀 开始补充财务因子 (2018-2024)")
    log("="*60)
    
    create_fina_tushare_table()
    pro = init_tushare()
    conn = sqlite3.connect(DB_PATH)
    
    # 获取股票列表
    df_stocks = pd.read_sql("""
        SELECT DISTINCT ts_code FROM stock_basic 
        WHERE ts_code NOT IN (
            SELECT DISTINCT ts_code FROM stock_fina_tushare 
            WHERE year >= 2018
        )
    """, conn)
    
    stocks = df_stocks['ts_code'].tolist()
    log(f"需要补充的股票: {len(stocks)}只")
    
    years = list(range(2018, 2025))
    quarters = [3, 6, 9, 12]
    
    success_count = 0
    total_records = 0
    
    for i, ts_code in enumerate(stocks, 1):
        if i % 10 == 0:
            log(f"进度: {i}/{len(stocks)} | 成功:{success_count} | 累计:{total_records}条")
            conn.commit()
        
        for year in years:
            for q in quarters:
                data = get_fina_data_from_tushare(pro, ts_code, year, q)
                if data and save_fina_data(conn, data):
                    success_count += 1
                    total_records += 1
                time.sleep(0.15)  # 限速
    
    conn.commit()
    conn.close()
    
    log(f"\n{'='*60}")
    log(f"✅ 财务因子补充完成!")
    log(f"   成功: {success_count}条")
    log(f"{'='*60}\n")

# ============================================
# 3. 估值因子补充 (PE, PB)
# ============================================

def supplement_valuation_factors():
    """补充估值因子"""
    log("="*60)
    log("🚀 开始补充估值因子 (PE, PB)")
    log("="*60)
    
    pro = init_tushare()
    conn = sqlite3.connect(DB_PATH)
    
    # 获取需要补充的股票
    df_stocks = pd.read_sql("""
        SELECT DISTINCT ts_code FROM stock_basic 
        WHERE ts_code NOT IN (
            SELECT DISTINCT ts_code FROM stock_fina WHERE pe_ttm IS NOT NULL
        )
    """, conn)
    
    stocks = df_stocks['ts_code'].tolist()
    log(f"需要补充的股票: {len(stocks)}只")
    
    success_count = 0
    
    for i, ts_code in enumerate(stocks, 1):
        if i % 50 == 0:
            log(f"进度: {i}/{len(stocks)} | 成功:{success_count}")
            conn.commit()
        
        try:
            # 获取最新日线数据计算PE/PB
            df = pro.daily_basic(ts_code=ts_code, start_date='20180101', end_date='20241231')
            
            if df.empty:
                continue
            
            for _, row in df.iterrows():
                conn.execute('''
                    INSERT OR REPLACE INTO stock_fina 
                    (ts_code, report_date, pe_ttm, pb, update_time)
                    VALUES (?, ?, ?, ?, datetime('now'))
                ''', (ts_code, row['trade_date'], row['pe_ttm'], row['pb']))
            
            success_count += 1
            time.sleep(0.1)
            
        except Exception as e:
            continue
    
    conn.commit()
    conn.close()
    
    log(f"\n{'='*60}")
    log(f"✅ 估值因子补充完成!")
    log(f"   成功: {success_count}只")
    log(f"{'='*60}\n")

# ============================================
# 主入口
# ============================================

def main():
    log("\n" + "="*60)
    log("🚀 量化数据系统 - 全量数据补充 (2018-2024)")
    log("="*60 + "\n")
    
    # 1. 补充技术指标
    supplement_technical_factors()
    
    # 2. 补充财务因子
    supplement_fina_factors()
    
    # 3. 补充估值因子
    supplement_valuation_factors()
    
    log("\n" + "="*60)
    log("✅ 所有数据补充完成!")
    log("="*60 + "\n")

if __name__ == '__main__':
    main()
