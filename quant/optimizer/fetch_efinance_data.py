#!/usr/bin/env python3
"""用efinance补齐历史数据"""
import sqlite3
import efinance as ef
import pandas as pd
from datetime import datetime
import time

DB = '/root/.openclaw/workspace/data/historical/historical.db'

print("="*50)
print("efinance补齐数据")
print("="*50)

conn = sqlite3.connect(DB)

# 创建扩展表
print("\n[1] 创建扩展表...")
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
    pe REAL,
    pb REAL,
    ps REAL,
    PRIMARY KEY (ts_code, trade_date)
)
""")
conn.commit()

# 获取股票列表
print("\n[2] 获取股票列表...")
stocks = pd.read_sql("SELECT DISTINCT ts_code FROM daily_price LIMIT 100", conn)
print(f"股票数: {len(stocks)}")

# 获取每只股票数据
success = 0
for i, row in stocks.iterrows():
    code = row['ts_code']
    ts_code = code.replace('.SZ', '').replace('.SH', '')
    
    try:
        # 获取历史数据
        df = ef.stock.get_quote_history(ts_code)
        if df is not None and len(df) > 0:
            # 过滤日期范围
            df = df[(df['日期'] >= '2018-01-01') & (df['日期'] <= '2021-12-31')]
            
            if len(df) > 0:
                # 转换格式
                df['ts_code'] = code
                df['trade_date'] = df['日期'].str.replace('-', '')
                df = df.rename(columns={
                    '开盘': 'open',
                    '收盘': 'close',
                    '最高': 'high',
                    '最低': 'low',
                    '成交量': 'volume',
                    '成交额': 'amount',
                    '涨跌幅': 'change_pct',
                    '换手率': 'turnover_rate'
                })
                
                # 选择需要的列
                cols = ['ts_code', 'trade_date', 'open', 'high', 'low', 'close', 
                       'volume', 'amount', 'change_pct', 'turnover_rate']
                df = df[cols]
                
                # 保存
                df.to_sql('stock_efinance', conn, if_exists='append', index=False)
                success += 1
                print(f"  {code}: {len(df)}条", end='\r')
        
        time.sleep(0.5)  # 避免请求过快
        
    except Exception as e:
        print(f"  {code}: 失败 - {e}")
        continue
    
    if success >= 20:
        break

# 统计
print(f"\n\n成功: {success} 只")
cnt = pd.read_sql("SELECT COUNT(*) as cnt FROM stock_efinance", conn)
print(f"总记录: {cnt['cnt'].iloc[0]} 条")

conn.close()
print("\n✅ 完成")
