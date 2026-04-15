#!/root/.openclaw/workspace/venv/bin/python3
"""
获取上证指数分钟级别K线数据 - 最后尝试
"""
import sys
sys.path.insert(0, '/root/.openclaw/workspace/venv/lib/python3.12/site-packages')
import pandas as pd
import numpy as np
from datetime import datetime

print("=" * 70)
print("上证指数分钟K线数据获取 - 最后尝试")
print("=" * 70)

# 方法1: 使用 akshare stock_zh_a_spot_em 获取实时行情
print("\n【方法1: akshare 实时行情】")
try:
    import akshare as ak
    
    # 获取指数实时行情
    df_spot = ak.index_zh_a_spot_em()
    sh_index = df_spot[df_spot['代码'] == '000001']
    print(f"上证指数实时行情:")
    print(sh_index.to_string(index=False))
    
except Exception as e:
    print(f"❌ 失败: {e}")

# 方法2: 使用 akshare 指数分时数据
print("\n【方法2: akshare 指数分时】")
try:
    import akshare as ak
    
    # 获取上证指数分时数据
    df_min = ak.index_zh_a_hist_min_em(symbol="000001", period="1", start_date="20260414", end_date="20260414")
    print(f"✅ 获取到 {len(df_min)} 条1分钟数据")
    print(df_min.head(10).to_string(index=False))
    df_min.to_csv('/tmp/sh_1m_em2.csv', index=False)
except Exception as e:
    print(f"❌ 失败: {e}")

# 方法3: 使用 akshare 指数5分钟数据
print("\n【方法3: akshare 指数5分钟】")
try:
    import akshare as ak
    
    df_5m = ak.index_zh_a_hist_min_em(symbol="000001", period="5", start_date="20260414", end_date="20260414")
    print(f"✅ 获取到 {len(df_5m)} 条5分钟数据")
    print(df_5m.to_string(index=False))
    df_5m.to_csv('/tmp/sh_5m_em2.csv', index=False)
except Exception as e:
    print(f"❌ 失败: {e}")

# 方法4: 使用 akshare 股票分钟数据 (尝试)
print("\n【方法4: akshare 股票分钟】")
try:
    import akshare as ak
    
    # 尝试用股票接口获取指数数据
    df_5m_stock = ak.stock_zh_a_hist_min_em(symbol="000001", period="5", start_date="20260414", end_date="20260414", adjust="qfq")
    print(f"✅ 股票接口获取到 {len(df_5m_stock)} 条数据")
    print(df_5m_stock.to_string(index=False))
except Exception as e:
    print(f"❌ 失败: {e}")

# 方法5: 使用同花顺个股分钟数据
print("\n【方法5: 同花顺个股分钟】")
try:
    import akshare as ak
    
    # 同花顺个股分时数据
    df_ths = ak.stock_zh_a_hist_tx(symbol="sh000001", period="daily", start_date="20260401", end_date="20260414")
    print(f"✅ 同花顺获取到 {len(df_ths)} 条数据")
    print(df_ths.tail().to_string(index=False))
except Exception as e:
    print(f"❌ 失败: {e}")

print("\n" + "=" * 70)
print("尝试完成")
print("=" * 70)
