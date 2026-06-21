#!/root/.openclaw/workspace/venv/bin/python3
"""
缠论分析 v4.0 - 修复版（120F完整+段数分解+X段识别+时间窗口）
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
# v4.0: 段数分解（分型→笔→线段）
# =====================================================

def find_local_extrema(df, window=5):
    """
    找局部高点和低点（分型）
    window=5: 检查前后各2根K线，确保更显著的顶底
    """
    highs = df['High'].values
    lows = df['Low'].values
    n = len(df)
    
    peaks = []  # (index, type, price, date)
    
    for i in range(window, n - window):
        # 顶分型: 当前高点 >= 前后window根K线的高点
        is_top = True
        for j in range(1, window + 1):
            if highs[i] < highs[i-j] or highs[i] < highs[i+j]:
                is_top = False
                break
        
        if is_top:
            peaks.append((i, 'top', highs[i], df['Date'].iloc[i]))
            continue
        
        # 底分型: 当前低点 <= 前后window根K线的低点
        is_bottom = True
        for j in range(1, window + 1):
            if lows[i] > lows[i-j] or lows[i] > lows[i+j]:
                is_bottom = False
                break
        
        if is_bottom:
            peaks.append((i, 'bottom', lows[i], df['Date'].iloc[i]))
    
    return peaks

def merge_extrema(peaks, min_distance=5):
    """
    合并距离太近的分型
    保留更极值的
    """
    if not peaks:
        return []
    
    merged = [peaks[0]]
    for p in peaks[1:]:
        last = merged[-1]
        # 如果类型相同且距离太近，合并
        if p[1] == last[1] and p[0] - last[0] < min_distance:
            if p[1] == 'top' and p[2] > last[2]:
                merged[-1] = p
            elif p[1] == 'bottom' and p[2] < last[2]:
                merged[-1] = p
        else:
            merged.append(p)
    
    return merged

def count_segments(df, level_name='15F'):
    """
    段数统计（基于分型→笔→线段）
    """
    if len(df) < 10:
        return {'segment_count': 0, 'current': 'unknown', 'description': '数据不足'}
    
    # 根据级别调整窗口大小
    window_map = {'3F': 3, '5F': 5, '15F': 5, '30F': 5, '60F': 3, '120F': 3}
    window = window_map.get(level_name, 5)
    
    peaks = find_local_extrema(df, window=window)
    peaks = merge_extrema(peaks, min_distance=window)
    
    if not peaks:
        return {'segment_count': 0, 'current': 'unknown', 'description': '未找到分型'}
    
    # 统计段数（顶底交替）
    valid_peaks = []
    for p in peaks:
        if not valid_peaks or p[1] != valid_peaks[-1][1]:
            valid_peaks.append(p)
    
    segment_count = len(valid_peaks) - 1
    
    # 当前段状态
    last_peak = valid_peaks[-1]
    if last_peak[1] == 'top':
        current = f'第{segment_count + 1}段up运行中（从{valid_peaks[-2][2]:.2f}到{last_peak[2]:.2f}）' if len(valid_peaks) >= 2 else 'up运行中'
    else:
        current = f'第{segment_count + 1}段down运行中（从{valid_peaks[-2][2]:.2f}到{last_peak[2]:.2f}）' if len(valid_peaks) >= 2 else 'down运行中'
    
    # 段结构描述
    if segment_count <= 2:
        structure = '简单结构（1-2段，未形成中枢）'
    elif segment_count <= 4:
        structure = '标准盘整（3-4段，1个中枢）'
    elif segment_count <= 6:
        structure = '标准趋势（5-6段，2个中枢）'
    else:
        structure = f'复杂结构（{segment_count}段，中枢扩展或更大级别）'
    
    # 显示最近的分型
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
# v4.0: X段判定（3条件）
# =====================================================

def analyze_x_segment(df_current, df_upper, current_name='15F', upper_name='30F'):
    """
    X段判定 (v4.0)
    
    条件1: 复合结构（前段+X段+后段）
    条件2: 起点=前段最高点
    条件3: 终点=回踩N+1级别中轨
    
    后验确认: 突破N级别55线 + 不创新低
    """
    if len(df_current) < 55 or len(df_upper) < 20:
        return {'is_x_segment': False, 'description': '数据不足'}
    
    p = df_current['Close'].iloc[-1]
    m55 = ma(df_current, 55).iloc[-1]
    m_upper = ma(df_upper, 20).iloc[-1]  # 用MA20作为中轨近似
    
    md = macd(df_current)['macd'].iloc[-1]
    md_upper = macd(df_upper)['macd'].iloc[-1]
    
    # X段判定: 价格>55线但MACD<0，或价格<55线但MACD>0
    is_x = (p > m55 and md < 0) or (p < m55 and md > 0)
    
    if is_x:
        if p > m55 and md < 0:
            desc = '{} 55线上方X段（价格>55线但MACD<0）'.format(current_name)
        else:
            desc = '{} 55线下方X段（价格<55线但MACD>0）'.format(current_name)
        
        # 检查是否突破55线（后验确认）
        if p > m55:
            confirm = '已突破55线，等待不创新低确认'
        else:
            confirm = '被55线压制，X段可能变异为下跌段'
    else:
        desc = '{} 非X段'.format(current_name)
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
# v4.0: 主涨段判定
# =====================================================

def analyze_main_trend_segment(df, level_name='30F'):
    """主涨段判定"""
    if len(df) < 55:
        return {'is_main_trend': False, 'description': '数据不足'}
    
    p = df['Close'].iloc[-1]
    m55 = ma(df, 55).iloc[-1]
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
# v4.0: 传导链分析
# =====================================================

def analyze_transmission_chain(levels_data):
    """
    分析级别传导链
    levels_data: dict of {level_name: {'macd': value, 'price': p, 'ma55': m55}}
    """
    # 从大到小检查传导
    chain = []
    
    # 双日
    if '双日' in levels_data:
        dd = levels_data['双日']
        if dd['macd'] > 0:
            chain.append('双日MACD>0')
        else:
            chain.append('双日MACD<0（极弱）')
    
    # 120F
    if '120F' in levels_data:
        l120 = levels_data['120F']
        if l120['macd'] > 0:
            chain.append('120F极强')
        else:
            chain.append('120F非极强')
    
    # 60F
    if '60F' in levels_data:
        l60 = levels_data['60F']
        if l60['macd'] > 0:
            chain.append('60F强/极强')
        else:
            chain.append('60F弱')
    
    # 30F
    if '30F' in levels_data:
        l30 = levels_data['30F']
        if l30['is_main_trend']:
            chain.append('30F主涨段')
        else:
            chain.append('30F非主涨段')
    
    # 15F
    if '15F' in levels_data:
        l15 = levels_data['15F']
        if l15.get('macd', 0) > 0:
            chain.append('15F MACD>0')
        else:
            chain.append('15F MACD<0')
    
    # 5F
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
    """
    估算日线MACD金叉时间窗口
    基于当前DIF/DEA的差值和趋势
    """
    if len(df_daily) < 30:
        return {'is_open': False, 'description': '数据不足'}
    
    md = macd(df_daily)
    dif = md['dif'].iloc[-1]
    dea = md['dea'].iloc[-1]
    
    # 计算DIF-DEA差值的变化速度
    dif_dea_diff = dif - dea
    
    if dif > dea:
        return {'is_open': True, 'description': '日线MACD已金叉，时间窗口开启'}
    
    # 估算还需要多少根K线才能金叉
    # 简单线性外推（不够精确，仅供参考）
    if len(md['dif']) >= 3:
        dif_trend = md['dif'].iloc[-1] - md['dif'].iloc[-3]
        dea_trend = md['dea'].iloc[-1] - md['dea'].iloc[-3]
        
        if dif_trend > dea_trend:
            # DIF追赶DEA中
            gap = dea - dif
            closing_speed = (dif_trend - dea_trend) / 2  # 每根K线的追赶速度
            if closing_speed > 0:
                klines_needed = gap / closing_speed
                days_needed = klines_needed  # 日线级别
                
                if days_needed <= 1:
                    return {'is_open': False, 'description': '日线MACD即将金叉（1天内）'}
                elif days_needed <= 3:
                    return {'is_open': False, 'description': '日线MACD金叉窗口临近（{}天内）'.format(int(days_needed))}
                else:
                    return {'is_open': False, 'description': '日线MACD死叉中，金叉窗口还需约{}天'.format(int(days_needed))}
    
    return {'is_open': False, 'description': '日线MACD死叉中，时间窗口未开启'}

# =====================================================
# 主程序
# =====================================================

def main():
    print("="*70)
    print("缠论分析 v4.0 - 修复版（120F完整+段数分解+X段+时间窗口）")
    print("="*70)
    
    print("\n📡 从长桥获取实时数据...")
    
    # 获取各级别数据
    df_1m = fetch_longbridge('000001.SH', '1m', 1000)
    df_2m = fetch_longbridge('000001.SH', '2m', 500)   # 用于3F合成
    df_3m = fetch_longbridge('000001.SH', '3m', 334)   # 直接获取3F
    df_5m = fetch_longbridge('000001.SH', '5m', 1000)
    df_10m = fetch_longbridge('000001.SH', '10m', 500) # 用于15F合成
    df_15m = fetch_longbridge('000001.SH', '15m', 334) # 直接获取15F
    df_30m = fetch_longbridge('000001.SH', '30m', 167) # 直接获取30F
    df_60m = fetch_longbridge('000001.SH', '60m', 84)  # 直接获取60F
    df_120m_raw = fetch_longbridge('000001.SH', '120m', 100) # 多取一些，过滤部分K线
    df_d = fetch_longbridge('000001.SH', '1d', 120)    # 日线
    
    # 修复120F：Longbridge返回3根/天（含15:00部分K线），标准应为2根/天
    # 过滤掉15:00的部分K线（只有几分钟数据，不是完整的120分钟）
    from datetime import time as dt_time
    df_120m = df_120m_raw[df_120m_raw['Date'].dt.time != dt_time(15, 0, 0)].reset_index(drop=True)
    
    print(f"  120F原始: {len(df_120m_raw)}根, 过滤15:00后: {len(df_120m)}根")
    
    # 如果过滤后不够55根，说明数据量不足，用原始数据（但标记警告）
    if len(df_120m) < 55:
        print(f"  ⚠️ 120F过滤后仅{len(df_120m)}根(<55)，回退到原始数据")
        df_120m = df_120m_raw.tail(55).reset_index(drop=True)
    
    # 合成双日
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
    # 15F vs 30F
    x15 = analyze_x_segment(df_15m, df_30m, '15F', '30F')
    x_segments['15F'] = x15
    print(f"  {x15['description']}")
    print(f"    确认: {x15['confirmation']}")
    
    # 30F vs 60F
    x30 = analyze_x_segment(df_30m, df_60m, '30F', '60F')
    x_segments['30F'] = x30
    print(f"  {x30['description']}")
    print(f"    确认: {x30['confirmation']}")
    
    # 120F vs 日线
    if len(df_120m) >= 55:
        x120 = analyze_x_segment(df_120m, df_d, '120F', '日线')
        x_segments['120F'] = x120
        print(f"  {x120['description']}")
        print(f"    确认: {x120['confirmation']}")
    
    # 日线 vs 双日
    if len(df_bid) >= 55:
        xd = analyze_x_segment(df_d, df_bid, '日线', '双日')
        x_segments['日线'] = xd
        print(f"  {xd['description']}")
        print(f"    确认: {xd['confirmation']}")
    
    # Step 6: 55线思维
    print(f"\n{'='*70}")
    print("Step 6: 55线思维")
    print(f"{'='*70}")
    
    levels_55 = {}
    for name, df in [('5F', df_5m), ('15F', df_15m), ('30F', df_30m), ('60F', df_60m), ('120F', df_120m), ('日线', df_d), ('双日', df_bid)]:
        if len(df) >= 55:
            p = df['Close'].iloc[-1]
            m55 = ma(df, 55).iloc[-1]
            mc = macd(df)['macd'].iloc[-1]
            
            if p > m55 and mc > 0: st = '✅ 主涨段'
            elif p < m55 and mc < 0: st = '❌ 主跌段'
            elif p > m55 and mc < 0: st = '⚠️ 55线上方X段'
            elif p < m55 and mc > 0: st = '⚠️ 55线下方X段'
            else: st = '中性'
            
            levels_55[name] = {'price': p, 'ma55': m55, 'macd': mc, 'structure': st}
            print(f"  {name}: 价{p:.2f} vs MA55={m55:.2f} | {st}")
    
    # Step 7: 联合支撑/压制区
    print(f"\n{'='*70}")
    print("Step 7: 联合支撑/压制区")
    print(f"{'='*70}")
    
    if len(df_d) >= 55 and len(df_bid) >= 55:
        d55 = ma(df_d, 55).iloc[-1]
        b55 = ma(df_bid, 55).iloc[-1]
        db = boll(df_d)
        bb = boll(df_bid)
        
        diff = abs(d55 - b55)
        strength = '极强' if diff < 5 else ('强' if diff < 20 else '中等')
        print(f"  🛡️ {strength}联合支撑: 日线55={d55:.2f} vs 双日55={b55:.2f} (差{diff:.2f})")
        
        if len(df_bid) >= 20:
            diffm = abs(db['middle'].iloc[-1] - bb['middle'].iloc[-1])
            strength = '极强' if diffm < 5 else ('强' if diffm < 20 else '中等')
            print(f"  ⛰️ {strength}联合压制: 日线中轨={db['middle'].iloc[-1]:.2f} vs 双日中轨={bb['middle'].iloc[-1]:.2f} (差{diffm:.2f})")
    
    # 120F MA55
    if len(df_120m) >= 55:
        l120_55 = ma(df_120m, 55).iloc[-1]
        l120_p = df_120m['Close'].iloc[-1]
        print(f"  📍 120F MA55: {l120_55:.2f} (当前价{l120_p:.2f})")
    
    # Step 8: 传导链
    print(f"\n{'='*70}")
    print("Step 8: 级别传导链")
    print(f"{'='*70}")
    
    # 构建传导链数据
    chain_data = {}
    for name in levels_macd:
        chain_data[name] = levels_macd[name]
        if name in levels_trend:
            chain_data[name]['is_main_trend'] = levels_trend[name]['is_main_trend']
    
    chain_desc = analyze_transmission_chain(chain_data)
    print(f"  传导链: {chain_desc}")
    
    # Step 9: 时间窗口
    print(f"\n{'='*70}")
    print("Step 9: 时间窗口估算")
    print(f"{'='*70}")
    
    tw = estimate_time_window(df_d, df_bid)
    print(f"  {tw['description']}")
    
    # Step 10: 明日策略
    print(f"\n{'='*70}")
    print("Step 10: 明日策略（基于120F战略级别）")
    print(f"{'='*70}")
    
    p = df_d['Close'].iloc[-1]
    print(f"\n  当前收盘: {p:.2f}")
    
    if len(df_120m) >= 55:
        l120_55 = ma(df_120m, 55).iloc[-1]
        l120_macd = macd(df_120m)['macd'].iloc[-1]
        print(f"  120F MA55: {l120_55:.2f}")
        print(f"  120F MACD: {l120_macd:.2f}")
    
    # 策略输出
    print(f"\n  📌 核心判断:")
    print(f"    120F级别是战略锚点，明日关键看是否突破/受阻120F55线")
    
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
    
    print(f"\n📅 日期: {df_d['Date'].iloc[-1].date()}")
    print("="*70)

if __name__ == "__main__":
    main()
