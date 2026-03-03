#!/usr/bin/env python3
"""
数据回补后台守护进程 - 可断点续传
用于session断开后继续执行
"""
import sqlite3
import pandas as pd
import time
import tushare as ts
import json
import os
from datetime import datetime
from pathlib import Path

WORKSPACE = '/root/.openclaw/workspace'
DB_PATH = f'{WORKSPACE}/data/historical/historical.db'
STATE_FILE = f'{WORKSPACE}/data/supplement_state.json'
LOG_FILE = f'{WORKSPACE}/logs/supplement_daemon.log'
REPORT_FILE = f'{WORKSPACE}/reports/supplement_progress.json'
TS_TOKEN = 'cd2c935050381b52c9849eb054d1b198c21b0f29be2f025f9a9ece30'

BATCH_SIZE = 100  # 每批处理100只
YEARS = [2018, 2019, 2020, 2021, 2022, 2023, 2024, 2025]

# 初始化Tushare
ts.set_token(TS_TOKEN)
pro = ts.pro_api()

def log(msg):
    line = f"[{datetime.now().strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    with open(LOG_FILE, 'a') as f:
        f.write(line + '\n')

def load_state():
    """加载执行状态"""
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, 'r') as f:
            return json.load(f)
    return {
        'current_year': 2018,
        'processed_stocks': [],
        'total_inserted': 0,
        'start_time': datetime.now().isoformat(),
        'status': 'running'
    }

def save_state(state):
    """保存执行状态"""
    state['last_update'] = datetime.now().isoformat()
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f, indent=2)

def generate_report():
    """生成进度报告"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    report = {
        'timestamp': datetime.now().isoformat(),
        'years': {}
    }
    
    for year in YEARS:
        cursor.execute("""
            SELECT COUNT(*), COUNT(DISTINCT ts_code) 
            FROM fina_tushare 
            WHERE period LIKE ?
        """, (f'{year}%',))
        records, stocks = cursor.fetchone()
        report['years'][str(year)] = {
            'records': records,
            'stocks': stocks,
            'expected_stocks': 5000  # 预计5000只
        }
    
    conn.close()
    
    with open(REPORT_FILE, 'w') as f:
        json.dump(report, f, indent=2)
    
    return report

def get_active_stocks():
    """获取当前上市的股票"""
    try:
        df_basic = pro.stock_basic(exchange='', list_status='L', fields='ts_code,name,list_date')
        return df_basic['ts_code'].tolist()
    except Exception as e:
        log(f"❌ 获取上市股票失败: {e}")
        return []

def get_pending_stocks_for_year(year, processed_stocks, active_stocks):
    """获取某年度未处理的股票"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # 排除已处理的
    exclude_list = processed_stocks[:]
    
    # 查询该年度缺失数据且未处理的上市股票
    placeholders = ','.join(['?' for _ in active_stocks])
    exclude_placeholders = ','.join(['?' for _ in exclude_list]) if exclude_list else "''"
    
    query = f"""
        SELECT ts_code FROM stock_basic 
        WHERE ts_code IN ({placeholders})
        AND ts_code NOT IN ({exclude_placeholders})
        AND ts_code NOT IN (
            SELECT DISTINCT ts_code FROM fina_tushare 
            WHERE period LIKE '{year}%'
        )
        LIMIT {BATCH_SIZE}
    """
    
    params = active_stocks + (exclude_list if exclude_list else [])
    cursor.execute(query, params)
    
    stocks = [r[0] for r in cursor.fetchall()]
    conn.close()
    
    return stocks

def process_year(year, stocks):
    """处理某一年度的数据"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    periods = [f"{year}0331", f"{year}0630", f"{year}0930", f"{year}1231"]
    inserted = 0
    
    for i, ts_code in enumerate(stocks):
        if i % 10 == 0:
            log(f"  {year}年 进度: {i}/{len(stocks)} | 入库:{inserted}")
        
        for period in periods:
            try:
                # 检查是否已存在
                cursor.execute(
                    "SELECT 1 FROM fina_tushare WHERE ts_code=? AND period=?",
                    (ts_code, period)
                )
                if cursor.fetchone():
                    continue
                
                # 查询
                df = pro.fina_indicator(
                    ts_code=ts_code, 
                    period=period,
                    fields='ts_code,roe,roe_waa,roe_dt,roa,roic,netprofit_yoy,dt_netprofit_yoy,revenue_yoy,grossprofit_margin,netprofit_margin,assets_turn,op_yoy,debt_to_assets,current_ratio'
                )
                
                if df is not None and not df.empty:
                    row = df.iloc[0]
                    cursor.execute('''
                        INSERT OR REPLACE INTO fina_tushare 
                        (ts_code, period, roe, roe_waa, roe_dt, roa, roic, 
                         netprofit_yoy, dt_netprofit_yoy, revenue_yoy, 
                         grossprofit_margin, netprofit_margin, assets_turn, op_yoy, 
                         debt_to_assets, current_ratio, update_time)
                        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,datetime('now'))
                    ''', (
                        ts_code, period, 
                        row.get('roe'), row.get('roe_waa'), row.get('roe_dt'),
                        row.get('roa'), row.get('roic'),
                        row.get('netprofit_yoy'), row.get('dt_netprofit_yoy'), row.get('revenue_yoy'),
                        row.get('grossprofit_margin'), row.get('netprofit_margin'), row.get('assets_turn'),
                        row.get('op_yoy'), row.get('debt_to_assets'), row.get('current_ratio')
                    ))
                    inserted += 1
                
                time.sleep(0.35)
                
            except Exception as e:
                log(f"    ⚠️ {ts_code} {period}: {str(e)[:50]}")
                time.sleep(1)
        
        if i % 10 == 0:
            conn.commit()
    
    conn.commit()
    conn.close()
    
    return inserted

def main():
    """主函数 - 守护进程模式"""
    log("=" * 60)
    log("🚀 数据回补守护进程启动")
    log("=" * 60)
    
    # 加载状态
    state = load_state()
    log(f"加载状态: {state['current_year']}年, 已处理{len(state['processed_stocks'])}只")
    
    # 获取上市股票列表
    active_stocks = get_active_stocks()
    if not active_stocks:
        log("❌ 无法获取上市股票，退出")
        return
    
    log(f"✅ 获取到{len(active_stocks)}只上市股票")
    
    # 按年度处理
    for year in YEARS:
        if year < state['current_year']:
            continue  # 跳过已完成的年份
        
        log(f"\n{'=' * 60}")
        log(f"📅 处理 {year} 年度")
        log(f"{'=' * 60}")
        
        year_total = 0
        batch_num = 0
        
        while True:
            # 获取待处理股票
            stocks = get_pending_stocks_for_year(
                year, state['processed_stocks'], active_stocks
            )
            
            if not stocks:
                log(f"✅ {year}年数据已完整")
                break
            
            batch_num += 1
            log(f"\n批次 {batch_num}: 处理 {len(stocks)} 只")
            
            # 处理
            inserted = process_year(year, stocks)
            year_total += inserted
            
            # 更新状态
            state['processed_stocks'].extend(stocks)
            state['total_inserted'] += inserted
            save_state(state)
            
            log(f"✅ 批次完成: 入库 {inserted} 条")
            
            # 生成报告
            report = generate_report()
            log(f"📊 进度报告已更新: {REPORT_FILE}")
            
            # 每小时休息一次
            if batch_num % 10 == 0:
                log(f"⏸️ 已处理10批次，休息30秒...")
                time.sleep(30)
        
        # 年度完成
        state['current_year'] = year + 1
        state['processed_stocks'] = []  # 清空已处理列表
        save_state(state)
        
        log(f"✅ {year}年度完成，共入库 {year_total} 条")
    
    # 全部完成
    state['status'] = 'completed'
    state['end_time'] = datetime.now().isoformat()
    save_state(state)
    
    log("\n" + "=" * 60)
    log("✅ 所有年度处理完成!")
    log(f"总入库: {state['total_inserted']} 条")
    log("=" * 60)

if __name__ == '__main__':
    main()
