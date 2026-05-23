#!/root/.openclaw/workspace/venv/bin/python3
"""获取今日A股基本行情数据"""
import sys
sys.path.insert(0, '/root/.openclaw/workspace/tools')

import requests
import pandas as pd
from datetime import datetime
import json

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")
    sys.stdout.flush()

# ========== 1. 官方指数 ==========
log("获取官方指数...")
url = 'https://qt.gtimg.cn/q=sh000001,sz399001,sz399006,sh000688'
r = requests.get(url, timeout=10)
indices = {}
for line in r.text.strip().split(';'):
    if not line.strip(): continue
    parts = line.split('=')
    if len(parts) < 2: continue
    code = parts[0].split('_')[-1]
    values = parts[1].strip('"').split('~')
    if len(values) > 32:
        name = values[1]
        price = float(values[3])
        change = float(values[31]) if len(values) > 31 else 0
        change_pct = float(values[32])
        indices[code] = {'name': name, 'price': price, 'change': change, 'change_pct': change_pct}

for k, v in indices.items():
    log(f"  {v['name']}: {v['price']:.2f} ({v['change']:>+.2f}, {v['change_pct']:>+.2f}%)")

# ========== 2. 美股 ==========
log("获取美股行情...")
url = 'https://qt.gtimg.cn/q=usDJI,usIXIC,usINX'
r = requests.get(url, timeout=10)
us = {}
for line in r.text.strip().split(';'):
    if not line.strip(): continue
    parts = line.split('=')
    if len(parts) < 2: continue
    code = parts[0].split('_')[-1]
    values = parts[1].strip('"').split('~')
    if len(values) > 30:
        name_map = {'usDJI': '道琼斯', 'usIXIC': '纳斯达克', 'usINX': '标普500'}
        name = name_map.get(code, code)
        price = float(values[3])
        pre = float(values[4])
        change_pct = (price - pre) / pre * 100 if pre > 0 else 0
        change = price - pre
        us[code] = {'name': name, 'price': price, 'change': change, 'change_pct': change_pct}

for k, v in us.items():
    log(f"  {v['name']}: {v['price']:.2f} ({v['change']:>+.2f}, {v['change_pct']:>+.2f}%)")

# ========== 3. 港股 ==========
log("获取港股行情...")
url = 'https://qt.gtimg.cn/q=hkHSI,hkHSTECH'
r = requests.get(url, timeout=10)
hk = {}
for line in r.text.strip().split(';'):
    if not line.strip(): continue
    parts = line.split('=')
    if len(parts) < 2: continue
    values = parts[1].strip('"').split('~')
    if len(values) > 30:
        name = values[1]
        price = float(values[3])
        pre = float(values[4])
        change_pct = (price - pre) / pre * 100 if pre > 0 else 0
        change = price - pre
        hk[name] = {'price': price, 'change': change, 'change_pct': change_pct}

for k, v in hk.items():
    log(f"  {k}: {v['price']:.2f} ({v['change']:>+.2f}, {v['change_pct']:>+.2f}%)")

# ========== 4. 尝试用Tushare获取A股全市场 ==========
log("尝试Tushare获取A股行情...")
try:
    import tushare as ts
    ts.set_token('cd2c935050381b52c9849eb054d1b198c21b0f29be2f025f9a9ece30')
    pro = ts.pro_api()
    
    today = datetime.now().strftime('%Y%m%d')
    # 获取今日行情
    df = pro.daily(trade_date=today)
    if df is not None and not df.empty:
        log(f"  获取到 {len(df)} 只股票")
        total = len(df)
        up = len(df[df['pct_chg'] > 0])
        down = len(df[df['pct_chg'] < 0])
        avg_change = df['pct_chg'].mean()
        limit_up = len(df[df['pct_chg'] >= 9.5])
        limit_down = len(df[df['pct_chg'] <= -9.5])
        total_amount = df['amount'].sum() / 100000000  # 亿
        log(f"  涨跌: {up}涨 / {down}跌, 平均: {avg_change:+.2f}%")
        log(f"  涨停: {limit_up}, 跌停: {limit_down}")
        log(f"  成交额: {total_amount:.0f}亿")
        
        # 板块分类
        def classify(ts_code):
            code = ts_code.split('.')[0]
            if code.startswith('688'):
                return '科创板'
            elif code.startswith('3'):
                return '创业板'
            elif code.startswith('8') or code.startswith('4'):
                return '北交所'
            else:
                return '主板'
        
        df['sector'] = df['ts_code'].apply(classify)
        sector_perf = df.groupby('sector')['pct_chg'].mean().sort_values(ascending=False)
        log(f"  板块: {dict(sector_perf)}")
        
        # 涨跌幅榜
        top_up = df.nlargest(10, 'pct_chg')[['ts_code', 'name', 'pct_chg', 'sector']]
        top_down = df.nsmallest(10, 'pct_chg')[['ts_code', 'name', 'pct_chg', 'sector']]
        
        # 保存数据
        data = {
            'indices': indices,
            'us': us,
            'hk': hk,
            'market': {
                'total': total, 'up': up, 'down': down,
                'avg_change': avg_change,
                'limit_up': limit_up, 'limit_down': limit_down,
                'total_amount': total_amount,
                'sector_perf': dict(sector_perf)
            },
            'top_up': top_up.to_dict('records'),
            'top_down': top_down.to_dict('records')
        }
    else:
        log("  Tushare无数据，尝试备用方案...")
        data = None
except Exception as e:
    log(f"  Tushare失败: {e}")
    data = None

# 备用方案 - 东方财富API获取涨跌家数
if data is None:
    log("使用东方财富备用API...")
    try:
        # 涨跌家数统计
        url = 'https://push2ex.eastmoney.com/getTopicZDFStat?ut=7eea3edcaed734bea9cbfc24409ed989&dpt=wz.ztzt'
        # 简化处理，只保存已有数据
        data = {
            'indices': indices,
            'us': us,
            'hk': hk,
            'market': None,
            'top_up': None,
            'top_down': None
        }
    except Exception as e:
        log(f"  备用API也失败: {e}")

# 保存结果
result_file = f'/root/.openclaw/workspace/data/market_data_{datetime.now().strftime("%Y%m%d")}.json'
with open(result_file, 'w', encoding='utf-8') as f:
    json.dump(data, f, ensure_ascii=False, indent=2)
log(f"数据已保存: {result_file}")

print("\n=== 数据摘要 ===")
print(json.dumps(data, ensure_ascii=False, indent=2)[:3000])
