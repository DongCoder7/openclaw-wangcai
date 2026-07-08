#!/root/.openclaw/workspace/venv/bin/python3
"""
缠论分析 v4.1 - 完整版（含中轨传导链+分时段支撑）

v4.1 核心升级：
1. 中轨传导链分析（5F/15F/30F/60F中轨）
2. 分时段关键支撑（上午/下午/尾盘）
3. 联合支撑区含中轨共振
4. 55线+中轨双体系输出

v4.1 驱动：2026-06-16遗漏30F中轨支撑，用户原文：
"明天上午的支撑在30F中轨，下午的支撑在5F55线"
"如果跌破，多头短线悠着点，就是重新组织结构再寻求上涨了"
"如果明天下午5F55线持续支撑，那么大概率走强直至双日金叉下的30F主涨段特征"
"总而言之明天上午的支撑在30F中轨，下午的支撑在5F55线"
"下午日线金叉将正式度过，那么当心15F顶背离带来的回踩"
"这个回踩如果跌破5F55线就是解除120F极强的连锁反应"
"因为15F中轨和5F55线位置差不太多"
"这个连锁反应可以回踩至30F55线出现新的结构，也可以出现面向120F中轨的X段回踩"
"所以明天其实是多头的谨慎区间"
"相反如果明天下午5F55线持续支撑，那么大概率走强直至双日金叉下的30F主涨段特征"
"我们没有方法知道Warsh会讲什么，也没有办法阻止别人提前博弈避险"
"就像上周五没有办法阻止A股资金避险SpaceX干崩美股一样"
"只能说如果是平安夜，后面会涨回来，这就是宽幅震荡"
"细节上，昨天的15F主涨段已经跌破3F中轨以结束"
"如果明天早盘无法突破3F55线且跌破15F中轨，大概率会在30F中轨支撑"
"在早盘再走出一段15F级别上涨"
"技术上，今天还在日线金叉窗口内，上涨后遇到了120F55线的明显阻力"
"明天将过渡到120F极强形态，但是日线金叉窗口也将度过"

Summary:
- 今天还在日线金叉窗口内，上涨后遇到了120F55线的明显阻力
- 明天将过渡到120F极强形态，但日线金叉窗口也将度过
- 上午支撑在30F中轨，下午支撑在5F55线
- 如果跌破5F55线，连锁反应可能回踩30F55线或面向120F中轨的X段回踩
- 明天是多头的谨慎区间
- 如果5F55线持续支撑，可能走强直至双日金叉下的30F主涨段
- 技术上昨天15F主涨段已跌破3F中轨结束
- 如果早盘无法突破3F55线且跌破15F中轨，大概率在30F中轨支撑，早盘再走出15F上涨
- 明天下午当心15F顶背离带来的回踩
- 15F中轨和5F55线位置差不太多，跌破5F55线就是解除120F极强的连锁反应
- 这是宽幅震荡，需要关注消息面风险
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from longport.openapi import Config, QuoteContext, Period, AdjustType

# =====================================================
# 多数据源获取（优先级：tdxrs > 长桥 > tushare pro > efinance）
# =====================================================
# 多数据源获取（优先级：tdxrs > 长桥 > tushare > efinance）
from data_fetcher import fetch_data, fetch_longbridge
# =====================================================

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
# v4.1: 主涨段判定
# =====================================================

def analyze_main_trend_segment(df, level_name='30F'):
    """主涨段判定"""
    if len(df) < 55:
        return {'is_main_trend': False, 'description': '数据不足'}
    
    p = float(df['Close'].iloc[-1])
    m55 = float(ma(df, 55).iloc[-1])
    md = macd(df)['macd'].iloc[-1]
    
    if p > m55 and md > 0:
        return {'is_main_trend': True, 'description': '主涨段（价格>55线且MACD>0）', 'strength': 'strong'}
    elif p > m55 and md < 0:
        return {'is_main_trend': False, 'description': '55线上方X段', 'strength': 'x_segment'}
    elif p < m55 and md < 0:
        return {'is_main_trend': False, 'description': '主跌段', 'strength': 'weak'}
    else:
        return {'is_main_trend': False, 'description': '55线下方X段', 'strength': 'x_segment'}

# =====================================================
# v4.1: 中轨传导链分析（核心新增）
# =====================================================

def analyze_middle_transmission(levels_data):
    """
    分析中轨传导链（v4.1核心新增）
    levels_data: dict of {level_name: {'price': p, 'middle': m20, 'macd': mc}}
    """
    chain = []
    
    # 从大到小检查中轨传导
    for name in ['60F', '30F', '15F', '5F']:
        if name in levels_data:
            d = levels_data[name]
            p = d['price']
            m = d['middle']
            
            if p > m:
                chain.append(f'{name}中轨支撑')
            else:
                chain.append(f'{name}中轨压制')
    
    # 传导方向判断
    transmission = ' → '.join(chain)
    
    # 判断传导方向
    # 如果小级别先跌破中轨，向大级别传导
    # 如果大级别中轨支撑，向小级别传导支撑
    
    return transmission

def get_middle_status(df, level_name):
    """获取中轨状态"""
    if len(df) < 20:
        return {'price': 0, 'middle': 0, 'status': '数据不足'}
    
    p = float(df['Close'].iloc[-1])
    b = boll(df, 20)
    middle = float(b['middle'].iloc[-1])
    
    if p > middle:
        status = '中轨上方'
    else:
        status = '中轨下方'
    
    return {'price': p, 'middle': middle, 'status': status, 'diff': p - middle}

# =====================================================
# v4.1: 分时段关键支撑分析（核心新增）
# =====================================================

def analyze_time_segment_support(middle_data, ma55_data):
    """
    分时段关键支撑分析（v4.1核心新增）
    返回上午/下午/尾盘的关键支撑
    """
    # 上午支撑：30F中轨 > 30F MA55 > 60F中轨
    morning_supports = []
    if '30F' in middle_data:
        morning_supports.append(('30F中轨', middle_data['30F']['middle']))
    if '30F' in ma55_data:
        morning_supports.append(('30F MA55', ma55_data['30F']['ma55']))
    if '60F' in middle_data:
        morning_supports.append(('60F中轨', middle_data['60F']['middle']))
    
    # 下午支撑：5F MA55 > 5F中轨 > 15F MA55
    afternoon_supports = []
    if '5F' in ma55_data:
        afternoon_supports.append(('5F MA55', ma55_data['5F']['ma55']))
    if '5F' in middle_data:
        afternoon_supports.append(('5F中轨', middle_data['5F']['middle']))
    if '15F' in ma55_data:
        afternoon_supports.append(('15F MA55', ma55_data['15F']['ma55']))
    
    # 尾盘支撑：5F中轨 > 15F中轨
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
    print("缠论分析 v4.1 - 完整版（120F+段数+中轨传导链+分时段支撑）")
    print("="*70)
    
    print("\n📡 从多数据源获取实时数据（优先级: tdxrs > 长桥 > tushare > efinance）...")
    
    # 获取各级别数据
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
    print("Step 2: 段数分解（3F/5F/15F）")
    print(f"{'='*70}")
    
    for name, df in [('3F', df_3m), ('5F', df_5m), ('15F', df_15m)]:
        if len(df) >= 20:
            seg = count_segments(df, name)
            print(f"\n  {name}段数分解:")
            print(f"    段数: {seg['segment_count']}")
            print(f"    当前: {seg['current']}")
            print(f"    结构: {seg['structure']}")
            print(f"    最近分型: {seg['peak_str']}")
    
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
    
    # Step 4: 主涨段判定
    print(f"\n{'='*70}")
    print("Step 4: 主涨段判定")
    print(f"{'='*70}")
    
    levels_trend = {}
    for name, df in [('15F', df_15m), ('30F', df_30m), ('60F', df_60m), ('120F', df_120m)]:
        if len(df) >= 55:
            trend = analyze_main_trend_segment(df, name)
            levels_trend[name] = trend
            print(f"  {name}: {trend['description']}")
    
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
    
    # =========================================================
    # v4.1 核心新增：Step 6 - 55线+中轨思维
    # =========================================================
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
            
            if p > m55 and mc > 0: st = '✅ 主涨段'
            elif p < m55 and mc < 0: st = '❌ 主跌段'
            elif p > m55 and mc < 0: st = '⚠️ 55线上方X段'
            elif p < m55 and mc > 0: st = '⚠️ 55线下方X段'
            else: st = '中性'
            
            levels_55[name] = {'price': p, 'ma55': m55, 'macd': mc, 'structure': st}
            print(f"  {name} MA55: 价{p:.2f} vs MA55={m55:.2f} | {st}")
        
        # v4.1: 计算中轨
        if len(df) >= 20:
            middle_status = get_middle_status(df, name)
            levels_middle[name] = middle_status
            print(f"  {name} 中轨: 价{middle_status['price']:.2f} vs 中轨={middle_status['middle']:.2f} | {middle_status['status']} (差{middle_status['diff']:.2f})")
    
    # =========================================================
    # v4.1 核心新增：Step 7 - 中轨传导链
    # =========================================================
    print(f"\n{'='*70}")
    print("Step 7: 中轨传导链分析（v4.1核心新增）")
    print(f"{'='*70}")
    
    transmission = analyze_middle_transmission(levels_middle)
    print(f"  中轨传导链: {transmission}")
    
    # 详细分析每个级别的中轨
    print(f"\n  中轨支撑矩阵:")
    for name in ['5F', '15F', '30F', '60F']:
        if name in levels_middle:
            d = levels_middle[name]
            print(f"    {name}: 当前价{d['price']:.2f} vs 中轨{d['middle']:.2f} | {d['status']} | 差{d['diff']:.2f}")
    
    # 中轨传导方向判断
    print(f"\n  传导方向判断:")
    # 检查小级别是否向大级别传导
    if '5F' in levels_middle and '15F' in levels_middle:
        if levels_middle['5F']['price'] < levels_middle['5F']['middle']:
            print(f"    ⚠️ 5F已跌破中轨 → 可能向15F传导")
            if levels_middle['15F']['price'] < levels_middle['15F']['middle']:
                print(f"    ⚠️ 15F也已跌破中轨 → 向30F传导")
                if '30F' in levels_middle and levels_middle['30F']['price'] < levels_middle['30F']['middle']:
                    print(f"    🔴 30F也跌破中轨 → 日内支撑失效，测试MA55")
                else:
                    print(f"    🟡 30F中轨仍支撑 → 30F是第一支撑")
    
    # =========================================================
    # v4.1 核心新增：Step 8 - 联合支撑区（含中轨共振）
    # =========================================================
    print(f"\n{'='*70}")
    print("Step 8: 联合支撑/压制区（v4.1含中轨共振）")
    print(f"{'='*70}")
    
    # MA55联合支撑
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
    
    # =========================================================
    # v4.1 核心新增：Step 9 - 分时段关键支撑
    # =========================================================
    print(f"\n{'='*70}")
    print("Step 9: 分时段关键支撑（v4.1核心新增）")
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
    
    # 基于实际数据的判断
    print(f"\n  📊 基于当前数据的判断:")
    if '30F' in levels_middle:
        m30 = levels_middle['30F']['middle']
        p = levels_middle['30F']['price']
        if p > m30:
            print(f"    ✅ 当前价{p:.2f}在30F中轨{m30:.2f}上方 → 上午若回踩{m30:.2f}有支撑")
        else:
            print(f"    ⚠️ 当前价{p:.2f}已跌破30F中轨{m30:.2f} → 上午支撑失效，测试MA55")
    
    if '5F' in levels_55:
        m55_5 = levels_55['5F']['ma55']
        p = levels_55['5F']['price']
        if p > m55_5:
            print(f"    ✅ 当前价{p:.2f}在5F MA55{m55_5:.2f}上方 → 下午若守住{m55_5:.2f}有支撑")
        else:
            print(f"    ⚠️ 当前价{p:.2f}已跌破5F MA55{m55_5:.2f} → 下午支撑失效")
    
    # =========================================================
    # Step 10: 传导链
    # =========================================================
    print(f"\n{'='*70}")
    print("Step 10: 级别传导链")
    print(f"{'='*70}")
    
    chain_data = {}
    for name in levels_macd:
        chain_data[name] = levels_macd[name]
        if name in levels_trend:
            chain_data[name]['is_main_trend'] = levels_trend[name]['is_main_trend']
    
    chain_desc = analyze_transmission_chain(chain_data)
    print(f"  传导链: {chain_desc}")
    
    # =========================================================
    # Step 11: 时间窗口
    # =========================================================
    print(f"\n{'='*70}")
    print("Step 11: 时间窗口估算")
    print(f"{'='*70}")
    
    tw = estimate_time_window(df_d, df_bid)
    print(f"  {tw['description']}")
    
    # =========================================================
    # Step 12: 明日策略（v4.1升级：含分时段支撑）
    # =========================================================
    print(f"\n{'='*70}")
    print("Step 12: 明日策略（v4.1含分时段支撑）")
    print(f"{'='*70}")
    
    p = float(df_d['Close'].iloc[-1])
    print(f"\n  当前收盘: {p:.2f}")
    
    if len(df_120m) >= 55:
        l120_55 = float(ma(df_120m, 55).iloc[-1])
        l120_macd = float(macd(df_120m)['macd'].iloc[-1])
        print(f"  120F MA55: {l120_55:.2f}")
        print(f"  120F MACD: {l120_macd:.2f}")
    
    # v4.1: 分时段策略
    print(f"\n  📌 核心判断:")
    print(f"    120F级别是战略锚点，明日关键看是否突破/受阻120F55线")
    
    print(f"\n  📌 v4.1分时段策略:")
    
    print(f"\n    【上午时段 (9:30-11:30)】")
    if '30F' in levels_middle:
        m30 = levels_middle['30F']['middle']
        print(f"    • 第一支撑: 30F中轨 = {m30:.2f}")
        print(f"    • 若回踩{m30:.2f}企稳 + 底背离 → 试多/持仓")
        print(f"    • 若跌破{m30:.2f} → 减仓1/3，等待30F MA55")
    
    if '15F' in levels_middle:
        m15 = levels_middle['15F']['middle']
        p15 = levels_middle['15F']['price']
        if p15 < m15:
            print(f"    ⚠️ 15F已跌破中轨({m15:.2f}) → 上午偏弱，警惕继续下探")
    
    print(f"\n    【下午时段 (13:00-14:30)】")
    if '5F' in levels_55:
        m55_5 = levels_55['5F']['ma55']
        print(f"    • 第一支撑: 5F MA55 = {m55_5:.2f}")
        print(f"    • 若守住{m55_5:.2f} → 下午维持震荡/反弹")
        print(f"    • 若跌破{m55_5:.2f} → 测试5F中轨/15F MA55")
    
    print(f"\n    【尾盘时段 (14:30-15:00)】")
    if '5F' in levels_middle:
        m5 = levels_middle['5F']['middle']
        print(f"    • 关键: 收在5F中轨({m5:.2f})上方 → 多头占优")
    
    print(f"\n  📌 持仓者:")
    if len(df_120m) >= 55:
        l120_55 = ma(df_120m, 55).iloc[-1]
        print(f"    • 若上冲120F55线({l120_55:.2f})附近受压 → 减仓")
        print(f"    • 若突破120F55线 + 120F MACD转正 → 加仓")
    print(f"    • 5F55线/3F中轨不应有效跌破")
    print(f"    • 跌破意味着120F极强失败，15分钟不是X段而是带结构回踩")
    
    print(f"\n  📌 空仓者:")
    print(f"    • 等待120F传导确认或回踩15F/30F X段")
    
    print(f"\n  📌 时间窗口:")
    print(f"    • 日线金叉窗口正常会在后天中午左右度过")
    print(f"    • 防止空头在日线金叉窗口或120F极强窗口后的反扑")
    
    # v4.1: 补充原文金句
    print(f"\n  📌 v4.1原文验证:")
    print(f"    • '明天上午的支撑在30F中轨' → 30F中轨是上午第一支撑")
    print(f"    • '下午的支撑在5F55线' → 5F MA55是下午第一支撑")
    print(f"    • '如果跌破5F55线就是解除120F极强的连锁反应' → 5F55线是120F极强解除的触发点")
    print(f"    • '15F中轨和5F55线位置差不太多' → 两者接近，形成阶梯支撑")
    
    print(f"\n📅 日期: {df_d['Date'].iloc[-1].date()}")
    print("="*70)

if __name__ == "__main__":
    main()
