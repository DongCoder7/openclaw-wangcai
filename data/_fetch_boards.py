#!/root/.openclaw/workspace/venv/bin/python3
"""用腾讯API获取板块和个股数据"""
import requests
import pandas as pd
from datetime import datetime

# 尝试获取板块涨幅排行
print("=== 获取板块数据 ===")
try:
    # 行业板块 - 腾讯
    url = 'https://qt.gtimg.cn/q=zs_hy'  
    r = requests.get(url, timeout=10)
    print("板块:", r.text[:1000])
except Exception as e:
    print(f"板块错误: {e}")

# 尝试获取个股排行
print("\n=== 获取个股排行 ===")
try:
    # 涨幅榜 - 使用东方财富API
    url = 'http://push2.eastmoney.com/api/qt/clist/get?pn=1&pz=20&po=1&np=1&fltt=2&invt=2&fid=f3&fs=m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23,m:0+t:81+s:2048&fields=f12,f14,f2,f3,f4,f5,f6,f7,f8,f9,f10,f18,f20,f21,f23,f24,f25,f22,f11,f62,f128,f136,f115,f152&_=' + str(int(datetime.now().timestamp()*1000))
    r = requests.get(url, timeout=15, headers={'User-Agent': 'Mozilla/5.0'})
    data = r.json()
    if data.get('data') and data['data'].get('diff'):
        stocks = data['data']['diff']
        print(f"获取到 {len(stocks)} 只股票")
        for s in stocks[:5]:
            print(f"  {s.get('f12')} {s.get('f14')}: {s.get('f3')}%, 成交额: {s.get('f6')}")
except Exception as e:
    print(f"个股排行错误: {e}")

# 涨跌家数 - 东方财富
print("\n=== 涨跌家数 ===")
try:
    url = 'http://push2ex.eastmoney.com/getTopicZDFStat?ut=7eea3edcaed734bea9cbfc24409ed989&dpt=wz.ztzt'
    r = requests.get(url, timeout=10)
    print("涨跌家数原始:", r.text[:500])
except Exception as e:
    print(f"涨跌家数错误: {e}")
