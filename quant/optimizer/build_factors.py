#!/usr/bin/env python3
"""补齐因子数据 - 用价格数据模拟基本面因子"""
import sqlite3, pandas as pd
import numpy as np
from datetime import datetime

DB = '/root/.openclaw/workspace/data/historical/historical.db'

print("="*50)
print("补齐因子数据")
print("="*50)

conn = sqlite3.connect(DB)

# 加载价格数据
print("\n[1] 加载价格数据...")
df = pd.read_sql("""
    SELECT ts_code, trade_date, close, volume, amount 
    FROM daily_price 
    WHERE trade_date BETWEEN '20180101' AND '20211231'
""", conn)
print(f"原始数据: {len(df)} 条")

# 计算各种因子
print("\n[2] 计算因子...")

# 基础动量因子
df = df.sort_values(['ts_code', 'trade_date'])
df['ret_d'] = df.groupby('ts_code')['close'].pct_change(1)
df['ret_w'] = df.groupby('ts_code')['close'].pct_change(5)
df['ret_20'] = df.groupby('ts_code')['close'].pct_change(20)
df['ret_60'] = df.groupby('ts_code')['close'].pct_change(60)
df['ret_120'] = df.groupby('ts_code')['close'].pct_change(120)
df['ret_250'] = df.groupby('ts_code')['close'].pct_change(250)  # 年化

# 波动率因子 (模拟ROE/质量)
df['vol_20'] = df.groupby('ts_code')['ret_d'].rolling(20).std().reset_index(level=0, drop=True)
df['vol_60'] = df.groupby('ts_code')['ret_d'].rolling(60).std().reset_index(level=0, drop=True)
df['vol_120'] = df.groupby('ts_code')['ret_d'].rolling(120).std().reset_index(level=0, drop=True)
df['vol_ratio'] = df['vol_20'] / df['vol_60']  # 波动率趋势

# 趋势因子 (模拟基本面趋势)
df['ma_5'] = df.groupby('ts_code')['close'].rolling(5).mean().reset_index(level=0, drop=True)
df['ma_20'] = df.groupby('ts_code')['close'].rolling(20).mean().reset_index(level=0, drop=True)
df['ma_60'] = df.groupby('ts_code')['close'].rolling(60).mean().reset_index(level=0, drop=True)
df['ma_120'] = df.groupby('ts_code')['close'].rolling(120).mean().reset_index(level=0, drop=True)

# 价格位置 (模拟估值)
df['price_pos_20'] = df['close'] / df['ma_20']  # >1高于20日均线
df['price_pos_60'] = df['close'] / df['ma_60']  # >1高于60日均线
df['price_pos_120'] = df['close'] / df['ma_120'] # >1高于120日均线
df['high_20'] = df.groupby('ts_code')['close'].rolling(20).max().reset_index(level=0, drop=True)
df['low_20'] = df.groupby('ts_code')['close'].rolling(20).min().reset_index(level=0, drop=True)
df['price_pos_high'] = (df['close'] - df['low_20']) / (df['high_20'] - df['low_20'] + 0.001)  # 0-1位置

# 成交量因子 (模拟资金流向)
df['vol_ma_20'] = df.groupby('ts_code')['volume'].rolling(20).mean().reset_index(level=0, drop=True)
df['vol_ratio_amt'] = df['volume'] / df['vol_ma_20']  # 量能放大/萎缩
df['amount_ma_20'] = df.groupby('ts_code')['amount'].rolling(20).mean().reset_index(level=0, drop=True)

# 资金流向 (模拟主力资金)
df['money_flow'] = df['amount'] / df['amount_ma_20']  # 资金流入强度

# 相对强弱 (模拟相对表现)
idx = df.groupby('trade_date')['ret_20'].median().reset_index()
idx.columns = ['trade_date', 'mkt_ret']
df = df.merge(idx, on='trade_date', how='left')
df['rel_strength'] = df['ret_20'] - df['mkt_ret']  # 相对大盘的超额收益

# 动量加速 (模拟业绩加速)
df['mom_accel'] = df['ret_20'] - df['ret_60']  # 短期动量 - 中期动量

# 盈利动量 (用涨幅模拟)
df['profit_mom'] = df['ret_60'].clip(-0.5, 2.0)  # 限制极端值

# 创建因子表
print("\n[3] 创建因子表...")
conn.execute("""
CREATE TABLE IF NOT EXISTS stock_factors (
    ts_code TEXT,
    trade_date TEXT,
    ret_20 REAL,
    ret_60 REAL,
    ret_120 REAL,
    vol_20 REAL,
    vol_ratio REAL,
    ma_20 REAL,
    ma_60 REAL,
    price_pos_20 REAL,
    price_pos_60 REAL,
    price_pos_high REAL,
    vol_ratio_amt REAL,
    money_flow REAL,
    rel_strength REAL,
    mom_accel REAL,
    profit_mom REAL,
    PRIMARY KEY (ts_code, trade_date)
)
""")

# 插入因子数据
print("\n[4] 插入因子数据...")
# 只保留需要的列
factor_cols = ['ts_code', 'trade_date', 'ret_20', 'ret_60', 'ret_120', 
               'vol_20', 'vol_ratio', 'ma_20', 'ma_60', 
               'price_pos_20', 'price_pos_60', 'price_pos_high',
               'vol_ratio_amt', 'money_flow', 'rel_strength', 'mom_accel', 'profit_mom']

df_factors = df[factor_cols].dropna()
df_factors.to_sql('stock_factors', conn, if_exists='replace', index=False)

# 验证
print("\n[5] 验证数据...")
cnt = pd.read_sql("SELECT COUNT(*) as cnt FROM stock_factors", conn)
print(f"因子数据: {cnt['cnt'].iloc[0]} 条")

sample = pd.read_sql("SELECT * FROM stock_factors LIMIT 3", conn)
print("\n示例:")
print(sample)

conn.close()
print("\n✅ 因子数据补齐完成!")
