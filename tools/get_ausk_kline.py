#!/root/.openclaw/workspace/venv/bin/python3
"""获取奥士康K线数据用于技术分析"""
from longport.openapi import Config, QuoteContext, Period, AdjustType
import json
from datetime import datetime, timedelta

config = Config.from_env()
ctx = QuoteContext(config)

stock_code = '002913.SZ'

# 获取日线数据（最近60天）
candles = ctx.candles(
    stock_code, 
    period=Period.Day,
    count=60,
    adjust_type=AdjustType.Forward
)

print(f"=== 奥士康 (002913.SZ) K线数据 ===")
print(f"获取到 {len(candles)} 条日线数据\n")

# 提取关键数据
recent = candles[-10:]
print("最近10个交易日:")
for c in recent:
    print(f"  {c.timestamp.date()}: 开{c.open}, 收{c.close}, 高{c.high}, 低{c.low}, 量{c.volume}")

# 计算技术指标
closes = [float(c.close) for c in candles]

# 计算5日、10日、20日均线
ma5 = sum(closes[-5:]) / 5
ma10 = sum(closes[-10:]) / 10
ma20 = sum(closes[-20:]) / 20 if len(closes) >= 20 else sum(closes) / len(closes)

# 计算近期涨跌幅
change_5d = (closes[-1] - closes[-5]) / closes[-5] * 100 if len(closes) >= 5 else 0
change_20d = (closes[-1] - closes[-20]) / closes[-20] * 100 if len(closes) >= 20 else 0

print(f"\n=== 技术指标 ===")
print(f"当前收盘价: {closes[-1]}")
print(f"5日均线: {ma5:.2f}")
print(f"10日均线: {ma10:.2f}")
print(f"20日均线: {ma20:.2f}")
print(f"5日涨跌幅: {change_5d:.2f}%")
print(f"20日涨跌幅: {change_20d:.2f}%")

# 判断趋势
if closes[-1] > ma5 > ma10 > ma20:
    trend = "强势上涨"
elif closes[-1] > ma5 > ma10:
    trend = "短期上升"
elif closes[-1] > ma20:
    trend = "中期上升"
elif closes[-1] < ma5 < ma10 < ma20:
    trend = "弱势下跌"
elif closes[-1] < ma20:
    trend = "中期下降"
else:
    trend = "震荡整理"

print(f"趋势判断: {trend}")

result = {
    "current_price": closes[-1],
    "ma5": round(ma5, 2),
    "ma10": round(ma10, 2),
    "ma20": round(ma20, 2),
    "change_5d": round(change_5d, 2),
    "change_20d": round(change_20d, 2),
    "trend": trend
}
print(f"\n{json.dumps(result, ensure_ascii=False)}")
