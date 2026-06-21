#!/root/.openclaw/workspace/venv/bin/python3
"""
缠论分析 v4.1 - 完整升级版（技能文档同步升级）

v4.1 核心升级（8大优化）：
1. 主涨段雏形判定（三档：正式/雏形/X段）— 结构优先于MACD
2. 套娃传导链分析（N+2→N→N-2 级别嵌套）
3. 三路径情景推演（理想/震荡/风险，震荡是正常选项）
4. 顶背离监控（主涨段末端风险）
5. 盘中结构描述（上午/下午/尾盘关键动作）
6. 历史段数分析（大周期如"3927以来第五段"）
7. 预警/确认双体系（操作线+战略线）
8. 分时段关键支撑（保留v4.1已有）

来源：2026-06-17 对比分析（原文 vs v4.0）经验教训固化
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from longport.openapi import Config, QuoteContext, Period, AdjustType

# =====================================================
# 数据获取
# =====================================================

def fetch_longbridge(symbol, period, count):
    """从长桥获取K线"""
    config = Config.from_env()
    ctx = QuoteContext(config)
    
    period_map = {
        '1m': Period.Min_1, '2m': Period.Min_2, '3m': Period.Min_3,
        '5m': Period.Min_5, '10m': Period.Min_10, '15m': Period.Min_15,
        '20m': Period.Min_20, '30m': Period.Min_30, '45m': Period.Min_45,
        '60m': Period.Min_60, '120m': Period.Min_120, '180m': Period.Min_180,
        '240m': Period.Min_240, '1d': Period.Day
    }
    p = period_map.get(period, Period.Day)
    
    resp = ctx.candlesticks(symbol, p, count, AdjustType.NoAdjust)
    
    data = []
    for c in resp:
        data.append({
            'Date': pd.to_datetime(c.timestamp),
            'Open': c.open, 'High': c.high, 'Low': c.low,
            'Close': c.close, 'Volume': c.volume
        })
    return pd.DataFrame(data).sort_values('Date').reset_index(drop=True)

# =====================================================
# 级别合成
# =====================================================

def synthesize_kline(df, n):
    df = df.copy()
    df['Group'] = df.index // n
    return df.groupby('Group').agg({
        'Date': 'last', 'Open': 'first', 'High': 'max',
        'Low': 'min', 'Close': 'last', 'Volume': 'sum'
    }).reset_index(drop=True)

# =====================================================
# 指标计算
# =====================================================

def ma(df, w): return df['Close'].rolling(window=w).mean()

def boll(df, w=20):
    """布林带指标"""
    m = df['Close'].rolling(window=w).mean()
    s = df['Close'].rolling(window=w).std()
    return {'upper': m + s*2, 'middle': m, 'lower': m - s*2}

def macd(df, f=12, s=26, sig=9):
    ef = df['Close'].ewm(span=f, adjust=False).mean()
    es = df['Close'].ewm(span=s, adjust=False).mean()
    dif = ef - es
    dea = dif.ewm(span=sig, adjust=False).mean()
    return {'dif': dif, 'dea': dea, 'macd': (dif - dea)*2}

# =====================================================
# v4.1: 段数分解（分型→笔→线段）
# =====================================================

def find_local_extrema(df, window=5):
    """找局部高点和低点（分型）"""
    highs = df['High'].values
    lows = df['Low'].values
    n = len(df)
    
    peaks = []
    for i in range(window, n - window):
        is_top = True
        for j in range(1, window + 1):
            if highs[i] < highs[i-j] or highs[i] < highs[i+j]:
                is_top = False
                break
        if is_top:
            peaks.append((i, 'top', highs[i], df['Date'].iloc[i]))
            continue
        
        is_bottom = True
        for j in range(1, window + 1):
            if lows[i] > lows[i-j] or lows[i] > lows[i+j]:
                is_bottom = False
                break
        if is_bottom:
            peaks.append((i, 'bottom', lows[i], df['Date'].iloc[i]))
    
    return peaks

def merge_extrema(peaks, min_distance=5):
    """合并距离太近的分型"""
    if not peaks:
        return []
    merged = [peaks[0]]
    for p in peaks[1:]:
        last = merged[-1]
        if p[1] == last[1] and p[0] - last[0] < min_distance:
            if p[1] == 'top' and p[2] > last[2]:
                merged[-1] = p
            elif p[1] == 'bottom' and p[2] < last[2]:
                merged[-1] = p
        else:
            merged.append(p)
    return merged

def count_segments(df, level_name='15F'):
    """段数统计"""
    if len(df) < 10:
        return {'segment_count': 0, 'current': 'unknown', 'description': '数据不足'}
    
    window_map = {'3F': 3, '5F': 5, '15F': 5, '30F': 5, '60F': 3, '120F': 3}
    window = window_map.get(level_name, 5)
    
    peaks = find_local_extrema(df, window=window)
    peaks = merge_extrema(peaks, min_distance=window)
    
    if not peaks:
        return {'segment_count': 0, 'current': 'unknown', 'description': '未找到分型'}
    
    valid_peaks = []
    for p in peaks:
        if not valid_peaks or p[1] != valid_peaks[-1][1]:
            valid_peaks.append(p)
    
    segment_count = len(valid_peaks) - 1
    
    last_peak = valid_peaks[-1]
    if last_peak[1] == 'top':
        current = f'第{segment_count + 1}段up运行中（从{valid_peaks[-2][2]:.2f}到{last_peak[2]:.2f}）' if len(valid_peaks) >= 2 else 'up运行中'
    else:
        current = f'第{segment_count + 1}段down运行中（从{valid_peaks[-2][2]:.2f}到{last_peak[2]:.2f}）' if len(valid_peaks) >= 2 else 'down运行中'
    
    if segment_count <= 2:
        structure = '简单结构（1-2段，未形成中枢）'
    elif segment_count <= 4:
        structure = '标准盘整（3-4段，1个中枢）'
    elif segment_count <= 6:
        structure = '标准趋势（5-6段，2个中枢）'
    else:
        structure = f'复杂结构（{segment_count}段，中枢扩展或更大级别）'
    
    recent_peaks = valid_peaks[-6:] if len(valid_peaks) >= 6 else valid_peaks
    peak_str = ' → '.join([f"{'顶' if p[1]=='top' else '底'}{p[2]:.2f}" for p in recent_peaks])
    
    return {
        'segment_count': segment_count,
        'current': current,
        'structure': structure,
        'peaks': valid_peaks,
        'peak_str': peak_str,
        'description': f'{segment_count}段 | {current} | {structure}'
    }

# =====================================================
# v4.1: 历史段数分析（大周期）
# =====================================================

def analyze_historical_segments(df, level_name='30F', major_low=None):
    """
    分析大周期历史段数结构（如"3927以来第五段上涨"）
    major_low: 主要低点，如3927
    """
    if len(df) < 200:
        return {'description': '数据不足200根，无法做历史段数分析'}
    
    window_map = {'30F': 5, '60F': 5, '120F': 3, '日线': 3, '双日': 3}
    window = window_map.get(level_name, 5)
    
    peaks = find_local_extrema(df, window=window)
    peaks = merge_extrema(peaks, min_distance=window)
    
    valid_peaks = []
    for p in peaks:
        if not valid_peaks or p[1] != valid_peaks[-1][1]:
            valid_peaks.append(p)
    
    if len(valid_peaks) < 3:
        return {'description': '未找到足够分型'}
    
    # 找从major_low开始的段数
    start_idx = 0
    if major_low:
        for i, p in enumerate(valid_peaks):
            if p[1] == 'bottom' and p[2] <= major_low * 1.05:  # 允许5%误差
                start_idx = i
                break
    
    recent_peaks = valid_peaks[start_idx:]
    segment_count = len(recent_peaks) - 1
    
    # 判断当前是第几段
    current_segment = segment_count
    current_direction = 'up' if recent_peaks[-1][1] == 'top' else 'down'
    
    # 判断结构类型
    if current_segment <= 2:
        structure_type = '初期上涨（1-2段）'
    elif current_segment <= 4:
        structure_type = '标准盘整结构（3-4段）'
    elif current_segment <= 6:
        structure_type = '标准趋势结构（5-6段，2个中枢）'
    elif current_segment <= 8:
        structure_type = '趋势延续（7-8段，中枢扩展）'
    else:
        structure_type = f'复杂扩展（{current_segment}段+）'
    
    # 末端风险提示
    risk = ''
    if current_segment >= 5 and current_direction == 'up':
        risk = '⚠️ 处于第五段上涨，注意末端顶背离风险'
    
    return {
        'major_low': major_low,
        'segment_count': current_segment,
        'current_direction': current_direction,
        'structure_type': structure_type,
        'risk': risk,
        'description': f'{major_low}以来第{current_segment}段{current_direction} | {structure_type} {risk}'
    }

# =====================================================
# v4.1: 主涨段判定（三档：正式/雏形/X段）
# =====================================================

def analyze_main_trend_segment_v41(df, level_name='30F', segment_data=None):
    """
    v4.1 主涨段三档判定：
    - 正式：价格>55线 + MACD>0 + 结构完整
    - 雏形：价格>55线 + 结构完整 + 回踩确认 + MACD暂时<0
    - X段：价格>55线 + MACD<0 + 结构不完整/被破坏
    """
    if len(df) < 55:
        return {'level': level_name, 'grade': 'unknown', 'description': '数据不足'}
    
    p = float(df['Close'].iloc[-1])
    m55 = float(ma(df, 55).iloc[-1])
    md = macd(df)['macd'].iloc[-1]
    
    # 获取中轨
    b = boll(df, 20)
    middle = float(b['middle'].iloc[-1])
    
    # 结构检查（简化版：是否有段数结构）
    has_structure = segment_data is not None and segment_data.get('segment_count', 0) >= 3
    
    # 回踩确认：近期是否回踩过中轨/55线后反弹
    recent_low = df['Low'].tail(20).min()
    pullback_confirmed = recent_low <= m55 * 1.01 or recent_low <= middle * 1.01  # 允许1%误差
    
    # 判断结构完整性
    structure_intact = True
    if segment_data and segment_data.get('segment_count', 0) > 0:
        current = segment_data.get('current', '')
        if 'down运行中' in current and segment_data.get('segment_count', 0) >= 3:
            # 检查是否破坏了之前的结构
            recent_peaks = segment_data.get('peaks', [])
            if len(recent_peaks) >= 3:
                # 最新低点是否低于前低
                latest_low = float(recent_peaks[-1][2]) if recent_peaks[-1][1] == 'bottom' else (float(recent_peaks[-2][2]) if len(recent_peaks) >= 2 else float('inf'))
                prev_low = float(recent_peaks[-3][2]) if len(recent_peaks) >= 3 and recent_peaks[-3][1] == 'bottom' else float('inf')
                if prev_low != float('inf') and latest_low < prev_low * 0.99:  # 新低
                    structure_intact = False
    
    # 三档判定
    if p > m55 and md > 0:
        # 有结构数据时检查结构，无结构数据时默认认为结构完整（基于价格和MACD）
        if has_structure:
            grade = '正式'
            desc = '主涨段（正式）— 价格>55线 + MACD>0 + 结构完整'
        else:
            grade = '正式'
            desc = '主涨段（正式）— 价格>55线 + MACD>0'
    elif p > m55 and has_structure and pullback_confirmed and md < 0:
        grade = '雏形'
        desc = '主涨段雏形 — 价格>55线 + 结构完整 + 回踩确认 + MACD暂时<0（等待转正）'
    elif p > m55 and md < 0 and not structure_intact and has_structure:
        grade = 'x段'
        desc = '55线上方X段 — 结构被破坏，MACD<0'
    elif p > m55 and md < 0:
        # 无结构数据或结构未确认时，给雏形（等待确认）
        if has_structure:
            grade = '雏形'
            desc = '主涨段雏形（结构确认中）— 价格>55线 + 结构完整 + MACD暂时<0'
        else:
            grade = '雏形'
            desc = '主涨段雏形（无段数数据，基于价格>55线 + MACD暂时<0）'
    elif p < m55 and md < 0:
        grade = '主跌段'
        desc = '主跌段'
    elif p < m55 and md > 0:
        grade = 'x段下方'
        desc = '55线下方X段'
    else:
        grade = '中性'
        desc = '中性'
    
    return {
        'level': level_name,
        'grade': grade,
        'price': p,
        'ma55': m55,
        'macd': md,
        'middle': middle,
        'has_structure': has_structure,
        'pullback_confirmed': pullback_confirmed,
        'structure_intact': structure_intact,
        'description': desc
    }

# =====================================================
# v4.1: 顶背离监控
# =====================================================

def check_top_divergence(df, level_name='30F', segment_data=None):
    """
    检查顶背离：价格创新高但MACD不创新高
    """
    if len(df) < 30:
        return {'has_divergence': False, 'description': '数据不足'}
    
    md = macd(df)
    prices = df['Close'].values
    macd_values = md['macd'].values
    
    # 找最近的高点
    recent_prices = prices[-20:]
    recent_macd = macd_values[-20:]
    
    price_high_idx = np.argmax(recent_prices)
    price_high = recent_prices[price_high_idx]
    
    # 找之前的MACD高点（往前推10-20根）
    if len(macd_values) >= 40:
        prev_macd = macd_values[-40:-20]
        prev_macd_high = np.max(prev_macd)
    else:
        prev_macd_high = np.max(macd_values[:-20]) if len(macd_values) > 20 else 0
    
    current_macd_at_high = recent_macd[price_high_idx]
    
    # 顶背离条件：价格创新高 且 MACD不创新高（当前MACD < 前高MACD的80%）
    # 简化判断：当前价格接近近期高点，但MACD柱体收敛
    recent_high = float(df['High'].tail(10).max())
    latest_price = float(prices[-1])
    
    macd_recent = [float(x) for x in md['macd'].tail(10).values]
    macd_older = [float(x) for x in md['macd'].tail(20).head(10).values]
    
    price_near_high = latest_price >= recent_high * 0.995  # 接近前高
    macd_weaker = max(macd_recent) < max(macd_older) * 0.8 if len(macd_older) > 0 else False
    
    # 结构末端判断（第五段或更高）
    at_end = False
    if segment_data and segment_data.get('segment_count', 0) >= 5:
        at_end = True
    
    is_divergence = price_near_high and macd_weaker and at_end
    
    if is_divergence:
        return {
            'has_divergence': True,
            'price_near_high': price_near_high,
            'macd_weaker': macd_weaker,
            'at_end': at_end,
            'description': f'⚠️ {level_name}顶背离预警！价格接近前高{recent_high:.2f}但MACD柱体减弱，且处于第{segment_data.get("segment_count", "?")}段末端',
            'risk_level': 'high' if at_end else 'medium'
        }
    elif price_near_high and macd_weaker:
        return {
            'has_divergence': False,
            'warning': True,
            'description': f'{level_name}价格接近前高但MACD减弱，需警惕（非末端段）',
            'risk_level': 'medium'
        }
    else:
        return {
            'has_divergence': False,
            'description': f'{level_name}无顶背离信号'
        }

# =====================================================
# v4.1: 套娃传导链分析
# =====================================================

def analyze_nesting_chain(levels_data):
    """
    分析套娃传导链：N级别主涨段套住N-2级别主涨段
    典型链：30F → 120F → 双日
    
    levels_data: dict of {level_name: {'grade': '正式'/'雏形'/'x段', 'price': p, 'ma55': m, 'macd': mc}}
    """
    chain = []
    
    # 检查各级别状态
    for level in ['30F', '60F', '120F', '日线', '双日']:
        if level in levels_data:
            d = levels_data[level]
            grade = d.get('grade', 'unknown')
            chain.append(f'{level}:{grade}')
    
    # 判断套娃状态
    nesting_status = 'unknown'
    
    # 30F→120F套娃
    has_30f = '30F' in levels_data
    has_120f = '120F' in levels_data
    
    if has_30f and has_120f:
        g30 = levels_data['30F'].get('grade', '')
        g120 = levels_data['120F'].get('grade', '')
        
        if g30 in ['正式', '雏形'] and g120 in ['正式', '雏形']:
            nesting_status = '完整（30F→120F套娃中）'
        elif g30 in ['正式', '雏形'] and g120 in ['x段', 'x段上方']:
            nesting_status = '预警（30F套娃120F断裂）'
        elif g30 in ['x段', '主跌段'] and g120 in ['正式', '雏形']:
            nesting_status = '传导中（30F问题向120F传导）'
        else:
            nesting_status = '断裂'
    
    # 120F→双日套娃
    has_bid = '双日' in levels_data
    if has_120f and has_bid:
        g120 = levels_data['120F'].get('grade', '')
        gbid = levels_data['双日'].get('grade', '')
        
        if g120 in ['正式', '雏形'] and gbid in ['正式', '雏形', 'x段上方']:
            nesting_status += ' | 120F→双日套娃中'
        elif g120 in ['正式', '雏形'] and gbid in ['主跌段', 'x段']:
            nesting_status += ' | 120F→双日套娃预警（双日结构领先MACD）'
    
    # 套娃维持条件
    maintain_conditions = []
    if '120F' in levels_data:
        p120 = levels_data['120F'].get('price', 0)
        m55_120 = levels_data['120F'].get('ma55', 0)
        if p120 > m55_120:
            maintain_conditions.append(f'120F价格{p120:.2f}>MA55({m55_120:.2f})')
    
    if '30F' in levels_data:
        p30 = levels_data['30F'].get('price', 0)
        m30 = levels_data['30F'].get('middle', 0)
        if p30 > m30:
            maintain_conditions.append(f'30F价格{p30:.2f}>中轨({m30:.2f})')
    
    # 断裂触发条件
    break_triggers = []
    if '5F' in levels_data:
        p5 = levels_data['5F'].get('price', 0)
        m5_middle = levels_data.get('5F', {}).get('middle', 0)
        if p5 < m5_middle:
            break_triggers.append('5F中轨跌破')
    
    return {
        'chain': ' → '.join(chain),
        'status': nesting_status,
        'maintain_conditions': maintain_conditions,
        'break_triggers': break_triggers,
        'description': f'套娃状态: {nesting_status} | 维持条件: {"; ".join(maintain_conditions) if maintain_conditions else "无"} | 断裂触发: {", ".join(break_triggers) if break_triggers else "无"}'
    }

# =====================================================
# v4.1: 三路径情景推演
# =====================================================

def analyze_three_paths(levels_data, time_window_status, segment_30f=None):
    """
    三路径情景推演：
    A. 理想路径：快速突破，套娃完整
    B. 震荡路径：横盘震荡，时间换空间
    C. 风险路径：跌破关键位，套娃断裂
    """
    paths = {}
    
    # 获取关键数据
    p = levels_data.get('30F', {}).get('price', 0)
    m55_30f = levels_data.get('30F', {}).get('ma55', 0)
    m55_5f = levels_data.get('5F', {}).get('ma55', 0)
    middle_5f = levels_data.get('5F', {}).get('middle', 0)
    m55_120f = levels_data.get('120F', {}).get('ma55', 0)
    
    # 路径A：理想
    paths['A'] = {
        'name': '理想路径',
        'condition': '高开高走，30F MACD转正，突破4115',
        'movement': '30F第五段持续上涨，斜率加大',
        'result': '双日金叉+明显斜率和幅度',
        'operation': '持仓/加仓',
        'probability': '中（需量能配合）'
    }
    
    # 路径B：震荡（v4.1核心新增：正常选项）
    paths['B'] = {
        'name': '震荡路径（正常选项）',
        'condition': f'{m55_5f:.0f}-{m55_120f:.0f}区间横盘，不突破也不深跌',
        'movement': '用震荡换取时间，等待双日MACD金叉',
        'result': '时间换空间，金叉后突破',
        'operation': '持仓，高抛低吸',
        'probability': '高（市场常选此路径）'
    }
    
    # 路径C：风险
    paths['C'] = {
        'name': '风险路径',
        'condition': f'跌破5F中轨({middle_5f:.2f}) + 跌破5F55线({m55_5f:.2f})',
        'movement': '传导链启动，回踩30F55线(4044)',
        'result': '30F主涨段结束，套娃断裂',
        'operation': '减仓→清仓',
        'probability': '中（需关注消息面）'
    }
    
    return paths

# =====================================================
# v4.1: 预警/确认双体系
# =====================================================

def analyze_warning_confirm(levels_data):
    """
    预警/确认双体系：
    - 操作预警线（减仓）：5F中轨、5F55线、15F55线、30F中轨
    - 战略确认线（清仓）：30F55线、120F55线、日线55线、联合支撑区
    """
    warnings = []
    confirms = []
    
    p = levels_data.get('5F', {}).get('price', 0)
    
    # 操作预警线
    if '5F' in levels_data:
        m5_middle = levels_data['5F'].get('middle', 0)
        m5_55 = levels_data['5F'].get('ma55', 0)
        if p < m5_middle:
            warnings.append(f'🔴 5F中轨跌破({m5_middle:.2f}) → 减仓1/3')
        if p < m5_55:
            warnings.append(f'🔴 5F55线跌破({m5_55:.2f}) → 再减仓1/3')
    
    if '15F' in levels_data:
        m15_55 = levels_data['15F'].get('ma55', 0)
        if p < m15_55:
            warnings.append(f'🟠 15F55线跌破({m15_55:.2f}) → 再减仓1/3')
    
    if '30F' in levels_data:
        m30_middle = levels_data['30F'].get('middle', 0)
        if p < m30_middle:
            warnings.append(f'🟠 30F中轨跌破({m30_middle:.2f}) → 减仓1/2')
    
    # 战略确认线
    if '30F' in levels_data:
        p30 = levels_data['30F'].get('price', 0)
        m30_55 = levels_data['30F'].get('ma55', 0)
        if p30 < m30_55:
            confirms.append(f'🔴 30F55线跌破({m30_55:.2f}) → 战略确认，大幅减仓')
    
    if '120F' in levels_data:
        p120 = levels_data['120F'].get('price', 0)
        m120_55 = levels_data['120F'].get('ma55', 0)
        if p120 < m120_55:
            confirms.append(f'🔴 120F55线跌破({m120_55:.2f}) → 120F极强解除，清仓')
    
    if '日线' in levels_data:
        p_daily = levels_data['日线'].get('price', 0)
        m_daily = levels_data['日线'].get('ma55', 0)
        if p_daily < m_daily:
            confirms.append(f'🔴 日线55线跌破({m_daily:.2f}) → 中期转空，清仓')
    
    return {
        'warnings': warnings,
        'confirms': confirms,
        'warning_levels': [w.split(' ')[1] for w in warnings] if warnings else [],
        'confirm_levels': [c.split(' ')[1] for c in confirms] if confirms else [],
        'description': f'预警: {len(warnings)}个 | 确认: {len(confirms)}个'
    }

# =====================================================
# v4.1: 盘中结构分析（日内走势）
# =====================================================

def analyze_intraday_structure(df_1m, df_5m, levels_data):
    """
    基于1F/5F数据做日内结构分析
    """
    if len(df_1m) < 240 or len(df_5m) < 48:
        return {'description': '1F/5F数据不足，无法做日内结构分析'}
    
    # 提取今日数据
    today = df_1m['Date'].iloc[-1].date()
    today_1m = df_1m[df_1m['Date'].dt.date == today]
    today_5m = df_5m[df_5m['Date'].dt.date == today]
    
    if len(today_1m) < 100:
        return {'description': '今日数据不足，可能非交易日或数据延迟'}
    
    # 分时结构
    morning_end = pd.Timestamp(f'{today} 11:30:00')
    afternoon_start = pd.Timestamp(f'{today} 13:00:00')
    
    morning_1m = today_1m[today_1m['Date'] <= morning_end]
    afternoon_1m = today_1m[today_1m['Date'] >= afternoon_start]
    
    morning_high = float(morning_1m['High'].max()) if len(morning_1m) > 0 else 0
    morning_low = float(morning_1m['Low'].min()) if len(morning_1m) > 0 else 0
    afternoon_high = float(afternoon_1m['High'].max()) if len(afternoon_1m) > 0 else 0
    afternoon_low = float(afternoon_1m['Low'].min()) if len(afternoon_1m) > 0 else 0
    
    # 判断日内走势类型
    open_price = float(today_1m['Open'].iloc[0]) if len(today_1m) > 0 else 0
    close_price = float(today_1m['Close'].iloc[-1]) if len(today_1m) > 0 else 0
    
    pattern = ''
    if close_price > open_price * 1.005:
        pattern = '阳线'
    elif close_price < open_price * 0.995:
        pattern = '阴线'
    else:
        pattern = '十字星'
    
    # 关键动作识别
    key_actions = []
    
    # 上午结构
    if len(morning_1m) > 0:
        morning_open = float(morning_1m['Open'].iloc[0])
        morning_close = float(morning_1m['Close'].iloc[-1])
        if morning_close > morning_open:
            key_actions.append(f'上午: 高开高走/探底回升（{morning_low:.2f}→{morning_high:.2f}）')
        else:
            key_actions.append(f'上午: 冲高回落/低开低走（{morning_high:.2f}→{morning_low:.2f}）')
    
    # 下午结构
    if len(afternoon_1m) > 0:
        afternoon_open = float(afternoon_1m['Open'].iloc[0])
        afternoon_close = float(afternoon_1m['Close'].iloc[-1])
        if afternoon_close > afternoon_open:
            key_actions.append(f'下午: 回升收高（{afternoon_low:.2f}→{afternoon_close:.2f}）')
        else:
            key_actions.append(f'下午: 回落收低（{afternoon_high:.2f}→{afternoon_close:.2f}）')
    
    # 与关键位关系
    if '5F' in levels_data:
        m5_55 = float(levels_data['5F'].get('ma55', 0))
        if afternoon_low <= m5_55 * 1.005 and close_price > m5_55:
            key_actions.append(f'盘中回踩5F55线({m5_55:.2f})后反弹')
    
    today_high = float(today_1m['High'].max())
    today_low = float(today_1m['Low'].min())
    
    return {
        'today': str(today),
        'open': open_price,
        'high': today_high,
        'low': today_low,
        'close': close_price,
        'pattern': pattern,
        'morning_range': (morning_low, morning_high),
        'afternoon_range': (afternoon_low, afternoon_high),
        'key_actions': key_actions,
        'description': f'今日{pattern}: 开{open_price:.2f} 高{today_high:.2f} 低{today_low:.2f} 收{close_price:.2f} | {"; ".join(key_actions)}'
    }

# =====================================================
# v4.1: X段判定
# =====================================================

def analyze_x_segment(df_current, df_upper, current_name='15F', upper_name='30F'):
    """X段判定"""
    if len(df_current) < 55 or len(df_upper) < 20:
        return {'is_x_segment': False, 'description': '数据不足'}
    
    p = float(df_current['Close'].iloc[-1])
    m55 = float(ma(df_current, 55).iloc[-1])
    m_upper = float(ma(df_upper, 20).iloc[-1])
    
    md = macd(df_current)['macd'].iloc[-1]
    md_upper = macd(df_upper)['macd'].iloc[-1]
    
    is_x = (p > m55 and md < 0) or (p < m55 and md > 0)
    
    if is_x:
        if p > m55 and md < 0:
            desc = f'{current_name} 55线上方X段（价格>55线但MACD<0）'
            confirm = '已突破55线，等待不创新低确认'
        else:
            desc = f'{current_name} 55线下方X段（价格<55线但MACD>0）'
            confirm = '被55线压制，X段可能变异为下跌段'
    else:
        desc = f'{current_name} 非X段'
        confirm = 'N/A'
    
    return {
        'is_x_segment': is_x,
        'description': desc,
        'confirmation': confirm,
        'price': p,
        'ma55': m55,
        'macd': md
    }

# =====================================================
# v4.1: 中轨传导链分析
# =====================================================

def analyze_middle_transmission(levels_data):
    """
    分析中轨传导链
    levels_data: dict of {level_name: {'price': p, 'middle': m20, 'macd': mc}}
    """
    chain = []
    for name in ['60F', '30F', '15F', '5F']:
        if name in levels_data:
            d = levels_data[name]
            p = d['price']
            m = d['middle']
            if p > m:
                chain.append(f'{name}中轨支撑')
            else:
                chain.append(f'{name}中轨压制')
    return ' → '.join(chain)

def get_middle_status(df, level_name):
    """获取中轨状态"""
    if len(df) < 20:
        return {'price': 0, 'middle': 0, 'status': '数据不足'}
    p = float(df['Close'].iloc[-1])
    b = boll(df, 20)
    middle = float(b['middle'].iloc[-1])
    status = '中轨上方' if p > middle else '中轨下方'
    return {'price': p, 'middle': middle, 'status': status, 'diff': p - middle}

# =====================================================
# v4.1: 分时段关键支撑分析
# =====================================================

def analyze_time_segment_support(middle_data, ma55_data):
    """分时段关键支撑分析"""
    morning_supports = []
    if '30F' in middle_data:
        morning_supports.append(('30F中轨', middle_data['30F']['middle']))
    if '30F' in ma55_data:
        morning_supports.append(('30F MA55', ma55_data['30F']['ma55']))
    if '60F' in middle_data:
        morning_supports.append(('60F中轨', middle_data['60F']['middle']))
    
    afternoon_supports = []
    if '5F' in ma55_data:
        afternoon_supports.append(('5F MA55', ma55_data['5F']['ma55']))
    if '5F' in middle_data:
        afternoon_supports.append(('5F中轨', middle_data['5F']['middle']))
    if '15F' in ma55_data:
        afternoon_supports.append(('15F MA55', ma55_data['15F']['ma55']))
    
    close_supports = []
    if '5F' in middle_data:
        close_supports.append(('5F中轨', middle_data['5F']['middle']))
    if '15F' in middle_data:
        close_supports.append(('15F中轨', middle_data['15F']['middle']))
    
    return {
        'morning': morning_supports,
        'afternoon': afternoon_supports,
        'close': close_supports
    }

# =====================================================
# v4.1: 传导链分析
# =====================================================

def analyze_transmission_chain(levels_data):
    """分析级别传导链"""
    chain = []
    if '双日' in levels_data:
        dd = levels_data['双日']
        if dd['macd'] > 0:
            chain.append('双日MACD>0')
        else:
            chain.append('双日MACD<0（极弱）')
    if '120F' in levels_data:
        l120 = levels_data['120F']
        if l120['macd'] > 0:
            chain.append('120F极强')
        else:
            chain.append('120F非极强')
    if '60F' in levels_data:
        l60 = levels_data['60F']
        if l60['macd'] > 0:
            chain.append('60F强/极强')
        else:
            chain.append('60F弱')
    if '30F' in levels_data:
        l30 = levels_data['30F']
        if l30.get('is_main_trend', False):
            chain.append('30F主涨段')
        else:
            chain.append('30F非主涨段')
    if '15F' in levels_data:
        l15 = levels_data['15F']
        if l15.get('macd', 0) > 0:
            chain.append('15F MACD>0')
        else:
            chain.append('15F MACD<0')
    if '5F' in levels_data:
        l5 = levels_data['5F']
        if l5.get('macd', 0) > 0:
            chain.append('5F MACD>0')
        else:
            chain.append('5F MACD<0')
    return ' → '.join(chain)

# =====================================================
# 时间窗口估算
# =====================================================

def estimate_time_window(df_daily, df_bid):
    """估算日线MACD金叉时间窗口"""
    if len(df_daily) < 30:
        return {'is_open': False, 'description': '数据不足'}
    
    md = macd(df_daily)
    dif = md['dif'].iloc[-1]
    dea = md['dea'].iloc[-1]
    
    if dif > dea:
        return {'is_open': True, 'description': '日线MACD已金叉，时间窗口开启'}
    
    dif_dea_diff = dif - dea
    
    if len(md['dif']) >= 3:
        dif_trend = md['dif'].iloc[-1] - md['dif'].iloc[-3]
        dea_trend = md['dea'].iloc[-1] - md['dea'].iloc[-3]
        
        if dif_trend > dea_trend:
            gap = dea - dif
            closing_speed = (dif_trend - dea_trend) / 2
            if closing_speed > 0:
                klines_needed = gap / closing_speed
                days_needed = klines_needed
                
                if days_needed <= 1:
                    return {'is_open': False, 'description': '日线MACD即将金叉（1天内）'}
                elif days_needed <= 3:
                    return {'is_open': False, 'description': f'日线MACD金叉窗口临近（{int(days_needed)}天内）'}
                else:
                    return {'is_open': False, 'description': f'日线MACD死叉中，金叉窗口还需约{int(days_needed)}天'}
    
    return {'is_open': False, 'description': '日线MACD死叉中，时间窗口未开启'}

# =====================================================
# 主程序
# =====================================================

def main():
    print("="*70)
    print("缠论分析 v4.1 - 完整升级版（技能文档同步）")
    print("="*70)
    
    print("\n📡 从长桥获取实时数据...")
    
    # 获取各级别数据
    df_1m = fetch_longbridge('000001.SH', '1m', 1000)
    df_3m = fetch_longbridge('000001.SH', '3m', 334)
    df_5m = fetch_longbridge('000001.SH', '5m', 1000)
    df_15m = fetch_longbridge('000001.SH', '15m', 334)
    df_30m = fetch_longbridge('000001.SH', '30m', 167)
    df_60m = fetch_longbridge('000001.SH', '60m', 84)
    df_120m_raw = fetch_longbridge('000001.SH', '120m', 100)
    df_d = fetch_longbridge('000001.SH', '1d', 120)
    
    # 修复120F
    from datetime import time as dt_time
    df_120m = df_120m_raw[df_120m_raw['Date'].dt.time != dt_time(15, 0, 0)].reset_index(drop=True)
    if len(df_120m) < 55:
        df_120m = df_120m_raw.tail(55).reset_index(drop=True)
    
    # 合成双日
    df_bid = synthesize_kline(df_d, 2)
    
    print(f"  120F原始: {len(df_120m_raw)}根, 过滤后: {len(df_120m)}根")
    
    print(f"\n✅ 数据获取完成:")
    levels_count = {
        '1F': len(df_1m), '3F': len(df_3m), '5F': len(df_5m),
        '15F': len(df_15m), '30F': len(df_30m), '60F': len(df_60m),
        '120F': len(df_120m), '日线': len(df_d), '双日': len(df_bid)
    }
    for name, n in levels_count.items():
        ok = "✅" if n >= 55 else ("⚠️" if n >= 20 else "❌")
        print(f"  {ok} {name}: {n}根")
    
    # Step 1: 数据完整性
    print(f"\n{'='*70}")
    print("Step 1: 数据完整性检查")
    print(f"{'='*70}")
    
    # Step 2: 段数分解
    print(f"\n{'='*70}")
    print("Step 2: 段数分解（3F/5F/15F/30F）")
    print(f"{'='*70}")
    
    segment_data = {}
    for name, df in [('3F', df_3m), ('5F', df_5m), ('15F', df_15m), ('30F', df_30m)]:
        if len(df) >= 20:
            seg = count_segments(df, name)
            segment_data[name] = seg
            print(f"\n  {name}段数分解:")
            print(f"    段数: {seg['segment_count']}")
            print(f"    当前: {seg['current']}")
            print(f"    结构: {seg['structure']}")
            print(f"    最近分型: {seg['peak_str']}")
    
    # v4.1新增: 历史段数分析（30F大周期）
    print(f"\n{'='*70}")
    print("Step 2b: 历史段数分析（v4.1新增）")
    print(f"{'='*70}")
    hist_30f = analyze_historical_segments(df_30m, '30F', major_low=3927)
    print(f"  {hist_30f['description']}")
    
    # Step 3: MACD稳定性
    print(f"\n{'='*70}")
    print("Step 3: MACD稳定性分析")
    print(f"{'='*70}")
    
    levels_macd = {}
    for name, df in [('3F', df_3m), ('5F', df_5m), ('15F', df_15m), ('30F', df_30m), ('60F', df_60m), ('120F', df_120m), ('日线', df_d), ('双日', df_bid)]:
        if len(df) >= 30:
            md = macd(df)
            dif, dea, mc = md['dif'].iloc[-1], md['dea'].iloc[-1], md['macd'].iloc[-1]
            
            if dif >= 0 and dea <= 0 and mc > 0: state = '极强'
            elif dif > dea > 0 and mc > 0: state = '强'
            elif 0 > dif > dea and mc > 0: state = '中性偏强'
            elif dif <= 0 and dea >= 0 and mc < 0: state = '极弱'
            elif dif < dea < 0 and mc < 0: state = '弱'
            elif 0 < dif < dea and mc < 0: state = '中性偏弱'
            else: state = '中性'
            
            levels_macd[name] = {'dif': dif, 'dea': dea, 'macd': mc, 'state': state}
            print(f"  {name}: {state} | DIF={round(dif,2)}, DEA={round(dea,2)}, MACD={round(mc,2)}")
    
    # Step 4: v4.1 主涨段三档判定（核心升级）
    print(f"\n{'='*70}")
    print("Step 4: 主涨段三档判定（v4.1核心升级：正式/雏形/X段）")
    print(f"{'='*70}")
    
    levels_trend = {}
    for name, df in [('15F', df_15m), ('30F', df_30m), ('60F', df_60m), ('120F', df_120m)]:
        if len(df) >= 55:
            trend = analyze_main_trend_segment_v41(df, name, segment_data.get(name))
            levels_trend[name] = trend
            grade_icon = {'正式':'✅', '雏形':'⚠️', 'x段':'❌', '主跌段':'❌', 'x段下方':'⚠️'}
            icon = grade_icon.get(trend['grade'], '?')
            print(f"  {icon} {name}: 【{trend['grade']}】{trend['description']}")
    
    # v4.1新增: 顶背离监控
    print(f"\n{'='*70}")
    print("Step 4b: 顶背离监控（v4.1核心新增）")
    print(f"{'='*70}")
    
    for name, df in [('30F', df_30m), ('60F', df_60m)]:
        if len(df) >= 30:
            div = check_top_divergence(df, name, segment_data.get(name))
            if div.get('has_divergence', False):
                print(f"  🔴 {div['description']}")
            elif div.get('warning', False):
                print(f"  🟠 {div['description']}")
            else:
                print(f"  ✅ {div['description']}")
    
    # Step 5: X段识别
    print(f"\n{'='*70}")
    print("Step 5: X段判定（多级别）")
    print(f"{'='*70}")
    
    x_segments = {}
    x15 = analyze_x_segment(df_15m, df_30m, '15F', '30F')
    x_segments['15F'] = x15
    print(f"  {x15['description']}")
    print(f"    确认: {x15['confirmation']}")
    
    x30 = analyze_x_segment(df_30m, df_60m, '30F', '60F')
    x_segments['30F'] = x30
    print(f"  {x30['description']}")
    print(f"    确认: {x30['confirmation']}")
    
    if len(df_120m) >= 55:
        x120 = analyze_x_segment(df_120m, df_d, '120F', '日线')
        x_segments['120F'] = x120
        print(f"  {x120['description']}")
        print(f"    确认: {x120['confirmation']}")
    
    if len(df_bid) >= 55:
        xd = analyze_x_segment(df_d, df_bid, '日线', '双日')
        x_segments['日线'] = xd
        print(f"  {xd['description']}")
        print(f"    确认: {xd['confirmation']}")
    
    # Step 6: 55线+中轨思维
    print(f"\n{'='*70}")
    print("Step 6: 55线+中轨思维（v4.1双体系）")
    print(f"{'='*70}")
    
    levels_55 = {}
    levels_middle = {}
    
    for name, df in [('5F', df_5m), ('15F', df_15m), ('30F', df_30m), ('60F', df_60m), ('120F', df_120m), ('日线', df_d), ('双日', df_bid)]:
        if len(df) >= 55:
            p = float(df['Close'].iloc[-1])
            m55 = float(ma(df, 55).iloc[-1])
            mc = macd(df)['macd'].iloc[-1]
            levels_55[name] = {'price': p, 'ma55': m55, 'macd': mc}
        if len(df) >= 20:
            middle_status = get_middle_status(df, name)
            levels_middle[name] = middle_status
            levels_55[name]['middle'] = middle_status['middle']
    
    # Step 7: 中轨传导链
    print(f"\n{'='*70}")
    print("Step 7: 中轨传导链分析")
    print(f"{'='*70}")
    
    transmission = analyze_middle_transmission(levels_middle)
    print(f"  中轨传导链: {transmission}")
    
    # Step 8: 联合支撑/压制区
    print(f"\n{'='*70}")
    print("Step 8: 联合支撑/压制区（v4.1含中轨共振）")
    print(f"{'='*70}")
    
    if len(df_d) >= 55 and len(df_bid) >= 55:
        d55 = float(ma(df_d, 55).iloc[-1])
        b55 = float(ma(df_bid, 55).iloc[-1])
        db = boll(df_d)
        bb = boll(df_bid)
        
        diff = abs(d55 - b55)
        strength = '极强' if diff < 5 else ('强' if diff < 20 else '中等')
        print(f"  🛡️ {strength}联合支撑: 日线55={d55:.2f} vs 双日55={b55:.2f} (差{diff:.2f})")
        
        if len(df_bid) >= 20:
            diffm = abs(float(db['middle'].iloc[-1]) - float(bb['middle'].iloc[-1]))
            strength = '极强' if diffm < 5 else ('强' if diffm < 20 else '中等')
            print(f"  ⛰️ {strength}联合压制: 日线中轨={float(db['middle'].iloc[-1]):.2f} vs 双日中轨={float(bb['middle'].iloc[-1]):.2f} (差{diffm:.2f})")
    
    # v4.1: 中轨+MA55联合支撑
    print(f"\n  v4.1新增 - 中轨+MA55联合支撑:")
    if '30F' in levels_middle and '30F' in levels_55:
        m30 = levels_middle['30F']['middle']
        m55_30 = levels_55['30F']['ma55']
        diff_30 = abs(m30 - m55_30)
        if diff_30 < 30:
            print(f"    🟡 30F联合支撑: 中轨={m30:.2f} vs MA55={m55_30:.2f} (差{diff_30:.2f}) → 阶梯支撑带")
    
    if '15F' in levels_middle and '15F' in levels_55:
        m15 = levels_middle['15F']['middle']
        m55_15 = levels_55['15F']['ma55']
        diff_15 = abs(m15 - m55_15)
        if diff_15 < 20:
            print(f"    🟡 15F联合支撑: 中轨={m15:.2f} vs MA55={m55_15:.2f} (差{diff_15:.2f}) → 阶梯支撑带")
    
    # 120F MA55
    if len(df_120m) >= 55:
        l120_55 = float(ma(df_120m, 55).iloc[-1])
        l120_p = float(df_120m['Close'].iloc[-1])
        print(f"  📍 120F MA55: {l120_55:.2f} (当前价{l120_p:.2f})")
    
    # Step 9: 分时段关键支撑
    print(f"\n{'='*70}")
    print("Step 9: 分时段关键支撑（v4.1核心）")
    print(f"{'='*70}")
    
    time_support = analyze_time_segment_support(levels_middle, levels_55)
    
    print(f"\n  📅 上午时段 (9:30-11:30):")
    for i, (name, val) in enumerate(time_support['morning']):
        star = "⭐" if i == 0 else ""
        print(f"    {star} 第{i+1}支撑: {name} = {val:.2f}")
    
    print(f"\n  📅 下午时段 (13:00-14:30):")
    for i, (name, val) in enumerate(time_support['afternoon']):
        star = "⭐" if i == 0 else ""
        print(f"    {star} 第{i+1}支撑: {name} = {val:.2f}")
    
    print(f"\n  📅 尾盘时段 (14:30-15:00):")
    for i, (name, val) in enumerate(time_support['close']):
        star = "⭐" if i == 0 else ""
        print(f"    {star} 第{i+1}支撑: {name} = {val:.2f}")
    
    # v4.1新增: 盘中结构分析
    print(f"\n{'='*70}")
    print("Step 9b: 盘中结构分析（v4.1核心新增）")
    print(f"{'='*70}")
    
    intraday = analyze_intraday_structure(df_1m, df_5m, levels_55)
    print(f"  {intraday['description']}")
    
    # Step 10: v4.1 套娃传导链（核心新增）
    print(f"\n{'='*70}")
    print("Step 10: 套娃传导链分析（v4.1核心新增）")
    print(f"{'='*70}")
    
    # 构建levels_data用于套娃分析
    nesting_levels = {}
    for name in ['5F', '15F', '30F', '60F', '120F', '日线', '双日']:
        if name in levels_55 and name in levels_trend:
            nesting_levels[name] = {
                'price': levels_55[name]['price'],
                'ma55': levels_55[name]['ma55'],
                'macd': levels_55[name]['macd'],
                'middle': levels_55[name].get('middle', 0),
                'grade': levels_trend[name]['grade']
            }
    
    nesting = analyze_nesting_chain(nesting_levels)
    print(f"  套娃链: {nesting['chain']}")
    print(f"  状态: {nesting['status']}")
    print(f"  维持条件: {nesting['maintain_conditions']}")
    print(f"  断裂触发: {nesting['break_triggers']}")
    
    # Step 11: 级别传导链
    print(f"\n{'='*70}")
    print("Step 11: 级别传导链")
    print(f"{'='*70}")
    
    chain_data = {}
    for name in levels_macd:
        chain_data[name] = levels_macd[name]
        if name in levels_trend:
            chain_data[name]['is_main_trend'] = levels_trend[name]['grade'] in ['正式', '雏形']
    
    chain_desc = analyze_transmission_chain(chain_data)
    print(f"  传导链: {chain_desc}")
    
    # Step 12: 时间窗口
    print(f"\n{'='*70}")
    print("Step 12: 时间窗口估算")
    print(f"{'='*70}")
    
    tw = estimate_time_window(df_d, df_bid)
    print(f"  {tw['description']}")
    
    # Step 13: v4.1 三路径情景推演（核心新增）
    print(f"\n{'='*70}")
    print("Step 13: 三路径情景推演（v4.1核心新增）")
    print(f"{'='*70}")
    
    paths = analyze_three_paths(levels_55, tw, segment_data.get('30F'))
    
    for key, path in paths.items():
        print(f"\n  【路径{key}】{path['name']}")
        print(f"    条件: {path['condition']}")
        print(f"    走势: {path['movement']}")
        print(f"    结果: {path['result']}")
        print(f"    操作: {path['operation']}")
        print(f"    概率: {path['probability']}")
    
    print(f"\n  ⚠️ 重要：路径B（震荡）是正常选项，不是失败！")
    
    # Step 14: v4.1 预警/确认双体系（核心新增）
    print(f"\n{'='*70}")
    print("Step 14: 预警/确认双体系（v4.1核心新增）")
    print(f"{'='*70}")
    
    wc = analyze_warning_confirm(levels_55)
    
    print(f"  操作预警线（减仓触发）:")
    if wc['warnings']:
        for w in wc['warnings']:
            print(f"    {w}")
    else:
        print(f"    ✅ 无预警，持仓安全")
    
    print(f"\n  战略确认线（清仓触发）:")
    if wc['confirms']:
        for c in wc['confirms']:
            print(f"    {c}")
    else:
        print(f"    ✅ 无确认，未达清仓条件")
    
    # Step 15: 明日策略（v4.1含三路径+套娃+预警/确认）
    print(f"\n{'='*70}")
    print("Step 15: 明日策略（v4.1完整版）")
    print(f"{'='*70}")
    
    p = float(df_d['Close'].iloc[-1])
    print(f"\n  当前收盘: {p:.2f}")
    
    if len(df_120m) >= 55:
        l120_55 = float(ma(df_120m, 55).iloc[-1])
        l120_macd = float(macd(df_120m)['macd'].iloc[-1])
        print(f"  120F MA55: {l120_55:.2f}")
        print(f"  120F MACD: {l120_macd:.2f}")
    
    # 套娃状态
    print(f"\n  📌 套娃状态: {nesting['status']}")
    
    # 三路径应对
    print(f"\n  📌 三路径应对策略:")
    
    print(f"\n    【路径A - 理想】快速突破")
    print(f"    • 条件: 30F MACD转正，突破前高")
    print(f"    • 操作: 持仓，可加仓")
    print(f"    • 目标: 双日金叉+明显斜率")
    
    print(f"\n    【路径B - 震荡】时间换空间（概率最高）")
    print(f"    • 条件: 关键位之间横盘")
    print(f"    • 操作: 持仓，高抛低吸")
    print(f"    • 目标: 等待双日MACD金叉后再突破")
    
    print(f"\n    【路径C - 风险】套娃断裂")
    print(f"    • 条件: 跌破5F中轨→5F55线→传导链启动")
    print(f"    • 操作: 减仓→清仓")
    print(f"    • 目标: 回踩30F55线(4044)")
    
    # 关键价位监控
    print(f"\n  📌 关键价位监控清单:")
    for name, val in [('5F中轨', levels_middle.get('5F', {}).get('middle', 0)),
                       ('5F MA55', levels_55.get('5F', {}).get('ma55', 0)),
                       ('15F MA55', levels_55.get('15F', {}).get('ma55', 0)),
                       ('30F中轨', levels_middle.get('30F', {}).get('middle', 0)),
                       ('30F MA55', levels_55.get('30F', {}).get('ma55', 0)),
                       ('120F MA55', levels_55.get('120F', {}).get('ma55', 0))]:
        if val > 0:
            print(f"    • {name}: {val:.2f}")
    
    # 分时段策略
    print(f"\n  📌 v4.1分时段策略:")
    
    print(f"\n    【上午时段 (9:30-11:30)】")
    if '30F' in levels_middle:
        m30 = levels_middle['30F']['middle']
        print(f"    • 第一支撑: 30F中轨 = {m30:.2f}")
        print(f"    • 若回踩{m30:.2f}企稳 + 底背离 → 试多/持仓")
        print(f"    • 若跌破{m30:.2f} → 减仓1/3，等待30F MA55")
    
    print(f"\n    【下午时段 (13:00-14:30)】")
    if '5F' in levels_55:
        m55_5 = levels_55['5F']['ma55']
        print(f"    • 第一支撑: 5F MA55 = {m55_5:.2f}")
        print(f"    • 若守住{m55_5:.2f} → 下午维持震荡/反弹")
        print(f"    • 若跌破{m55_5:.2f} → 传导链启动，测试30F55线")
    
    print(f"\n    【尾盘时段 (14:30-15:00)】")
    if '5F' in levels_middle:
        m5 = levels_middle['5F']['middle']
        print(f"    • 关键: 收在5F中轨({m5:.2f})上方 → 多头占优")
    
    print(f"\n  📌 持仓者:")
    if len(df_120m) >= 55:
        l120_55 = ma(df_120m, 55).iloc[-1]
        print(f"    • 若上冲120F55线({l120_55:.2f})附近受压 → 减仓")
        print(f"    • 若突破120F55线 + 120F MACD转正 → 加仓")
    print(f"    • 5F55线/3F中轨不应有效跌破（操作预警）")
    print(f"    • 跌破30F55线(4044) → 战略确认，清仓")
    
    print(f"\n  📌 空仓者:")
    print(f"    • 路径A: 等待突破确认，追涨")
    print(f"    • 路径B: 震荡区间内低吸高抛")
    print(f"    • 路径C: 等待回踩30F55线(4044)附近")
    
    print(f"\n  📌 时间窗口:")
    print(f"    • 日线金叉窗口正常会在后天中午左右度过")
    print(f"    • 防止空头在日线金叉窗口或120F极强窗口后的反扑")
    
    print(f"\n  📌 v4.1原文验证:")
    print(f"    • '30F级别走出3927以来第五段上涨' → 历史段数确认")
    print(f"    • '回踩30F中轨后出现30F主涨段特征' → 主涨段雏形判定")
    print(f"    • '同步套娃了120F主涨段特征' → 套娃传导链")
    print(f"    • '120F主涨特征是因为双日第三段上涨有可能套娃' → 双日结构推演")
    print(f"    • '跌破5F中轨导致30F主涨段结束' → 操作预警线")
    print(f"    • '震荡换取时间' → 路径B是正常选项")
    
    print(f"\n📅 日期: {df_d['Date'].iloc[-1].date()}")
    print("="*70)

if __name__ == "__main__":
    main()
