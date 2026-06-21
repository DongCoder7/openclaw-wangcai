#!/root/.openclaw/workspace/venv/bin/python3
"""
缠论多级别联立分析系统 v3.5
更新日期: 2026-06-09

v3.5 核心升级 (基于SKILL.md v3.5方法论):
  1. 【120F级别核心分析】120分钟=2小时K线，日线内部结构的核心观察级别
  2. 【X段识别】55线上方X段=价格>MA55+MACD<0，下方X段=价格<MA55+MACD>0
  3. 【5F套娃结构】5F站稳但30F主跌→小心是X段，套娃循环继续
  4. 【双周/55周线】双周55线=55周线=终极牛熊分界线
  5. 保留v3.4: 底背离/顶背离检测+信号优先级+情景推演
  6. 保留v3.3: 联合区/假突破/二买二卖/传导链/双日/时间窗口
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import subprocess

# =====================================================
# 数据获取 & 级别合成 (同v3.3)
# =====================================================

def fetch_data(file_path):
    df = pd.read_csv(file_path)
    df['Date'] = pd.to_datetime(df['Date'])
    return df

def synthesize_kline(df_source, n, name=""):
    df = df_source.copy()
    df['Group'] = df.index // n
    df_target = df.groupby('Group').agg({
        'Date': 'last', 'Open': 'first', 'High': 'max',
        'Low': 'min', 'Close': 'last', 'Volume': 'sum'
    }).reset_index(drop=True)
    return df_target

# =====================================================
# v3.3: 数据完整性检查
# =====================================================

def check_data_integrity(df, level_name='未知'):
    n = len(df)
    integrity = {
        'level': level_name,
        'total_rows': n,
        'ma55_ok': n >= 55,
        'boll_ok': n >= 20,
        'ma233_ok': n >= 233,
        'usable': n >= 55,
        'warning': None
    }
    if n < 55:
        integrity['warning'] = f'{level_name}数据仅{n}根(<55), MA55计算失真, 不可用于决策!'
    elif n < 20:
        integrity['warning'] = f'{level_name}数据仅{n}根(<20), 布林带指标失真!'
    return integrity

# =====================================================
# 指标计算
# =====================================================

def calc_all_indicators(df):
    df = df.copy()
    df['BOLL_MID'] = df['Close'].rolling(window=20, min_periods=1).mean()
    df['BOLL_STD'] = df['Close'].rolling(window=20, min_periods=1).std()
    df['BOLL_UP'] = df['BOLL_MID'] + df['BOLL_STD'] * 2
    df['BOLL_DOWN'] = df['BOLL_MID'] - df['BOLL_STD'] * 2
    ema_fast = df['Close'].ewm(span=12, adjust=False).mean()
    ema_slow = df['Close'].ewm(span=26, adjust=False).mean()
    df['MACD'] = ema_fast - ema_slow
    df['MACD_Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
    df['MACD_Hist'] = df['MACD'] - df['MACD_Signal']
    df['MA5'] = df['Close'].rolling(window=5, min_periods=1).mean()
    df['MA10'] = df['Close'].rolling(window=10, min_periods=1).mean()
    df['MA20'] = df['Close'].rolling(window=20, min_periods=1).mean()
    df['MA55'] = df['Close'].rolling(window=55, min_periods=1).mean()
    df['Vol_MA5'] = df['Volume'].rolling(window=5, min_periods=1).mean()
    df['Vol_MA20'] = df['Volume'].rolling(window=20, min_periods=1).mean()
    return df

# =====================================================
# 分型-笔-段识别
# =====================================================

def find_fractals(df):
    df = df.copy()
    n = len(df)
    df['top_fractal'] = False
    df['bottom_fractal'] = False
    for i in range(1, n - 1):
        if df['High'].iloc[i] > df['High'].iloc[i-1] and df['High'].iloc[i] > df['High'].iloc[i+1]:
            df.loc[df.index[i], 'top_fractal'] = True
        if df['Low'].iloc[i] < df['Low'].iloc[i-1] and df['Low'].iloc[i] < df['Low'].iloc[i+1]:
            df.loc[df.index[i], 'bottom_fractal'] = True
    return df

def find_strokes(df):
    df = find_fractals(df)
    strokes = []
    last = None
    for i in range(len(df)):
        if df['top_fractal'].iloc[i] or df['bottom_fractal'].iloc[i]:
            curr_type = 'top' if df['top_fractal'].iloc[i] else 'bottom'
            if last is None:
                last = {'idx': i, 'type': curr_type}
            else:
                if last['type'] != curr_type and i - last['idx'] >= 2:
                    direction = 'down' if last['type'] == 'top' else 'up'
                    strokes.append({
                        'start_idx': last['idx'], 'end_idx': i, 'direction': direction,
                        'start_price': df['High'].iloc[last['idx']] if last['type'] == 'top' else df['Low'].iloc[last['idx']],
                        'end_price': df['Low'].iloc[i] if curr_type == 'bottom' else df['High'].iloc[i]
                    })
                    last = {'idx': i, 'type': curr_type}
                elif last['type'] == curr_type:
                    if curr_type == 'top' and df['High'].iloc[i] > df['High'].iloc[last['idx']]:
                        last = {'idx': i, 'type': curr_type}
                    elif curr_type == 'bottom' and df['Low'].iloc[i] < df['Low'].iloc[last['idx']]:
                        last = {'idx': i, 'type': curr_type}
    return strokes

# =====================================================
# v3.4 核心新增: 底背离/顶背离检测
# =====================================================

def detect_divergence(df_level, level_name='30F', lookback=30):
    """
    底背离/顶背离检测 (v3.4核心)
    
    底背离: 价格创新低 + MACD未创新低 → 动能衰竭, 高胜率买点
    顶背离: 价格创新高 + MACD未创新高 → 动能衰竭, 高胜率卖点
    
    实战: 2026-05-28 "30F已经底背离, 60F有底背离雏形, 且背离位置在55日线/双日55线"
    → 30F底背离 + 60F底背离 + 联合支撑区4055-4058 = "4050附近先手胜率非常高"
    """
    if len(df_level) < lookback + 10:
        return {'usable': False, 'description': '数据不足'}
    
    recent = df_level.tail(lookback).copy().reset_index(drop=True)
    
    # 找局部低点和高点
    prices = recent['Close'].values
    lows = recent['Low'].values
    highs = recent['High'].values
    macds = recent['MACD'].values
    
    # 找两个显著低点（底背离）
    bottom_div = None
    top_div = None
    
    # 简化：找近期最低的两个低点
    min_idx = np.argmin(lows)
    min_price = lows[min_idx]
    min_macd = macds[min_idx]
    
    # 找前一个低点（在min_idx之前）
    if min_idx > 5:
        prev_lows = lows[:min_idx-3]
        prev_macds = macds[:min_idx-3]
        if len(prev_lows) > 5:
            prev_min_idx = np.argmin(prev_lows)
            prev_min_price = prev_lows[prev_min_idx]
            prev_min_macd = prev_macds[prev_min_idx]
            
            # 底背离：新低价格 + MACD未新低
            if min_price < prev_min_price * 0.998 and min_macd > prev_min_macd * 1.05:
                bottom_div = {
                    'type': '底背离',
                    'strength': abs(min_macd - prev_min_macd) / (abs(prev_min_macd) + 1e-9),
                    'price1': prev_min_price,
                    'price2': min_price,
                    'macd1': prev_min_macd,
                    'macd2': min_macd,
                    'description': f'{level_name}底背离: 价格{prev_min_price:.2f}→{min_price:.2f}(创新低), MACD{prev_min_macd:.2f}→{min_macd:.2f}(未创新低)'
                }
    
    # 找两个显著高点（顶背离）
    max_idx = np.argmax(highs)
    max_price = highs[max_idx]
    max_macd = macds[max_idx]
    
    if max_idx > 5:
        prev_highs = highs[:max_idx-3]
        prev_macds = macds[:max_idx-3]
        if len(prev_highs) > 5:
            prev_max_idx = np.argmax(prev_highs)
            prev_max_price = prev_highs[prev_max_idx]
            prev_max_macd = prev_macds[prev_max_idx]
            
            # 顶背离：新高价格 + MACD未新高
            if max_price > prev_max_price * 1.002 and max_macd < prev_max_macd * 0.95:
                top_div = {
                    'type': '顶背离',
                    'strength': abs(max_macd - prev_max_macd) / (abs(prev_max_macd) + 1e-9),
                    'price1': prev_max_price,
                    'price2': max_price,
                    'macd1': prev_max_macd,
                    'macd2': max_macd,
                    'description': f'{level_name}顶背离: 价格{prev_max_price:.2f}→{max_price:.2f}(创新高), MACD{prev_max_macd:.2f}→{max_macd:.2f}(未创新高)'
                }
    
    result = {
        'level': level_name,
        'has_bottom_divergence': bottom_div is not None,
        'has_top_divergence': top_div is not None,
        'bottom': bottom_div,
        'top': top_div
    }
    
    if bottom_div:
        result['signal'] = '底背离'
        result['action'] = '建仓/加仓信号'
    elif top_div:
        result['signal'] = '顶背离'
        result['action'] = '减仓/清仓信号'
    else:
        result['signal'] = '无背离'
        result['action'] = '观望'
    
    return result

# =====================================================
# v3.4 核心新增: 多级别共振底背离分析
# =====================================================

def analyze_multi_level_divergence(divergence_results, unified_zone_result):
    """
    多级别共振底背离 + 联合支撑区 = 高胜率买点
    
    优先级: 底背离+联合支撑区 > 二卖成立
    """
    bottom_levels = []
    top_levels = []
    
    for level, div in divergence_results.items():
        if div.get('has_bottom_divergence'):
            bottom_levels.append(level)
        if div.get('has_top_divergence'):
            top_levels.append(level)
    
    # 检查是否在联合支撑区附近
    near_support = False
    support_zone = None
    if unified_zone_result and unified_zone_result.get('unified_zones'):
        for z in unified_zone_result['unified_zones']:
            if '支撑' in z.get('type', ''):
                near_support = True
                support_zone = z
                break
    
    # 共振判断
    bottom_count = len(bottom_levels)
    top_count = len(top_levels)
    
    if bottom_count >= 2 and near_support:
        return {
            'signal': '极高胜率买点',
            'type': '多级别共振底背离+联合支撑区',
            'bottom_levels': bottom_levels,
            'support_zone': support_zone,
            'description': f'{"/".join(bottom_levels)}底背离共振 + 联合支撑区 = 极高胜率买点',
            'action': '建仓/加仓',
            'priority': 'P0'
        }
    elif bottom_count >= 2:
        return {
            'signal': '高胜率买点',
            'type': '多级别共振底背离',
            'bottom_levels': bottom_levels,
            'description': f'{"/".join(bottom_levels)}底背离共振',
            'action': '建仓/加仓',
            'priority': 'P1'
        }
    elif bottom_count == 1 and near_support:
        return {
            'signal': '高胜率买点',
            'type': '单级别底背离+联合支撑区',
            'bottom_levels': bottom_levels,
            'support_zone': support_zone,
            'description': f'{bottom_levels[0]}底背离 + 联合支撑区 = 高胜率买点',
            'action': '建仓/加仓',
            'priority': 'P1'
        }
    elif top_count >= 2:
        return {
            'signal': '高胜率卖点',
            'type': '多级别共振顶背离',
            'top_levels': top_levels,
            'description': f'{"/".join(top_levels)}顶背离共振',
            'action': '减仓/清仓',
            'priority': 'P0'
        }
    
    return {
        'signal': '无显著背离信号',
        'type': '观望',
        'bottom_levels': [],
        'top_levels': [],
        'action': '按其他信号操作',
        'priority': 'P3'
    }

# =====================================================
# v3.4 核心新增: 信号优先级判定
# =====================================================

def judge_signal_priority(divergence_result, second_buy_result, unified_zone_result, dual_day_status):
    """
    信号优先级判定 (v3.4核心)
    
    当多信号冲突时的裁决规则:
    P0: 底背离+联合支撑区 > 二卖成立
    P1: 顶背离+联合压制区 > 二买成立
    """
    # 检查多级别共振
    multi_div = analyze_multi_level_divergence(
        divergence_result if isinstance(divergence_result, dict) else {},
        unified_zone_result
    )
    
    priority = multi_div.get('priority', 'P3')
    signal = multi_div.get('signal', '无')
    
    # 如果有背离信号，优先使用
    if signal in ['极高胜率买点', '高胜率买点']:
        return {
            'final_signal': '买点',
            'priority': priority,
            'reason': multi_div['description'],
            'action': multi_div['action'],
            'source': '底背离+联合区',
            'override_second_buy': True,
            'override_second_sell': True  # 底背离终结二卖
        }
    elif signal == '高胜率卖点':
        return {
            'final_signal': '卖点',
            'priority': priority,
            'reason': multi_div['description'],
            'action': multi_div['action'],
            'source': '顶背离',
            'override_second_buy': True,  # 顶背离终结二买
            'override_second_sell': False
        }
    
    # 无背离时，使用二买/二卖
    has_second_buy = False
    has_second_sell = False
    for level, data in second_buy_result.items():
        if data.get('is_valid') and '二买' in data.get('type', ''):
            has_second_buy = True
        elif not data.get('is_valid') and '二卖失败' not in data.get('type', '') and ('二卖' in data.get('type', '') or '失败' in data.get('type', '')):
            has_second_sell = True
    
    if has_second_buy:
        return {
            'final_signal': '买点',
            'priority': 'P2',
            'reason': '二买成立',
            'action': '加仓',
            'source': '二买',
            'override_second_buy': False,
            'override_second_sell': False
        }
    elif has_second_sell:
        return {
            'final_signal': '卖点',
            'priority': 'P3',
            'reason': '二卖成立',
            'action': '减仓',
            'source': '二卖',
            'override_second_buy': False,
            'override_second_sell': False
        }
    
    return {
        'final_signal': '观望',
        'priority': 'P3',
        'reason': '无明确信号',
        'action': '观望',
        'source': '无',
        'override_second_buy': False,
        'override_second_sell': False
    }

# =====================================================
# v3.4 核心新增: 情景推演/路径分析
# =====================================================

def scenario_analysis(report):
    """
    情景推演/路径分析 (v3.4核心)
    
    基于当前多级别状态，推演明日三种可能走势:
    - 强势情景: 底背离确认+放量突破
    - 中性情景: 震荡蓄势+缓慢回升
    - 弱势情景: 无量反弹+二次探底
    """
    scenarios = []
    
    # 获取关键数据
    divergence = report.get('divergence', {})
    unified_zone = report.get('unified_zone', {})
    dual_day = report.get('dual_day', {})
    transmission = report.get('transmission_chain', {})
    
    has_bottom_div = any(d.get('has_bottom_divergence') for d in divergence.values() if isinstance(d, dict))
    has_top_div = any(d.get('has_top_divergence') for d in divergence.values() if isinstance(d, dict))
    
    # 联合支撑/压制区
    support_zone = None
    resistance_zone = None
    if unified_zone and 'unified_zones' in unified_zone:
        for z in unified_zone['unified_zones']:
            if '支撑' in z.get('type', ''):
                support_zone = z
            if '压制' in z.get('type', ''):
                resistance_zone = z
    
    # 双日状态
    dd_hist = dual_day.get('hist', 1.0) if isinstance(dual_day, dict) else 1.0
    dd_death_risk = dual_day.get('death_risk', False) if isinstance(dual_day, dict) else False
    
    # 传导链方向
    chain_dir = transmission.get('direction', 'neutral') if isinstance(transmission, dict) else 'neutral'
    
    # --- 强势情景 ---
    if has_bottom_div and support_zone:
        support_low = min(support_zone.get('value1', 0), support_zone.get('value2', 0))
        support_high = max(support_zone.get('value1', 0), support_zone.get('value2', 0))
        
        # 找压制区目标
        target = None
        if resistance_zone:
            target = min(resistance_zone.get('value1', 0), resistance_zone.get('value2', 0))
        
        scenarios.append({
            'name': '强势情景',
            'probability': '中等(40%)',
            'condition': '底背离确认 + 联合支撑守住 + 次日放量突破中轨',
            'path': f'回踩{support_low:.0f}-{support_high:.0f}支撑区 → 放量反弹 → 突破联合压制区 → 目标{int(target) if target else "前高"}',
            'trigger': '开盘守住支撑区 + 30分钟内站上1F55线 + MACD柱放大',
            'action': '加仓至满仓',
            'stop_loss': f'{support_low * 0.995:.0f}'
        })
    
    # --- 中性情景 ---
    scenarios.append({
        'name': '中性情景',
        'probability': '最高(50%)',
        'condition': '底背离后无量反弹 + 在联合区之间震荡',
        'path': '支撑区反弹 → 压制区遇阻 → 回落 → 再反弹（日内震荡）',
        'trigger': '量能萎缩 + 1F/3F在55线附近反复',
        'action': '高抛低吸，仓位不变',
        'stop_loss': f'跌破{support_zone["zone_range"][0] if support_zone else "支撑区"}' if support_zone else '跌破支撑区'
    })
    
    # --- 弱势情景 ---
    if dd_death_risk or chain_dir == 'down':
        scenarios.append({
            'name': '弱势情景',
            'probability': '较低(10%)',
            'condition': '底背离后无量反弹 → 二次探底 → 等待双日死叉窗口度过',
            'path': '小幅反弹 → 遇阻回落 → 跌破支撑区 → 新低 → 等待下一个时间窗口',
            'trigger': '反弹无量 + 30F55线压制 + 1F顶背离',
            'action': '反弹减仓，等待下一个买点',
            'stop_loss': '反弹高点'
        })
    
    # 确定主推情景
    if has_bottom_div and not dd_death_risk:
        primary = '强势情景' if len(scenarios) > 0 and scenarios[0]['name'] == '强势情景' else '中性情景'
    else:
        primary = '中性情景'
    
    return {
        'scenarios': scenarios,
        'primary_scenario': primary,
        'recommendation': f'主推: {primary}，{'建议底背离区域建仓' if has_bottom_div else '建议观望等待'}'
    }

# =====================================================
# v3.3: 假突破/骗炮识别
# =====================================================

def judge_fake_breakout(df_level, level_name='30F'):
    if len(df_level) < 3:
        return {'usable': False, 'description': '数据不足'}
    
    latest = df_level.iloc[-1]
    prev = df_level.iloc[-2]
    price = latest['Close']
    ma55 = latest['MA55']
    macd = latest['MACD']
    
    recent_hist = df_level['MACD_Hist'].tail(3).values
    is_expanding = len(recent_hist) >= 3 and all(abs(recent_hist[i]) >= abs(recent_hist[i-1]) for i in range(1, len(recent_hist)))
    
    prev_price = prev['Close']
    
    if prev_price < ma55 and price > ma55:
        if macd > 0 and is_expanding:
            return {'type': '真突破', 'is_fake': False, 'description': f'{level_name}真突破: 站上55线+MACD>0+柱放大', 'action': '追涨'}
        else:
            return {'type': '假突破(骗炮)', 'is_fake': True, 'description': f'{level_name}假突破: 站上55线但MACD<0或柱收敛', 'action': '不追涨'}
    
    if prev_price > ma55 and price < ma55:
        if macd < 0 and is_expanding:
            return {'type': '真跌破', 'is_fake': False, 'description': f'{level_name}真跌破: 跌破55线+MACD<0+柱放大', 'action': '止损'}
        else:
            return {'type': '假跌破', 'is_fake': True, 'description': f'{level_name}假跌破: 跌破55线但MACD>0或柱收敛', 'action': '不恐慌'}
    
    if price > ma55:
        return {'type': '55线上方运行', 'is_fake': False, 'description': f'{level_name}55线上方+MACD{"" if macd>0 else "<0"}', 'action': '持仓' if macd>0 else '警惕'}
    if price < ma55:
        return {'type': '55线下方运行', 'is_fake': False, 'description': f'{level_name}55线下方+MACD{"" if macd<0 else ">0"}', 'action': '清仓' if macd<0 else '关注买点'}
    return {'type': '胶着', 'is_fake': False, 'description': f'{level_name}55线附近', 'action': '观望'}

# =====================================================
# v3.3: 二买/二卖
# =====================================================

def identify_second_buy(strokes, level_name='30F'):
    if len(strokes) < 3:
        return {'usable': False, 'description': '笔数不足'}
    
    last_3 = strokes[-3:]
    directions = [s['direction'] for s in last_3]
    
    if directions == ['down', 'up', 'down']:
        first_down_low = min(last_3[0]['start_price'], last_3[0]['end_price'])
        second_down_low = min(last_3[2]['start_price'], last_3[2]['end_price'])
        if second_down_low > first_down_low:
            return {'type': '二买成立', 'is_valid': True, 'description': f'{level_name}二买成立', 'action': '加仓'}
        else:
            return {'type': '二买失败', 'is_valid': False, 'description': f'{level_name}二买失败: 创新低', 'action': '减仓'}
    
    if directions == ['up', 'down', 'up']:
        first_up_high = max(last_3[0]['start_price'], last_3[0]['end_price'])
        second_up_high = max(last_3[2]['start_price'], last_3[2]['end_price'])
        if second_up_high < first_up_high:
            return {'type': '二卖成立', 'is_valid': True, 'description': f'{level_name}二卖成立', 'action': '减仓'}
        else:
            return {'type': '二卖失败', 'is_valid': False, 'description': f'{level_name}二卖失败: 创新高', 'action': '持仓'}
    
    return {'type': '非二买二卖', 'is_valid': False, 'description': f'{level_name}最近3笔为{"-".join(directions)}', 'action': '观望'}

# =====================================================
# v3.3: 联合支撑/压制区
# =====================================================

def analyze_unified_zone(level_data_dict):
    zones = []
    pairs = [
        ('日线55线', 'MA55', '双日55线', 'MA55'),
        ('60F55线', 'MA55', '日线中轨', 'BOLL_MID'),
        ('30F55线', 'MA55', '60F中轨', 'BOLL_MID'),
        ('日线中轨', 'BOLL_MID', '双日中轨', 'BOLL_MID'),
    ]
    
    for name1, key1, name2, key2 in pairs:
        parts1 = name1.split('55线')[0] if '55线' in name1 else name1.replace('中轨','').replace('线','')
        parts2 = name2.split('55线')[0] if '55线' in name2 else name2.replace('中轨','').replace('线','')
        
        level1_key = None
        level2_key = None
        for k in level_data_dict.keys():
            if parts1 in k or k in parts1:
                level1_key = k
            if parts2 in k or k in parts2:
                level2_key = k
        
        if level1_key and level2_key and level1_key in level_data_dict and level2_key in level_data_dict:
            df1 = level_data_dict[level1_key]
            df2 = level_data_dict[level2_key]
            if len(df1) > 0 and len(df2) > 0:
                val1 = df1.iloc[-1][key1] if key1 in df1.columns else None
                val2 = df2.iloc[-1][key2] if key2 in df2.columns else None
                if val1 is not None and val2 is not None and val2 != 0:
                    diff = abs(val1 - val2)
                    diff_pct = diff / val2 * 100
                    
                    if diff < 5: strength = '极强联合'
                    elif diff < 10: strength = '强联合'
                    elif diff < 20: strength = '中等联合'
                    else: strength = None
                    
                    if strength:
                        zone_type = '联合支撑区' if '55线' in name1 and '55线' in name2 else '联合区'
                        if '中轨' in name2 and '55线' in name1:
                            zone_type = '联合压制区'
                        
                        zones.append({
                            'type': zone_type,
                            'name': f'{name1}+{name2}',
                            'value1': val1,
                            'value2': val2,
                            'diff': diff,
                            'strength': strength,
                            'zone_range': (min(val1, val2), max(val1, val2)),
                            'description': f'{zone_type}: {name1}({val1:.2f})与{name2}({val2:.2f})差值{diff:.2f}点({strength})'
                        })
    
    return {'unified_zones': zones, 'count': len(zones), 'has_strong_zone': any(z['strength'] in ['极强联合', '强联合'] for z in zones)}

# =====================================================
# v3.3: 级别传导链
# =====================================================

def analyze_transmission_chain(level_data_dict):
    chain = {'steps': [], 'direction': 'neutral', 'risk_level': 'low', 'description': ''}
    levels_to_check = ['1F', '3F', '5F', '15F', '30F', '60F', '日线', '双日']
    prev_status = None
    
    for lvl_name in levels_to_check:
        df = level_data_dict.get(lvl_name)
        if df is None or len(df) < 3:
            continue
        latest = df.iloc[-1]
        price = latest['Close']
        ma55 = latest.get('MA55', price)
        macd = latest.get('MACD', 0)
        status = 'above' if price > ma55 else 'below'
        
        if prev_status is not None:
            if prev_status == 'below' and status == 'below':
                chain['steps'].append({'level': lvl_name, 'status': f'{status}+macd_{"positive" if macd>0 else "negative"}', 'transmission': True, 'direction': 'down'})
            elif prev_status == 'above' and status == 'above':
                chain['steps'].append({'level': lvl_name, 'status': f'{status}+macd_{"positive" if macd>0 else "negative"}', 'transmission': True, 'direction': 'up'})
            else:
                chain['steps'].append({'level': lvl_name, 'status': f'{status}+macd_{"positive" if macd>0 else "negative"}', 'transmission': False, 'direction': 'mixed'})
        else:
            chain['steps'].append({'level': lvl_name, 'status': f'{status}+macd_{"positive" if macd>0 else "negative"}', 'transmission': False, 'direction': 'start'})
        prev_status = status
    
    down_steps = sum(1 for s in chain['steps'] if s.get('direction') == 'down')
    up_steps = sum(1 for s in chain['steps'] if s.get('direction') == 'up')
    
    if down_steps >= 3:
        chain['direction'] = 'down'
        chain['risk_level'] = 'high'
        chain['description'] = f'下跌传导链启动({down_steps}步共振)'
    elif up_steps >= 3:
        chain['direction'] = 'up'
        chain['risk_level'] = 'low'
        chain['description'] = f'上涨传导链启动({up_steps}步共振)'
    else:
        chain['description'] = '传导链未形成明确方向'
    
    return chain

# =====================================================
# v3.3: 双日级别
# =====================================================

def analyze_dual_day(df_dual_day):
    if df_dual_day is None or len(df_dual_day) < 3:
        return {'usable': False, 'description': '无双日数据'}
    
    latest = df_dual_day.iloc[-1]
    prev = df_dual_day.iloc[-2] if len(df_dual_day) > 1 else latest
    macd = latest.get('MACD', 0)
    signal = latest.get('MACD_Signal', 0)
    hist = latest.get('MACD_Hist', 0)
    prev_hist = prev.get('MACD_Hist', 0)
    
    death_cross_risk = hist > 0 and hist < 0.5 and macd > signal
    is_death_cross = hist < 0 and macd < signal
    is_golden_cross = prev.get('MACD', 0) < 0 and macd > 0
    
    if is_golden_cross:
        return {'status': '多头', 'trend': 'golden_cross', 'description': '双日MACD金叉', 'action': '持仓', 'death_risk': False, 'hist': hist}
    elif is_death_cross:
        return {'status': '空头', 'trend': 'death_cross', 'description': '双日MACD死叉', 'action': '清仓', 'death_risk': True, 'hist': hist}
    elif death_cross_risk:
        return {'status': '多头', 'trend': 'death_risk', 'description': f'双日MACD接近死叉 Hist={hist:.2f}', 'action': '警惕', 'death_risk': True, 'hist': hist}
    elif macd > 0 and hist > 0:
        return {'status': '多头', 'trend': 'bull', 'description': f'双日MACD多头 Hist={hist:.2f}', 'action': '持仓', 'death_risk': False, 'hist': hist}
    else:
        return {'status': '空头', 'trend': 'bear', 'description': f'双日MACD空头 Hist={hist:.2f}', 'action': '观望', 'death_risk': False, 'hist': hist}

# =====================================================
# v3.3: 时间窗口
# =====================================================

def judge_time_window(dual_day_status, transmission_chain):
    window = {'is_window_open': False, 'window_type': None, 'description': '', 'conditions': [], 'action': '观望'}
    
    if dual_day_status.get('trend') == 'death_cross':
        window['description'] = '双日MACD死叉，需等待3-5天修复'
        window['conditions'] = ['等待双日MACD金叉', '等待底背离+突破中轨']
        return window
    
    if dual_day_status.get('death_risk') and dual_day_status.get('hist', 1) > 0:
        window['description'] = '双日MACD接近死叉，修复需3-5天'
        window['conditions'] = ['观察是否死叉', '等待传导链逆转']
        return window
    
    if transmission_chain.get('direction') == 'down' and len(transmission_chain.get('steps', [])) >= 4:
        # 检查是否有底背离出现
        window['is_window_open'] = True
        window['window_type'] = '下跌后反弹窗口'
        window['description'] = '下跌传导链完成，等待底背离确认的时间窗口'
        window['conditions'] = ['底背离出现', '突破中轨确认', '放量阳线']
        window['action'] = '轻仓试多'
        return window
    
    if dual_day_status.get('trend') == 'golden_cross':
        window['is_window_open'] = True
        window['window_type'] = '正常操作窗口'
        window['description'] = '双日MACD金叉运行'
        window['action'] = '正常操作'
        return window
    
    if transmission_chain.get('direction') == 'up':
        window['is_window_open'] = True
        window['window_type'] = '上涨持仓窗口'
        window['description'] = '上涨传导链启动'
        window['action'] = '持仓'
        return window
    
    window['description'] = '无明确时间窗口'
    return window

# =====================================================
# v3.1+: MACD极强期
# =====================================================

def judge_macd_extreme(df_level, level_name='30F'):
    latest = df_level.iloc[-1]
    macd = latest['MACD']
    signal = latest['MACD_Signal']
    hist = latest['MACD_Hist']
    recent_hist = df_level['MACD_Hist'].tail(3).values
    is_expanding = len(recent_hist) >= 3 and all(abs(recent_hist[i]) >= abs(recent_hist[i-1]) for i in range(1, len(recent_hist)))
    
    is_up_extreme = macd > 0 and signal > 0 and is_expanding
    is_down_extreme = macd < 0 and signal < 0 and is_expanding
    
    if is_up_extreme:
        return {'is_extreme': True, 'direction': 'extreme_up', 'strength': min(abs(hist)/abs(macd)*100 if macd!=0 else 0, 100), 'description': f'{level_name} MACD极强(多头)'}
    elif is_down_extreme:
        return {'is_extreme': True, 'direction': 'extreme_down', 'strength': min(abs(hist)/abs(macd)*100 if macd!=0 else 0, 100), 'description': f'{level_name} MACD极强(空头)'}
    return {'is_extreme': False, 'direction': 'normal', 'strength': 0, 'description': f'{level_name} MACD正常'}

# =====================================================
# v3.1+: 零轴金叉
# =====================================================

def judge_zero_axis_cross(df_level, level_name='120F'):
    if len(df_level) < 3:
        return {'cross_type': 'none', 'description': '数据不足'}
    latest = df_level.iloc[-1]
    prev = df_level.iloc[-2]
    macd_latest = latest['MACD']
    macd_prev = prev['MACD']
    
    if macd_prev < 0 and macd_latest > 0:
        return {'cross_type': 'golden', 'description': f'{level_name}零轴金叉', 'importance': 'high'}
    if macd_prev > 0 and macd_latest < 0:
        return {'cross_type': 'death', 'description': f'{level_name}零轴死叉', 'importance': 'high'}
    
    macd_range = df_level['MACD'].max() - df_level['MACD'].min()
    zero_threshold = abs(macd_range) * 0.05
    if abs(macd_latest) < zero_threshold:
        return {'cross_type': 'near_zero', 'description': f'{level_name}MACD零轴附近', 'importance': 'medium'}
    return {'cross_type': 'none', 'description': f'{level_name}MACD远离零轴', 'importance': 'low'}

# =====================================================
# v3.1+: 级别重叠
# =====================================================

def analyze_level_overlap(df_lower, df_upper, lower_name='5F', upper_name='30F'):
    lower_latest = df_lower.iloc[-1]
    upper_latest = df_upper.iloc[-1]
    lower_55 = lower_latest['MA55']
    upper_mid = upper_latest['BOLL_MID']
    deviation = abs(lower_55 - upper_mid) / upper_mid * 100
    is_overlap = deviation < 0.5
    
    if is_overlap:
        return {'is_overlap': True, 'overlap_zone': (min(lower_55, upper_mid)*0.995, max(lower_55, upper_mid)*1.005), 'strength': 1-deviation/0.5, 'description': f'{lower_name}55线与{upper_name}中轨重叠'}
    return {'is_overlap': False, 'overlap_zone': None, 'strength': 0, 'description': f'{lower_name}55线与{upper_name}中轨无重叠'}

# =====================================================
# v3.1+: 目标价
# =====================================================

def derive_target_price(df_level, level_name='30F'):
    latest = df_level.iloc[-1]
    price = latest['Close']
    ma55 = latest['MA55']
    recent_high = df_level['High'].tail(60).max()
    recent_low = df_level['Low'].tail(60).min()
    mid_zone = df_level['BOLL_MID'].tail(20)
    center_high = mid_zone.max()
    center_low = mid_zone.min()
    fib_618 = center_low + (recent_high - recent_low) * 1.618
    equal_measure = ma55 + (recent_high - recent_low)
    supports = [latest['BOLL_DOWN'], ma55, recent_low]
    resistances = [latest['BOLL_UP'], recent_high, center_high]
    nearest_support = max([s for s in supports if s < price], default=price*0.95)
    nearest_resistance = min([r for r in resistances if r > price], default=price*1.05)
    
    return {
        'target_high': recent_high,
        'target_fib': fib_618,
        'target_equal': equal_measure,
        'nearest_support': nearest_support,
        'nearest_resistance': nearest_resistance,
        'description': f'{level_name}: 前高{recent_high:.2f}/斐波那契{fib_618:.2f}/等距{equal_measure:.2f}'
    }

# =====================================================
# v3.1: 段数分析
# =====================================================

def analyze_segment_count(df, lookback=50):
    df_check = df.tail(lookback)
    strokes = find_strokes(df_check)
    
    if len(strokes) == 0:
        return {'total_strokes': 0, 'completed_segments': 0, 'current_segment_strokes': 0, 'current_segment_status': '无笔', 'is_complete': False, 'trend': 'unclear', 'strokes': []}
    
    completed_segments = len(strokes) // 3
    current_segment_strokes = len(strokes) % 3
    
    if current_segment_strokes == 0 and len(strokes) >= 3:
        last_3 = strokes[-3:]
        directions = [s['direction'] for s in last_3]
        is_alternating = all(directions[j] != directions[j+1] for j in range(2))
        total_klines = last_3[-1]['end_idx'] - last_3[0]['start_idx'] + 1
        is_complete = is_alternating and total_klines >= 7
    else:
        is_complete = False
    
    last_direction = strokes[-1]['direction']
    trend = 'down' if last_direction == 'down' else 'up'
    
    return {
        'total_strokes': len(strokes),
        'completed_segments': completed_segments,
        'current_segment_strokes': current_segment_strokes,
        'current_segment_status': '已完成' if current_segment_strokes == 0 and is_complete else f'进行中(第{current_segment_strokes}笔)',
        'is_complete': is_complete,
        'trend': trend,
        'last_stroke_direction': last_direction,
        'strokes': strokes
    }

# =====================================================
# v3.1: 55线思维
# =====================================================

def judge_55line_status(level_name, df_level):
    latest = df_level.iloc[-1]
    price = latest['Close']
    ma55 = latest['MA55']
    mid = latest['BOLL_MID']
    macd = latest['MACD']
    status_55 = '55线上方' if price > ma55 else '55线下方'
    prev = df_level.iloc[-2] if len(df_level) > 1 else latest
    prev_price = prev['Close']
    
    if prev_price < ma55 and price > ma55: key_signal = '突破55线'
    elif prev_price > ma55 and price < ma55: key_signal = '跌破55线'
    elif price > ma55 * 0.995 and price < ma55 * 1.005: key_signal = '55线胶着'
    elif price > ma55: key_signal = '55线上方运行'
    else: key_signal = '55线下方运行'
    
    if price > ma55 and macd > 0: structure = '主涨段'
    elif price < ma55 and macd < 0: structure = '主跌段'
    else: structure = 'X段'
    
    return {'level': level_name, 'price': price, 'ma55': ma55, 'mid': mid, 'status_55': status_55, 'key_signal': key_signal, 'structure': structure, 'macd': macd}

# =====================================================
# v3.1: 补偿性买点
# =====================================================

def identify_compensation_buy(df_level, level_name='5F'):
    latest = df_level.iloc[-1]
    price = latest['Close']
    ma55 = latest['MA55']
    mid = latest['BOLL_MID']
    macd = latest['MACD']
    recent = df_level.tail(20)
    min_price = recent['Low'].min()
    is_below_55 = price < ma55
    was_below_55 = min_price < ma55 * 0.99
    price_low = recent['Low'].min()
    macd_low = recent['MACD'].min()
    is_bottom_div = (price <= price_low * 1.002) and (macd > macd_low * 1.1)
    vol_ratio = latest['Volume'] / latest['Vol_MA5'] if latest['Vol_MA5'] > 0 else 1
    is_shrink = vol_ratio < 0.8
    
    if was_below_55 and (is_bottom_div or is_shrink):
        return {'is_compensation_zone': True, 'zone': (ma55*0.98, ma55), 'confirmation': '底背离' if is_bottom_div else '缩量', 'target': mid, 'action': f'在{level_name}55线下方低吸'}
    return {'is_compensation_zone': False}

# =====================================================
# v3.1: 复合风控
# =====================================================

def check_composite_risk(df_upper, df_lower):
    signals = []
    risk_score = 0
    upper_latest = df_upper.iloc[-1]
    upper_price = upper_latest['Close']
    upper_ma55 = upper_latest['MA55']
    upper_macd = upper_latest['MACD']
    
    if upper_price < upper_ma55 and upper_macd < 0:
        signals.append('上级55线压制+MACD<0')
        risk_score += 40
    elif upper_price < upper_ma55:
        signals.append('上级55线压制')
        risk_score += 25
    
    lower_recent = df_lower.tail(20)
    lower_price_high = lower_recent['High'].max()
    lower_macd_high = lower_recent['MACD'].max()
    lower_current_price = df_lower.iloc[-1]['Close']
    lower_current_macd = df_lower.iloc[-1]['MACD']
    is_top_div = (lower_current_price >= lower_price_high * 0.998) and (lower_current_macd < lower_macd_high * 0.9)
    if is_top_div:
        signals.append('下级顶背离')
        risk_score += 35
    
    lower_latest = df_lower.iloc[-1]
    vol_ratio = lower_latest['Volume'] / lower_latest['Vol_MA5'] if lower_latest['Vol_MA5'] > 0 else 1
    if vol_ratio > 1.5:
        signals.append(f'放量{vol_ratio:.1f}倍')
        risk_score += 15
    
    if risk_score >= 60:
        return {'risk_level': 'high', 'risk_score': risk_score, 'signals': signals, 'action': '兑现一部分多头'}
    elif risk_score >= 40:
        return {'risk_level': 'medium', 'risk_score': risk_score, 'signals': signals, 'action': '警惕, 减仓1/3'}
    elif risk_score >= 20:
        return {'risk_level': 'low', 'risk_score': risk_score, 'signals': signals, 'action': '观察'}
    return {'risk_level': 'none', 'risk_score': risk_score, 'signals': signals, 'action': '持仓'}

# =====================================================
# v3.5 核心新增: 120F级别分析
# =====================================================

def analyze_120f_core(df_120f, df_30f=None, current_price=None):
    """
    120F级别核心分析 (v3.5核心)
    
    120分钟 = 2小时K线，是日线内部结构的核心观察级别
    120F中轨/55线 = 日线内部多空分界
    120F第三段 = 日线级别内部结构的关键段落
    120F死叉/金叉 = 日线内部趋势转折信号
    
    核心问题（SKILL.md原文）:
    "明天行情的核心，还是能不能反抽到120F中轨，而不是直接畅想反抽到了怎么办。"
    """
    if df_120f is None or len(df_120f) < 55:
        return {'usable': False, 'description': '120F数据不足'}
    
    latest = df_120f.iloc[-1]
    ma55 = latest['MA55']
    boll_mid = latest['BOLL_MID']
    macd = latest['MACD']
    macd_signal = latest['MACD_Signal']
    price = latest['Close']
    
    # 判断120F结构
    if price > ma55 and macd > 0:
        structure = '120F主涨段'
    elif price < ma55 and macd < 0:
        structure = '120F主跌段'
    elif price > ma55 and macd < 0:
        structure = '120F55线上方X段'
    else:
        structure = '120F55线下方X段'
    
    # 核心判断：能否反抽到120F中轨
    can_reach_mid = price < boll_mid  # 当前在中轨下方，有反弹空间
    
    # 判断120F零轴金叉/死叉
    prev = df_120f.iloc[-2] if len(df_120f) > 1 else latest
    macd_prev = prev['MACD']
    is_zero_golden = macd_prev < 0 and macd > 0
    is_zero_death = macd_prev > 0 and macd < 0
    
    # 判断第三段（需要段数分析）
    # 简化：假设当前在主跌段/主涨段中
    
    # 核心矛盾
    core_question = f"明天核心：能否反抽到120F中轨({boll_mid:.2f})？"
    if can_reach_mid:
        core_answer = f"当前{price:.2f}<{boll_mid:.2f}，有反弹空间。如果不能突破{boll_mid:.2f}，则是30F X段回抽，后续继续新低"
    else:
        core_answer = f"当前已站上中轨，关注能否突破120F55线({ma55:.2f})"
    
    return {
        'usable': True,
        'level': '120F',
        'price': price,
        'ma55': ma55,
        'boll_mid': boll_mid,
        'macd': macd,
        'structure': structure,
        'can_reach_mid': can_reach_mid,
        'is_zero_golden': is_zero_golden,
        'is_zero_death': is_zero_death,
        'core_question': core_question,
        'core_answer': core_answer,
        'description': f'{structure}，{"能" if can_reach_mid else "不能"}反抽中轨'
    }


# =====================================================
# v3.5 核心新增: X段识别
# =====================================================

def identify_x_segment(df_level, level_name='30F'):
    """
    X段识别 (v3.5核心)
    
    定义：
    - 55线上方X段：价格>MA55 + MACD<0 → 上涨中的回调/中枢震荡
    - 55线下方X段：价格<MA55 + MACD>0 → 下跌中的反弹/中枢震荡
    
    X段是套娃循环的核心结构，是最高骗炮区域
    """
    if len(df_level) < 3:
        return {'usable': False, 'description': '数据不足'}
    
    latest = df_level.iloc[-1]
    price = latest['Close']
    ma55 = latest['MA55']
    macd = latest['MACD']
    
    is_above_55 = price > ma55
    is_macd_negative = macd < 0
    
    if is_above_55 and is_macd_negative:
        x_type = '55线上方X段'
        risk = '高'
        description = f'{level_name}价格>{ma55:.2f}但MACD={macd:.2f}<0，上涨中的回调/中枢震荡，警惕回落'
    elif not is_above_55 and not is_macd_negative:
        x_type = '55线下方X段'
        risk = '高'
        description = f'{level_name}价格<{ma55:.2f}但MACD={macd:.2f}>0，下跌中的反弹/中枢震荡，警惕新低'
    elif is_above_55 and not is_macd_negative:
        x_type = '主涨段'
        risk = '低'
        description = f'{level_name}主涨段，明确上涨趋势'
    else:
        x_type = '主跌段'
        risk = '低'
        description = f'{level_name}主跌段，明确下跌趋势'
    
    is_x_segment = x_type in ['55线上方X段', '55线下方X段']
    
    return {
        'usable': True,
        'level': level_name,
        'x_type': x_type,
        'is_x_segment': is_x_segment,
        'risk': risk,
        'description': description,
        'price': price,
        'ma55': ma55,
        'macd': macd
    }


# =====================================================
# v3.5 核心新增: 5F套娃结构分析
# =====================================================

def analyze_5f_taowa(df_5f, df_30f):
    """
    5F套娃结构分析 (v3.5核心)
    
    核心问题（SKILL.md原文）:
    "其分界点在于明天5F55线能否站稳，如果不能，那么就继续5F新下跌结构套娃循环，
    那我觉得叠加日线极弱，指数可能就要3开头了。"
    
    5F套娃 = 5F反弹但30F主跌 → 小心5F反弹是X段，套娃循环继续
    """
    if df_5f is None or df_30f is None:
        return {'usable': False, 'description': '数据不足'}
    
    # 5F状态
    latest_5f = df_5f.iloc[-1]
    price_5f = latest_5f['Close']
    ma55_5f = latest_5f['MA55']
    macd_5f = latest_5f['MACD']
    structure_5f = '主涨' if price_5f > ma55_5f and macd_5f > 0 else '主跌' if price_5f < ma55_5f and macd_5f < 0 else 'X段'
    
    # 30F状态
    latest_30f = df_30f.iloc[-1]
    price_30f = latest_30f['Close']
    ma55_30f = latest_30f['MA55']
    macd_30f = latest_30f['MACD']
    structure_30f = '主涨' if price_30f > ma55_30f and macd_30f > 0 else '主跌' if price_30f < ma55_30f and macd_30f < 0 else 'X段'
    
    # 套娃判断
    is_taowa = (structure_5f == '主涨' and structure_30f == '主跌')
    
    if is_taowa:
        risk_level = '极高'
        analysis = f'⚠️ 5F主涨但30F主跌 → 5F反弹极大概率是X段，小心套娃循环继续'
        suggestion = '不追涨，等待5F回落或30F反转'
    elif structure_5f == '主涨' and structure_30f == '主涨':
        risk_level = '低'
        analysis = '5F+30F共振上涨，趋势健康'
        suggestion = '持仓或加仓'
    elif structure_5f == '主跌' and structure_30f == '主跌':
        risk_level = '高'
        analysis = '5F+30F共振下跌，趋势明确'
        suggestion = '清仓或观望'
    else:
        risk_level = '中'
        analysis = '5F与30F方向不一致，震荡中'
        suggestion = '观望，等待方向确认'
    
    return {
        'usable': True,
        'is_taowa': is_taowa,
        'structure_5f': structure_5f,
        'structure_30f': structure_30f,
        'risk_level': risk_level,
        'analysis': analysis,
        'suggestion': suggestion,
        'price_5f': price_5f,
        'price_30f': price_30f,
        'ma55_5f': ma55_5f,
        'ma55_30f': ma55_30f
    }


# =====================================================
# v3.5 核心新增: 双周/55周线分析
# =====================================================

def analyze_biweek_55week(df_biweek):
    """
    双周/55周线分析 (v3.5核心)
    
    双周55线 = 55周线 = 终极牛熊分界线
    跌破55��线 = 周线中枢构筑 = 大周期空头确认
    
    需要550天数据才能形成可靠的55周线
    """
    if df_biweek is None or len(df_biweek) < 55:
        return {'usable': False, 'description': '双周数据不足55根'}
    
    latest = df_biweek.iloc[-1]
    price = latest['Close']
    ma55 = latest['MA55']
    macd = latest['MACD']
    
    if price > ma55 and macd > 0:
        structure = '周线多头'
    elif price < ma55 and macd < 0:
        structure = '周线空头'
    elif price > ma55 and macd < 0:
        structure = '55周线上方X段'
    else:
        structure = '55周线下方X段'
    
    is_below_55week = price < ma55
    
    return {
        'usable': True,
        'level': '双周',
        'price': price,
        'ma55': ma55,
        'macd': macd,
        'structure': structure,
        'is_below_55week': is_below_55week,
        'description': f'{structure}，{"在55周线下方" if is_below_55week else "在55周线上方"}'
    }


# =====================================================
# v3.5 主分析器
# =====================================================

FEISHU_USER = "user:ou_efbad805767f4572e8f93ebafa8d5402"


def send_feishu(message):
    """发送飞书消息"""
    cmd = [
        "openclaw", "message", "send",
        "--channel", "feishu",
        "--target", FEISHU_USER,
        "--message", message
    ]
    try:
        subprocess.run(cmd, timeout=30, capture_output=True)
        return True
    except Exception as e:
        print(f"  ❌ 发送失败: {e}")
        return False


class ChanAnalysisV35:
    """缠论分析器 v3.5 - 完整版"""
    
    def __init__(self, df_1m=None, df_5m=None, df_30m=None, df_daily=None):
        self.df_1m = df_1m.copy() if df_1m is not None else None
        self.df_5m = df_5m.copy() if df_5m is not None else None
        self.df_30m_raw = df_30m.copy() if df_30m is not None else None
        self.df_daily = df_daily.copy() if df_daily is not None else None
        self._prepare()
    
    def _prepare(self):
        if self.df_1m is not None:
            self.df_1f = calc_all_indicators(self.df_1m)
            self.df_3m = calc_all_indicators(synthesize_kline(self.df_1m, 3, "3F"))
        if self.df_5m is not None:
            self.df_5m = calc_all_indicators(self.df_5m)
            self.df_15m = calc_all_indicators(synthesize_kline(self.df_5m, 3, "15F"))
            self.df_30m = calc_all_indicators(synthesize_kline(self.df_5m, 6, "30F"))
            self.df_60m = calc_all_indicators(synthesize_kline(self.df_5m, 12, "60F"))
        if self.df_30m_raw is not None:
            self.df_120f = calc_all_indicators(synthesize_kline(self.df_30m_raw, 4, "120F"))
        elif self.df_daily is not None:
            self.df_120f = calc_all_indicators(synthesize_kline(self.df_daily, 5, "120F"))
        if self.df_daily is not None:
            self.df_daily = calc_all_indicators(self.df_daily)
            self.df_biday = calc_all_indicators(synthesize_kline(self.df_daily, 2, "双日"))
            self.df_biweek = calc_all_indicators(synthesize_kline(self.df_daily, 10, "双周"))
    
    def _get_level_dict(self):
        d = {}
        for name, df in [
            ('1F', getattr(self, 'df_1f', None)),
            ('3F', getattr(self, 'df_3m', None)),
            ('5F', getattr(self, 'df_5m', None)),
            ('15F', getattr(self, 'df_15m', None)),
            ('30F', getattr(self, 'df_30m', None)),
            ('60F', getattr(self, 'df_60m', None)),
            ('120F', getattr(self, 'df_120f', None)),
            ('日线', self.df_daily),
            ('双日', getattr(self, 'df_biday', None)),
            ('双周', getattr(self, 'df_biweek', None))
        ]:
            if df is not None:
                d[name] = df
        return d
    
    # v3.4 新增方法
    def get_divergence(self):
        """底背离/顶背离检测"""
        result = {}
        for name, df in self._get_level_dict().items():
            if len(df) >= 40:
                result[name] = detect_divergence(df, name, lookback=30)
        return result
    
    def get_signal_priority(self):
        """信号优先级判定"""
        div = self.get_divergence()
        sb = self.get_second_buy()
        uz = self.get_unified_zone()
        dd = self.get_dual_day()
        return judge_signal_priority(div, sb, uz, dd)
    
    def get_scenario(self):
        """情景推演"""
        # 先构建报告字典
        report = {
            'divergence': self.get_divergence(),
            'unified_zone': self.get_unified_zone(),
            'dual_day': self.get_dual_day(),
            'transmission_chain': self.get_transmission_chain()
        }
        return scenario_analysis(report)
    
    # v3.3/v3.1+ 保留方法
    def get_data_integrity(self):
        result = {}
        for name, df in self._get_level_dict().items():
            result[name] = check_data_integrity(df, name)
        return result
    
    def get_fake_breakout(self):
        result = {}
        for name, df in self._get_level_dict().items():
            if len(df) >= 3:
                result[name] = judge_fake_breakout(df, name)
        return result
    
    def get_second_buy(self):
        result = {}
        for name, df in self._get_level_dict().items():
            if len(df) >= 50:
                seg = analyze_segment_count(df, lookback=50)
                if seg.get('strokes'):
                    result[name] = identify_second_buy(seg['strokes'], name)
        return result
    
    def get_unified_zone(self):
        return analyze_unified_zone(self._get_level_dict())
    
    def get_transmission_chain(self):
        return analyze_transmission_chain(self._get_level_dict())
    
    def get_dual_day(self):
        if hasattr(self, 'df_biday') and self.df_biday is not None:
            return analyze_dual_day(self.df_biday)
        return {'usable': False, 'description': '无双日数据'}
    
    def get_time_window(self):
        dual_day = self.get_dual_day()
        chain = self.get_transmission_chain()
        return judge_time_window(dual_day, chain)
    
    def get_55line_analysis(self):
        result = {}
        for name, df in self._get_level_dict().items():
            result[name] = judge_55line_status(name, df)
        return result
    
    def get_macd_extreme(self):
        result = {}
        for name, df in self._get_level_dict().items():
            if len(df) >= 3:
                result[name] = judge_macd_extreme(df, name)
        return result
    
    def get_zero_axis_cross(self):
        result = {}
        for name, df in self._get_level_dict().items():
            if len(df) >= 3:
                result[name] = judge_zero_axis_cross(df, name)
        return result
    
    def get_level_overlap(self):
        result = {}
        pairs = [('1F', '5F', getattr(self, 'df_1f', None), getattr(self, 'df_3m', None)),
                 ('5F', '30F', getattr(self, 'df_3m', None), getattr(self, 'df_30m', None))]
        for lower_name, upper_name, df_lower, df_upper in pairs:
            if df_lower is not None and df_upper is not None:
                result[f'{lower_name}_{upper_name}'] = analyze_level_overlap(df_lower, df_upper, lower_name, upper_name)
        return result
    
    def get_target_price(self):
        result = {}
        for name, df in [('30F', getattr(self, 'df_30m', None)), ('120F', getattr(self, 'df_120f', None)), ('日线', self.df_daily)]:
            if df is not None:
                result[name] = derive_target_price(df, name)
        return result
    
    def get_segment_analysis(self):
        result = {}
        for name, df in [('1F', getattr(self, 'df_1f', None)), ('5F', getattr(self, 'df_3m', None)), ('30F', getattr(self, 'df_30m', None)), ('60F', getattr(self, 'df_60m', None)), ('日线', self.df_daily)]:
            if df is not None:
                result[name] = analyze_segment_count(df, lookback=50)
        return result
    
    def get_compensation_buy(self):
        result = {}
        if hasattr(self, 'df_3m') and self.df_3m is not None:
            result['5F'] = identify_compensation_buy(self.df_3m, '5F')
        if hasattr(self, 'df_30m') and self.df_30m is not None:
            result['30F'] = identify_compensation_buy(self.df_30m, '30F')
        return result
    
    def get_composite_risk(self):
        risks = {}
        if self.df_daily is not None and hasattr(self, 'df_30m') and self.df_30m is not None:
            risks['日线vs30F'] = check_composite_risk(self.df_daily, self.df_30m)
        if hasattr(self, 'df_30m') and self.df_30m is not None and hasattr(self, 'df_3m') and self.df_3m is not None:
            risks['30Fvs5F'] = check_composite_risk(self.df_30m, self.df_3m)
        return risks
    
    def generate_report(self):
        """生成完整分析报告（v3.5）"""
        report = {
            'data_integrity': self.get_data_integrity(),
            '55line_analysis': self.get_55line_analysis(),
            'fake_breakout': self.get_fake_breakout(),
            'divergence': self.get_divergence(),              # v3.4新增
            'signal_priority': self.get_signal_priority(),    # v3.4新增
            'scenario': self.get_scenario(),                # v3.4新增
            'unified_zone': self.get_unified_zone(),
            'second_buy': self.get_second_buy(),
            'segment_analysis': self.get_segment_analysis(),
            'transmission_chain': self.get_transmission_chain(),
            'dual_day': self.get_dual_day(),
            'time_window': self.get_time_window(),
            'compensation_buy': self.get_compensation_buy(),
            'composite_risk': self.get_composite_risk(),
            'macd_extreme': self.get_macd_extreme(),
            'zero_axis_cross': self.get_zero_axis_cross(),
            'level_overlap': self.get_level_overlap(),
            'target_price': self.get_target_price(),
            # v3.5新增
            'x_segment': self.get_x_segment(),
            'taowa': self.get_taowa(),
            'biweek_55week': self.get_biweek_55week()
        }
        return report
    
    # v3.5 新增方法
    def get_x_segment(self):
        """X段识别"""
        result = {}
        for name, df in self._get_level_dict().items():
            if len(df) >= 55:
                result[name] = identify_x_segment(df, name)
        return result
    
    def get_taowa(self):
        """5F套娃结构分析"""
        if hasattr(self, 'df_5m') and hasattr(self, 'df_30m'):
            return analyze_5f_taowa(self.df_5m, self.df_30m)
        return {'usable': False}
    
    def get_biweek_55week(self):
        """双周/55周线分析"""
        if hasattr(self, 'df_biweek') and self.df_biweek is not None:
            return analyze_biweek_55week(self.df_biweek)
        return {'usable': False}


# =====================================================
# 主程序
# =====================================================

def main():
    print("="*60)
    print("缠论分析系统 v3.5 - 完整版")
    print("="*60)
    
    try:
        df_1m = fetch_data("/mnt/kimi/output/sh_1min.csv")
        df_5m = fetch_data("/mnt/kimi/output/sh_5min_full.csv")
        df_daily = fetch_data("/mnt/kimi/output/sh_1day.csv")
        
        analyzer = ChanAnalysisV35(df_1m=df_1m, df_5m=df_5m, df_daily=df_daily)
        report = analyzer.generate_report()
        
        print("\n【数据完整性】")
        for level, data in report['data_integrity'].items():
            status = "✅" if data['usable'] else "❌"
            print(f"  {status} {level}: {data['total_rows']}根")
        
        print("\n【X段识别 - v3.5核心】")
        for level, data in report.get('x_segment', {}).items():
            if data.get('is_x_segment'):
                print(f"  ⚠️ {level}: {data['description']}")
        
        print("\n【5F套娃结构 - v3.5核心】")
        taowa = report.get('taowa', {})
        if taowa.get('usable'):
            print(f"  {taowa.get('analysis')}")
            print(f"  建议: {taowa.get('suggestion')}")
        
        print("\n【双周/55周线 - v3.5核心】")
        biweek = report.get('biweek_55week', {})
        if biweek.get('usable'):
            print(f"  {biweek.get('description')}")
        
        print("\n【底背离/顶背离检测 - v3.4核心】")
        for level, data in report['divergence'].items():
            if data.get('has_bottom_divergence'):
                print(f"  🟢 {level}: {data['bottom']['description']}")
            if data.get('has_top_divergence'):
                print(f"  🔴 {level}: {data['top']['description']}")
        
        print("\n【信号优先级判定 - v3.4核心】")
        sp = report['signal_priority']
        print(f"  最终信号: {sp['final_signal']} ({sp['priority']})")
        print(f"  原因: {sp['reason']}")
        print(f"  操作: {sp['action']}")
        
        print("\n【情景推演 - v3.4核心】")
        sc = report['scenario']
        print(f"  主推情景: {sc['primary_scenario']}")
        print(f"  {sc['recommendation']}")
        
        print("\n【55线思维】")
        for level, data in report['55line_analysis'].items():
            if level in ['日线', '30F', '双日', '120F']:
                print(f"  {level}: 价{data['price']:.2f} vs MA55={data['ma55']:.2f} | {data['structure']}")
        
        print("\n【联合支撑/压制区】")
        uz = report['unified_zone']
        for z in uz.get('unified_zones', []):
            icon = '🛡️' if '支撑' in z['type'] else '⛰️'
            print(f"  {icon} {z['strength']}: {z['description']}")
        
        print("\n【二买/二卖】")
        for level, data in report['second_buy'].items():
            if level in ['日线', '30F']:
                icon = "✅" if data.get('is_valid') else "❌"
                print(f"  {icon} {level}: {data.get('type','')} → {data.get('action','')}")
        
        print("\n【传导链】")
        tc = report['transmission_chain']
        print(f"  方向: {tc['direction'].upper()} | {tc['description']}")
        
        print("\n【时间窗口】")
        tw = report['time_window']
        icon = "✅" if tw['is_window_open'] else "⛔"
        print(f"  {icon} {tw['description']} → {tw['action']}")
        
        print("\n【双日级别】")
        dd = report['dual_day']
        if dd.get('usable', True):
            print(f"  {dd['description']} → {dd['action']}")
        
    except Exception as e:
        print(f"\n分析出错: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
