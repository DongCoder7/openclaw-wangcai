#!/root/.openclaw/workspace/venv/bin/python3
"""
世运电路(603920)财务数据获取脚本
使用Tushare Pro API获取实时财务数据
"""

import sys
sys.path.insert(0, '/root/.openclaw/workspace/venv/lib/python3.12/site-packages')

import tushare as ts
import json
from datetime import datetime
import os

# 从环境变量获取token
token = os.environ.get('TUSHARE_TOKEN', '')
ts.set_token(token)
pro = ts.pro_api()

print('='*80)
print('📊 世运电路(603920)基础数据获取')
print('='*80)

# 获取股票基本信息
print('\n1️⃣ 基本信息:')
stock_basic = pro.stock_basic(ts_code='603920.SH', exchange='SSE', list_status='L')
print(f"   股票代码: {stock_basic.iloc[0]['ts_code']}")
print(f"   股票名称: {stock_basic.iloc[0]['name']}")
print(f"   所属行业: {stock_basic.iloc[0]['industry']}")
print(f"   上市日期: {stock_basic.iloc[0]['list_date']}")

# 获取最新行情
print('\n2️⃣ 最新行情数据:')
daily_basic = pro.daily_basic(ts_code='603920.SH', trade_date='20260415')
if len(daily_basic) == 0:
    daily_basic = pro.daily_basic(ts_code='603920.SH', trade_date='20260414')

if len(daily_basic) > 0:
    print(f"   当前股价: {daily_basic.iloc[0]['close']:.2f} 元")
    print(f"   总市值: {daily_basic.iloc[0]['total_mv']/10000:.2f} 亿元")
    print(f"   流通市值: {daily_basic.iloc[0]['circ_mv']/10000:.2f} 亿元")
    print(f"   PE_TTM: {daily_basic.iloc[0]['pe_ttm']:.2f} 倍")
    print(f"   PB: {daily_basic.iloc[0]['pb']:.2f} 倍")
    print(f"   换手率: {daily_basic.iloc[0]['turnover_rate']:.2f}%")

# 获取财报数据
print('\n3️⃣ 最新财务数据(2024年报):')
income = pro.income(ts_code='603920.SH', period='20241231')
if len(income) > 0:
    print(f"   营业总收入: {income.iloc[0]['total_revenue']/1e8:.2f} 亿元")
    print(f"   营业收入: {income.iloc[0]['revenue']/1e8:.2f} 亿元")
    print(f"   净利润: {income.iloc[0]['n_income']/1e8:.2f} 亿元")

# 获取2025年三季报
print('\n4️⃣ 2025年三季报数据:')
income_q3 = pro.income(ts_code='603920.SH', period='20250930')
if len(income_q3) > 0:
    print(f"   营业总收入: {income_q3.iloc[0]['total_revenue']/1e8:.2f} 亿元")
    print(f"   净利润: {income_q3.iloc[0]['n_income']/1e8:.2f} 亿元")

# 获取2025年中报
print('\n5️⃣ 2025年中报数据:')
income_h1 = pro.income(ts_code='603920.SH', period='20250630')
if len(income_h1) > 0:
    print(f"   营业总收入: {income_h1.iloc[0]['total_revenue']/1e8:.2f} 亿元")
    print(f"   净利润: {income_h1.iloc[0]['n_income']/1e8:.2f} 亿元")

# 获取业绩快报
print('\n6️⃣ 业绩快报数据:')
express = pro.express(ts_code='603920.SH')
if len(express) > 0:
    print(f"   最新快报日期: {express.iloc[0]['end_date']}")
    cols = express.columns.tolist()
    if 'or' in cols:
        print(f"   营业收入: {express.iloc[0]['or']/1e8:.2f} 亿元")
    if 'n_income' in cols:
        print(f"   净利润: {express.iloc[0]['n_income']/1e8:.2f} 亿元")
    if 'yoy_d_np' in cols and express.iloc[0]['yoy_d_np']:
        print(f"   同比增速: {express.iloc[0]['yoy_d_np']:.2f}%")

# 获取券商研报
print('\n7️⃣ 最新券商研报:')
reports = pro.report_rc(ts_code='603920.SH')
if len(reports) > 0:
    recent_reports = reports.head(5)
    for idx, row in recent_reports.iterrows():
        cols = row.index.tolist()
        org = row['org_name'] if 'org_name' in cols else '未知机构'
        date = row['report_date'][:10] if 'report_date' in cols and row['report_date'] else '未知日期'
        title = row['title'][:50] if 'title' in cols and row['title'] else '无标题'
        print(f"   [{org}] {date} - {title}...")

# 获取总股本
print('\n8️⃣ 股本信息:')
daily = pro.daily(ts_code='603920.SH', trade_date='20260415')
if len(daily) == 0:
    daily = pro.daily(ts_code='603920.SH', trade_date='20260414')
if len(daily) > 0:
    total_shares = daily.iloc[0]['total_share']  # 单位：万股
    float_shares = daily.iloc[0]['float_share']  # 单位：万股
    print(f"   总股本: {total_shares:.2f} 万股 = {total_shares/10000:.4f} 亿股")
    print(f"   流通股本: {float_shares:.2f} 万股 = {float_shares/10000:.4f} 亿股")

# 保存所有数据
data = {
    'basic': stock_basic.to_dict('records'),
    'daily_basic': daily_basic.to_dict('records') if len(daily_basic) > 0 else [],
    'income_2024': income.to_dict('records') if len(income) > 0 else [],
    'income_2025q3': income_q3.to_dict('records') if len(income_q3) > 0 else [],
    'income_2025h1': income_h1.to_dict('records') if len(income_h1) > 0 else [],
    'express': express.to_dict('records') if len(express) > 0 else [],
    'reports': reports.to_dict('records') if len(reports) > 0 else [],
    'daily': daily.to_dict('records') if len(daily) > 0 else [],
    'fetch_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
}

output_file = '/root/.openclaw/workspace/data/shiyun_circuit_financial.json'
with open(output_file, 'w', encoding='utf-8') as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

print(f'\n✅ 财务数据已保存到: {output_file}')
print(f"\n📊 数据获取时间: {data['fetch_time']}")
