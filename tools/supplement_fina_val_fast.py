#!/usr/bin/env python3
"""
高效财务和估值数据补充脚本
批量获取 + 批量写入
"""
import sqlite3
import pandas as pd
import time
import tushare as ts
from datetime import datetime

WORKSPACE = '/root/.openclaw/workspace'
DB_PATH = f'{WORKSPACE}/data/historical/historical.db'
TS_TOKEN = 'cd2c935050381b52c9849eb054d1b198c21b0f29be2f025f9a9ece30'

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)

# ============================================
# 财务因子补充
# ============================================

def create_fina_table():
    conn = sqlite3.connect(DB_PATH)
    conn.execute('''
        CREATE TABLE IF NOT EXISTS stock_fina_tushare (
            ts_code TEXT,
            year INTEGER,
            quarter INTEGER,
            report_date TEXT,
            roe REAL, roe_diluted REAL, roe_avg REAL,
            netprofit_yoy REAL, dt_netprofit_yoy REAL, revenue_yoy REAL,
            grossprofit_margin REAL, netprofit_margin REAL, assets_turn REAL,
            op_yoy REAL, ebit_yoy REAL, debt_to_assets REAL,
            current_ratio REAL, quick_ratio REAL,
            update_time TEXT,
            PRIMARY KEY (ts_code, year, quarter)
        )
    ''')
    conn.commit()
    conn.close()
    log("✅ 财务表已创建")

def supplement_fina():
    log("="*50)
    log("🚀 财务因子补充 (2018-2025)")
    log("="*50)
    
    ts.set_token(TS_TOKEN)
    pro = ts.pro_api()
    conn = sqlite3.connect(DB_PATH)
    
    # 获取已有数据的年份
    existing = pd.read_sql("SELECT ts_code, year, quarter FROM stock_fina_tushare", conn)
    log(f"已有财务数据: {len(existing)}条")
    
    years = [2018, 2019, 2020, 2021, 2022, 2023, 2024, 2025]
    quarters = [3, 6, 9, 12]
    
    total_success = 0
    
    for year in years:
        log(f"\n>>> 处理 {year} 年数据...")
        
        for q in quarters:
            period = f"{year}{q:02d}01"
            log(f"    季度 {q}: {period}...")
            
            try:
                # 批量获取一个季度的所有公司财务数据
                df = pro.fina_indicator(period=period, fields='ts_code,end_date,roe,roe_diluted,roe_avg,netprofit_yoy,dt_netprofit_yoy,revenue_yoy,grossprofit_margin,netprofit_margin,assets_turn,op_yoy,ebit_yoy,debt_to_assets,current_ratio,quick_ratio')
                
                if df is not None and not df.empty:
                    df['year'] = year
                    df['quarter'] = q
                    df['report_date'] = period
                    df['update_time'] = datetime.now().isoformat()
                    
                    # 批量写入
                    df.to_sql('stock_fina_tushare', conn, if_exists='append', index=False)
                    log(f"✅ {len(df)}条")
                    total_success += len(df)
                else:
                    log("⚠️ 无数据")
                    
                time.sleep(0.5)  # API限速
                
            except Exception as e:
                log(f"❌ 错误: {str(e)[:30]}")
                time.sleep(1)
        
        # 每 year 提交一次
        conn.commit()
    
    conn.close()
    log(f"\n✅ 财务因子补充完成! 总计: {total_success}条")

# ============================================
# 估值因子补充
# ============================================

def create_val_table():
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
    log("✅ 估值表已创建")

def supplement_valuation():
    log("="*50)
    log("🚀 估值因子补充 (PE, PB)")
    log("="*50)
    
    ts.set_token(TS_TOKEN)
    pro = ts.pro_api()
    conn = sqlite3.connect(DB_PATH)
    
    # 检查已有数据
    existing = pd.read_sql("SELECT COUNT(*) as cnt FROM stock_fina", conn)
    log(f"已有估值数据: {existing.iloc[0]['cnt']}条")
    
    # 获取所有股票
    stocks = pd.read_sql("SELECT ts_code FROM stock_basic", conn)['ts_code'].tolist()
    log(f"总股票数: {len(stocks)}")
    
    # 分批获取 (每批50只)
    batch_size = 50
    total_success = 0
    
    for i in range(0, len(stocks), batch_size):
        batch = stocks[i:i+batch_size]
        batch_str = ','.join(batch)
        
        if (i // batch_size) % 10 == 0:
            log(f"进度: {i}/{len(stocks)} | 已处理: {total_success}条")
        
        try:
            # 批量获取日线基础数据
            df = pro.daily_basic(ts_code=batch_str, start_date='20180101', end_date='20251231', 
                                fields='ts_code,trade_date,pe,pb')
            
            if df is not None and not df.empty:
                df = df.rename(columns={'pe': 'pe_ttm'})
                df['update_time'] = datetime.now().isoformat()
                df.to_sql('stock_fina', conn, if_exists='append', index=False)
                total_success += len(df)
            
            time.sleep(0.5)
            
        except Exception as e:
            log(f"批次 {i//batch_size} 错误: {str(e)[:30]}")
            time.sleep(1)
    
    conn.commit()
    conn.close()
    log(f"\n✅ 估值因子补充完成! 总计: {total_success}条")

# ============================================
# 主入口
# ============================================

def main():
    log("\n" + "="*50)
    log("🚀 财务和估值数据批量补充")
    log("="*50 + "\n")
    
    create_fina_table()
    create_val_table()
    
    supplement_fina()
    supplement_valuation()
    
    log("\n" + "="*50)
    log("✅ 全部完成!")
    log("="*50 + "\n")

if __name__ == '__main__':
    main()
