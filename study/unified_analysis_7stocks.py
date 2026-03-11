#!/root/.openclaw/workspace/venv/bin/python3
"""
7只股票统一预期走势分析
使用优化后的4项技能
"""

import pandas as pd
import numpy as np
from datetime import datetime
import pickle

# 加载数据
with open('/root/.openclaw/workspace/study/all_7stocks_data.pkl', 'rb') as f:
    all_data = pickle.load(f)

print("="*70)
print("7只股票统一预期走势分析")
print("使用优化技能：多周期 + 触碰验证 + 形态识别 + Volume Profile")
print("="*70)
print(f"分析时间: {datetime.now()}")
print("="*70)

# 技能1: 多周期技术指标计算
def calculate_multi_timeframe_indicators(df_day, df_60):
    """计算多周期技术指标"""
    results = {}
    
    # 日线指标 (大趋势)
    if df_day is not None and len(df_day) > 20:
        df_day['ma20'] = df_day['close'].rolling(20).mean()
        df_day['ma60'] = df_day['close'].rolling(60).mean()
        df_day['return'] = df_day['close'].pct_change()
        
        # MACD
        exp1 = df_day['close'].ewm(span=12, adjust=False).mean()
        exp2 = df_day['close'].ewm(span=26, adjust=False).mean()
        df_day['macd'] = exp1 - exp2
        
        # RSI
        delta = df_day['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        df_day['rsi'] = 100 - (100 / (1 + gain / loss))
        
        latest_day = df_day.iloc[-1]
        results['day'] = {
            'close': latest_day['close'],
            'ma20': latest_day['ma20'],
            'ma60': latest_day['ma60'],
            'macd': latest_day['macd'],
            'rsi': latest_day['rsi'],
            'trend': '上涨' if latest_day['close'] > latest_day['ma20'] else '下跌'
        }
    
    # 60分钟指标 (中趋势)
    if df_60 is not None and len(df_60) > 20:
        df_60['ma20'] = df_60['close'].rolling(20).mean()
        df_60['bb_middle'] = df_60['close'].rolling(20).mean()
        bb_std = df_60['close'].rolling(20).std()
        df_60['bb_upper'] = df_60['bb_middle'] + (bb_std * 2)
        df_60['bb_lower'] = df_60['bb_middle'] - (bb_std * 2)
        
        latest_60 = df_60.iloc[-1]
        results['60min'] = {
            'close': latest_60['close'],
            'ma20': latest_60['ma20'],
            'bb_upper': latest_60['bb_upper'],
            'bb_lower': latest_60['bb_lower'],
            'high_40': df_60['high'].tail(40).max(),
            'low_40': df_60['low'].tail(40).min()
        }
    
    return results

# 技能2: 触碰次数统计
def count_touch_points(df, level, tolerance=0.015, lookback=60):
    """统计价格水平触碰次数"""
    if df is None or len(df) < lookback:
        return {'count': 0, 'bounce_rate': 0}
    
    recent = df.tail(lookback)
    lower = level * (1 - tolerance)
    upper = level * (1 + tolerance)
    
    touches = 0
    bounces = 0
    
    for i in range(len(recent) - 1):
        row = recent.iloc[i]
        next_row = recent.iloc[i + 1]
        
        # 检查是否触碰
        if row['low'] <= upper and row['high'] >= lower:
            touches += 1
            # 检查是否反弹 (下一根反向)
            if (row['close'] < level and next_row['close'] > row['close']) or \
               (row['close'] > level and next_row['close'] < row['close']):
                bounces += 1
    
    return {
        'count': touches,
        'bounce_rate': bounces / touches if touches > 0 else 0
    }

# 技能3: 形态识别
def detect_price_patterns(df):
    """识别价格形态"""
    if df is None or len(df) < 20:
        return []
    
    patterns = []
    recent = df.tail(20)
    
    # 找局部高低点
    highs = recent['high'].values
    lows = recent['low'].values
    
    # W底检测 (简化)
    for i in range(3, len(recent) - 6):
        if lows[i] == min(lows[i-2:i+3]):  # 局部低点
            for j in range(i + 3, len(recent) - 3):
                if lows[j] == min(lows[j-2:j+3]):  # 第二个低点
                    if abs(lows[j] - lows[i]) / lows[i] < 0.03:  # 相近
                        mid_high = max(highs[i:j])
                        if mid_high > lows[i] * 1.02:  # 有反弹
                            patterns.append({
                                'type': 'W底',
                                'strength': '强' if abs(lows[j] - lows[i]) / lows[i] < 0.01 else '中'
                            })
                            break
    
    # M顶检测
    for i in range(3, len(recent) - 6):
        if highs[i] == max(highs[i-2:i+3]):
            for j in range(i + 3, len(recent) - 3):
                if highs[j] == max(highs[j-2:j+3]):
                    if abs(highs[j] - highs[i]) / highs[i] < 0.03:
                        mid_low = min(lows[i:j])
                        if mid_low < highs[i] * 0.98:
                            patterns.append({
                                'type': 'M顶',
                                'strength': '强' if abs(highs[j] - highs[i]) / highs[i] < 0.01 else '中'
                            })
                            break
    
    return patterns

# 技能4: Volume Profile分析
def volume_profile_analysis(df, levels=8):
    """成交量分布分析"""
    if df is None or len(df) < 20:
        return {}
    
    price_min = df['low'].min()
    price_max = df['high'].max()
    bin_size = (price_max - price_min) / levels
    
    volume_dist = {}
    for i in range(levels):
        bin_low = price_min + i * bin_size
        bin_high = price_min + (i + 1) * bin_size
        mask = (df['low'] <= bin_high) & (df['high'] >= bin_low)
        vol = df[mask]['volume'].sum()
        volume_dist[f"{bin_low:.2f}-{bin_high:.2f}"] = {
            'mid': (bin_low + bin_high) / 2,
            'volume': vol
        }
    
    # 找POC
    poc_key = max(volume_dist.keys(), key=lambda k: volume_dist[k]['volume'])
    poc = volume_dist[poc_key]
    
    return {
        'poc_price': poc['mid'],
        'poc_volume': poc['volume'],
        'total_volume': sum([v['volume'] for v in volume_dist.values()])
    }

# 统一分析所有股票
results = []

for symbol, data in all_data.items():
    name = data['name']
    df_day = data['df_day']
    df_60 = data['df_60']
    
    print(f"\n{'='*70}")
    print(f"📊 {name} ({symbol})")
    print(f"{'='*70}")
    
    # 技能1: 多周期分析
    mt_indicators = calculate_multi_timeframe_indicators(df_day, df_60)
    
    if not mt_indicators:
        print("  ❌ 指标计算失败")
        continue
    
    latest_price = mt_indicators.get('60min', {}).get('close', 0)
    print(f"最新价格: {latest_price:.2f}")
    
    # 确定支撑压力位
    if '60min' in mt_indicators:
        support = mt_indicators['60min']['low_40']
        resistance = mt_indicators['60min']['high_40']
        bb_lower = mt_indicators['60min']['bb_lower']
        bb_upper = mt_indicators['60min']['bb_upper']
    else:
        support = df_60['low'].tail(40).min() if df_60 is not None else 0
        resistance = df_60['high'].tail(40).max() if df_60 is not None else 0
        bb_lower = support
        bb_upper = resistance
    
    print(f"\n【技能1: 多周期支撑压力】")
    print(f"  强支撑: {support:.2f}")
    print(f"  强压力: {resistance:.2f}")
    print(f"  布林带下轨: {bb_lower:.2f}")
    print(f"  布林带上轨: {bb_upper:.2f}")
    
    # 技能2: 触碰验证
    print(f"\n【技能2: 触碰次数验证】")
    touch_support = count_touch_points(df_60, support, tolerance=0.02)
    touch_resistance = count_touch_points(df_60, resistance, tolerance=0.02)
    
    print(f"  支撑位 {support:.2f}:")
    print(f"    触碰: {touch_support['count']} 次, 反弹率: {touch_support['bounce_rate']:.1%}")
    
    print(f"  压力位 {resistance:.2f}:")
    print(f"    触碰: {touch_resistance['count']} 次, 回落率: {touch_resistance['bounce_rate']:.1%}")
    
    # 技能3: 形态识别
    print(f"\n【技能3: 形态结构识别】")
    patterns = detect_price_patterns(df_60)
    
    if patterns:
        for p in patterns[-2:]:  # 最近2个
            print(f"  • {p['type']} (强度: {p['strength']})")
    else:
        print(f"  近期无明显形态")
    
    # 技能4: Volume Profile
    print(f"\n【技能4: Volume Profile分析】")
    vp = volume_profile_analysis(df_60)
    
    if vp:
        print(f"  POC (控制点): {vp['poc_price']:.2f}")
        print(f"  POC占比: {vp['poc_volume'] / vp['total_volume']:.1%}")
        
        # 当前价格与POC关系
        if abs(latest_price - vp['poc_price']) / vp['poc_price'] < 0.03:
            poc_signal = "✅ 接近POC (强支撑/压力)"
        elif latest_price > vp['poc_price']:
            poc_signal = "📈 高于POC"
        else:
            poc_signal = "📉 低于POC"
        print(f"  {poc_signal}")
    
    # 综合评分
    print(f"\n【综合评分与预期走势】")
    
    score = 0
    factors = []
    
    # 日线趋势
    if 'day' in mt_indicators:
        day_data = mt_indicators['day']
        if day_data['trend'] == '上涨':
            score += 1
            factors.append("日线上涨趋势(+1)")
        else:
            score -= 1
            factors.append("日线下跌趋势(-1)")
        
        if day_data['rsi'] > 70:
            score -= 0.5
            factors.append("RSI超买(-0.5)")
        elif day_data['rsi'] < 30:
            score += 0.5
            factors.append("RSI超卖(+0.5)")
    
    # 支撑有效性
    if touch_support['count'] >= 3 and touch_support['bounce_rate'] >= 0.5:
        score += 1
        factors.append("强支撑验证(+1)")
    elif touch_support['count'] >= 2:
        score += 0.5
        factors.append("有支撑测试(+0.5)")
    
    # 形态
    if patterns:
        if any('W底' in p['type'] for p in patterns):
            score += 1
            factors.append("W底形态(+1)")
        if any('M顶' in p['type'] for p in patterns):
            score -= 1
            factors.append("M顶形态(-1)")
    
    # 位置
    range_size = resistance - support
    if range_size > 0:
        position = (latest_price - support) / range_size
        if position < 0.3:
            score += 0.5
            factors.append("低位区间(+0.5)")
        elif position > 0.7:
            score -= 0.5
            factors.append("高位区间(-0.5)")
    
    # 预期走势判定
    if score >= 2:
        outlook = "🚀 强烈看涨"
        outlook_code = 2
        expected_return = "+15~25%"
    elif score >= 1:
        outlook = "📈 看涨"
        outlook_code = 1
        expected_return = "+5~15%"
    elif score >= -1:
        outlook = "➡️ 震荡"
        outlook_code = 0
        expected_return = "-5~5%"
    elif score >= -2:
        outlook = "📉 看跌"
        outlook_code = -1
        expected_return = "-15~-5%"
    else:
        outlook = "🔻 强烈看跌"
        outlook_code = -2
        expected_return = "-25~-15%"
    
    print(f"  综合评分: {score:.1f}")
    print(f"  评分因素: {', '.join(factors)}")
    print(f"  预期走势: {outlook}")
    print(f"  预期收益(20日): {expected_return}")
    
    # 保存结果
    results.append({
        'symbol': symbol,
        'name': name,
        'price': latest_price,
        'support': support,
        'resistance': resistance,
        'touch_count': touch_support['count'],
        'bounce_rate': touch_support['bounce_rate'],
        'patterns': [p['type'] for p in patterns],
        'poc': vp.get('poc_price', 0),
        'score': score,
        'outlook': outlook,
        'outlook_code': outlook_code,
        'expected_return': expected_return
    })

# 排序
results.sort(key=lambda x: x['score'], reverse=True)

print("\n" + "="*70)
print("7只股票预期走势排名")
print("="*70)

for i, r in enumerate(results, 1):
    rank_emoji = '🥇' if i == 1 else '🥈' if i == 2 else '🥉' if i == 3 else f'{i}.'
    print(f"\n{rank_emoji} {r['name']} ({r['symbol']})")
    print(f"   价格: {r['price']:.2f} | 支撑: {r['support']:.2f} | 压力: {r['resistance']:.2f}")
    print(f"   触碰验证: {r['touch_count']}次/{r['bounce_rate']:.0%}反弹")
    print(f"   形态: {', '.join(r['patterns']) if r['patterns'] else '无'}")
    print(f"   POC: {r['poc']:.2f}")
    print(f"   评分: {r['score']:.1f} | {r['outlook']} | 预期收益: {r['expected_return']}")

# 保存结果
with open('/root/.openclaw/workspace/study/unified_analysis_7stocks.pkl', 'wb') as f:
    pickle.dump(results, f)

print("\n" + "="*70)
print("✅ 统一分析完成，结果已保存")
print("="*70)
