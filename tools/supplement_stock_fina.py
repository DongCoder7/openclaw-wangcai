#!/usr/bin/env python3
"""
补充 stock_fina 财务数据 - 使用新浪API
"""
import sqlite3
import requests
import time
from datetime import datetime

DB_PATH = '/root/.openclaw/workspace/data/historical/historical.db'
LOG_FILE = '/root/.openclaw/workspace/data/supplement_fina.log'

def log(msg):
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f"[{timestamp}] {msg}")
    with open(LOG_FILE, 'a') as f:
        f.write(f"[{timestamp}] {msg}\n")

def get_fina_data_sina(code):
    """使用新浪API获取财务数据"""
    try:
        clean_code = code.replace('.SH', '').replace('.SZ', '')
        
        if code.startswith('6'):
            symbol = f"sh{clean_code}"
        else:
            symbol = f"sz{clean_code}"
        
        # 新浪财务数据API
        url = f"https://money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData?symbol={symbol}&scale=240&ma=5"
        response = requests.get(url, timeout=5)
        data = response.text
        
        # 使用另一个API获取实时行情(包含PE/PB)
        url2 = f"https://hq.sinajs.cn/list={symbol}"
        response2 = requests.get(url2, timeout=5)
        response2.encoding = 'gbk'
        data2 = response2.text
        
        if '=' in data2:
            parts = data2.split('=')[1].split(',')
            if len(parts) >= 45:
                return {
                    'pe_ttm': float(parts[38]) if parts[38] and parts[38] != '0.00' else None,
                    'pb': float(parts[45]) if len(parts) > 45 and parts[45] and parts[45] != '0.00' else None,
                    'roe': None,
                    'revenue_growth': None,
                    'netprofit_growth': None,
                    'debt_ratio': None,
                    'dividend_yield': None
                }
    except Exception as e:
        pass
    return None

def get_fina_data_tencent(code):
    """使用腾讯API获取财务数据"""
    try:
        clean_code = code.replace('.SH', '').replace('.SZ', '')
        
        if code.startswith('6'):
            symbol = f"sh{clean_code}"
        else:
            symbol = f"sz{clean_code}"
        
        url = f"https://qt.gtimg.cn/q={symbol}"
        response = requests.get(url, timeout=5)
        response.encoding = 'gbk'
        data = response.text
        
        if '=' in data:
            parts = data.split('=')[1].split(',')
            # 腾讯API字段说明:
            # 38: pe_ttm, 39: pe, 44: pb
            if len(parts) >= 45:
                pe_ttm = parts[38] if parts[38] and parts[38] != '0.00' and parts[38] != '-' else None
                pb = parts[44] if len(parts) > 44 and parts[44] and parts[44] != '0.00' and parts[44] != '-' else None
                
                return {
                    'pe_ttm': float(pe_ttm) if pe_ttm else None,
                    'pb': float(pb) if pb else None,
                    'roe': None,
                    'revenue_growth': None,
                    'netprofit_growth': None,
                    'debt_ratio': None,
                    'dividend_yield': None
                }
    except Exception as e:
        log(f"  {code} 腾讯API失败: {e}")
    return None

def main():
    log("="*60)
    log("📊 开始补充 stock_fina 财务数据")
    log("="*60)
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # 获取所有股票代码
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
    
    # 最新报告日期
    report_date = datetime.now().strftime('%Y%m%d')
    
    success_count = 0
    fail_count = 0
    
    for i, ts_code in enumerate(to_add, 1):
        # 先尝试腾讯API
        fina_data = get_fina_data_tencent(ts_code)
        
        if fina_data and (fina_data['pe_ttm'] is not None or fina_data['pb'] is not None):
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
    cursor.execute('SELECT COUNT(DISTINCT ts_code) FROM stock_fina')
    distinct = cursor.fetchone()[0]
    
    conn.close()
    
    log(f"\n✅ stock_fina 补充完成")
    log(f"   成功: {success_count}")
    log(f"   失败: {fail_count}")
    log(f"   覆盖股票数: {distinct}")

if __name__ == "__main__":
    main()
