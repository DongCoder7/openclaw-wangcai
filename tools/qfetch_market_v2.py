#!/usr/bin/env python3
import requests
import json
from datetime import datetime

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Referer': 'https://finance.qq.com'
}

# 获取A股指数
indices = {
    '沪深300': 'sh000300',
    '上证指数': 'sh000001',
    '深证成指': 'sz399001',
    '创业板': 'sz399006',
    '科创50': 'sh000688',
}

print(f"=== A股指数 ({datetime.now().strftime('%H:%M:%S')}) ===")
for name, code in indices.items():
    try:
        url = f"https://qt.gtimg.cn/q={code}"
        r = requests.get(url, headers=headers, timeout=5)
        if r.status_code == 200:
            text = r.text.strip()
            # 格式: v_sz000001="1~平安银行~5.86~0.03~0.05%~..."
            parts = text.split('~')
            if len(parts) > 5:
                price = parts[3]
                chg = parts[4]
                pct = parts[32] if len(parts) > 32 else parts[31]
                print(f'{name}: {price} ({pct})')
    except Exception as e:
        print(f'{name}: {e}')

# 获取港股主要标的
hk_stocks = {
    '腾讯': 'hk00700',
    '阿里': 'hk09988',
    '美团': 'hk03690',
    '小米': 'hk01810',
    '中海油': 'hk00883',
    '平安': 'hk02318',
    '神华': 'hk01088',
    '中石油': 'hk00857',
    '友邦': 'hk01299',
    '中烟': 'hk01898',
}

print(f"\n=== 港股主要标的 ({datetime.now().strftime('%H:%M:%S')}) ===")
codes_str = ','.join(hk_stocks.values())
try:
    url = f"https://qt.gtimg.cn/q={codes_str}"
    r = requests.get(url, headers=headers, timeout=10)
    if r.status_code == 200:
        lines = r.text.strip().split('\n')
        name_map = {v: k for k, v in hk_stocks.items()}
        for line in lines:
            if '=' in line:
                code = line.split('=')[0].replace('v_', '').replace('"', '')
                parts = line.split('~')
                if len(parts) > 5:
                    name = name_map.get(code, code)
                    price = parts[3]
                    chg = parts[4]
                    pct = parts[32] if len(parts) > 32 else parts[31]
                    print(f'{name}({code}): {price} ({pct})')
except Exception as e:
    print(f'获取失败: {e}')

# 获取A股热点板块
print(f"\n=== A股板块动向 ===")
sectors = ['sz002594', 'sz300750', 'sh601012', 'sh600519', 'sh600036', 'sh688981', 'sz002371', 'sh688012', 'sz300308', 'sz300502']
codes_str = ','.join(sectors)
try:
    url = f"https://qt.gtimg.cn/q={codes_str}"
    r = requests.get(url, headers=headers, timeout=10)
    if r.status_code == 200:
        lines = r.text.strip().split('\n')
        for line in lines:
            if '=' in line:
                parts = line.split('~')
                if len(parts) > 10:
                    name = parts[1]
                    price = parts[3]
                    pct = parts[32] if len(parts) > 32 else parts[31]
                    print(f'{name}: {price} ({pct})')
except Exception as e:
    print(f'获取失败: {e}')