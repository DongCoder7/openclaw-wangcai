#!/usr/bin/env python3
"""
补充 stock_basic 和 stock_fina 表数据
"""
import sqlite3
import requests
import pandas as pd
import time
from datetime import datetime

DB_PATH = '/root/.openclaw/workspace/data/historical/historical.db'
LOG_FILE = '/root/.openclaw/workspace/data/supplement_data.log'

def log(msg):
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f"[{timestamp}] {msg}")
    with open(LOG_FILE, 'a') as f:
        f.write(f"[{timestamp}] {msg}\n")

def get_stock_name_tushare(code):
    """使用akshare获取股票名称"""
    try:
        clean_code = code.replace('.SH', '').replace('.SZ', '').replace('.BJ', '')
        # 使用腾讯API获取名称
        if code.startswith('6'):
            symbol = f"sh{clean_code}"
        elif code.startswith('4') or code.startswith('8'):
            symbol = f"bj{clean_code}"
        else:
            symbol = f"sz{clean_code}"
        
        url = f"https://qt.gtimg.cn/q={symbol}"
        response = requests.get(url, timeout=5)
        response.encoding = 'gbk'
        data = response.text
        
        # 解析返回数据
        if '~' in data:
            parts = data.split('~')
            if len(parts) >= 2:
                return parts[1]  # 股票名称
    except Exception as e:
        pass
    return None

def get_fina_data_tushare(code):
    """获取财务数据"""
    try:
        clean_code = code.replace('.SH', '').replace('.SZ', '').replace('.BJ', '')
        if code.startswith('6'):
            symbol = f"sh{clean_code}"
        elif code.startswith('4') or code.startswith('8'):
            symbol = f"bj{clean_code}"
        else:
            symbol = f"sz{clean_code}"
        
        url = f"https://qt.gtimg.cn/q={symbol}"
        response = requests.get(url, timeout=5)
        response.encoding = 'gbk'
        data = response.text
        
        if '~' in data:
            parts = data.split('~')
            if len(parts) >= 45:
                return {
                    'pe_ttm': float(parts[39]) if parts[39] else None,  # 市盈率TTM
                    'pb': float(parts[46]) if len(parts) > 46 and parts[46] else None,  # 市净率
                    'roe': None,  # ROE需要另外获取
                    'revenue_growth': None,
                    'netprofit_growth': None,
                    'debt_ratio': None,
                    'dividend_yield': None
                }
    except Exception as e:
        pass
    return None

def supplement_stock_basic():
    """补充 stock_basic 表"""
    log("="*60)
    log("📊 开始补充 stock_basic 表")
    log("="*60)
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # 获取所有已存在的ts_code
    cursor.execute('SELECT ts_code FROM stock_basic')
    existing = set(row[0] for row in cursor.fetchall())
    log(f"现有 stock_basic: {len(existing)} 条")
    
    # 从 daily_price 获取所有股票
    cursor.execute('SELECT DISTINCT ts_code FROM daily_price')
    daily_stocks = set(row[0] for row in cursor.fetchall())
    
    # 从 stock_factors 获取所有股票
    cursor.execute('SELECT DISTINCT ts_code FROM stock_factors')
    factor_stocks = set(row[0] for row in cursor.fetchall())
    
    # 合并所有需要的股票代码
    all_needed = daily_stocks.union(factor_stocks)
    log(f"需要补充的股票: {len(all_needed)} 只")
    
    # 找出需要补充的
    to_add = all_needed - existing
    log(f"需要新增: {len(to_add)} 只")
    
    success_count = 0
    fail_count = 0
    
    for i, ts_code in enumerate(sorted(to_add), 1):
        clean_code = ts_code.replace('.SH', '').replace('.SZ', '').replace('.BJ', '')
        name = get_stock_name_tushare(ts_code)
        
        if name:
            try:
                cursor.execute(
                    'INSERT INTO stock_basic (\"股票代码\", \"股票名称\", ts_code) VALUES (?, ?, ?)',
                    (clean_code, name, ts_code)
                )
                success_count += 1
            except Exception as e:
                log(f"  插入失败 {ts_code}: {e}")
                fail_count += 1
        else:
            # 如果获取不到名称，使用代码作为名称
            try:
                cursor.execute(
                    'INSERT INTO stock_basic (\"股票代码\", \"股票名称\", ts_code) VALUES (?, ?, ?)',
                    (clean_code, clean_code, ts_code)
                )
                success_count += 1
            except Exception as e:
                fail_count += 1
        
        if i % 100 == 0:
            log(f"  进度: {i}/{len(to_add)} | 成功: {success_count} | 失败: {fail_count}")
            conn.commit()
            time.sleep(0.5)
        
        # 限速
        if i % 50 == 0:
            time.sleep(0.3)
    
    conn.commit()
    conn.close()
    
    log(f"\n✅ stock_basic 补充完成")
    log(f"   成功: {success_count}")
    log(f"   失败: {fail_count}")
    return success_count

def supplement_stock_fina():
    """补充 stock_fina 表"""
    log("="*60)
    log("📊 开始补充 stock_fina 表")
    log("="*60)
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # 获取所有需要填充的股票（从stock_basic）
    cursor.execute('SELECT ts_code FROM stock_basic')
    all_stocks = [row[0] for row in cursor.fetchall()]
    log(f"需要处理的股票: {len(all_stocks)} 只")
    
    # 获取已有财务数据的股票
    cursor.execute('SELECT DISTINCT ts_code FROM stock_fina')
    existing = set(row[0] for row in cursor.fetchall())
    log(f"已有财务数据: {len(existing)} 只")
    
    # 需要补充的
    to_add = [code for code in all_stocks if code not in existing]
    log(f"需要新增: {len(to_add)} 只")
    
    # 获取最新报告日期
    report_date = datetime.now().strftime('%Y%m%d')
    
    success_count = 0
    fail_count = 0
    
    for i, ts_code in enumerate(to_add, 1):
        fina_data = get_fina_data_tushare(ts_code)
        
        if fina_data:
            try:
                cursor.execute('''
                    INSERT INTO stock_fina 
                    (ts_code, report_date, pe_ttm, pb, roe, revenue_growth, netprofit_growth, debt_ratio, dividend_yield)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    ts_code, report_date,
                    fina_data.get('pe_ttm'),
                    fina_data.get('pb'),
                    fina_data.get('roe'),
                    fina_data.get('revenue_growth'),
                    fina_data.get('netprofit_growth'),
                    fina_data.get('debt_ratio'),
                    fina_data.get('dividend_yield')
                ))
                success_count += 1
            except Exception as e:
                log(f"  插入失败 {ts_code}: {e}")
                fail_count += 1
        else:
            fail_count += 1
        
        if i % 100 == 0:
            log(f"  进度: {i}/{len(to_add)} | 成功: {success_count} | 失败: {fail_count}")
            conn.commit()
            time.sleep(0.5)
        
        # 限速
        if i % 50 == 0:
            time.sleep(0.3)
    
    conn.commit()
    
    # 统计结果
    cursor.execute('SELECT COUNT(*) FROM stock_fina')
    total = cursor.fetchone()[0]
    cursor.execute('SELECT COUNT(DISTINCT ts_code) FROM stock_fina')
    distinct = cursor.fetchone()[0]
    
    conn.close()
    
    log(f"\n✅ stock_fina 补充完成")
    log(f"   成功: {success_count}")
    log(f"   失败: {fail_count}")
    log(f"   表内总记录: {total}")
    log(f"   覆盖股票数: {distinct}")
    return success_count

def main():
    log("="*60)
    log("🚀 开始数据补充任务")
    log("="*60)
    
    # 任务1: 补充 stock_basic
    basic_count = supplement_stock_basic()
    time.sleep(2)
    
    # 任务2: 补充 stock_fina
    fina_count = supplement_stock_fina()
    
    # 最终结果
    log("\n" + "="*60)
    log("🎉 所有任务完成")
    log("="*60)
    
    # 验证结果
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('SELECT COUNT(*) FROM stock_basic')
    basic_total = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(DISTINCT ts_code) FROM stock_fina')
    fina_distinct = cursor.fetchone()[0]
    
    conn.close()
    
    log(f"\n📊 最终结果:")
    log(f"   stock_basic: {basic_total} 只股票")
    log(f"   stock_fina: {fina_distinct} 只股票")
    
    if basic_total >= 3000:
        log(f"   ✅ stock_basic 已达到3000+要求")
    else:
        log(f"   ⚠️ stock_basic 仍不足3000")

if __name__ == "__main__":
    main()
