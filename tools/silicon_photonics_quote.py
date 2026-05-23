#!/root/.openclaw/workspace/venv/bin/python3
import os
import sys
import json
from datetime import datetime

# Load longbridge env
env_path = '/root/.openclaw/workspace/.longbridge.env'
if os.path.exists(env_path):
    with open(env_path) as f:
        for line in f:
            if line.strip() and not line.startswith('#'):
                key, val = line.strip().split('=', 1)
                os.environ[key] = val.strip('"')

from longport.openapi import Config, QuoteContext, Market, SubType

# 硅光模块核心标的
codes = [
    "300308.SZ",   # 中际旭创 - 光模块龙头，硅光布局
    "300502.SZ",   # 新易盛 - 光模块，硅光技术
    "300394.SZ",   # 天孚通信 - 光器件
    "002281.SZ",   # 光迅科技 - 光模块，硅光芯片自研
    "000988.SZ",   # 华工科技 - 光模块
    "300548.SZ",   # 博创科技 - 光器件，硅光
    "688313.SH",   # 仕佳光子 - 光芯片
    "688498.SH",   # 源杰科技 - 光芯片
    "688048.SH",   # 长光华芯 - 光芯片/激光芯片
    "688205.SH",   # 德科立 - 光模块
    "603083.SH",   # 剑桥科技 - 光模块
    "300570.SZ",   # 太辰光 - 光器件
]

config = Config.from_env()
ctx = QuoteContext(config)

# Get quotes
quotes = ctx.quote(codes)

results = []
for q in quotes:
    code = q.symbol
    name = q.name
    last_done = float(q.last_done) if q.last_done else 0
    prev_close = float(q.prev_close) if q.prev_close else 0
    change = last_done - prev_close if prev_close else 0
    change_pct = (change / prev_close * 100) if prev_close else 0
    turnover = float(q.turnover) if q.turnover else 0
    volume = int(q.volume) if q.volume else 0
    
    results.append({
        'code': code,
        'name': name,
        'price': round(last_done, 2),
        'prev_close': round(prev_close, 2),
        'change': round(change, 2),
        'change_pct': round(change_pct, 2),
        'turnover': round(turnover / 100000000, 2),  # 亿
        'volume': volume,
    })

# Sort by change_pct desc
results.sort(key=lambda x: x['change_pct'], reverse=True)

print(json.dumps(results, ensure_ascii=False, indent=2))
