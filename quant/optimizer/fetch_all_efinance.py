#!/usr/bin/env python3
"""efinance批量获取所有股票数据"""
import sqlite3
import efinance as ef
import pandas as pd
from datetime import datetime
import time

DB = '/root/.openclaw/workspace/data/historical/historical.db'

print("="*50)
print("efinance批量获取所有股票")
print("="*50)

conn = sqlite3.connect(DB)

# 检查已有
existing = pd.read_sql("SELECT DISTINCT ts_code FROM stock_efinance", conn)
existing_codes = set(existing['ts_code'].str.replace('.SZ', '').str.replace('.SH', '').tolist())
print(f"已有: {len(existing_codes)} 只")

# 获取全部A股
print("\n获取股票列表...")
all_stocks = pd.read_sql("SELECT DISTINCT ts_code FROM daily_price", conn)
print(f"总数: {len(all_stocks)} 只")

# 创建表
conn.execute("""
CREATE TABLE IF NOT EXISTS stock_efinance (
    ts_code TEXT,
    trade_date TEXT,
    open REAL,
    high REAL,
    low REAL,
    close REAL,
    volume REAL,
    amount REAL,
    change_pct REAL,
    turnover_rate REAL,
    PRIMARY KEY (ts_code, trade_date)
)
""")
conn.commit()

# 逐批获取
success = 0
failed = 0
batch_size = 50

for i, row in all_stocks.iterrows():
    code = row['ts_code']
    ts_code = code.replace('.SZ', '').replace('.SH', '')
    
    if ts_code in existing_codes:
        continue
    
    try:
        df = ef.stock.get_quote_history(ts_code)
        if df is not None and len(df) > 0:
            df = df[(df['日期'] >= '2018-01-01') & (df['日期'] <= '2021-12-31')]
            if len(df) > 0:
                df['ts_code'] = code
                df['trade_date'] = df['日期'].str.replace('-', '')
                df = df.rename(columns={
                    '开盘': 'open', '收盘': 'close', '最高': 'high', '最低': 'low',
                    '成交量': 'volume', '成交额': 'amount', '涨跌幅': 'change_pct', '换手率': 'turnover_rate'
                })
                cols = ['ts_code', 'trade_date', 'open', 'high', 'low', 'close', 'volume', 'amount', 'change_pct', 'turnover_rate']
                df[cols].to_sql('stock_efinance', conn, if_exists='append', index=False)
                success += 1
                print(f"  {code}: {len(df)}条", end='\r')
        
        time.sleep(0.3)
        
    except Exception as e:
        failed += 1
        continue
    
    # 每50只报告一次
    if (i + 1) % 50 == 0:
        cnt = pd.read_sql("SELECT COUNT(*) as c FROM stock_efinance", conn)
        print(f"\n进度: {i+1}/{len(all_stocks)} | 成功: {success} | 失败: {failed} | 总记录: {cnt['c'].iloc[0]}")

# 最终统计
cnt = pd.read_sql("SELECT COUNT(*) as c, COUNT(DISTINCT ts_code) as s FROM stock_efinance", conn)
print(f"\n\n✅ 完成!")
print(f"  新增: {success} 只")
print(f"  失败: {failed} 只")
print(f"  总记录: {cnt['c'].iloc[0]} 条")
print(f"  总股票: {cnt['s'].iloc[0]} 只")

conn.close()
