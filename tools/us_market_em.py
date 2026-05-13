#!/root/.openclaw/workspace/venv/bin/python3
"""东方财富美股指数"""
import requests
import json

# 东方财富美股指数接口
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
}

# 尝试获取美股期货/指数
try:
    # 全球指数
    url = "https://push2.eastmoney.com/api/qt/ulist.np/get"
    params = {
        'fltt': 2,
        'invt': 2,
        'fields': 'f2,f3,f4,f12,f14',
        'secids': '100.DJI,100.IXIC,100.INX,100.VIX'
    }
    resp = requests.get(url, params=params, headers=headers, timeout=10)
    print(resp.text[:500])
except Exception as e:
    print(f'Error: {e}')

# 尝试英为财情数据
try:
    url2 = "https://cn.investing.com/indices/us-30"
    resp2 = requests.get(url2, headers=headers, timeout=10)
    print(f"\nInvesting.com status: {resp2.status_code}")
except Exception as e:
    print(f'Investing error: {e}')
