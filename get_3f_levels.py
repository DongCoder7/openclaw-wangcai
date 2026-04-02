#!/root/.openclaw/workspace/venv/bin/python3
"""
使用长桥API获取上证指数3分钟K线数据
计算3F55线和3F中轨
"""
import os
import json
from datetime import datetime

# 加载长桥环境变量
env_path = "/root/.openclaw/workspace/.longbridge.env"
with open(env_path) as f:
    for line in f:
        if line.strip() and not line.startswith('#'):
            key, val = line.strip().split('=', 1)
            os.environ[key] = val

from longport.openapi import QuoteContext, Config, Period, AdjustType

print("=" * 60)
print("上证指数3分钟K线数据（长桥API）")
print(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
print("=" * 60)

# 初始化API
config = Config.from_env()
ctx = QuoteContext(config)

# 上证指数代码
symbol = "SH.000001"

# 获取3分钟K线
print("\n【获取3分钟K线】")
try:
    bars = ctx.history_candles(symbol, period=Period.Min_3, count=80)
    
    closes = [b.close for b in bars]
    highs = [b.high for b in bars]
    lows = [b.low for b in bars]
    
    # 计算55周期均线
    if len(closes) >= 55:
        ma55 = sum(closes[-55:]) / 55
        ma20 = sum(closes[-20:]) / 20  # 中轨
        
        print(f"3F55线: {ma55:.2f}")
        print(f"3F中轨(20周期): {ma20:.2f}")
        print(f"最新收盘: {closes[-1]:.2f}")
        
        # 保存结果
        result = {
            "timestamp": datetime.now().isoformat(),
            "3F55线": round(ma55, 2),
            "3F中轨": round(ma20, 2),
            "当前收盘": round(closes[-1], 2)
        }
        
        with open("/root/.openclaw/workspace/data/3f_levels.json", "w") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        print("\n✅ 数据已保存")
        
    else:
        print(f"数据不足: 只有{len(closes)}条K线")
        
except Exception as e:
    print(f"获取失败: {e}")
    print("请检查token是否有效")
