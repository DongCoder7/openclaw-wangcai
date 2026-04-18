#!/root/.openclaw/workspace/venv/bin/python3
import sys
sys.path.insert(0, '/root/.openclaw/workspace')

import os
from longport.openapi import QuoteContext, Config
import json

# 加载环境变量
env_path = '/root/.openclaw/workspace/.longbridge.env'
if os.path.exists(env_path):
    with open(env_path, 'r') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#'):
                key, value = line.split('=', 1)
                os.environ[key] = value

config = Config.from_env()
ctx = QuoteContext(config)

# DSP芯片相关A股标的 - 根据行业知识整理
# DSP (Digital Signal Processor) 数字信号处理器

watchlist = [
    # 直接涉及DSP芯片设计/制造
    '688008.SH',   # 澜起科技 - 内存接口芯片+数字信号处理
    '688396.SH',   # 华润微 - 功率半导体+信号处理芯片
    '600460.SH',   # 士兰微 - MCU+DSP相关
    '603893.SH',   # 瑞芯微 - SoC芯片，含DSP模块
    '688521.SH',   # 芯原股份 - 芯片设计服务，含DSP IP
    '688608.SH',   # 恒玄科技 - 智能音频SoC，含DSP
    '300613.SZ',   # 富瀚微 - 视频监控芯片，含视频DSP
    '300458.SZ',   # 全志科技 - 智能应用处理器，含DSP
    '300223.SZ',   # 北京君正 - 嵌入式CPU+信号处理
    '688595.SH',   # 芯海科技 - 信号链芯片+ADC/DSP
    '300077.SZ',   # 国民技术 - 安全芯片+通用MCU
    '603160.SH',   # 汇顶科技 - 触控芯片+音频DSP
    '688049.SH',   # 炬芯科技 - 蓝牙音频SoC，含DSP
    '688385.SH',   # 复旦微电 - FPGA+信号处理
    '688018.SH',   # 乐鑫科技 - WiFi MCU，含信号处理
    '688107.SH',   # 安路科技 - FPGA，用于信号处理
    '688072.SH',   # 拓荆科技 - 薄膜沉积设备（芯片制造）
    '688120.SH',   # 华海清科 - CMP设备（芯片制造）
]

print('='*60)
print('DSP数字信号处理器芯片 - A股相关标的分析')
print('='*60)
print()

# 获取实时行情
quotes = ctx.quote(watchlist)

result = []
for q in quotes:
    symbol = q.symbol
    last_done = float(q.last_done) if q.last_done else 0
    change_rate = float(q.change_rate) if q.change_rate else 0
    
    result.append({
        'symbol': symbol,
        'last_done': last_done,
        'change_rate': change_rate,
    })

# 按涨跌幅排序
result_sorted = sorted(result, key=lambda x: x['change_rate'], reverse=True)

print('【实时行情 - 按涨跌幅排序】')
print('-'*60)
for item in result_sorted:
    symbol = item['symbol']
    last_done = item['last_done']
    change_rate = item['change_rate']
    
    # 格式化涨跌幅
    if change_rate > 0:
        change_str = f'+{change_rate:.2f}%'
    else:
        change_str = f'{change_rate:.2f}%'
    
    print(f'{symbol} | {last_done:>8.2f} | {change_str:>8}')

print()
print('='*60)
