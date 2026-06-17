#!/root/.openclaw/workspace/venv/bin/python3
import pandas as pd
import numpy as np
from longport.openapi import Config, QuoteContext, Period, AdjustType

config = Config.from_env()
ctx = QuoteContext(config)

# 获取30F数据
resp = ctx.candlesticks('000001.SH', Period.Min_30, 167, AdjustType.NoAdjust)
df_30m = pd.DataFrame([
    {'Date': pd.to_datetime(c.timestamp), 'Open': c.open, 'High': c.high, 'Low': c.low, 'Close': c.close, 'Volume': c.volume}
    for c in resp
]).sort_values('Date').reset_index(drop=True)

# 计算布林带中轨
def boll(df, w=20):
    m = df['Close'].rolling(window=w).mean()
    s = df['Close'].rolling(window=w).std()
    return {'upper': m + s*2, 'middle': m, 'lower': m - s*2}

b = boll(df_30m)
print(f'30F 当前收盘价: {df_30m["Close"].iloc[-1]:.2f}')
print(f'30F 布林带中轨(MA20): {b["middle"].iloc[-1]:.2f}')
print(f'30F 布林带上轨: {b["upper"].iloc[-1]:.2f}')
print(f'30F 布林带下轨: {b["lower"].iloc[-1]:.2f}')
print(f'30F MA55: {df_30m["Close"].rolling(55).mean().iloc[-1]:.2f}')

# 也看看15F和5F
resp15 = ctx.candlesticks('000001.SH', Period.Min_15, 334, AdjustType.NoAdjust)
df_15m = pd.DataFrame([
    {'Date': pd.to_datetime(c.timestamp), 'Open': c.open, 'High': c.high, 'Low': c.low, 'Close': c.close, 'Volume': c.volume}
    for c in resp15
]).sort_values('Date').reset_index(drop=True)

b15 = boll(df_15m)
print(f'')
print(f'15F 布林带中轨(MA20): {b15["middle"].iloc[-1]:.2f}')
print(f'15F MA55: {df_15m["Close"].rolling(55).mean().iloc[-1]:.2f}')

resp5 = ctx.candlesticks('000001.SH', Period.Min_5, 500, AdjustType.NoAdjust)
df_5m = pd.DataFrame([
    {'Date': pd.to_datetime(c.timestamp), 'Open': c.open, 'High': c.high, 'Low': c.low, 'Close': c.close, 'Volume': c.volume}
    for c in resp5
]).sort_values('Date').reset_index(drop=True)

b5 = boll(df_5m)
print(f'')
print(f'5F 当前收盘价: {df_5m["Close"].iloc[-1]:.2f}')
print(f'5F 布林带中轨(MA20): {b5["middle"].iloc[-1]:.2f}')
print(f'5F MA55: {df_5m["Close"].rolling(55).mean().iloc[-1]:.2f}')
