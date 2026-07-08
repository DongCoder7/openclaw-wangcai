#!/root/.openclaw/workspace/venv/bin/python3
"""
缠论分析 v4.2 - 高手复盘优化版

根据图片中的复盘笔记优化：
1. 突破120F55线条件精细化（30F第五段主涨段 + 5F中轨维持）
2. "回踩更深"双情景分析（情景1: 回踩30F55线；情景2: 30F X段回踩120F中轨）
3. X段高级分类（3段+X+新 vs 5段+X+新）
4. 120F中轨分析（上移速度、跌破预警）
5. "不主观判断"临盘应对（给出触发条件而非预测）
6. 30F级别结构精细化（五段/三段识别、结构变异分析）

v4.2 升级对照（基于图片复盘）：
┌─────────────────────────────────────────────────────────────────┐
│ 图片分析要点                    →  v4.2 升级功能                  │
├─────────────────────────────────────────────────────────────────┤
│ 突破120F55线条件苛刻            →  analyze_breakthrough_120f55() │
│ 情景1: 回踩30F55线再第五段      →  analyze_deeper_pullback()     │
│ 情景2: 30F X段回踩120F中轨      →  analyze_x_segment_advanced()  │
│ 3段+X+新 / 5段+X+新             →  classify_x_segment_type()      │
│ 120F中轨上移不明显              →  analyze_120f_middle_trend()   │
│ 不主观判断，临盘处理            →  generate_linpang_strategy()   │
│ 跌破120F中轨更复杂              →  warn_120f_middle_break()      │
└─────────────────────────────────────────────────────────────────┘
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from longport.openapi import Config, QuoteContext, Period, AdjustType

# =====================================================
# v4.0-v4.1 基础函数（保留）
# =====================================================
# 多数据源获取（优先级：tdxrs > 长桥 > tushare > efinance）
from data_fetcher import fetch_data, fetch_longbridge
# =====================================================

# =====================================================
# v4.1 基础函数（保留）
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
# v4.2 核心升级函数
# =====================================================

def analyze_30f_structure_detailed(df_30f, major_low=3927):
    """
    v4.2 升级：30F级别结构精细化分析
    
    图片分析："从3927开始，30F是五段上涨结构的样子"
    
    需要识别：
    1. 是否从major_low开始的五段上涨
    2. 当前是第几段运行中
    3. 结构是"五段趋势"还是"三段盘整"
    4. 结构是否可能变异（如4117是否为第三段顶点）
    """
    if len(df_30f) < 50:
        return {'description': '数据不足'}
    
    seg = count_segments(df_30f, '30F')
    segment_count = seg.get('segment_count', 0)
    peaks = seg.get('peaks', [])
    
    # 找从major_low开始的起点
    start_idx = 0
    for i, p in enumerate(peaks):
        if p[1] == 'bottom' and p[2] <= major_low * 1.02:
            start_idx = i
            break
    
    recent_peaks = peaks[start_idx:] if start_idx < len(peaks) else peaks
    recent_count = len(recent_peaks) - 1
    
    # 判断结构类型
    if recent_count >= 5:
        structure_type = '五段上涨趋势（2个中枢）'
        current_status = '第五段上涨运行中'
        risk_note = '⚠️ 第五段末端，注意顶背离风险'
    elif recent_count >= 3:
        structure_type = '三段盘整结构（1个中枢）'
        current_status = '第三段上涨运行中'
        risk_note = '第三段运行中，可能延伸为五段'
    else:
        structure_type = '初期结构（1-2段）'
        current_status = '上涨初期'
        risk_note = '结构未完整，继续观察'
    
    # 关键：判断4117是否为"放宽的第三段"
    # 如果当前从低点反弹后，高点未能超过前高，可能形成"三段+X"结构
    has_new_high = False
    if len(recent_peaks) >= 3:
        latest_high = recent_peaks[-1][2] if recent_peaks[-1][1] == 'top' else recent_peaks[-2][2]
        prev_high = recent_peaks[-3][2] if recent_peaks[-3][1] == 'top' else 0
        if prev_high > 0 and latest_high >= prev_high * 0.99:
            has_new_high = True
    
    # 判断"4117放宽为第三段"的可能性
    relaxed_third = False
    if recent_count >= 3 and not has_new_high:
        relaxed_third = True
    
    return {
        'major_low': major_low,
        'segment_count': recent_count,
        'structure_type': structure_type,
        'current_status': current_status,
        'has_new_high': has_new_high,
        'relaxed_third': relaxed_third,
        'risk_note': risk_note,
        'peaks': recent_peaks,
        'description': f'{major_low}以来{structure_type} | 当前{current_status} | {"新高点" if has_new_high else "未创新高"} | {risk_note}',
        'detail': f'若{major_low}以来是五段上涨，则当前应处于第五段；若4117为放宽的第三段顶点，则后续回踩30F55线后可能开启第五段'
    }

def analyze_breakthrough_120f55(df_30f, df_5f, df_120f):
    """
    v4.2 升级：突破120F55线条件精细化分析
    
    图片分析："突破120F55线，要么是120F极强，要么是30F主涨段，前者已经证伪"
    
    需要分析：
    1. 120F极强是否已证伪？
    2. 30F主涨段是否成立？
    3. 突破需要什么条件？
    """
    if len(df_120f) < 55 or len(df_30f) < 55 or len(df_5f) < 55:
        return {'description': '数据不足'}
    
    p120 = float(df_120f['Close'].iloc[-1])
    m55_120 = float(ma(df_120f, 55).iloc[-1])
    md_120 = macd(df_120f)['macd'].iloc[-1]
    
    p30 = float(df_30f['Close'].iloc[-1])
    m55_30 = float(ma(df_30f, 55).iloc[-1])
    md_30 = macd(df_30f)['macd'].iloc[-1]
    middle_30 = float(boll(df_30f, 20)['middle'].iloc[-1])
    
    p5 = float(df_5f['Close'].iloc[-1])
    middle_5 = float(boll(df_5f, 20)['middle'].iloc[-1])
    
    # 1. 120F极强是否已证伪？
    is_120f_strong = md_120 > 0 and p120 > m55_120
    is_120f_extreme = md_120 > 20 and p120 > m55_120  # 极强阈值
    
    # 图片说"120F极强已经证伪"——可能指120F MACD虽然>0但不是"极强"状态
    # 或者指价格未能突破120F55线
    f120_falsified = p120 < m55_120 or md_120 < 10
    
    # 2. 30F主涨段是否成立？
    is_30f_main_trend = p30 > m55_30 and md_30 > 0
    
    # 3. 突破条件
    breakthrough_conditions = []
    
    # 条件A：120F极强直接突破（已证伪路径）
    if is_120f_extreme and p120 > m55_120:
        breakthrough_conditions.append('A: 120F极强直接突破（当前不满足）')
    else:
        breakthrough_conditions.append('A: 120F极强直接突破 ❌ 已证伪/不满足')
    
    # 条件B：30F主涨段推动（当前可能路径）
    if is_30f_main_trend:
        breakthrough_conditions.append(f'B: 30F主涨段推动 ✅ 当前满足（价格>{m55_30:.2f} + MACD>0）')
    else:
        breakthrough_conditions.append(f'B: 30F主涨段推动 ⚠️ 当前不满足（需价格>{m55_30:.2f} + MACD>0）')
    
    # 条件C：30F第五段主涨段 + 5F中轨维持（图片核心条件）
    # "最多回踩到30F中轨后，始终维持在5F中轨以上"
    can_sustain_5f_middle = p5 > middle_5
    can_pullback_to_30f_middle = p30 > middle_30
    
    if can_sustain_5f_middle and can_pullback_to_30f_middle:
        breakthrough_conditions.append(f'C: 30F第五段主涨段 + 5F中轨维持 ✅ 苛刻但满足')
    else:
        breakthrough_conditions.append(f'C: 30F第五段主涨段 + 5F中轨维持 ⚠️ 苛刻（需5F>{middle_5:.2f}且30F>{middle_30:.2f}）')
    
    return {
        'f120_strong': is_120f_strong,
        'f120_extreme': is_120f_extreme,
        'f120_falsified': f120_falsified,
        '30f_main_trend': is_30f_main_trend,
        'p120': p120,
        'm55_120': m55_120,
        'p30': p30,
        'm55_30': m55_30,
        'middle_30': middle_30,
        'p5': p5,
        'middle_5': middle_5,
        'conditions': breakthrough_conditions,
        'description': f'120F极强{"已证伪" if f120_falsified else "仍有效"} | 30F主涨段{"成立" if is_30f_main_trend else "未成立"} | 突破条件C{"苛刻但满足" if can_sustain_5f_middle and can_pullback_to_30f_middle else "苛刻"}',
        'conclusion': '若要突破120F55线，需要30F第五段出现主涨段，且最多回踩30F中轨后始终维持在5F中轨以上'
    }

def classify_x_segment_type(df_30f, df_120f, segment_data_30f=None):
    """
    v4.2 升级：X段高级分类
    
    图片分析："30分钟级别出现X段，可以是3段上涨结构+X段+新上涨结构，
    也可以是5段上涨结构+X段+新上涨结构"
    
    分类：
    - 类型A：3段上涨 + X段 + 新上涨结构（回踩120F中轨）
    - 类型B：5段上涨 + X段 + 新上涨结构（回踩120F中轨）
    - 共性：都回踩120F中轨
    """
    if len(df_30f) < 55 or len(df_120f) < 20:
        return {'description': '数据不足'}
    
    seg = segment_data_30f or count_segments(df_30f, '30F')
    segment_count = seg.get('segment_count', 0)
    
    p30 = float(df_30f['Close'].iloc[-1])
    m55_30 = float(ma(df_30f, 55).iloc[-1])
    md_30 = macd(df_30f)['macd'].iloc[-1]
    
    middle_120 = float(boll(df_120f, 20)['middle'].iloc[-1])
    p120 = float(df_120f['Close'].iloc[-1])
    
    # 判断是否是X段
    is_x_segment = (p30 > m55_30 and md_30 < 0) or (p30 < m55_30 and md_30 > 0)
    
    if not is_x_segment:
        return {
            'is_x': False,
            'description': '30F当前非X段',
            'type': 'N/A'
        }
    
    # 分类X段类型
    if segment_count <= 3:
        x_type = 'A'
        x_name = '3段上涨结构 + X段 + 新上涨结构'
        x_detail = '前三段形成盘整中枢，当前X段是对中枢的回踩'
    elif segment_count <= 5:
        x_type = 'B'
        x_name = '5段上涨结构 + X段 + 新上涨结构'
        x_detail = '五段趋势结构完成后，X段是趋势后的回踩调整'
    else:
        x_type = 'C'
        x_name = '复杂结构 + X段 + 新上涨结构'
        x_detail = '中枢扩展后的X段回踩'
    
    # 共性：回踩120F中轨
    pullback_to_120f_middle = p120 <= middle_120 * 1.01  # 允许1%误差
    
    return {
        'is_x': True,
        'x_type': x_type,
        'x_name': x_name,
        'x_detail': x_detail,
        'segment_count': segment_count,
        'pullback_to_120f_middle': pullback_to_120f_middle,
        'middle_120': middle_120,
        'p120': p120,
        'description': f'30F X段（类型{x_type}）: {x_name} | {"已回踩" if pullback_to_120f_middle else "未回踩"}120F中轨({middle_120:.2f})',
        'common_feature': '共性：都回踩120F中轨',
        'implication': '若出现X段，意味着需要一个快速回踩120F中轨的过程，然后才能形成新的上涨结构'
    }

def analyze_deeper_pullback(df_30f, df_120f, df_5f, segment_data_30f=None):
    """
    v4.2 升级："回踩更深"双情景分析
    
    图片分析："这点略微苛刻，所以展开写一下潜在的回踩更深的情况"
    
    情景1：回踩到30F55线，4117放宽为30F第三段上涨，回踩30F55线后再开始第五段上涨
    情景2：30F出现X段，共性是回踩120F中轨
    """
    if len(df_30f) < 55 or len(df_120f) < 20 or len(df_5f) < 55:
        return {'description': '数据不足'}
    
    p30 = float(df_30f['Close'].iloc[-1])
    m55_30 = float(ma(df_30f, 55).iloc[-1])
    middle_30 = float(boll(df_30f, 20)['middle'].iloc[-1])
    
    p120 = float(df_120f['Close'].iloc[-1])
    middle_120 = float(boll(df_120f, 20)['middle'].iloc[-1])
    m55_120 = float(ma(df_120f, 55).iloc[-1])
    
    p5 = float(df_5f['Close'].iloc[-1])
    middle_5 = float(boll(df_5f, 20)['middle'].iloc[-1])
    
    seg = segment_data_30f or count_segments(df_30f, '30F')
    segment_count = seg.get('segment_count', 0)
    
    scenarios = {}
    
    # 情景1：回踩30F55线（"4117放宽为第三段"）
    # 条件：当前不是五段而是三段，回踩30F55线后开启第五段
    is_three_segment = segment_count <= 3
    can_pullback_to_30f55 = p30 > m55_30  # 当前还在30F55线上方
    
    scenarios['1'] = {
        'name': '情景1：回踩30F55线，再开启第五段',
        'condition': '4117放宽为30F第三段顶点，当前处于第三段上涨中或刚结束',
        'pullback_target': f'30F55线 = {m55_30:.2f}',
        'depth': f'从当前{p30:.2f}回踩至{m55_30:.2f}，约{p30 - m55_30:.2f}点（{(p30 - m55_30)/p30*100:.1f}%）',
        'after_pullback': '回踩30F55线后，若企稳，开始第五段上涨，配合双日金叉形成主涨段',
        'probability': '中' if is_three_segment else '低（当前可能已是五段）',
        'trigger': f'跌破30F中轨({middle_30:.2f})且向{m55_30:.2f}靠近',
        'operation': '若回踩30F55线企稳 + 底背离 → 试多/加仓'
    }
    
    # 情景2：30F X段，回踩120F中轨
    scenarios['2'] = {
        'name': '情景2：30F X段，回踩120F中轨',
        'condition': '30F出现X段（3段+X+新 或 5段+X+新）',
        'pullback_target': f'120F中轨 = {middle_120:.2f}',
        'depth': f'从当前{p30:.2f}回踩至{middle_120:.2f}，约{p30 - middle_120:.2f}点（{(p30 - middle_120)/p30*100:.1f}%）',
        'after_pullback': '回踩120F中轨后，形成新的上涨结构（新的3段或5段）',
        'probability': '中（若周一下午未能快速突破）',
        'trigger': f'跌破5F中轨({middle_5:.2f})且快速下探至{middle_120:.2f}附近',
        'operation': '若回踩120F中轨企稳 + 5F底背离 → 试多/加仓',
        'note': '⚠️  Tuesday可能有一个快速回踩，因为120F中轨在前两天上移不明显'
    }
    
    # 快速突破路径（图片提到"先看能否周一快速突破"）
    scenarios['fast'] = {
        'name': '快速突破路径（首选）',
        'condition': '周一快速突破，不给回踩机会',
        'requirement': f'30F第五段直接出现主涨段，始终维持在5F中轨({middle_5:.2f})以上',
        'probability': '中低（条件苛刻）',
        'trigger': f'开盘即站稳5F中轨({middle_5:.2f})且快速突破120F55线({m55_120:.2f})',
        'operation': '持仓/追涨'
    }
    
    return {
        'scenarios': scenarios,
        'current_segment': segment_count,
        'is_three_segment': is_three_segment,
        'description': f'30F当前{"三段" if is_three_segment else "五段"}结构 | 若快速突破失败，情景1和2概率均上升 | 120F中轨上移速度决定回踩深度',
        'recommendation': '不主观判断，临盘处理：若周一快速突破 → 持仓；若不能 → 准备迎接情景1或2'
    }

def analyze_120f_middle_trend(df_120f, days=5):
    """
    v4.2 升级：120F中轨上移速度分析
    
    图片分析："120F中轨在前两天上移不明显"
    
    需要分析120F中轨的趋势：
    - 上移速度（斜率）
    - 是否走平或下行
    - 对回踩深度的影响
    """
    if len(df_120f) < 20 + days:
        return {'description': '数据不足'}
    
    b = boll(df_120f, 20)
    middle = b['middle']
    
    # 计算最近days根的中轨变化
    recent_middle = middle.tail(days).values
    
    if len(recent_middle) >= 2:
        slope = (recent_middle[-1] - recent_middle[0]) / (len(recent_middle) - 1)
        slope_pct = slope / recent_middle[-1] * 100 if recent_middle[-1] > 0 else 0
    else:
        slope = 0
        slope_pct = 0
    
    # 判断上移速度
    if slope > 2:
        trend = '快速上移'
        implication = '回踩空间被压缩，突破更容易'
    elif slope > 0.5:
        trend = '缓慢上移'
        implication = '回踩空间适中，需关注'
    elif slope > -0.5:
        trend = '走平'
        implication = '⚠️ 120F中轨上移不明显，回踩可能更深（如图片所述）'
    else:
        trend = '下行'
        implication = '⚠️ 中轨下行，支撑减弱，风险加大'
    
    current_middle = float(recent_middle[-1])
    
    return {
        'current_middle': current_middle,
        'slope': slope,
        'slope_pct': slope_pct,
        'trend': trend,
        'implication': implication,
        'description': f'120F中轨当前{current_middle:.2f}，最近{days}根斜率{slope:.2f}点/根 | {trend} | {implication}',
        'note_for_scenario2': '若120F中轨上移不明显，情景2（X段回踩120F中轨）的回踩深度可能更大，Tuesday快速回踩概率上升'
    }

def generate_linpang_strategy(levels_data, breakthrough_analysis, pullback_analysis, x_segment_analysis):
    """
    v4.2 升级："不主观判断"临盘应对策略
    
    图片分析："你们也不要有太多主观的判断，历史证明每次你们主观判断大多都会哇哇叫"
    
    策略原则：
    1. 不预测路径，只给出触发条件
    2. 每个条件对应明确的操作
    3. 操作分档：持仓/减仓/清仓/加仓
    """
    
    strategies = {
        'principle': '临盘应对，不主观判断。根据实际走势触发条件执行操作。',
        'triggers': []
    }
    
    # 获取关键价位
    m5_middle = levels_data.get('5F', {}).get('middle', 0)
    m5_55 = levels_data.get('5F', {}).get('ma55', 0)
    m30_middle = levels_data.get('30F', {}).get('middle', 0)
    m30_55 = levels_data.get('30F', {}).get('ma55', 0)
    m120_55 = levels_data.get('120F', {}).get('ma55', 0)
    m120_middle = levels_data.get('120F', {}).get('middle', 0)
    
    # 触发条件1：快速突破（路径A）
    strategies['triggers'].append({
        'name': '触发条件1：快速突破',
        'condition': f'开盘站稳5F中轨({m5_middle:.2f})且30分钟内突破120F55线({m120_55:.2f})',
        'action': '持仓，若放量突破可加仓',
        'probability': '中低',
        'note': '首选路径，但条件苛刻'
    })
    
    # 触发条件2：情景1 - 回踩30F55线
    strategies['triggers'].append({
        'name': '触发条件2：情景1（回踩30F55线）',
        'condition': f'跌破5F中轨({m5_middle:.2f})后，向30F55线({m30_55:.2f})靠近，且速度不快（非快速杀跌）',
        'action': '减仓1/3，观察30F55线附近是否有底背离',
        'probability': '中',
        'note': '若30F55线企稳+底背离 → 试多/加仓'
    })
    
    # 触发条件3：情景2 - X段回踩120F中轨
    strategies['triggers'].append({
        'name': '触发条件3：情景2（X段回踩120F中轨）',
        'condition': f'快速跌破5F55线({m5_55:.2f})，向120F中轨({m120_middle:.2f})靠近',
        'action': '减仓1/2，等待120F中轨附近企稳信号',
        'probability': '中',
        'note': '⚠️ Tuesday可能快速回踩，因为120F中轨上移不明显'
    })
    
    # 触发条件4：120F中轨跌破
    strategies['triggers'].append({
        'name': '触发条件4：120F中轨跌破',
        'condition': f'跌破120F中轨({m120_middle:.2f})且反抽不上',
        'action': '清仓，等跌破了再来分析',
        'probability': '低',
        'note': '图片："如果跌破120F中轨，就会更加复杂，等真的跌破了再来分析"'
    })
    
    # 触发条件5：30F55线跌破（战略确认）
    strategies['triggers'].append({
        'name': '触发条件5：30F55线跌破',
        'condition': f'跌破30F55线({m30_55:.2f})且反抽不上',
        'action': '无条件清仓',
        'probability': '低',
        'note': '战略确认线，套娃断裂'
    })
    
    # 触发条件6：震荡路径B（最可能）
    strategies['triggers'].append({
        'name': '触发条件6：震荡路径（概率最高）',
        'condition': f'在5F中轨({m5_middle:.2f})和120F55线({m120_55:.2f})之间横盘，不突破也不深跌',
        'action': '持仓，高抛低吸。上方{:.0f}减仓，下方{:.0f}加仓'.format(m120_55, m5_middle),
        'probability': '高',
        'note': '图片："用震荡换取时间"'
    })
    
    return strategies

def warn_120f_middle_break(df_120f):
    """
    v4.2 升级：120F中轨跌破预警
    
    图片分析："如果跌破120F中轨，就会更加复杂，等真的跌破了再来分析"
    
    需要提前监控120F中轨状态，一旦跌破立即预警
    """
    if len(df_120f) < 20:
        return {'description': '数据不足'}
    
    p120 = float(df_120f['Close'].iloc[-1])
    middle_120 = float(boll(df_120f, 20)['middle'].iloc[-1])
    m55_120 = float(ma(df_120f, 55).iloc[-1])
    
    distance_to_middle = p120 - middle_120
    distance_to_ma55 = p120 - m55_120
    
    # 预警级别
    if p120 < middle_120:
        level = '🔴 已跌破'
        action = '等真的跌破了再来分析（复杂化，暂不判断）'
    elif distance_to_middle < 5:
        level = '🟠 临界'
        action = '高度警惕，若跌破中轨且反抽不上 → 清仓观察'
    elif distance_to_middle < 15:
        level = '🟡 接近'
        action = '关注，准备应对复杂化走势'
    else:
        level = '✅ 安全'
        action = '暂无风险'
    
    return {
        'current_price': p120,
        'middle_120': middle_120,
        'm55_120': m55_120,
        'distance_to_middle': distance_to_middle,
        'distance_to_ma55': distance_to_ma55,
        'level': level,
        'action': action,
        'description': f'120F中轨: {middle_120:.2f} | 当前{p120:.2f} | 距中轨{distance_to_middle:.2f}点 | {level} | {action}',
        'note': '图片：跌破120F中轨后走势复杂化，需等待新的结构形成后再分析'
    }

# =====================================================
# v4.1 函数（保留）
# =====================================================

def analyze_main_trend_segment_v41(df, level_name='30F', segment_data=None):
    """v4.1 主涨段三档判定"""
    if len(df) < 55:
        return {'level': level_name, 'grade': 'unknown', 'description': '数据不足'}
    
    p = float(df['Close'].iloc[-1])
    m55 = float(ma(df, 55).iloc[-1])
    md = macd(df)['macd'].iloc[-1]
    
    b = boll(df, 20)
    middle = float(b['middle'].iloc[-1])
    
    has_structure = segment_data is not None and segment_data.get('segment_count', 0) >= 3
    recent_low = df['Low'].tail(20).min()
    pullback_confirmed = recent_low <= m55 * 1.01 or recent_low <= middle * 1.01
    
    structure_intact = True
    if segment_data and segment_data.get('segment_count', 0) > 0:
        current = segment_data.get('current', '')
        if 'down运行中' in current and segment_data.get('segment_count', 0) >= 3:
            recent_peaks = segment_data.get('peaks', [])
            if len(recent_peaks) >= 3:
                latest_low = float(recent_peaks[-1][2]) if recent_peaks[-1][1] == 'bottom' else (float(recent_peaks[-2][2]) if len(recent_peaks) >= 2 else float('inf'))
                prev_low = float(recent_peaks[-3][2]) if len(recent_peaks) >= 3 and recent_peaks[-3][1] == 'bottom' else float('inf')
                if prev_low != float('inf') and latest_low < prev_low * 0.99:
                    structure_intact = False
    
    if p > m55 and md > 0:
        grade = '正式'
        desc = '主涨段（正式）'
    elif p > m55 and has_structure and pullback_confirmed and md < 0:
        grade = '雏形'
        desc = '主涨段雏形 — 结构完整 + 回踩确认 + MACD暂时<0'
    elif p > m55 and md < 0 and not structure_intact and has_structure:
        grade = 'x段'
        desc = '55线上方X段 — 结构被破坏'
    elif p > m55 and md < 0:
        grade = '雏形'
        desc = '主涨段雏形（结构确认中）'
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

def analyze_nesting_chain(levels_data):
    """v4.1 套娃传导链"""
    chain = []
    for level in ['30F', '60F', '120F', '日线', '双日']:
        if level in levels_data:
            d = levels_data[level]
            grade = d.get('grade', 'unknown')
            chain.append(f'{level}:{grade}')
    
    nesting_status = 'unknown'
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
        'description': f'套娃状态: {nesting_status}'
    }

# =====================================================
# v4.2 主程序
# =====================================================

def main():
    print("="*70)
    print("缠论分析 v4.2 - 高手复盘优化版")
    print("="*70)
    
    print("\n📡 从多数据源获取实时数据（优先级: tdxrs > 长桥 > tushare > efinance）...")
    
    # 获取数据
    df_1m = fetch_data('000001.SH', '1m', 1000)
    df_3m = fetch_data('000001.SH', '3m', 334)
    df_5m = fetch_data('000001.SH', '5m', 1000)
    df_15m = fetch_data('000001.SH', '15m', 334)
    df_30m = fetch_data('000001.SH', '30m', 167)
    df_60m = fetch_data('000001.SH', '60m', 84)
    df_120m_raw = fetch_data('000001.SH', '120m', 100)
    df_d = fetch_data('000001.SH', '1d', 120)
    
    # 修复120F
    from datetime import time as dt_time
    df_120m = df_120m_raw[df_120m_raw['Date'].dt.time != dt_time(15, 0, 0)].reset_index(drop=True)
    if len(df_120m) < 55:
        df_120m = df_120m_raw.tail(55).reset_index(drop=True)
    
    df_bid = synthesize_kline(df_d, 2)
    
    print(f"\n✅ 数据获取完成:")
    levels_count = {
        '1F': len(df_1m), '3F': len(df_3m), '5F': len(df_5m),
        '15F': len(df_15m), '30F': len(df_30m), '60F': len(df_60m),
        '120F': len(df_120m), '日线': len(df_d), '双日': len(df_bid)
    }
    for name, n in levels_count.items():
        ok = "✅" if n >= 55 else ("⚠️" if n >= 20 else "❌")
        print(f"  {ok} {name}: {n}根")
    
    # 段数分解
    segment_data = {}
    for name, df in [('3F', df_3m), ('5F', df_5m), ('15F', df_15m), ('30F', df_30m)]:
        if len(df) >= 20:
            seg = count_segments(df, name)
            segment_data[name] = seg
    
    # 计算基础指标
    levels_55 = {}
    levels_middle = {}
    levels_trend = {}
    
    for name, df in [('5F', df_5m), ('15F', df_15m), ('30F', df_30m), ('60F', df_60m), ('120F', df_120m), ('日线', df_d), ('双日', df_bid)]:
        if len(df) >= 55:
            p = float(df['Close'].iloc[-1])
            m55 = float(ma(df, 55).iloc[-1])
            mc = macd(df)['macd'].iloc[-1]
            levels_55[name] = {'price': p, 'ma55': m55, 'macd': mc}
        if len(df) >= 20:
            b = boll(df, 20)
            middle = float(b['middle'].iloc[-1])
            levels_middle[name] = {'price': p, 'middle': middle, 'status': '中轨上方' if p > middle else '中轨下方'}
            if name in levels_55:
                levels_55[name]['middle'] = middle
    
    for name, df in [('15F', df_15m), ('30F', df_30m), ('60F', df_60m), ('120F', df_120m)]:
        if len(df) >= 55:
            trend = analyze_main_trend_segment_v41(df, name, segment_data.get(name))
            levels_trend[name] = trend
    
    # =====================================================
    # v4.2 核心分析输出
    # =====================================================
    
    print(f"\n{'='*70}")
    print("v4.2 核心分析：突破120F55线条件 + 回踩更深双情景")
    print(f"{'='*70}")
    
    # 1. 30F结构精细化分析
    print(f"\n【Step v4.2-1】30F级别结构精细化分析")
    print(f"{'─'*70}")
    
    structure_30f = analyze_30f_structure_detailed(df_30m, major_low=3927)
    print(f"  {structure_30f['description']}")
    print(f"  详细: {structure_30f['detail']}")
    
    # 2. 突破120F55线条件分析
    print(f"\n【Step v4.2-2】突破120F55线条件精细化分析")
    print(f"{'─'*70}")
    print(f"  图片分析：'突破120F55线，要么是120F极强，要么是30F主涨段，前者已经证伪'")
    
    breakthrough = analyze_breakthrough_120f55(df_30m, df_5m, df_120m)
    print(f"  结论: {breakthrough['conclusion']}")
    print(f"  状态: {breakthrough['description']}")
    for cond in breakthrough['conditions']:
        print(f"    → {cond}")
    
    # 3. 120F中轨分析
    print(f"\n【Step v4.2-3】120F中轨上移速度分析")
    print(f"{'─'*70}")
    print(f"  图片分析：'120F中轨在前两天上移不明显'")
    
    middle_trend = analyze_120f_middle_trend(df_120m, days=5)
    print(f"  {middle_trend['description']}")
    print(f"  对情景2的影响: {middle_trend['note_for_scenario2']}")
    
    # 4. 120F中轨跌破预警
    print(f"\n【Step v4.2-4】120F中轨跌破预警")
    print(f"{'─'*70}")
    print(f"  图片分析：'如果跌破120F中轨，就会更加复杂，等真的跌破了再来分析'")
    
    warn_middle = warn_120f_middle_break(df_120m)
    print(f"  {warn_middle['description']}")
    print(f"  建议: {warn_middle['action']}")
    
    # 5. 回踩更深双情景分析
    print(f"\n【Step v4.2-5】" + "="*50)
    print(f"  " + "🔥 回踩更深双情景分析（图片核心）".center(50))
    print(f"  " + "="*50)
    print(f"  图片分析：'这点略微苛刻，所以展开写一下潜在的回踩更深的情况'")
    
    pullback = analyze_deeper_pullback(df_30m, df_120m, df_5m, segment_data.get('30F'))
    print(f"\n  当前状态: {pullback['description']}")
    print(f"  建议: {pullback['recommendation']}")
    
    for key, sc in pullback['scenarios'].items():
        print(f"\n  ┌─【情景{key}】{sc['name']}")
        print(f"  │ 条件: {sc['condition']}")
        if 'pullback_target' in sc:
            print(f"  │ 回踩目标: {sc['pullback_target']}")
        if 'depth' in sc and sc.get('depth', 'N/A') != 'N/A':
            print(f"  │ 回踩深度: {sc['depth']}")
        if 'after_pullback' in sc:
            print(f"  │ 回踩后: {sc['after_pullback']}")
        if 'trigger' in sc:
            print(f"  │ 触发条件: {sc['trigger']}")
        if 'operation' in sc:
            print(f"  │ 应对: {sc['operation']}")
        if 'probability' in sc:
            print(f"  │ 概率: {sc['probability']}")
        if 'note' in sc:
            print(f"  │ 注意: {sc['note']}")
        if 'requirement' in sc:
            print(f"  │ 要求: {sc['requirement']}")
        print(f"  └─")
    
    # 6. X段高级分类
    print(f"\n【Step v4.2-6】X段高级分类")
    print(f"{'─'*70}")
    print(f"  图片分析：'30分钟级别出现X段，可以是3段上涨结构+X段+新上涨结构，也可以是5段上涨结构+X段+新上涨结构'")
    
    x_class = classify_x_segment_type(df_30m, df_120m, segment_data.get('30F'))
    if x_class['is_x']:
        print(f"  当前30F是X段: {x_class['description']}")
        print(f"  共性: {x_class['common_feature']}")
        print(f"  含义: {x_class['implication']}")
    else:
        print(f"  {x_class['description']}")
        print(f"  若后续出现X段，可能是：")
        print(f"    - 类型A: 3段+X+新（回踩120F中轨）")
        print(f"    - 类型B: 5段+X+新（回踩120F中轨）")
    
    # 7. 临盘应对策略（不主观判断）
    print(f"\n{'='*70}")
    print("【Step v4.2-7】临盘应对策略（不主观判断）")
    print(f"{'='*70}")
    print(f"  图片分析：'你们也不要有太多主观的判断，历史证明每次你们主观判断大多都会哇哇叫'")
    print(f"  原则：给出触发条件，不预测路径，根据实际走势执行操作")
    
    linpang = generate_linpang_strategy(levels_55, breakthrough, pullback, x_class)
    print(f"\n  📌 {linpang['principle']}")
    print(f"\n  触发条件清单（按优先级排序）：")
    
    for i, trig in enumerate(linpang['triggers'], 1):
        print(f"\n  {i}. 【{trig['name']}】")
        print(f"     条件: {trig['condition']}")
        print(f"     操作: {trig['action']}")
        print(f"     概率: {trig['probability']}")
        if 'note' in trig:
            print(f"     备注: {trig['note']}")
    
    # 8. 明日分时段策略（v4.2升级）
    print(f"\n{'='*70}")
    print("【Step v4.2-8】明日分时段策略（v4.2升级：不主观判断版）")
    print(f"{'='*70}")
    
    print(f"\n  📌 开盘前准备：")
    print(f"    • 记录关键价位：5F中轨={levels_middle['5F']['middle']:.2f}, 5F55={levels_55['5F']['ma55']:.2f}")
    print(f"    • 记录关键价位：30F中轨={levels_middle['30F']['middle']:.2f}, 30F55={levels_55['30F']['ma55']:.2f}")
    print(f"    • 记录关键价位：120F55={levels_55['120F']['ma55']:.2f}, 120F中轨={levels_middle['120F']['middle']:.2f}")
    
    print(f"\n  📌 开盘后30分钟内（9:30-10:00）：")
    print(f"    • 观察是否快速突破120F55线({levels_55['120F']['ma55']:.2f})")
    print(f"    • 是 → 持仓/加仓（触发条件1）")
    print(f"    • 否 → 进入观察模式，不判断路径")
    
    print(f"\n  📌 10:00-11:30：")
    print(f"    • 若回踩30F中轨({levels_middle['30F']['middle']:.2f})企稳 → 持仓")
    print(f"    • 若跌破30F中轨 → 减仓1/3（触发条件2预警）")
    
    print(f"\n  📌 13:00-14:30：")
    print(f"    • 若守住5F55线({levels_55['5F']['ma55']:.2f}) → 下午震荡/反弹")
    print(f"    • 若跌破5F55线 → 减仓1/2（触发条件3）")
    
    print(f"\n  📌 14:30-15:00：")
    print(f"    • 若收在5F中轨({levels_middle['5F']['middle']:.2f})上方 → 多头占优，持仓")
    print(f"    • 若收在下方 → 警惕路径C，准备明日应对")
    
    # 9. v4.1 基础分析（保留）
    print(f"\n{'='*70}")
    print("【附录】v4.1 基础分析（保留）")
    print(f"{'='*70}")
    
    # 套娃
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
    print(f"\n  套娃状态: {nesting['status']}")
    
    # 三路径（v4.1，对比v4.2）
    print(f"\n  v4.1三路径（对比）：")
    print(f"    A. 理想: 快速突破")
    print(f"    B. 震荡: 时间换空间（概率最高）")
    print(f"    C. 风险: 套娃断裂")
    
    print(f"\n  v4.2升级（图片分析细化）：")
    print(f"    快速突破路径（首选但苛刻）→ 若失败 → 情景1（回踩30F55）或情景2（X段回踩120F中轨）")
    print(f"    强调：不主观判断，临盘根据触发条件执行")
    
    print(f"\n📅 日期: {df_d['Date'].iloc[-1].date()}")
    print(f"v4.2 升级完成：根据图片复盘笔记优化，加入突破条件精细化、回踩双情景、X段分类、120F中轨分析、临盘应对")
    print("="*70)

if __name__ == "__main__":
    main()
