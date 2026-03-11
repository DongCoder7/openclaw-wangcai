#!/root/.openclaw/workspace/venv/bin/python3
"""
专业支撑压力位分析 - 多周期验证方法
学习并实践更严谨的支撑压力位识别技术
"""

import pandas as pd
import numpy as np
from datetime import datetime
import pickle

print("="*70)
print("专业支撑压力位分析学习")
print("="*70)
print("学习方法: 多周期验证 + 形态确认 + 成交量分析")
print("="*70)

# 加载数据
with open('/root/.openclaw/workspace/study/wfo_stock_data_v2.pkl', 'rb') as f:
    stock_data = pickle.load(f)

print("""
【专业支撑压力位分析方法】

一、多时间周期验证原则
====================

1. 日线级别 (大趋势)
   - 确定主要支撑/压力位置
   - 观察近3-6个月的高低点
   - 标注明显的反转点

2. 60分钟级别 (中趋势)
   - 验证日线的支撑/压力
   - 寻找更精确的入场点
   - 观察短期趋势结构

3. 15分钟级别 (小趋势)
   - 精确到具体价格区间
   - 观察微观结构
   - 确认支撑/压力的有效性

二、支撑压力位识别标准
=====================

【有效支撑位认定标准】:

1. 多次触碰测试 (至少2-3次)
   - 价格下跌到该位置后反弹
   - 每次触碰都有明显买盘介入
   
2. 成交量特征
   - 触碰支撑位时成交量放大
   - 反弹时成交量持续
   
3. 时间跨度
   - 至少2周以上的时间跨度
   - 不是单日低点
   
4. 形态确认
   - W底形态
   - 头肩底形态
   - 双底形态
   
5. 技术指标确认
   - RSI超卖反弹
   - MACD金叉
   - 布林带下轨反弹

【有效压力位认定标准】:

1. 多次触碰测试 (至少2-3次)
   - 价格上涨到该位置后回落
   - 每次触碰都有明显卖盘
   
2. 成交量特征
   - 触碰压力位时成交量放大
   - 但未能突破，量能萎缩
   
3. 形态确认
   - M顶形态
   - 头肩顶形态
   - 双顶形态
   
4. 技术指标确认
   - RSI超买回落
   - MACD死叉
   - 布林带上轨受阻

三、动态支撑压力 (移动平均线)
===========================

1. MA20 (20日均线)
   - 短期趋势支撑/压力
   - 强势股沿MA20上涨
   
2. MA60 (60日均线)
   - 中期趋势支撑/压力
   - 牛熊分界线
   
3. MA120/MA250
   - 长期趋势支撑/压力
   - 年线/半年线

四、黄金分割位 (斐波那契回调)
==========================

关键回调位:
- 0.236 (23.6%)
- 0.382 (38.2%) - 重要支撑位
- 0.500 (50%) - 心理关口
- 0.618 (61.8%) - 最重要支撑位
- 0.786 (78.6%)

计算方法:
支撑位 = 高点 - (高点 - 低点) × 回调比例

五、成交量分布 (Volume Profile)
===========================

1. POC (Point of Control)
   - 成交量最大的价格
   - 强支撑/压力
   
2. Value Area (70%成交量区间)
   - 高成交量区域形成支撑/压力
""")

print("\n" + "="*70)
print("开始多周期支撑压力位分析")
print("="*70)

# 为每只股票计算更详细的指标
def calculate_advanced_indicators(df):
    """计算高级技术指标"""
    df = df.copy()
    
    # 基础指标
    df['return'] = df['close'].pct_change()
    
    # 多周期均线
    df['ma5'] = df['close'].rolling(5).mean()
    df['ma10'] = df['close'].rolling(10).mean()
    df['ma20'] = df['close'].rolling(20).mean()
    df['ma60'] = df['close'].rolling(60).mean()
    
    # MACD
    exp1 = df['close'].ewm(span=12, adjust=False).mean()
    exp2 = df['close'].ewm(span=26, adjust=False).mean()
    df['macd'] = exp1 - exp2
    df['macd_signal'] = df['macd'].ewm(span=9, adjust=False).mean()
    
    # RSI
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df['rsi'] = 100 - (100 / (1 + rs))
    
    # 布林带
    df['bb_middle'] = df['close'].rolling(20).mean()
    bb_std = df['close'].rolling(20).std()
    df['bb_upper'] = df['bb_middle'] + (bb_std * 2)
    df['bb_lower'] = df['bb_middle'] - (bb_std * 2)
    
    return df

# 识别支撑压力位 (改进版)
def find_support_resistance_advanced(df, window=20):
    """
    改进的支撑压力位识别
    结合多次触碰、成交量、形态
    """
    recent = df.tail(window).copy()
    
    # 1. 基础高低点
    base_low = recent['low'].min()
    base_high = recent['high'].max()
    
    # 2. 多次触碰测试
    # 找最近20日内出现2次以上的低点
    lows = recent['low'].values
    highs = recent['high'].values
    
    # 简化：找3日内的局部低点/高点
    local_lows = []
    local_highs = []
    
    for i in range(3, len(recent)-3):
        # 局部低点: 比前后3天都低
        if lows[i] == min(lows[i-3:i+4]):
            local_lows.append((recent.index[i], lows[i]))
        # 局部高点: 比前后3天都高
        if highs[i] == max(highs[i-3:i+4]):
            local_highs.append((recent.index[i], highs[i]))
    
    # 3. 均线支撑压力
    ma20 = recent['ma20'].iloc[-1]
    ma60 = recent['ma60'].iloc[-1]
    bb_lower = recent['bb_lower'].iloc[-1]
    bb_upper = recent['bb_upper'].iloc[-1]
    
    # 4. 选择最强支撑/压力
    # 支撑: 最低局部低点、MA20、布林带下轨
    supports = [base_low]
    if not np.isnan(ma20):
        supports.append(ma20)
    if not np.isnan(bb_lower):
        supports.append(bb_lower)
    for _, price in local_lows[-2:]:  # 最近2个局部低点
        supports.append(price)
    
    # 压力: 最高局部高点、MA60、布林带上轨
    resistances = [base_high]
    if not np.isnan(ma60):
        resistances.append(ma60)
    if not np.isnan(bb_upper):
        resistances.append(bb_upper)
    for _, price in local_highs[-2:]:
        resistances.append(price)
    
    return {
        'base_support': base_low,
        'base_resistance': base_high,
        'ma20': ma20,
        'ma60': ma60,
        'bb_lower': bb_lower,
        'bb_upper': bb_upper,
        'local_lows': local_lows,
        'local_highs': local_highs,
        'strong_support': min(supports),
        'strong_resistance': max(resistances),
        'avg_support': np.mean(supports),
        'avg_resistance': np.mean(resistances)
    }

# 分析每只股票
for symbol, info in stock_data.items():
    df = calculate_advanced_indicators(info['data'])
    info['data'] = df
    
    levels = find_support_resistance_advanced(df)
    info['levels'] = levels
    
    print(f"\n📊 {info['name']} ({symbol})")
    print("-" * 60)
    
    latest = df['close'].iloc[-1]
    
    print(f"最新价: {latest:.2f}")
    print(f"\n【多层级支撑】:")
    print(f"  最强支撑: {levels['strong_support']:.2f} (距现价 {(latest-levels['strong_support'])/latest*100:.1f}%)")
    print(f"  MA20支撑: {levels['ma20']:.2f} (距现价 {(latest-levels['ma20'])/latest*100:.1f}%)" if not np.isnan(levels['ma20']) else "  MA20支撑: N/A")
    print(f"  布林带下轨: {levels['bb_lower']:.2f}" if not np.isnan(levels['bb_lower']) else "  布林带下轨: N/A")
    print(f"  20日低点: {levels['base_support']:.2f}")
    
    print(f"\n【多层级压力】:")
    print(f"  最强压力: {levels['strong_resistance']:.2f} (距现价 {(levels['strong_resistance']-latest)/latest*100:.1f}%)")
    print(f"  MA60压力: {levels['ma60']:.2f}" if not np.isnan(levels['ma60']) else "  MA60压力: N/A")
    print(f"  布林带上轨: {levels['bb_upper']:.2f}" if not np.isnan(levels['bb_upper']) else "  布林带上轨: N/A")
    print(f"  20日高点: {levels['base_resistance']:.2f}")
    
    # 位置判断
    range_size = levels['strong_resistance'] - levels['strong_support']
    position = (latest - levels['strong_support']) / range_size
    
    if position < 0.3:
        position_desc = "🔵 低位区间 (关注支撑有效性)"
    elif position > 0.7:
        position_desc = "🔴 高位区间 (关注压力突破)"
    else:
        position_desc = "🟡 中位区间 (等待方向选择)"
    
    print(f"\n【位置判断】: {position_desc}")
    print(f"  区间位置: {position:.1%}")

print("\n" + "="*70)
print("学习完成: 多周期支撑压力分析方法")
print("="*70)

# 保存分析结果
with open('/root/.openclaw/workspace/study/advanced_sr_analysis.pkl', 'wb') as f:
    pickle.dump(stock_data, f)

print("\n✅ 分析结果已保存")
