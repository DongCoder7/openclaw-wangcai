#!/usr/bin/env python3
"""
财务和估值数据补充脚本
只补充财务因子和估值因子，跳过已完整的技术指标
"""
import os
import sys
import sqlite3
import pandas as pd
import time
import tushare as ts

WORKSPACE = '/root/.openclaw/workspace'
DB_PATH = f'{WORKSPACE}/data/historical/historical.db'
TS_TOKEN = 'cd2c935050381b52c9849eb054d1b198c21b0f29be2f025f9a9ece30'

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")
    sys.stdout.flush()

from datetime import datetime

# ============================================
# 1. 财务因子补充 (stock_fina_tushare)
# ============================================

def init_tushare():
    ts.set_token(TS_TOKEN)
    return ts.pro_api()

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
    log("✅ 财务因子表已创建/确认")

def get_fina_data_from_tushare(pro, ts_code, year, quarter):
    """从Tushare获取财务数据"""
    try:
        period = f"{year}{quarter:02d}01"
        indicator = pro.fina_indicator(ts_code=ts_code, period=period)
        
        if indicator.empty:
            return None
        
        row = indicator.iloc[0]
        return {
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
    except Exception as e:
        return None

def supplement_fina_factors():
    """补充财务因子"""
    log("="*60)
    log("🚀 开始补充财务因子 (2018-2025)")
    log("="*60)
    
    create_fina_tushare_table()
    pro = init_tushare()
    conn = sqlite3.connect(DB_PATH)
    
    # 获取所有股票
    df_stocks = pd.read_sql("SELECT DISTINCT ts_code FROM stock_basic", conn)
    stocks = df_stocks['ts_code'].tolist()
    log(f"总股票数: {len(stocks)}只")
    
    years = list(range(2018, 2026))
    quarters = [3, 6, 9, 12]
    
    success_count = 0
    error_count = 0
    
    for i, ts_code in enumerate(stocks, 1):
        if i % 50 == 0:
            log(f"进度: {i}/{len(stocks)} | 成功:{success_count} | 失败:{error_count}")
            conn.commit()
        
        for year in years:
            for q in quarters:
                data = get_fina_data_from_tushare(pro, ts_code, year, q)
                if data:
                    try:
                        conn.execute('''
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
                        success_count += 1
                    except:
                        error_count += 1
                time.sleep(0.12)  # Tushare限速
    
    conn.commit()
    conn.close()
    
    log(f"\n✅ 财务因子补充完成! 成功: {success_count}条, 失败: {error_count}条")

# ============================================
# 2. 估值因子补充 (stock_fina)
# ============================================

def create_valuation_table():
    """创建估值表"""
    conn = sqlite3.connect(DB_PATH)
    conn.execute('''
        CREATE TABLE IF NOT EXISTS stock_fina (
            ts_code TEXT,
            report_date TEXT,
            pe_ttm REAL,
            pb REAL,
            update_time TEXT,
            PRIMARY KEY (ts_code, report_date)
        )
    ''')
    conn.commit()
    conn.close()
    log("✅ 估值因子表已创建/确认")

def supplement_valuation_factors():
    """补充估值因子"""
    log("="*60)
    log("🚀 开始补充估值因子 (PE, PB)")
    log("="*60)
    
    create_valuation_table()
    pro = init_tushare()
    conn = sqlite3.connect(DB_PATH)
    
    # 获取所有股票
    df_stocks = pd.read_sql("SELECT DISTINCT ts_code FROM stock_basic", conn)
    stocks = df_stocks['ts_code'].tolist()
    log(f"总股票数: {len(stocks)}只")
    
    success_count = 0
    
    for i, ts_code in enumerate(stocks, 1):
        if i % 50 == 0:
            log(f"进度: {i}/{len(stocks)} | 成功:{success_count}")
            conn.commit()
        
        try:
            # 获取日线基础数据
            df = pro.daily_basic(ts_code=ts_code, start_date='20180101', end_date='20251231', fields='ts_code,trade_date,pe,pb')
            
            if df is None or df.empty:
                time.sleep(0.1)
                continue
            
            for _, row in df.iterrows():
                try:
                    conn.execute('''
                        INSERT OR REPLACE INTO stock_fina 
                        (ts_code, report_date, pe_ttm, pb, update_time)
                        VALUES (?, ?, ?, ?, datetime('now'))
                    ''', (ts_code, row['trade_date'], row.get('pe'), row.get('pb')))
                    success_count += 1
                except:
                    pass
            
            time.sleep(0.1)
        except Exception as e:
            time.sleep(0.1)
            continue
    
    conn.commit()
    conn.close()
    
    log(f"\n✅ 估值因子补充完成! 成功: {success_count}条")

# ============================================
# 主入口
# ============================================

def main():
    log("\n" + "="*60)
    log("🚀 财务和估值数据补充 (2018-2025)")
    log("="*60 + "\n")
    
    # 1. 补充财务因子
    supplement_fina_factors()
    
    # 2. 补充估值因子
    supplement_valuation_factors()
    
    log("\n" + "="*60)
    log("✅ 所有数据补充完成!")
    log("="*60 + "\n")

if __name__ == '__main__':
    main()
