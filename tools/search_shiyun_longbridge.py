#!/root/.openclaw/workspace/venv/bin/python3
# search_shiyun_longbridge.py - 使用长桥API搜索世运电路相关新闻

import os
import sys
sys.path.insert(0, '/root/.openclaw/workspace/venv/lib/python3.12/site-packages')

# 加载环境变量
env_file = '/root/.openclaw/workspace/.longbridge.env'
if os.path.exists(env_file):
    with open(env_file, 'r') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#'):
                key, value = line.split('=', 1)
                os.environ[key] = value

from longport.openapi import Config, QuoteContext, Period, AdjustType
import json

print("="*60)
print("使用长桥API获取世运电路(603920.SH)信息")
print("="*60)

# 配置
config = Config.from_env()
ctx = QuoteContext(config)

# 世运电路在A股的symbol
symbol = "603920.SH"

# 获取股票基本信息
try:
    print("\n1. 获取股票基本信息:")
    securities = ctx.static_info([symbol])
    for sec in securities:
        print(f"   名称: {sec.name_cn}")
        print(f"   代码: {sec.symbol}")
        print(f"   总股本: {sec.total_shares}")
        print(f"   流通股本: {sec.circulating_shares}")
        print(f"   货币: {sec.currency}")
except Exception as e:
    print(f"   获取基本信息失败: {e}")

# 获取实时行情
try:
    print("\n2. 获取实时行情:")
    quote = ctx.quote([symbol])
    for q in quote:
        print(f"   最新价: {q.last_done}")
        print(f"   开盘价: {q.open}")
        print(f"   最高价: {q.high}")
        print(f"   最低价: {q.low}")
        print(f"   成交量: {q.volume}")
        print(f"   成交额: {q.turnover}")
except Exception as e:
    print(f"   获取行情失败: {e}")

# 获取历史K线
try:
    print("\n3. 获取近期日K线数据:")
    klines = ctx.history_klines(symbol, period=Period.DAY, count=5, adjust_type=AdjustType.NO_ADJUST)
    for k in klines[-5:]:
        print(f"   {k.timestamp}: 开={k.open}, 高={k.high}, 低={k.low}, 收={k.close}, 量={k.volume}")
except Exception as e:
    print(f"   获取K线失败: {e}")

print("\n注: 长桥API主要提供行情数据，新闻数据需要通过其他渠道获取")
print("="*60)
