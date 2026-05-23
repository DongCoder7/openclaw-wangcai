#!/root/.openclaw/workspace/venv/bin/python3
"""用Tushare获取涨跌停数据"""
import tushare as ts
from datetime import datetime

ts.set_token('cd2c935050381b52c9849eb054d1b198c21b0f29be2f025f9a9ece30')
pro = ts.pro_api()

today = '20260522'

# 涨跌停数据
try:
    df = pro.limit_list(trade_date=today)
    if df is not None and not df.empty:
        print(f"涨跌停数据: {len(df)} 条")
        limit_up = len(df[df['limit'] == 'U'])
        limit_down = len(df[df['limit'] == 'D'])
        print(f"涨停: {limit_up}, 跌停: {limit_down}")
        
        # 查看前几行
        print(df.head(10)[['ts_code', 'name', 'close', 'pct_chg', 'limit']].to_string(index=False))
except Exception as e:
    print(f"涨跌停错误: {e}")

# 每日指标
try:
    df = pro.daily_basic(trade_date=today)
    if df is not None and not df.empty:
        print(f"\n每日指标: {len(df)} 只")
        print(f"平均换手率: {df['turnover_rate'].mean():.2f}%")
        print(f"平均市盈率: {df['pe'].mean():.2f}")
except Exception as e:
    print(f"每日指标错误: {e}")
