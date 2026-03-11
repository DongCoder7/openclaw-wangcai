#!/root/.openclaw/workspace/venv/bin/python3
"""阳光电源完整分析 - 详细版"""
import pandas as pd
import numpy as np
from datetime import datetime
import sys
import os

sys.path.insert(0, '/root/.openclaw/workspace/venv/lib/python3.12/site-packages')

from longport.openapi import QuoteContext, Config, AdjustType, Period

print("="*70)
print("📊 阳光电源 (300274.SZ) 完整短期走势分析")
print("="*70)
print(f"分析时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
print("="*70)

# 初始化API
env_file = '/root/.openclaw/workspace/.longbridge.env'
if os.path.exists(env_file):
    with open(env_file) as f:
        for line in f:
            if '=' in line and not line.startswith('#'):
                key, value = line.strip().split('=', 1)
                os.environ[key] = value.strip('"')

config = Config.from_env()
ctx = QuoteContext(config)

symbol = '300274.SZ'

# Step 1: 获取数据
print("\n【Step 1】获取股票数据")
print("  获取60分钟K线数据...")
resp_60 = ctx.candlesticks(symbol, period=Period.Min_60, count=240, adjust_type=AdjustType.NoAdjust)
data_60 = []
for candle in resp_60:
    data_60.append({
        'datetime': candle.timestamp,
        'open': float(candle.open),
        'high': float(candle.high),
        'low': float(candle.low),
        'close': float(candle.close),
        'volume': int(candle.volume)
    })
df_60 = pd.DataFrame(data_60).sort_values('datetime').reset_index(drop=True)
print(f"  ✅ 获取到 {len(df_60)} 条60分钟K线")

print("  获取日线数据...")
resp_day = ctx.candlesticks(symbol, period=Period.Day, count=60, adjust_type=AdjustType.NoAdjust)
data_day = []
for candle in resp_day:
    data_day.append({
        'date': candle.timestamp.date(),
        'open': float(candle.open),
        'high': float(candle.high),
        'low': float(candle.low),
        'close': float(candle.close),
        'volume': int(candle.volume)
    })
df_day = pd.DataFrame(data_day).sort_values('date').reset_index(drop=True)
print(f"  ✅ 获取到 {len(df_day)} 条日线")

# 显示最新数据
latest_60 = df_60.iloc[-1]
latest_day = df_day.iloc[-1]
print(f"\n  最新60分钟线:")
print(f"    时间: {latest_60['datetime']}")
print(f"    开: {latest_60['open']:.2f} 高: {latest_60['high']:.2f} 低: {latest_60['low']:.2f} 收: {latest_60['close']:.2f}")
print(f"  最新日线:")
print(f"    日期: {latest_day['date']}")
print(f"    开: {latest_day['open']:.2f} 高: {latest_day['high']:.2f} 低: {latest_day['low']:.2f} 收: {latest_day['close']:.2f}")

# Step 2: 计算技术指标
print("\n【Step 2】计算技术指标")

# 60分钟布林带
df_60['ma20'] = df_60['close'].rolling(20).mean()
df_60['bb_middle'] = df_60['close'].rolling(20).mean()
bb_std = df_60['close'].rolling(20).std()
df_60['bb_upper'] = df_60['bb_middle'] + (bb_std * 2)
df_60['bb_lower'] = df_60['bb_middle'] - (bb_std * 2)

# 日线MA
df_day['ma5'] = df_day['close'].rolling(5).mean()
df_day['ma10'] = df_day['close'].rolling(10).mean()
df_day['ma20'] = df_day['close'].rolling(20).mean()
df_day['ma60'] = df_day['close'].rolling(60).mean()

# MACD
exp1 = df_day['close'].ewm(span=12, adjust=False).mean()
exp2 = df_day['close'].ewm(span=26, adjust=False).mean()
df_day['macd'] = exp1 - exp2
df_day['macd_signal'] = df_day['macd'].ewm(span=9, adjust=False).mean()

# RSI
delta = df_day['close'].diff()
gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
df_day['rsi'] = 100 - (100 / (1 + gain / loss))

print("  60分钟布林带:")
print(f"    上轨: {df_60['bb_upper'].iloc[-1]:.2f}")
print(f"    中轨: {df_60['bb_middle'].iloc[-1]:.2f}")
print(f"    下轨: {df_60['bb_lower'].iloc[-1]:.2f}")

print("  日线均线:")
print(f"    MA5: {df_day['ma5'].iloc[-1]:.2f}")
print(f"    MA10: {df_day['ma10'].iloc[-1]:.2f}")
print(f"    MA20: {df_day['ma20'].iloc[-1]:.2f}")
print(f"    MA60: {df_day['ma60'].iloc[-1]:.2f}")

print("  MACD:")
print(f"    DIF: {df_day['macd'].iloc[-1]:.2f}")
print(f"    DEA: {df_day['macd_signal'].iloc[-1]:.2f}")
print(f"    柱状: {(df_day['macd'] - df_day['macd_signal']).iloc[-1]:.2f}")

rsi_val = df_day['rsi'].iloc[-1]
print(f"  RSI(14): {rsi_val:.2f} ({'超买' if rsi_val > 70 else '超卖' if rsi_val < 30 else '中性'})")

# Step 3: 支撑压力分析
print("\n【Step 3】多周期支撑压力分析")

recent_60 = df_60.tail(40)
support = recent_60['low'].min()
resistance = recent_60['high'].max()
latest = df_60['close'].iloc[-1]

print("  60分钟级别(10天):")
print(f"    最高价: {resistance:.2f}元")
print(f"    最低价: {support:.2f}元")
print(f"    当前价: {latest:.2f}元")
print(f"    布林带下轨: {df_60['bb_lower'].iloc[-1]:.2f}元 (动态支撑)")
print(f"    布林带上轨: {df_60['bb_upper'].iloc[-1]:.2f}元 (动态压力)")

# 日线级别
recent_day = df_day.tail(20)
support_day = recent_day['low'].min()
resistance_day = recent_day['high'].max()
print("  日线级别(20天):")
print(f"    压力位: {resistance_day:.2f}元")
print(f"    支撑位: {support_day:.2f}元")

# Step 4: 触碰次数验证
print("\n【Step 4】触碰次数验证")

def count_touches_detailed(df, level, tolerance=0.02, lookback=60):
    """详细统计触碰次数"""
    recent = df.tail(lookback)
    lower = level * (1 - tolerance)
    upper = level * (1 + tolerance)
    
    touches = 0
    bounces = 0
    details = []
    
    for i in range(len(recent) - 1):
        row = recent.iloc[i]
        next_row = recent.iloc[i + 1]
        
        if row['low'] <= upper and row['high'] >= lower:
            touches += 1
            bounced = False
            if row['close'] < level and next_row['close'] > row['close']:
                bounces += 1
                bounced = True
            elif row['close'] > level and next_row['close'] < row['close']:
                bounces += 1
                bounced = True
            
            details.append({
                'time': row['datetime'],
                'price': row['close'],
                'bounced': bounced
            })
    
    return touches, bounces, details

touches, bounces, details = count_touches_detailed(df_60, support)
print(f"  支撑位 {support:.2f}元:")
print(f"    统计区间: 最近60根60分钟K线(约15个交易日)")
print(f"    触碰次数: {touches}次")
print(f"    反弹/回落次数: {bounces}次")
print(f"    反弹成功率: {bounces/touches*100:.1f}%" if touches > 0 else "    反弹成功率: N/A")
if touches > 0:
    rating = '⭐⭐⭐ 强' if bounces/touches >= 0.5 else '⭐⭐ 中' if touches >= 2 else '⭐ 弱'
else:
    rating = '⭐ 弱'
print(f"    有效性评级: {rating}")

if details:
    print(f"    最近3次触碰:")
    for d in details[-3:]:
        print(f"      {d['time']}: {d['price']:.2f}元 {'(反弹)' if d['bounced'] else ''}")

# Step 5: 形态识别
print("\n【Step 5】形态结构识别")

def detect_patterns_detailed(df):
    """详细形态识别"""
    patterns = []
    recent = df.tail(60)
    highs = recent['high'].values
    lows = recent['low'].values
    closes = recent['close'].values
    
    # W底检测
    for i in range(5, len(recent) - 10):
        if lows[i] == min(lows[i-3:i+4]):
            for j in range(i + 5, min(i + 20, len(recent) - 5)):
                if lows[j] == min(lows[j-3:j+4]):
                    if abs(lows[j] - lows[i]) / lows[i] < 0.05:
                        mid_high = max(highs[i:j])
                        neckline = mid_high
                        if mid_high > lows[i] * 1.02:
                            target = neckline + (neckline - lows[i])
                            patterns.append({
                                'type': 'W底',
                                'strength': '强',
                                'first_low': lows[i],
                                'second_low': lows[j],
                                'neckline': neckline,
                                'target': target,
                                'first_low_idx': i,
                                'second_low_idx': j
                            })
                            break
    
    # M顶检测
    for i in range(5, len(recent) - 10):
        if highs[i] == max(highs[i-3:i+4]):
            for j in range(i + 5, min(i + 20, len(recent) - 5)):
                if highs[j] == max(highs[j-3:j+4]):
                    if abs(highs[j] - highs[i]) / highs[i] < 0.05:
                        mid_low = min(lows[i:j])
                        neckline = mid_low
                        if mid_low < highs[i] * 0.98:
                            target = neckline - (highs[i] - neckline)
                            patterns.append({
                                'type': 'M顶',
                                'strength': '强',
                                'first_high': highs[i],
                                'second_high': highs[j],
                                'neckline': neckline,
                                'target': target,
                                'first_high_idx': i,
                                'second_high_idx': j
                            })
                            break
    
    return patterns

patterns = detect_patterns_detailed(df_60)
if patterns:
    print(f"  识别到 {len(patterns)} 个形态:")
    for p in patterns[-2:]:  # 显示最近2个
        print(f"    【{p['type']}】")
        print(f"      强度: {p['strength']}")
        if p['type'] == 'W底':
            print(f"      第一低点: {p['first_low']:.2f}元")
            print(f"      第二低点: {p['second_low']:.2f}元")
            print(f"      颈线位: {p['neckline']:.2f}元")
            print(f"      理论目标: {p['target']:.2f}元")
        else:
            print(f"      第一高点: {p['first_high']:.2f}元")
            print(f"      第二高点: {p['second_high']:.2f}元")
            print(f"      颈线位: {p['neckline']:.2f}元")
            print(f"      理论目标: {p['target']:.2f}元")
else:
    print("  未识别到明显形态")

# Step 6: Volume Profile
print("\n【Step 6】Volume Profile分析")

price_min = df_60['low'].min()
price_max = df_60['high'].max()
bin_size = (price_max - price_min) / 10

print(f"  价格区间: {price_min:.2f}元 - {price_max:.2f}元")
print(f"  分成10个档位，每个档位{bin_size:.2f}元")

volume_dist = []
for i in range(10):
    bin_low = price_min + i * bin_size
    bin_high = price_min + (i + 1) * bin_size
    mask = (df_60['low'] <= bin_high) & (df_60['high'] >= bin_low)
    vol = df_60[mask]['volume'].sum()
    volume_dist.append({
        'low': bin_low,
        'high': bin_high,
        'mid': (bin_low + bin_high) / 2,
        'volume': vol
    })
    print(f"    档位{i+1} [{bin_low:.2f}-{bin_high:.2f}]: 成交量 {vol/1e6:.2f}M")

# 找到POC
max_vol_idx = max(range(len(volume_dist)), key=lambda i: volume_dist[i]['volume'])
poc = volume_dist[max_vol_idx]
print(f"\n  POC (Point of Control):")
print(f"    价格: {poc['mid']:.2f}元")
print(f"    区间: {poc['low']:.2f}元 - {poc['high']:.2f}元")
print(f"    成交量: {poc['volume']/1e6:.2f}M")

# Value Area (70%成交量)
total_vol = sum([v['volume'] for v in volume_dist])
sorted_dist = sorted(volume_dist, key=lambda x: x['volume'], reverse=True)
cum_vol = 0
va_bins = []
for v in sorted_dist:
    cum_vol += v['volume']
    va_bins.append(v)
    if cum_vol >= total_vol * 0.7:
        break

va_low = min([v['low'] for v in va_bins])
va_high = max([v['high'] for v in va_bins])
print(f"  Value Area (70%成交量):")
print(f"    区间: {va_low:.2f}元 - {va_high:.2f}元")
print(f"    当前价格位置: {'POC上方' if latest > poc['mid'] else 'POC下方'} {(latest/poc['mid']-1)*100:+.1f}%")

# Step 7: 综合评分
print("\n【Step 7】综合评分计算")

score = 0
factors = []

# 获取最新日线数据（从df_day最后一行）
latest_day_data = df_day.iloc[-1]
close_price = latest_day_data['close']
ma20_val = latest_day_data['ma20']
macd_val = latest_day_data['macd']
macd_signal = latest_day_data['macd_signal']
rsi_val = latest_day_data['rsi']

# 1. 日线趋势
if close_price > ma20_val:
    score += 1
    factors.append("日线上涨(+1)")
    print("  +1分: 价格在MA20上方，日线趋势向上")
else:
    score -= 1
    factors.append("日线下跌(-1)")
    print("  -1分: 价格在MA20下方")

# 2. MACD
if macd_val > macd_signal:
    print(f"  +0.5分: MACD金叉 (DIF={macd_val:.2f} > DEA={macd_signal:.2f})")
    score += 0.5
    factors.append("MACD金叉(+0.5)")
else:
    print(f"  -0.5分: MACD死叉 (DIF={macd_val:.2f} < DEA={macd_signal:.2f})")
    score -= 0.5
    factors.append("MACD死叉(-0.5)")

# 3. RSI
if rsi_val > 70:
    print(f"  -0.5分: RSI超买 ({rsi_val:.1f} > 70)")
    score -= 0.5
    factors.append("RSI超买(-0.5)")
elif rsi_val < 30:
    print(f"  +0.5分: RSI超卖 ({rsi_val:.1f} < 30)")
    score += 0.5
    factors.append("RSI超卖(+0.5)")
else:
    print(f"  0分: RSI中性 ({rsi_val:.1f})")

# 4. 布林带位置
bb_pos = (latest - df_60['bb_lower'].iloc[-1]) / (df_60['bb_upper'].iloc[-1] - df_60['bb_lower'].iloc[-1])
print(f"  布林带位置: {bb_pos*100:.1f}% (0%=下轨, 100%=上轨)")

# 5. 支撑有效性
if touches >= 3 and bounces/touches >= 0.5:
    print(f"  +1分: 强支撑 (触碰{touches}次，反弹率{bounces/touches*100:.0f}%)")
    score += 1
    factors.append("强支撑(+1)")
elif touches >= 2:
    print(f"  +0.5分: 有支撑 (触碰{touches}次)")
    score += 0.5
    factors.append("有支撑(+0.5)")

# 6. 形态
if patterns:
    for p in patterns:
        if p['type'] == 'W底':
            print(f"  +1分: W底形态")
            score += 1
            factors.append("W底(+1)")
        elif p['type'] == 'M顶':
            print(f"  -1分: M顶形态")
            score -= 1
            factors.append("M顶(-1)")

# 7. 位置
range_size = resistance - support
position = (latest - support) / range_size if range_size > 0 else 0.5
print(f"  价格区间位置: {position*100:.1f}% (0%=支撑位, 100%=压力位)")
if position < 0.3:
    print(f"  +0.5分: 处于低位区间")
    score += 0.5
    factors.append("低位(+0.5)")
elif position > 0.7:
    print(f"  -0.5分: 处于高位区间")
    score -= 0.5
    factors.append("高位(-0.5)")

print(f"\n  综合评分: {score:.1f}分")
print(f"  评分因素: {', '.join(factors)}")

# Step 8: 预测方向
print("\n【Step 8】预测方向判定")

if score >= 2:
    outlook = "🚀 强烈看涨"
    expected_return = "+15~25%"
elif score >= 1:
    outlook = "📈 看涨"
    expected_return = "+5~15%"
elif score >= -1:
    outlook = "➡️ 震荡"
    expected_return = "-5~5%"
elif score >= -2:
    outlook = "📉 看跌"
    expected_return = "-15~-5%"
else:
    outlook = "🔻 强烈看跌"
    expected_return = "-25~-15%"

print(f"  评分: {score:.1f}分")
print(f"  预测方向: {outlook}")
print(f"  预期收益(20日): {expected_return}")

# Step 9: 买入建议
print("\n【Step 9】买入建议")

if score >= 1.5:
    advice = "✅ 回调至支撑位可买入"
elif score >= 1:
    advice = "⚠️ 可轻仓买入，等待突破"
elif score >= 0:
    advice = "⏸️ 观望，等待更明确信号"
else:
    advice = "❌ 回避，等待回调"

print(f"  建议: {advice}")
print(f"\n  关键价位:")
print(f"    当前价: {latest:.2f}元")
print(f"    支撑位: {support:.2f}元 (60分钟低点)")
print(f"    压力位: {resistance:.2f}元 (60分钟高点)")
print(f"    POC: {poc['mid']:.2f}元 (成交量最大价格)")
print(f"    布林带下轨: {df_60['bb_lower'].iloc[-1]:.2f}元")
print(f"    布林带上轨: {df_60['bb_upper'].iloc[-1]:.2f}元")

buy_zone = support * 1.02 if latest > support * 1.05 else latest
print(f"\n  建议操作:")
if position > 0.7:
    print(f"    当前价格处于高位({position*100:.1f}%)，不宜追高")
    print(f"    等待回调至 {support*1.02:.2f}-{support*1.05:.2f}元 区间买入")
else:
    print(f"    可在当前价位轻仓试仓")
    print(f"    加仓点: {support*1.02:.2f}元附近")

print(f"    止损位: {support*0.98:.2f}元 (支撑位下方2%)")
print(f"    目标位: {resistance*.98:.2f}元 (压力位附近)")

# 汇总
print("\n" + "="*70)
print("【完整分析汇总】")
print("="*70)
print(f"""
股票: 阳光电源 ({symbol})
当前价: {latest:.2f}元

技术指标:
  MA5/10/20: {latest_day_data['ma5']:.2f}/{latest_day_data['ma10']:.2f}/{latest_day_data['ma20']:.2f}元
  MACD: DIF={macd_val:.2f}, DEA={macd_signal:.2f}
  RSI: {rsi_val:.1f} ({'超买' if rsi_val > 70 else '超卖' if rsi_val < 30 else '中性'})
  布林带: [{df_60['bb_lower'].iloc[-1]:.2f}, {df_60['bb_upper'].iloc[-1]:.2f}]

支撑压力:
  支撑位: {support:.2f}元 (60分钟低点，触碰{touches}次，反弹率{bounces/touches*100:.0f}%)
  压力位: {resistance:.2f}元 (60分钟高点)
  POC: {poc['mid']:.2f}元 (成交量控制点)

综合评分: {score:.1f}分
预测方向: {outlook}
预期收益: {expected_return}

买入建议: {advice}
""")
print("="*70)
