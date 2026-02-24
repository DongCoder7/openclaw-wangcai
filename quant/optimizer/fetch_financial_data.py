#!/usr/bin/env python3
"""补齐财务数据 - 使用AKShare获取基本面数据"""
import sqlite3, pandas as pd
import akshare as ak
from datetime import datetime
import time

DB = '/root/.openclaw/workspace/data/historical/historical.db'
OUT = '/root/.openclaw/workspace/quant/optimizer'

print("="*50)
print("补齐财务数据")
print("="*50)

# 连接数据库
conn = sqlite3.connect(DB)

# 检查现有数据
print("\n[1] 检查现有数据...")
df_price = pd.read_sql("SELECT * FROM daily_price LIMIT 5", conn)
print(f"价格数据: {df_price.shape}")

# 检查是否有财务表
try:
    df_fin = pd.read_sql("SELECT * FROM stock_fina LIMIT 5", conn)
    print(f"财务数据: {df_fin.shape}")
except:
    print("财务数据表: 不存在")

# 创建财务数据表
print("\n[2] 创建财务数据表...")
conn.execute("""
CREATE TABLE IF NOT EXISTS stock_fina (
    ts_code TEXT,
    report_date TEXT,
    pe_ttm REAL,
    pb REAL,
    roe REAL,
    revenue_growth REAL,
    netprofit_growth REAL,
    debt_ratio REAL,
    dividend_yield REAL,
    PRIMARY KEY (ts_code, report_date)
)
""")
conn.commit()

# 获取A股股票列表
print("\n[3] 获取股票列表...")
try:
    stock_df = pd.read_sql("SELECT DISTINCT ts_code FROM daily_price LIMIT 100", conn)
    print(f"已有股票: {len(stock_df)}")
except Exception as e:
    print(f"获取股票列表失败: {e}")
    stock_df = pd.DataFrame()

# 尝试从AKShare获取财务数据
print("\n[4] 从AKShare获取财务数据...")

try:
    # 获取所有A股的财务数据
    print("获取财务指标...")
    fin_df = ak.stock_financial_abstract_ths(symbol="A股")
    print(f"获取到财务数据: {len(fin_df)}")
    print(fin_df.head())
except Exception as e:
    print(f"获取失败: {e}")
    # 尝试其他方式
    try:
        print("尝试备用方式...")
        fin_df = ak.stock_financial_analysis_indicator(symbol="上证指数")
        print(f"备用获取: {len(fin_df)}")
    except Exception as e2:
        print(f"备用也失败: {e2}")
        fin_df = pd.DataFrame()

# 保存到数据库
if not fin_df.empty:
    print("\n[5] 保存到数据库...")
    fin_df.to_sql('stock_fina', conn, if_exists='append', index=False)
    print(f"已保存 {len(fin_df)} 条记录")
else:
    print("\n无法获取财务数据，尝试模拟...")

# 检查数据
print("\n[6] 检查数据...")
try:
    count = pd.read_sql("SELECT COUNT(*) as cnt FROM stock_fina", conn)
    print(f"财务数据记录数: {count['cnt'].iloc[0]}")
except:
    print("财务表为空")

conn.close()
print("\n✅ 数据检查完成")
