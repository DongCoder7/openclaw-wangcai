#!/usr/bin/env python3
"""
分批次财务数据补充 - 修复版
修复内容：
1. 只处理上市状态股票，过滤退市股票
2. 优先处理2018-2022年缺失数据
3. 每批次验证数据入库情况
4. 详细的日志和验证报告
"""
import sqlite3
import pandas as pd
import time
import tushare as ts
from datetime import datetime

WORKSPACE = '/root/.openclaw/workspace'
DB_PATH = f'{WORKSPACE}/data/historical/historical.db'
LOG_PATH = f'{WORKSPACE}/reports/supplement_batch_v2.log'
VERIFY_PATH = f'{WORKSPACE}/reports/supplement_verify.log'
TS_TOKEN = 'cd2c935050381b52c9849eb054d1b198c21b0f29be2f025f9a9ece30'
BATCH_SIZE = 100  # 减小批次，确保质量

# 初始化Tushare
ts.set_token(TS_TOKEN)
pro = ts.pro_api()

def log(msg):
    """记录日志"""
    line = f"[{datetime.now().strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    with open(LOG_PATH, 'a') as f:
        f.write(line + '\n')

def verify_log(msg):
    """记录验证日志"""
    line = f"[{datetime.now().strftime('%H:%M:%S')}] {msg}"
    with open(VERIFY_PATH, 'a') as f:
        f.write(line + '\n')

def get_active_stocks():
    """获取当前上市的股票列表（排除退市股票）"""
    log("获取当前上市股票列表...")
    try:
        # 从Tushare获取上市状态的股票
        df_basic = pro.stock_basic(exchange='', list_status='L', fields='ts_code,name,list_date')
        active_stocks = df_basic['ts_code'].tolist()
        log(f"✅ 获取到 {len(active_stocks)} 只上市股票")
        return active_stocks
    except Exception as e:
        log(f"❌ 获取上市股票失败: {e}")
        return []

def get_pending_stocks_yearly(year):
    """获取某一年度缺失数据的股票"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # 获取当前上市的股票
    active_stocks = get_active_stocks()
    if not active_stocks:
        conn.close()
        return [], 0
    
    # 构建查询 - 只查询上市股票中缺失该年度数据的
    placeholders = ','.join(['?' for _ in active_stocks])
    
    # 检查该年度数据完整性
    year_start = f"{year}0101"
    year_end = f"{year}1231"
    
    cursor.execute(f"""
        SELECT ts_code FROM stock_basic 
        WHERE ts_code IN ({placeholders})
        AND ts_code NOT IN (
            SELECT DISTINCT ts_code FROM fina_tushare 
            WHERE period >= ? AND period <= ?
        )
        LIMIT ?
    """, active_stocks + [year_start, year_end, BATCH_SIZE])
    
    stocks = [r[0] for r in cursor.fetchall()]
    
    # 获取总数
    cursor.execute(f"""
        SELECT COUNT(*) FROM stock_basic 
        WHERE ts_code IN ({placeholders})
        AND ts_code NOT IN (
            SELECT DISTINCT ts_code FROM fina_tushare 
            WHERE period >= ? AND period <= ?
        )
    """, active_stocks + [year_start, year_end])
    
    remaining = cursor.fetchone()[0]
    conn.close()
    
    return stocks, remaining

def supplement_year(pro, year, stocks):
    """处理某一年度的数据补充"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # 该年度的4个季度
    periods = [
        f"{year}0331", f"{year}0630", 
        f"{year}0930", f"{year}1231"
    ]
    
    total_inserted = 0
    total_queried = 0
    
    for i, ts_code in enumerate(stocks):
        if i % 10 == 0:
            log(f"  进度: {i}/{len(stocks)} | 本年累计入库:{total_inserted}")
        
        for period in periods:
            try:
                # 查询前先检查是否已存在
                cursor.execute(
                    "SELECT 1 FROM fina_tushare WHERE ts_code=? AND period=?",
                    (ts_code, period)
                )
                if cursor.fetchone():
                    continue  # 已存在，跳过
                
                # 查询Tushare
                df = pro.fina_indicator(
                    ts_code=ts_code, 
                    period=period,
                    fields='ts_code,roe,roe_waa,roe_dt,roa,roic,netprofit_yoy,dt_netprofit_yoy,revenue_yoy,grossprofit_margin,netprofit_margin,assets_turn,op_yoy,debt_to_assets,current_ratio'
                )
                
                total_queried += 1
                
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
                    total_inserted += 1
                
                # 频率控制
                time.sleep(0.35)
                
            except Exception as e:
                log(f"    ⚠️ {ts_code} {period} 错误: {str(e)[:50]}")
                time.sleep(1)
        
        # 每10只提交一次
        if i % 10 == 0:
            conn.commit()
    
    conn.commit()
    conn.close()
    
    return total_inserted, total_queried

def verify_batch(year, stocks_before):
    """验证批次数据入库情况"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    year_start = f"{year}0101"
    year_end = f"{year}1231"
    
    # 验证该年度数据增长
    cursor.execute("""
        SELECT COUNT(*), COUNT(DISTINCT ts_code) 
        FROM fina_tushare 
        WHERE period >= ? AND period <= ?
    """, (year_start, year_end))
    
    total_records, total_stocks = cursor.fetchone()
    
    conn.close()
    
    verify_log(f"\n{'='*60}")
    verify_log(f"批次验证 - {year}年")
    verify_log(f"{'='*60}")
    verify_log(f"该年度总记录数: {total_records}")
    verify_log(f"该年度总股票数: {total_stocks}")
    verify_log(f"处理前待处理: {stocks_before}只")
    
    return total_records, total_stocks

def main():
    """主函数 - 按年度处理"""
    log("="*60)
    log("🚀 财务数据补充任务v2.0启动")
    log("="*60)
    log("修复内容：")
    log("  1. 只处理上市状态股票")
    log("  2. 优先处理2018-2022年数据")
    log("  3. 每批次验证入库情况")
    log("="*60)
    
    # 优先处理2018-2022年
    years = [2018, 2019, 2020, 2021, 2022, 2023, 2024, 2025]
    
    for year in years:
        log(f"\n{'='*60}")
        log(f"📅 处理 {year} 年度数据")
        log(f"{'='*60}")
        
        # 获取待处理股票
        stocks, remaining = get_pending_stocks_yearly(year)
        
        if not stocks:
            log(f"✅ {year}年数据已完整，跳过")
            continue
        
        log(f"本批次处理: {len(stocks)}只, 剩余待处理: {remaining}只")
        
        # 处理该年度
        inserted, queried = supplement_year(pro, year, stocks)
        
        log(f"✅ {year}年批次完成!")
        log(f"   查询次数: {queried}")
        log(f"   入库记录: {inserted}")
        
        # 验证
        total_records, total_stocks = verify_batch(year, remaining)
        log(f"   验证: {year}年共{total_records}条记录,{total_stocks}只股票")
        
        # 如果该年度数据量达到预期，进入下一年
        expected_records = len(stocks) * 4  # 每只股票4个季度
        if inserted < expected_records * 0.1:  # 入库率<10%
            log(f"⚠️ {year}年入库率过低，可能存在数据缺失")
        
        log(f"{'='*60}")
    
    log("\n" + "="*60)
    log("✅ 所有年度处理完成!")
    log("="*60)

if __name__ == '__main__':
    main()
