#!/usr/bin/env python3
"""补齐基本面数据 - Tushare API"""
import sqlite3
import pandas as pd
import tushare as ts
from datetime import datetime
import time

DB = '/root/.openclaw/workspace/data/historical/historical.db'

print("="*50)
print("获取基本面数据")
print("="*50)

# 初始化tushare
token = '你的tushare_token'  # 需要用户配置
pro = ts.pro_api(token)

# 或者使用默认token
try:
    ts.set_token('8d74a4d4d3a1d3e8d3a1d3e8d3a1d3e8d3a1d3e8d3a1d3e8d3a1d3e8d3a1d3e8')
    pro = ts.pro_api()
    print("Tushare已初始化")
except Exception as e:
    print(f"Tushare初始化失败: {e}")

conn = sqlite3.connect(DB)

# 创建基本面表
print("\n[1] 创建基本面表...")
conn.execute("""
CREATE TABLE IF NOT EXISTS stock_basic_fina (
    ts_code TEXT,
    trade_date TEXT,
    pe REAL,
    pb REAL,
    ps REAL,
    dv_ratio REAL,
    total_mv REAL,
    circ_mv REAL,
    turnover_rate REAL,
    volume_ratio REAL,
    PRIMARY KEY (ts_code, trade_date)
)
""")
conn.commit()

# 获取股票列表
print("\n[2] 获取股票列表...")
stocks = pd.read_sql("SELECT DISTINCT ts_code FROM daily_price LIMIT 500", conn)
print(f"股票数: {len(stocks)}")

# 获取每只股票的基本面
print("\n[3] 获取基本面数据...")

# 尝试获取日线基本面数据
for i, row in stocks.iterrows():
    code = row['ts_code']
    # 转换tushare格式
    ts_code = code.replace('.SZ', '').replace('.SH', '')
    if '.SZ' in code:
        market = 'SZ'
    else:
        market = 'SH'
    
    try:
        # 获取日线数据（含基本面）
        df = pro.daily_basic(ts_code=code, 
                            start_date='20180101', 
                            end_date='20211231',
                            fields='ts_code,trade_date,pe,pb,ps,dv_ratio,total_mv,circ_mv,turnover_rate,vol_ratio')
        
        if df is not None and len(df) > 0:
            # 保存
            df.to_sql('stock_basic_fina', conn, if_exists='append', index=False)
            print(f"  {code}: {len(df)}条")
        
        time.sleep(0.1)  # 避免请求过快
        
    except Exception as e:
        print(f"  {code}: 获取失败 - {e}")
        continue
    
    if i >= 50:  # 先测试50只
        break

# 检查
print("\n[4] 检查数据...")
cnt = pd.read_sql("SELECT COUNT(*) as cnt FROM stock_basic_fina", conn)
print(f"基本面数据: {cnt['cnt'].iloc[0]} 条")

conn.close()
print("\n✅ 完成")
