#!/usr/bin/env python3
"""用AKShare补齐完整的历史数据"""
import sqlite3
import pandas as pd
import akshare as ak
from datetime import datetime
import time
import sys

DB = '/root/.openclaw/workspace/data/historical/historical.db'

print("="*50)
print("AKShare补齐历史数据")
print("="*50)

conn = sqlite3.connect(DB)

# 获取股票列表
stocks = pd.read_sql("SELECT DISTINCT ts_code FROM daily_price LIMIT 200", conn)
print(f"股票数: {len(stocks)}")

# 创建扩展表
print("\n[1] 创建扩展表...")
conn.execute("""
CREATE TABLE IF NOT EXISTS stock_daily_extended (
    ts_code TEXT,
    trade_date TEXT,
    open REAL,
    high REAL,
    low REAL,
    close REAL,
    volume REAL,
    amount REAL,
    turnover_rate REAL,
    change_pct REAL,
    pe REAL,
    pb REAL,
    ps REAL,
    dv_ratio REAL,
    total_mv REAL,
    circ_mv REAL,
    volume_ratio REAL,
    PRIMARY KEY (ts_code, trade_date)
)
""")
conn.commit()

# 成功获取的股票
success = 0
failed = 0

print("\n[2] 获取数据...")

for i, row in stocks.iterrows():
    code = row['ts_code']
    # 转换代码格式
    symbol = code.replace('.SZ', '').replace('.SH', '')
    
    try:
        # 获取日线数据
        df = ak.stock_zh_a_hist(symbol=symbol, 
                                start_date='20180101', 
                                end_date='20211231',
                                adjust='qfq')
        
        if df is not None and len(df) > 0:
            # 转换列名
            df.columns = ['trade_date', 'ts_code', 'open', 'close', 'high', 'low', 
                         'volume', 'amount', 'amplitude', 'change_pct', 'change', 'turnover_rate']
            
            # 添加ts_code
            df['ts_code'] = code
            
            # 尝试获取基本面
            try:
                basic = ak.stock_zh_a_spot_em()
                basic = basic[basic['代码'] == symbol]
                if not basic.empty:
                    pe = basic['市盈率'].iloc[0]
                    pb = basic['市净率'].iloc[0]
                else:
                    pe = pb = None
            except:
                pe = pb = None
            
            # 简化：只保存有成交量的数据
            df = df[df['volume'] > 0]
            
            if len(df) > 0:
                df.to_sql('stock_daily_extended', conn, if_exists='append', index=False)
                success += 1
                print(f"  {code}: {len(df)}条", end='\r')
        
        time.sleep(0.3)  # 避免请求过快
        
    except Exception as e:
        failed += 1
        print(f"  {code}: 失败 ({e})")
        continue
    
    if success >= 30:  # 先测试30只
        break

# 统计
print(f"\n\n成功: {success} 只")
print(f"失败: {failed} 只")

cnt = pd.read_sql("SELECT COUNT(*) as cnt FROM stock_daily_extended", conn)
print(f"总记录: {cnt['cnt'].iloc[0]} 条")

conn.close()
print("\n✅ 完成")
