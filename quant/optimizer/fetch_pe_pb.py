#!/usr/bin/env python3
"""获取所有股票的实时PE/PB数据"""
import sqlite3
import efinance as ef
import pandas as pd

DB = '/root/.openclaw/workspace/data/historical/historical.db'

print("="*50)
print("获取PE/PB数据")
print("="*50)

conn = sqlite3.connect(DB)

# 获取实时行情
print("\n获取实时PE/PB...")
df = ef.stock.get_realtime_quotes()
print(f"获取到 {len(df)} 只股票")

# 提取需要的字段
df = df[['股票代码', '动态市盈率', '涨跌幅', '最新价', '总市值', '流通市值']].copy()
df.columns = ['code', 'pe', 'change_pct', 'close', 'total_mv', 'circ_mv']
df['pe'] = pd.to_numeric(df['pe'], errors='coerce')

print(f"有效PE数据: {df['pe'].notna().sum()}")

# 更新到数据库 - 获取最新交易日期的数据
print("\n更新最新数据...")

# 获取最新日期
latest_date = pd.read_sql("SELECT MAX(trade_date) as dt FROM stock_efinance", conn)
latest = latest_date['dt'].iloc[0]
print(f"最新日期: {latest}")

# 更新PE
updated = 0
for _, row in df[df['pe'].notna()].iterrows():
    code = row['code']
    # 匹配SZ或SH
    ts_code = code + '.SZ'
    sql = f"UPDATE stock_efinance SET pe = {row['pe']} WHERE ts_code = '{ts_code}' AND trade_date = '{latest}'"
    try:
        conn.execute(sql)
        updated += 1
    except:
        pass
    
    ts_code = code + '.SH'
    sql = f"UPDATE stock_efinance SET pe = {row['pe']} WHERE ts_code = '{ts_code}' AND trade_date = '{latest}'"
    try:
        conn.execute(sql)
        updated += 1
    except:
        pass

conn.commit()
print(f"更新了 {updated} 条记录")

# 验证
cnt = pd.read_sql("SELECT COUNT(*) as cnt FROM stock_efinance WHERE pe IS NOT NULL AND pe > 0", conn)
print(f"有PE的记录: {cnt['cnt'].iloc[0]}")

conn.close()
print("\n✅ 完成")
