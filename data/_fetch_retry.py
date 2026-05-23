#!/root/.openclaw/workspace/venv/bin/python3
"""尝试多种方式获取A股数据"""
import requests
import pandas as pd
from datetime import datetime

# 腾讯API - 尝试获取涨跌家数
url = 'https://qt.gtimg.cn/q=zrzt'  # 涨跌家数
r = requests.get(url, timeout=10)
print("腾讯涨跌家数:", r.text[:500])

# 尝试获取全市场数据 - 腾讯
try:
    # 获取主要股票
    url = 'https://qt.gtimg.cn/q=sh000001,sz399001,sz399006,sh000688'
    r = requests.get(url, timeout=10)
    print("\n指数:", r.text[:500])
except Exception as e:
    print(f"错误: {e}")

# 东方财富 - 另一种API
print("\n尝试东方财富API...")
try:
    url = 'https://push2.eastmoney.com/api/qt/stock/get?secid=1.000001&fields=f43,f44,f45,f46,f47,f48,f49,f50,f51,f52,f57,f58,f60,f61,f62,f63,f64,f65,f66,f67,f68,f69,f70,f71,f72,f73,f74,f75,f76,f77,f78,f79,f80,f81,f82,f83,f84,f85,f86,f87,f88,f89,f90,f91,f92,f93,f94,f95,f96,f97,f98,f99,f100,f101,f102,f103,f104,f105,f106,f107,f108,f109,f110,f111,f112,f113,f114,f115,f116,f117,f118,f119,f120,f121,f122,f123,f124,f125,f126,f127,f128,f129,f130'
    r = requests.get(url, timeout=10)
    print("东财返回:", r.text[:500])
except Exception as e:
    print(f"错误: {e}")
