#!/usr/bin/env python3
"""
Tushare Pro 财务数据补充
补充ROE、杜邦分析等财务因子
"""
import tushare as ts
import sqlite3
import pandas as pd
from datetime import datetime
import time

TOKEN = 'cd2c935050381b52c9849eb054d1b198c21b0f29be2f025f9a9ece30'
DB_PATH = '/root/.openclaw/workspace/data/historical/historical.db'

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

def init_tushare():
    """初始化Tushare"""
    ts.set_token(TOKEN)
    return ts.pro_api()

def get_stock_list():
    """获取股票列表"""
    conn = sqlite3.connect(DB_PATH)
    stocks = conn.execute('SELECT DISTINCT ts_code FROM stock_basic').fetchall()
    conn.close()
    return [s[0] for s in stocks]

def get_fina_data(pro, ts_code, year, quarter):
    """获取财务数据"""
    try:
        # 转换代码格式
        code = ts_code.replace('.SH', '').replace('.SZ', '').replace('.BJ', '')
        
        # 获取利润表
        income = pro.income(ts_code=ts_code, period=f'{year}{quarter:02d}01', fields='ts_code,total_revenue,n_income')
        
        # 获取资产负债表
        balance = pro.balancesheet(ts_code=ts_code, period=f'{year}{quarter:02d}01', fields='ts_code,total_hldr_eqy_exc_min_int')
        
        # 获取指标
        indicator = pro.fina_indicator(ts_code=ts_code, period=f'{year}{quarter:02d}01')
        
        if indicator.empty:
            return None
        
        result = {
            'ts_code': ts_code,
            'year': year,
            'quarter': quarter,
            'roe': indicator['roe'].values[0] if 'roe' in indicator.columns else None,
            'roe_diluted': indicator['roe_diluted'].values[0] if 'roe_diluted' in indicator.columns else None,
            'roe_avg': indicator['roe_avg'].values[0] if 'roe_avg' in indicator.columns else None,
            'netprofit_yoy': indicator['netprofit_yoy'].values[0] if 'netprofit_yoy' in indicator.columns else None,
            'dt_netprofit_yoy': indicator['dt_netprofit_yoy'].values[0] if 'dt_netprofit_yoy' in indicator.columns else None,
            'revenue_yoy': indicator['revenue_yoy'].values[0] if 'revenue_yoy' in indicator.columns else None,
            'grossprofit_margin': indicator['grossprofit_margin'].values[0] if 'grossprofit_margin' in indicator.columns else None,
            'netprofit_margin': indicator['netprofit_margin'].values[0] if 'netprofit_margin' in indicator.columns else None,
            'assets_turn': indicator['assets_turn'].values[0] if 'assets_turn' in indicator.columns else None,
            'op_yoy': indicator['op_yoy'].values[0] if 'op_yoy' in indicator.columns else None,
            'ebit_yoy': indicator['ebit_yoy'].values[0] if 'ebit_yoy' in indicator.columns else None,
        }
        
        return result
        
    except Exception as e:
        return None

def save_fina_data(conn, data):
    """保存财务数据"""
    try:
        conn.execute('''
            INSERT OR REPLACE INTO stock_fina_tushare 
            (ts_code, year, quarter, roe, roe_diluted, roe_avg, 
             netprofit_yoy, dt_netprofit_yoy, revenue_yoy,
             grossprofit_margin, netprofit_margin, assets_turn,
             op_yoy, ebit_yoy, update_time)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
        ''', [
            data['ts_code'], data['year'], data['quarter'],
            data['roe'], data['roe_diluted'], data['roe_avg'],
            data['netprofit_yoy'], data['dt_netprofit_yoy'], data['revenue_yoy'],
            data['grossprofit_margin'], data['netprofit_margin'], data['assets_turn'],
            data['op_yoy'], data['ebit_yoy']
        ])
        return True
    except Exception as e:
        return False

def create_table(conn):
    """创建财务数据表"""
    conn.execute('''
        CREATE TABLE IF NOT EXISTS stock_fina_tushare (
            ts_code TEXT,
            year INTEGER,
            quarter INTEGER,
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
            update_time TEXT,
            PRIMARY KEY (ts_code, year, quarter)
        )
    ''')
    conn.commit()

def main():
    log("="*60)
    log("🚀 Tushare Pro 财务数据补充")
    log("="*60)
    
    pro = init_tushare()
    conn = sqlite3.connect(DB_PATH)
    create_table(conn)
    
    stocks = get_stock_list()
    log(f"股票总数: {len(stocks)}")
    
    # 补充2022-2024年数据
    years = [2022, 2023, 2024]
    quarters = [3, 6, 9, 12]  # Q1, Q2, Q3, Q4
    
    success_count = 0
    fail_count = 0
    
    for i, ts_code in enumerate(stocks, 1):
        if i % 50 == 0:
            log(f"进度: {i}/{len(stocks)} | 成功: {success_count} | 失败: {fail_count}")
            conn.commit()
        
        for year in years:
            for q in quarters:
                data = get_fina_data(pro, ts_code, year, q)
                if data:
                    if save_fina_data(conn, data):
                        success_count += 1
                    else:
                        fail_count += 1
                time.sleep(0.1)  # 限速
    
    conn.commit()
    conn.close()
    
    log(f"\n{'='*60}")
    log(f"✅ 完成! 成功: {success_count}, 失败: {fail_count}")
    log(f"{'='*60}")

if __name__ == '__main__':
    main()
