#!/root/.openclaw/workspace/venv/bin/python3
"""
获取上证指数分钟级别K线数据 - 多源尝试
"""
import sys
sys.path.insert(0, '/root/.openclaw/workspace/venv/lib/python3.12/site-packages')
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

print("=" * 70)
print("上证指数分钟K线数据获取")
print("=" * 70)

# 方法1: 尝试 qteasy
print("\n【方法1: qteasy】")
try:
    import qteasy as qt
    # qteasy 获取分钟数据
    df_5m = qt.get_history_data('000001.SH', htypes='close', freq='5min', start='20260414', end='20260414')
    print(f"✅ qteasy 5分钟数据: {len(df_5m) if df_5m is not None else 0} 条")
except Exception as e:
    print(f"❌ qteasy 失败: {e}")

# 方法2: 尝试 akshare 指数分钟数据
print("\n【方法2: akshare 指数分钟】")
try:
    import akshare as ak
    # 尝试获取指数分钟数据
    df_5m = ak.index_zh_a_hist_min_em(symbol="000001", period="5", start_date="20260414", end_date="20260414")
    print(f"✅ akshare 5分钟: {len(df_5m)} 条")
    print(df_5m.tail())
    df_5m.to_csv('/tmp/sh_5m_ak.csv', index=False)
except Exception as e:
    print(f"❌ akshare 指数分钟失败: {e}")

# 方法3: 尝试 akshare 期货/期权数据源
print("\n【方法3: akshare 其他接口】")
try:
    import akshare as ak
    # 尝试获取指数分时数据
    df = ak.index_zh_a_hist(symbol="000001", period="daily", start_date="20260401", end_date="20260414")
    print(f"日线: {len(df)} 条")
except Exception as e:
    print(f"❌ akshare 日线失败: {e}")

# 方法4: 尝试 efinance 指数
print("\n【方法4: efinance 指数】")
try:
    import efinance as ef
    df_5m = ef.stock.get_quote_history('000001', klt=5)
    print(f"✅ efinance 5分钟: {len(df_5m)} 条")
    df_5m.to_csv('/tmp/sh_5m_ef.csv', index=False)
except Exception as e:
    print(f"❌ efinance 失败: {e}")

# 方法5: 尝试 AKShare 财经数据接口
print("\n【方法5: AKShare 东方财富】")
try:
    import akshare as ak
    # 尝试获取上证指数历史数据（东方财富）
    df = ak.index_zh_a_hist(symbol="000001", period="daily", start_date="20260401", end_date="20260414")
    print(f"✅ 东方财富日线: {len(df)} 条")
except Exception as e:
    print(f"❌ 东方财富失败: {e}")

# 方法6: 尝试直接请求东方财富API
print("\n【方法6: 直接请求东方财富API】")
try:
    import requests
    # 东方财富分钟数据API
    url = "https://push2his.eastmoney.com/api/qt/stock/kline/get"
    params = {
        "secid": "1.000001",  # 上证指数
        "fields1": "f1,f2,f3,f4,f5,f6,f7,f8,f9,f10,f11,f12,f13",
        "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61",
        "klt": "5",  # 5分钟
        "fqt": "0",
        "beg": "20260414",
        "end": "20260414",
        "ut": "fa5fd1943c7b386f172d6893dbfba10b"
    }
    resp = requests.get(url, params=params, timeout=10)
    print(f"状态码: {resp.status_code}")
    data = resp.json()
    if data.get('data') and data['data'].get('klines'):
        klines = data['data']['klines']
        print(f"✅ 获取到 {len(klines)} 条K线")
        # 解析数据
        rows = []
        for k in klines:
            parts = k.split(',')
            rows.append({
                'time': parts[0],
                'open': float(parts[1]),
                'close': float(parts[2]),
                'high': float(parts[3]),
                'low': float(parts[4]),
                'volume': float(parts[5]),
                'amount': float(parts[6]),
                'change': float(parts[7]) if len(parts) > 7 else 0
            })
        df = pd.DataFrame(rows)
        print(df.tail(10).to_string(index=False))
        df.to_csv('/tmp/sh_5m_em.csv', index=False)
    else:
        print(f"响应: {data.keys()}")
except Exception as e:
    print(f"❌ 东方财富API失败: {e}")

print("\n" + "=" * 70)
print("数据获取尝试完成")
print("=" * 70)
