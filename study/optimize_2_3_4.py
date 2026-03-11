#!/root/.openclaw/workspace/venv/bin/python3
"""
优化2-4: 触碰次数统计 + 形态识别 + 成交量分析
使用真实分钟级数据
"""

import pandas as pd
import numpy as np
from datetime import datetime
import pickle

# 加载分钟级数据
with open('/root/.openclaw/workspace/study/minute_data.pkl', 'rb') as f:
    minute_data = pickle.load(f)

print("="*70)
print("优化2: 支撑压力位触碰次数统计")
print("="*70)

def count_touch_tests(df, level, tolerance=0.02, window=20):
    """
    统计价格在某个水平位的触碰次数
    
    参数:
        df: DataFrame with price data
        level: 支撑/压力价格水平
        tolerance: 容忍度 (2%)
        window: 观察窗口
    
    返回:
        touch_count: 触碰次数
        bounce_count: 反弹次数 (触碰后反转)
        touch_details: 触碰详情
    """
    recent = df.tail(window).copy()
    
    # 定义触碰区间 (level ± tolerance)
    lower_bound = level * (1 - tolerance)
    upper_bound = level * (1 + tolerance)
    
    touches = []
    
    for i in range(len(recent)):
        row = recent.iloc[i]
        # 检查是否触碰 (最低价<=level<=最高价)
        if row['low'] <= upper_bound and row['high'] >= lower_bound:
            # 确定触碰类型
            if abs(row['close'] - level) / level < tolerance:
                touch_type = 'close_touch'
            elif abs(row['low'] - level) / level < tolerance:
                touch_type = 'low_touch'
            elif abs(row['high'] - level) / level < tolerance:
                touch_type = 'high_touch'
            else:
                touch_type = 'range_touch'
            
            touches.append({
                'index': i,
                'datetime': row['datetime'],
                'price': row['close'],
                'low': row['low'],
                'high': row['high'],
                'volume': row['volume'],
                'type': touch_type,
                'distance_to_level': abs(row['close'] - level) / level
            })
    
    # 统计反弹 (简单定义: 触碰后下一根K线反转)
    bounces = 0
    for i in range(len(touches)-1):
        curr_idx = touches[i]['index']
        next_idx = touches[i+1]['index'] if i+1 < len(touches) else curr_idx + 1
        
        if next_idx < len(recent):
            curr_close = recent.iloc[curr_idx]['close']
            next_close = recent.iloc[next_idx]['close']
            
            # 如果是支撑位，下一根上涨算反弹
            # 如果是压力位，下一根下跌算回落
            # 这里简化处理
            if abs(next_close - curr_close) / curr_close > 0.005:  # 0.5%以上变动
                bounces += 1
    
    return {
        'touch_count': len(touches),
        'bounce_count': bounces,
        'touch_rate': len(touches) / window,
        'bounce_rate': bounces / len(touches) if touches else 0,
        'touches': touches
    }

# 对每只股票进行触碰分析
for symbol, info in minute_data.items():
    name = info['name']
    df_60 = info['data']['60min']
    
    print(f"\n📊 {name} ({symbol})")
    print("-"*70)
    
    # 获取最近价格
    latest_price = df_60['close'].iloc[-1]
    
    # 确定分析的支撑和压力位 (基于60分钟数据)
    recent_high = df_60['high'].tail(40).max()
    recent_low = df_60['low'].tail(40).min()
    
    # 可能的支撑位 (近期低点附近)
    support_candidates = []
    for i in range(1, len(df_60)-1):
        if df_60['low'].iloc[i] <= df_60['low'].iloc[i-1] and df_60['low'].iloc[i] <= df_60['low'].iloc[i+1]:
            if df_60['low'].iloc[i] < recent_low * 1.05:  # 接近近期低点
                support_candidates.append((df_60['datetime'].iloc[i], df_60['low'].iloc[i]))
    
    # 可能的压力位 (近期高点附近)
    resistance_candidates = []
    for i in range(1, len(df_60)-1):
        if df_60['high'].iloc[i] >= df_60['high'].iloc[i-1] and df_60['high'].iloc[i] >= df_60['high'].iloc[i+1]:
            if df_60['high'].iloc[i] > recent_high * 0.95:  # 接近近期高点
                resistance_candidates.append((df_60['datetime'].iloc[i], df_60['high'].iloc[i]))
    
    # 统计最强支撑位的触碰次数
    if support_candidates:
        strongest_support = min([p for _, p in support_candidates])
        support_touch = count_touch_tests(df_60, strongest_support, tolerance=0.015, window=60)
        
        print(f"\n  【支撑位分析】")
        print(f"  支撑位价格: {strongest_support:.2f}")
        print(f"  触碰次数: {support_touch['touch_count']} 次")
        print(f"  反弹次数: {support_touch['bounce_count']} 次")
        print(f"  触碰频率: {support_touch['touch_rate']:.1%}")
        print(f"  反弹成功率: {support_touch['bounce_rate']:.1%}")
        
        if support_touch['touch_count'] >= 2 and support_touch['bounce_rate'] > 0.5:
            print(f"  ✅ 有效性: 高 (多次测试并反弹)")
        elif support_touch['touch_count'] >= 2:
            print(f"  ⚠️ 有效性: 中 (多次测试)")
        else:
            print(f"  ❌ 有效性: 低 (测试次数不足)")
    
    # 统计最强压力位的触碰次数
    if resistance_candidates:
        strongest_resistance = max([p for _, p in resistance_candidates])
        resistance_touch = count_touch_tests(df_60, strongest_resistance, tolerance=0.015, window=60)
        
        print(f"\n  【压力位分析】")
        print(f"  压力位价格: {strongest_resistance:.2f}")
        print(f"  触碰次数: {resistance_touch['touch_count']} 次")
        print(f"  回落次数: {resistance_touch['bounce_count']} 次")
        print(f"  触碰频率: {resistance_touch['touch_rate']:.1%}")
        print(f"  回落成功率: {resistance_touch['bounce_rate']:.1%}")
        
        if resistance_touch['touch_count'] >= 2 and resistance_touch['bounce_rate'] > 0.5:
            print(f"  ✅ 有效性: 高 (多次测试并回落)")
        elif resistance_touch['touch_count'] >= 2:
            print(f"  ⚠️ 有效性: 中 (多次测试)")
        else:
            print(f"  ❌ 有效性: 低 (测试次数不足)")

print("\n" + "="*70)
print("优化3: 形态结构自动识别")
print("="*70)

def detect_patterns(df):
    """
    识别常见K线形态
    """
    patterns = []
    
    # 需要至少20根K线
    if len(df) < 20:
        return patterns
    
    recent = df.tail(20).copy()
    
    # 1. W底形态检测
    # 找两个低点，中间有反弹
    lows = recent['low'].values
    for i in range(5, len(recent)-5):
        # 第一个低点
        if lows[i] == min(lows[i-3:i+4]):
            first_low = lows[i]
            # 找第二个低点 (在之后)
            for j in range(i+5, len(recent)-3):
                if lows[j] == min(lows[j-3:j+4]):
                    second_low = lows[j]
                    # 检查中间是否有反弹 (反弹幅度>3%)
                    mid_high = max(recent['high'].iloc[i:j])
                    if mid_high > first_low * 1.03 and abs(second_low - first_low) / first_low < 0.03:
                        patterns.append({
                            'type': 'W底',
                            'start_idx': i,
                            'end_idx': j,
                            'first_low': first_low,
                            'second_low': second_low,
                            'neckline': mid_high,
                            'confidence': '中' if abs(second_low - first_low) / first_low < 0.02 else '低'
                        })
    
    # 2. 头肩底形态检测 (简化版)
    # 找三个低点，中间最低
    for i in range(3, len(recent)-6):
        left_shoulder = lows[i]
        head = lows[i+2] if i+2 < len(lows) else lows[i]
        right_shoulder = lows[i+4] if i+4 < len(lows) else lows[i]
        
        if head < left_shoulder and head < right_shoulder:
            if abs(left_shoulder - right_shoulder) / left_shoulder < 0.05:
                patterns.append({
                    'type': '头肩底',
                    'left_shoulder': left_shoulder,
                    'head': head,
                    'right_shoulder': right_shoulder,
                    'confidence': '中'
                })
    
    # 3. M顶形态检测 (与W底相反)
    highs = recent['high'].values
    for i in range(5, len(recent)-5):
        if highs[i] == max(highs[i-3:i+4]):
            first_high = highs[i]
            for j in range(i+5, len(recent)-3):
                if highs[j] == max(highs[j-3:j+4]):
                    second_high = highs[j]
                    mid_low = min(recent['low'].iloc[i:j])
                    if mid_low < first_high * 0.97 and abs(second_high - first_high) / first_high < 0.03:
                        patterns.append({
                            'type': 'M顶',
                            'start_idx': i,
                            'end_idx': j,
                            'first_high': first_high,
                            'second_high': second_high,
                            'neckline': mid_low,
                            'confidence': '中' if abs(second_high - first_high) / first_high < 0.02 else '低'
                        })
    
    return patterns

# 形态识别
for symbol, info in minute_data.items():
    name = info['name']
    df_60 = info['data']['60min']
    
    print(f"\n📊 {name} ({symbol})")
    print("-"*70)
    
    patterns = detect_patterns(df_60)
    
    if patterns:
        print(f"  识别到 {len(patterns)} 个形态:")
        for p in patterns:
            print(f"    • {p['type']} (可信度: {p.get('confidence', '低')})")
            if 'first_low' in p:
                print(f"      第一低点: {p['first_low']:.2f}, 第二低点: {p['second_low']:.2f}")
            if 'first_high' in p:
                print(f"      第一高点: {p['first_high']:.2f}, 第二高点: {p['second_high']:.2f}")
    else:
        print("  未识别到明显形态")

print("\n" + "="*70)
print("优化4: 深入成交量分析")
print("="*70)

def analyze_volume_profile(df, price_levels=10):
    """
    成交量分布分析 (Volume Profile)
    """
    # 将价格区间分割
    price_min = df['low'].min()
    price_max = df['high'].max()
    price_range = price_max - price_min
    
    bin_size = price_range / price_levels
    
    # 计算每个价格区间的成交量
    volume_profile = {}
    
    for i in range(price_levels):
        bin_low = price_min + i * bin_size
        bin_high = price_min + (i + 1) * bin_size
        
        # 找到在该区间内交易的K线
        mask = (df['low'] <= bin_high) & (df['high'] >= bin_low)
        volume_in_bin = df[mask]['volume'].sum()
        
        volume_profile[f"{bin_low:.2f}-{bin_high:.2f}"] = {
            'low': bin_low,
            'high': bin_high,
            'volume': volume_in_bin,
            'mid_price': (bin_low + bin_high) / 2
        }
    
    # 找到POC (Point of Control - 成交量最大)
    poc_key = max(volume_profile.keys(), key=lambda k: volume_profile[k]['volume'])
    poc = volume_profile[poc_key]
    
    # 计算Value Area (70%成交量区间)
    total_volume = sum([v['volume'] for v in volume_profile.values()])
    target_volume = total_volume * 0.7
    
    # 从POC向两边扩展
    sorted_bins = sorted(volume_profile.items(), key=lambda x: x[1]['mid_price'])
    poc_idx = [i for i, (k, v) in enumerate(sorted_bins) if k == poc_key][0]
    
    included = [poc_idx]
    current_volume = poc['volume']
    
    left_idx = poc_idx - 1
    right_idx = poc_idx + 1
    
    while current_volume < target_volume and (left_idx >= 0 or right_idx < len(sorted_bins)):
        left_vol = sorted_bins[left_idx][1]['volume'] if left_idx >= 0 else 0
        right_vol = sorted_bins[right_idx][1]['volume'] if right_idx < len(sorted_bins) else 0
        
        if left_vol >= right_vol and left_idx >= 0:
            included.append(left_idx)
            current_volume += left_vol
            left_idx -= 1
        elif right_idx < len(sorted_bins):
            included.append(right_idx)
            current_volume += right_vol
            right_idx += 1
        else:
            break
    
    included.sort()
    value_area_low = sorted_bins[included[0]][1]['low']
    value_area_high = sorted_bins[included[-1]][1]['high']
    
    return {
        'poc_price': poc['mid_price'],
        'poc_volume': poc['volume'],
        'value_area_low': value_area_low,
        'value_area_high': value_area_high,
        'value_area_volume': current_volume,
        'volume_profile': volume_profile
    }

# 成交量分析
for symbol, info in minute_data.items():
    name = info['name']
    df_60 = info['data']['60min']
    df_15 = info['data']['15min']
    
    print(f"\n📊 {name} ({symbol})")
    print("-"*70)
    
    # 60分钟成交量分析
    vp_60 = analyze_volume_profile(df_60, price_levels=8)
    
    print(f"\n  【60分钟成交量分布】")
    print(f"  POC (控制点): {vp_60['poc_price']:.2f}")
    print(f"  POC成交量: {vp_60['poc_volume']:,.0f}")
    print(f"  Value Area (70%成交区间): {vp_60['value_area_low']:.2f} - {vp_60['value_area_high']:.2f}")
    
    latest = df_60['close'].iloc[-1]
    if latest >= vp_60['value_area_low'] and latest <= vp_60['value_area_high']:
        print(f"  ✅ 当前价格在Value Area内 (正常波动)")
    elif latest > vp_60['value_area_high']:
        print(f"  🔴 当前价格高于Value Area (突破上行)")
    else:
        print(f"  🔵 当前价格低于Value Area (破位下行)")
    
    # 近期成交量趋势
    recent_volume = df_60['volume'].tail(10).mean()
    previous_volume = df_60['volume'].tail(20).head(10).mean()
    volume_change = (recent_volume - previous_volume) / previous_volume
    
    print(f"\n  【成交量趋势】")
    print(f"  近10期平均成交量: {recent_volume:,.0f}")
    print(f"  前10期平均成交量: {previous_volume:,.0f}")
    print(f"  变化: {volume_change:+.1%}")
    
    if volume_change > 0.2:
        print(f"  📈 成交量明显放大")
    elif volume_change < -0.2:
        print(f"  📉 成交量明显萎缩")
    else:
        print(f"  ➡️ 成交量正常")

print("\n" + "="*70)
print("所有优化完成")
print("="*70)

# 保存完整分析结果
analysis_results = {}
for symbol, info in minute_data.items():
    df_60 = info['data']['60min']
    
    # 汇总所有分析
    analysis_results[symbol] = {
        'name': info['name'],
        'touch_analysis': count_touch_tests(df_60, df_60['low'].tail(40).min(), tolerance=0.015, window=60),
        'patterns': detect_patterns(df_60),
        'volume_profile': analyze_volume_profile(df_60)
    }

with open('/root/.openclaw/workspace/study/advanced_analysis_results.pkl', 'wb') as f:
    pickle.dump(analysis_results, f)

print("\n💾 完整分析结果已保存")
