#!/usr/bin/env python3
"""
Tushare因子快速采集 - 简化版
用于立即获取最新因子数据
"""

import sys
import os
import pandas as pd
import sqlite3
from datetime import datetime, timedelta
import tushare as ts

WORKSPACE = '/root/.openclaw/workspace'
DB_PATH = f'{WORKSPACE}/data/historical/historical.db'

def init_tushare():
    """初始化Tushare"""
    token = ''
    env_file = f'{WORKSPACE}/.tushare.env'
    if os.path.exists(env_file):
        with open(env_file, 'r') as f:
            for line in f:
                if 'TUSHARE_TOKEN' in line and '=' in line:
                    token = line.split('=', 1)[1].strip().strip('"').strip("'")
    return ts.pro_api(token)

def fetch_daily_valuation(pro, trade_date):
    """获取每日估值因子"""
    print(f"📊 获取 {trade_date} 估值因子...")
    
    try:
        df = pro.daily_basic(trade_date=trade_date)
        if df is None or df.empty:
            print("   ⚠️ 无数据")
            return None
        
        # 选择核心字段
        cols = ['ts_code', 'trade_date', 'pe', 'pe_ttm', 'pb', 'ps', 'ps_ttm', 
                'dv_ratio', 'total_mv', 'circ_mv']
        df = df[[c for c in cols if c in df.columns]].copy()
        df['update_time'] = datetime.now().isoformat()
        
        # 保存到数据库
        conn = sqlite3.connect(DB_PATH)
        df.to_sql('stock_valuation_factors', conn, if_exists='append', index=False)
        conn.close()
        
        print(f"   ✅ 保存 {len(df)} 条估值因子")
        return len(df)
        
    except Exception as e:
        print(f"   ❌ 失败: {e}")
        return 0

def fetch_stock_technical(pro, ts_code, trade_date):
    """获取单只股票技术指标"""
    try:
        # 获取60天数据用于计算
        start_date = (datetime.strptime(trade_date, '%Y%m%d') - timedelta(days=60)).strftime('%Y%m%d')
        df = pro.daily(ts_code=ts_code, start_date=start_date, end_date=trade_date)
        
        if df is None or len(df) < 30:
            return None
        
        df = df.sort_values('trade_date')
        
        # RSI_14
        delta = df['close'].diff()
        gain = delta.where(delta > 0, 0).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rs = gain / loss
        df['rsi_14'] = 100 - (100 / (1 + rs))
        
        # MACD
        exp1 = df['close'].ewm(span=12, adjust=False).mean()
        exp2 = df['close'].ewm(span=26, adjust=False).mean()
        df['macd'] = exp1 - exp2
        df['macd_signal'] = df['macd'].ewm(span=9, adjust=False).mean()
        df['macd_hist'] = df['macd'] - df['macd_signal']
        
        # 只保留最新一天
        latest = df.iloc[[-1]][['ts_code', 'trade_date', 'close', 'rsi_14', 'macd', 'macd_signal', 'macd_hist']].copy()
        latest['update_time'] = datetime.now().isoformat()
        
        return latest
        
    except Exception as e:
        return None

def fetch_technical_batch(pro, trade_date, limit=100):
    """批量获取技术指标"""
    print(f"📊 获取技术指标 (前{limit}只)...")
    
    # 获取股票列表
    conn = sqlite3.connect(DB_PATH)
    stocks = pd.read_sql("SELECT DISTINCT ts_code FROM stock_basic LIMIT ?", conn, params=(limit,))
    conn.close()
    
    total = 0
    for i, ts_code in enumerate(stocks['ts_code'], 1):
        if i % 50 == 0:
            print(f"   进度: {i}/{len(stocks)}")
        
        df = fetch_stock_technical(pro, ts_code, trade_date)
        if df is not None:
            conn = sqlite3.connect(DB_PATH)
            df.to_sql('stock_technical_factors', conn, if_exists='append', index=False)
            conn.close()
            total += 1
    
    print(f"   ✅ 保存 {total} 条技术指标")
    return total

def fetch_financial_batch(pro, trade_date, limit=50):
    """批量获取财务因子"""
    print(f"📊 获取财务因子 (前{limit}只)...")
    
    # 获取股票列表
    conn = sqlite3.connect(DB_PATH)
    stocks = pd.read_sql("SELECT DISTINCT ts_code FROM stock_basic LIMIT ?", conn, params=(limit,))
    conn.close()
    
    # 获取最近报告期
    year = trade_date[:4]
    quarter = '0930' if int(trade_date[4:6]) > 9 else '0630' if int(trade_date[4:6]) > 6 else '0331' if int(trade_date[4:6]) > 3 else '1231'
    
    total = 0
    for i, ts_code in enumerate(stocks['ts_code'], 1):
        if i % 20 == 0:
            print(f"   进度: {i}/{len(stocks)}")
        
        try:
            df = pro.fina_indicator(ts_code=ts_code, period=f"{year}{quarter}")
            if df is not None and not df.empty:
                df = df.rename(columns={'end_date': 'trade_date'})
                df['update_time'] = datetime.now().isoformat()
                
                conn = sqlite3.connect(DB_PATH)
                df.to_sql('stock_fina_tushare', conn, if_exists='append', index=False)
                conn.close()
                total += 1
        except:
            pass
    
    print(f"   ✅ 保存 {total} 条财务因子")
    return total

def create_tables():
    """创建表"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS stock_valuation_factors (
        ts_code TEXT, trade_date TEXT, pe REAL, pe_ttm REAL, pb REAL, ps REAL, ps_ttm REAL,
        dv_ratio REAL, total_mv REAL, circ_mv REAL, update_time TEXT,
        PRIMARY KEY (ts_code, trade_date)
    )
    """)
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS stock_technical_factors (
        ts_code TEXT, trade_date TEXT, close REAL, rsi_14 REAL,
        macd REAL, macd_signal REAL, macd_hist REAL, update_time TEXT,
        PRIMARY KEY (ts_code, trade_date)
    )
    """)
    
    conn.commit()
    conn.close()
    print("✅ 数据库表创建完成")

def main():
    """主函数"""
    # 获取日期
    trade_date = (datetime.now() - timedelta(days=1)).strftime('%Y%m%d')
    
    print(f"\n{'='*60}")
    print(f"🚀 Tushare因子快速采集 - {trade_date}")
    print(f"{'='*60}\n")
    
    # 初始化
    pro = init_tushare()
    create_tables()
    
    # 采集估值因子
    fetch_daily_valuation(pro, trade_date)
    
    # 采集技术指标
    fetch_technical_batch(pro, trade_date, limit=200)
    
    # 采集财务因子
    fetch_financial_batch(pro, trade_date, limit=100)
    
    print(f"\n{'='*60}")
    print("✅ 采集完成")
    print(f"{'='*60}\n")

if __name__ == "__main__":
    main()
