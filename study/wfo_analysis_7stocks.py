#!/root/.openclaw/workspace/venv/bin/python3
"""
WFO滚动周期预测分析 - 7只股票
数据源: 长桥API (真实数据)
分析框架: Walk-Forward Optimization
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json
import os
import sys

# 添加venv路径
sys.path.insert(0, '/root/.openclaw/workspace/venv/lib/python3.12/site-packages')

# 股票列表
STOCKS = {
    '澜起科技': '688008.SH',
    '兆易创新': '603986.SH', 
    '东山精密': '002384.SZ',
    '安集科技': '688019.SH',
    '世运电路': '603920.SH',
    '长芯博创': '688499.SH',  # 长芯博创 (长光华芯)
    '长光华芯': '688048.SH'   # 也可能是这只
}

print("="*60)
print("WFO滚动周期预测分析")
print("="*60)
print(f"分析时间: {datetime.now()}")
print(f"股票数量: {len(STOCKS)}")
print(f"数据源: 长桥API")
print("="*60)

# 检查长桥API配置
env_file = '/root/.openclaw/workspace/.longbridge.env'
if os.path.exists(env_file):
    with open(env_file) as f:
        lines = f.readlines()
        for line in lines:
            if '=' in line and not line.startswith('#'):
                key, value = line.strip().split('=', 1)
                os.environ[key] = value.strip('"')
    print("✅ 长桥API配置已加载")
else:
    print("❌ 长桥API配置不存在")
    sys.exit(1)

print("\n分析股票列表:")
for name, code in STOCKS.items():
    print(f"  • {name} ({code})")
