#!/usr/bin/env python3
"""
WFO真实数据库回测引擎 - 简化测试版
"""
import os
import sys
import sqlite3
import pandas as pd
import numpy as np
from datetime import datetime

DB_PATH = '/root/.openclaw/workspace/data/historical/historical.db'

def test_data_availability():
    """测试数据可用性"""
    conn = sqlite3.connect(DB_PATH)
    
    print("📊 测试数据可用性")
    print("="*60)
    
    # 1. 日期范围
    query = "SELECT MIN(trade_date), MAX(trade_date) FROM daily_price"
    df = pd.read_sql(query, conn)
    print(f"\n1. 价格数据范围: {df.iloc[0,0]} ~ {df.iloc[0,1]}")
    
    # 2. 股票数量
    query = "SELECT COUNT(DISTINCT ts_code) FROM daily_price WHERE trade_date >= '20250101'"
    count = pd.read_sql(query, conn).iloc[0,0]
    print(f"2. 2025年股票数量: {count}")
    
    # 3. 因子数据
    query = "SELECT COUNT(*) FROM stock_factors WHERE trade_date = '20250225'"
    count = pd.read_sql(query, conn).iloc[0,0]
    print(f"3. 2025-02-25因子数据: {count}条")
    
    # 4. 防御因子
    query = "SELECT COUNT(*) FROM stock_defensive_factors WHERE trade_date = '20250225'"
    count = pd.read_sql(query, conn).iloc[0,0]
    print(f"4. 2025-02-25防御因子: {count}条")
    
    # 5. 财务数据
    query = "SELECT COUNT(*) FROM stock_fina WHERE report_date >= '20240930'"
    count = pd.read_sql(query, conn).iloc[0,0]
    print(f"5. 2024Q3后财务数据: {count}条")
    
    # 6. 测试选股
    print("\n📋 测试选股逻辑")
    query = '''
        SELECT DISTINCT dp.ts_code, dp.close, dp.change_pct,
               sf.ret_20, sf.vol_20, sdf.sharpe_like
        FROM daily_price dp
        LEFT JOIN stock_factors sf ON dp.ts_code = sf.ts_code AND dp.trade_date = sf.trade_date
        LEFT JOIN stock_defensive_factors sdf ON dp.ts_code = sdf.ts_code AND dp.trade_date = sdf.trade_date
        WHERE dp.trade_date = '20250225'
        AND dp.close >= 10
        AND dp.volume > 0
        AND sf.ret_20 IS NOT NULL
        LIMIT 20
    '''
    df = pd.read_sql(query, conn)
    print(f"   获取到 {len(df)} 只股票")
    
    # 计算简单评分
    df['score'] = df['ret_20'].fillna(0) * 100 - df['vol_20'].fillna(0) * 50 + df['sharpe_like'].fillna(0) * 10
    df = df.sort_values('score', ascending=False)
    
    print("\n   Top 5 股票:")
    for _, row in df.head(5).iterrows():
        print(f"   {row['ts_code']}: 评分={row['score']:.2f}, "
              f"ret_20={row['ret_20']:.3f}, 价格={row['close']:.2f}")
    
    conn.close()
    print("\n✅ 数据测试完成")

if __name__ == '__main__':
    test_data_availability()
