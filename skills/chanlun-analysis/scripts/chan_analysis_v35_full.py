#!/root/.openclaw/workspace/venv/bin/python3
"""
缠论多级别联立分析系统 v3.5 - 完整版（实时数据版）
更新日期: 2026-06-09

基于SKILL.md v3.5方法论，结合长桥API实时数据：
  1. 十级别联立（1F/3F/5F/15F/30F/60F/120F/日线/双日/双周）
  2. 120F级别核心分析（120分钟=2小时K线，日线内部结构核心）
  3. X段识别（55线上方X段/下方X段 = 套娃核心）
  4. 5F套娃结构（5F反弹但30F主跌→小心X段）
  5. 双周/55周线（55周线=终极牛熊分界线）
  6. 底背离/顶背离检测 + 多级别共振
  7. 信号优先级判定（P0底背离+联合支撑 > 二卖）
  8. 联合支撑/压制区识别
  9. 二买/二卖结构识别
  10. 级别传导链（多米诺骨牌效应）
  11. 时间窗口判断
  12. 情景推演/路径分析
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import sys
import os
import subprocess

sys.path.insert(0, '/root/.openclaw/workspace/venv/lib/python3.12/site-packages')

from longport.openapi import QuoteContext, Config, AdjustType, Period

FEISHU_USER = "user:ou_efbad805767f4572e8f93ebafa8d5402"


def init_api():
    """初始化长桥API"""
    env_file = '/root/.openclaw/workspace/.longbridge.env'
    if os.path.exists(env_file):
        with open(env_file) as f:
            for line in f:
                if '=' in line and not line.startswith('#'):
                    key, value = line.strip().split('=', 1)
                    os.environ[key] = value.strip('"').strip("'")
    config = Config.from_env()
    return QuoteContext(config)


def get_data(ctx, symbol, period, count):
    """从长桥API获取数据"""
    try:
        resp = ctx.candlesticks(symbol, period=period, count=count, adjust_type=AdjustType.NoAdjust)
        data = []
        for c in resp:
            data.append({
                'datetime': c.timestamp,
                'open': float(c.open),
                'high': float(c.high),
                'low': float(c.low),
                'close': float(c.close),
                'volume': int(c.volume)
            })
        df = pd.DataFrame(data).sort_values('datetime').reset_index(drop=True)
        return df
    except Exception as e:
        print(f"  ❌ {period}数据获取失败: {e}")
        return None


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


# =====================================================
# 指标计算
# =====================================================

def calc_all_indicators(df):
    """计算所有指标：MA55/MACD/BOLL/量能"""
    df = df.copy()
    df['MA55'] = df['close'].rolling(window=55, min_periods=1).mean()
    df['MA233'] = df['close'].rolling(window=233, min_periods=1).mean()
    df['BOLL_MID'] = df['close'].rolling(window=20, min_periods=1).mean()
    std = df['close'].rolling(window=20, min_periods=1).std()
    df['BOLL_UP'] = df['BOLL_MID'] + std * 2
    df['BOLL_DOWN'] = df['BOLL_MID'] - std * 2
    
    ema_fast = df['close'].ewm(span=12, adjust=False).mean()
    ema_slow = df['close'].ewm(span=26, adjust=False).mean()
    df['MACD'] = ema_fast - ema_slow
    df['MACD_Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
    df['MACD_Hist'] = df['MACD'] - df['MACD_Signal']
    
    df['Vol_MA5'] = df['volume'].rolling(window=5, min_periods=1).mean()
    df['Vol_MA20'] = df['volume'].rolling(window=20, min_periods=1).mean()
    return df


def resample_kline(df, rule):
    """重采样K线"""
    if df is None or len(df) == 0:
        return None
    df = df.copy()
    df['datetime'] = pd.to_datetime(df['datetime'])
    df.set_index('datetime', inplace=True)
    
    resampled = df.resample(rule).agg({
        'open': 'first',
        'high': 'max',
        'low': 'min',
        'close': 'last',
        'volume': 'sum'
    }).dropna()
    resampled.reset_index(inplace=True)
    return resampled


# =====================================================
# 数据完整性检查
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
        integrity['warning'] = f'{level_name}数据仅{n}根(<55), MA55计算失真!'
    elif n < 20:
        integrity['warning'] = f'{level_name}数据仅{n}根(<20), 布林带指标失真!'
    return integrity


# =====================================================
# 55线思维分析
# =====================================================

def analyze_55line(df_level, level_name='30F'):
    """55线思维分析 - 核心判断"""
    if len(df_level) < 55:
        return {'usable': False, 'description': '数据不足'}
    
    latest = df_level.iloc[-1]
    price = latest['close']
    ma55 = latest['MA55']
    macd = latest['MACD']
    boll_mid = latest['BOLL_MID']
    
    # 结构判断
    if price > ma55 and macd > 0:
        structure = '主涨段'
        structure_score = 2
    elif price < ma55 and macd < 0:
        structure = '主跌段'
        structure_score = -2
    elif price > ma55 and macd < 0:
        structure = '55线上方X段'
        structure_score = -1
    else:
        structure = '55线下方X段'
        structure_score = 1
    
    # 关键信号
    prev = df_level.iloc[-2] if len(df_level) > 1 else latest
    prev_price = prev['close']
    if prev_price < ma55 and price > ma55:
        key_signal = '突破55线'
    elif prev_price > ma55 and price < ma55:
        key_signal = '跌破55线'
    elif price > ma55 * 0.995 and price < ma55 * 1.005:
        key_signal = '55线胶着'
    elif price > ma55:
        key_signal = '55线上方运行'
    else:
        key_signal = '55线下方运行'
    
    return {
        'level': level_name,
        'price': price,
        'ma55': ma55,
        'boll_mid': boll_mid,
        'structure': structure,
        'structure_score': structure_score,
        'key_signal': key_signal,
        'macd': macd,
        'dist_to_ma55_pct': round((price - ma55) / ma55 * 100, 2)
    }


# =====================================================
# v3.5 核心: X段识别
# =====================================================

def identify_x_segment(df_level, level_name='30F'):
    """X段识别 (v3.5核心)
    
    55线上方X段: 价格>MA55 + MACD<0 → 上涨中的回调/中枢震荡
    55线下方X段: 价格<MA55 + MACD>0 → 下跌中的反弹/中枢震荡
    """
    if len(df_level) < 55:
        return {'usable': False}
    
    latest = df_level.iloc[-1]
    price = latest['close']
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
    
    return {
        'usable': True,
        'level': level_name,
        'x_type': x_type,
        'is_x_segment': x_type in ['55线上方X段', '55线下方X段'],
        'risk': risk,
        'description': description
    }


# =====================================================
# v3.5 核心: 5F套娃结构分析
# =====================================================

def analyze_5f_taowa(df_5f, df_30f):
    """5F套娃结构分析 (v3.5核心)
    
    核心问题：5F站稳但30F主跌 → 小心5F反弹是X段，套娃循环继续
    """
    if df_5f is None or df_30f is None or len(df_5f) < 55 or len(df_30f) < 55:
        return {'usable': False}
    
    # 5F状态
    latest_5f = df_5f.iloc[-1]
    price_5f = latest_5f['close']
    ma55_5f = latest_5f['MA55']
    macd_5f = latest_5f['MACD']
    structure_5f = '主涨' if price_5f > ma55_5f and macd_5f > 0 else '主跌' if price_5f < ma55_5f and macd_5f < 0 else 'X段'
    
    # 30F状态
    latest_30f = df_30f.iloc[-1]
    price_30f = latest_30f['close']
    ma55_30f = latest_30f['MA55']
    macd_30f = latest_30f['MACD']
    structure_30f = '主涨' if price_30f > ma55_30f and macd_30f > 0 else '主跌' if price_30f < ma55_30f and macd_30f < 0 else 'X段'
    
    # 套娃判断
    is_taowa = (structure_5f == '主涨' and structure_30f == '主跌')
    
    if is_taowa:
        risk_level = '极高'
        analysis = '⚠️ 5F主涨但30F主跌 → 5F反弹极大概率是X段，小心套娃循环继续'
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
# v3.5 核心: 120F级别分析
# =====================================================

def analyze_120f_core(df_120f):
    """120F级别核心分析 (v3.5核心)
    
    120分钟 = 2小时K线，日线内部结构的核心观察级别
    120F中轨/55线 = 日线内部多空分界
    
    核心问题：明天能否反抽到120F中轨？
    """
    if df_120f is None or len(df_120f) < 55:
        return {'usable': False}
    
    latest = df_120f.iloc[-1]
    price = latest['close']
    ma55 = latest['MA55']
    boll_mid = latest['BOLL_MID']
    macd = latest['MACD']
    
    # 判断120F结构
    if price > ma55 and macd > 0:
        structure = '120F主涨段'
    elif price < ma55 and macd < 0:
        structure = '120F主跌段'
    elif price > ma55 and macd < 0:
        structure = '120F上方X段'
    else:
        structure = '120F下方X段'
    
    can_reach_mid = price < boll_mid
    
    core_question = f'明天核心：能否反抽到120F中轨({boll_mid:.2f})？'
    if can_reach_mid:
        core_answer = f'当前{price:.2f}<{boll_mid:.2f}，有反弹空间。如果不能突破{boll_mid:.2f}，则是30F X段回抽，后续继续新低'
    else:
        core_answer = f'当前已站上中轨，关注能否突破120F55线({ma55:.2f})'
    
    return {
        'usable': True,
        'structure': structure,
        'price': price,
        'ma55': ma55,
        'boll_mid': boll_mid,
        'can_reach_mid': can_reach_mid,
        'core_question': core_question,
        'core_answer': core_answer,
        'description': f'{structure}，{"能" if can_reach_mid else "不能"}反抽中轨'
    }


# =====================================================
# v3.5 核心: 双周/55周线分析
# =====================================================

def analyze_biweek_55week(df_biweek):
    """双周/55周线分析 (v3.5核心)
    
    双周55线 = 55周线 = 终极牛熊分界线
    """
    if df_biweek is None or len(df_biweek) < 55:
        return {'usable': False, 'description': '双周数据不足55根'}
    
    latest = df_biweek.iloc[-1]
    price = latest['close']
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
        'price': price,
        'ma55': ma55,
        'macd': macd,
        'structure': structure,
        'is_below_55week': is_below_55week,
        'description': f'{structure}，{"在55周线下方" if is_below_55week else "在55周线上方"}'
    }


# =====================================================
# v3.4: 底背离/顶背离检测
# =====================================================

def detect_divergence(df_level, level_name='30F', lookback=30):
    """底背离/顶背离检测"""
    if len(df_level) < lookback + 10:
        return {'usable': False, 'description': '数据不足'}
    
    recent = df_level.tail(lookback).copy().reset_index(drop=True)
    lows = recent['low'].values
    highs = recent['high'].values
    macds = recent['MACD'].values
    
    # 底背离
    bottom_div = None
    min_idx = np.argmin(lows)
    min_price = lows[min_idx]
    min_macd = macds[min_idx]
    
    if min_idx > 5:
        prev_lows = lows[:min_idx-3]
        prev_macds = macds[:min_idx-3]
        if len(prev_lows) > 5:
            prev_min_idx = np.argmin(prev_lows)
            prev_min_price = prev_lows[prev_min_idx]
            prev_min_macd = prev_macds[prev_min_idx]
            if min_price < prev_min_price * 0.998 and min_macd > prev_min_macd * 1.05:
                bottom_div = {
                    'type': '底背离',
                    'price1': prev_min_price, 'price2': min_price,
                    'macd1': prev_min_macd, 'macd2': min_macd,
                    'description': f'{level_name}底背离: 价格{prev_min_price:.2f}→{min_price:.2f}, MACD{prev_min_macd:.2f}→{min_macd:.2f}'
                }
    
    # 顶背离
    top_div = None
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
            if max_price > prev_max_price * 1.002 and max_macd < prev_max_macd * 0.95:
                top_div = {
                    'type': '顶背离',
                    'price1': prev_max_price, 'price2': max_price,
                    'macd1': prev_max_macd, 'macd2': max_macd,
                    'description': f'{level_name}顶背离: 价格{prev_max_price:.2f}→{max_price:.2f}, MACD{prev_max_macd:.2f}→{max_macd:.2f}'
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
        result['action'] = '建仓/加仓'
    elif top_div:
        result['signal'] = '顶背离'
        result['action'] = '减仓/清仓'
    else:
        result['signal'] = '无背离'
        result['action'] = '观望'
    
    return result


# =====================================================
# v3.4: 多级别共振底背离分析
# =====================================================

def analyze_multi_level_divergence(divergence_results, unified_zone_result):
    """多级别共振底背离 + 联合支撑区 = 高胜率买点"""
    bottom_levels = []
    top_levels = []
    
    for level, div in divergence_results.items():
        if div.get('has_bottom_divergence'):
            bottom_levels.append(level)
        if div.get('has_top_divergence'):
            top_levels.append(level)
    
    near_support = False
    support_zone = None
    if unified_zone_result and unified_zone_result.get('unified_zones'):
        for z in unified_zone_result['unified_zones']:
            if '支撑' in z.get('type', ''):
                near_support = True
                support_zone = z
                break
    
    bottom_count = len(bottom_levels)
    top_count = len(top_levels)
    
    if bottom_count >= 2 and near_support:
        return {
            'signal': '极高胜率买点',
            'type': '多级别共振底背离+联合支撑区',
            'bottom_levels': bottom_levels,
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
            'description': f'{bottom_levels[0]}底背离 + 联合支撑区',
            'action': '建仓/加仓',
            'priority': 'P1'
        }
    elif top_count >= 2:
        return {
            'signal': '高胜率卖点',
            'type': '多级别共振顶背离',
            'description': f'{"/".join(top_levels)}顶背离共振',
            'action': '减仓/清仓',
            'priority': 'P0'
        }
    
    return {
        'signal': '无显著背离',
        'type': '观望',
        'action': '按其他信号操作',
        'priority': 'P3'
    }


# =====================================================
# v3.4: 信号优先级判定
# =====================================================

def judge_signal_priority(divergence_results, unified_zone_result, dual_day_status):
    """信号优先级判定 (v3.4核心)
    
    P0: 底背离+联合支撑区 > 二卖成立
    P1: 顶背离+联合压制区 > 二买成立
    """
    multi_div = analyze_multi_level_divergence(divergence_results, unified_zone_result)
    
    priority = multi_div.get('priority', 'P3')
    signal = multi_div.get('signal', '无')
    
    if signal in ['极高胜率买点', '高胜率买点']:
        return {
            'final_signal': '买点',
            'priority': priority,
            'reason': multi_div['description'],
            'action': multi_div['action'],
            'source': '底背离+联合区'
        }
    elif signal == '高胜率卖点':
        return {
            'final_signal': '卖点',
            'priority': priority,
            'reason': multi_div['description'],
            'action': multi_div['action'],
            'source': '顶背离'
        }
    
    return {
        'final_signal': '观望',
        'priority': 'P3',
        'reason': '无明确信号',
        'action': '观望',
        'source': '无'
    }


# =====================================================
# v3.3: 联合支撑/压制区
# =====================================================

def analyze_unified_zone(level_data_dict):
    """联合支撑/压制区识别 (v3.3核心)"""
    zones = []
    # 获取当前价格（从日线最后一个close值）
    df_daily = level_data_dict.get('日线')
    if df_daily is not None and len(df_daily) > 0:
        current_price = float(df_daily.iloc[-1]['close'])
    else:
        current_price = 4000.0
    
    # 关键级别对比
    key_levels = {}
    for name in ['日线', '双日', '120F', '60F', '30F', '5F']:
        if name in level_data_dict and len(level_data_dict[name]) > 0:
            key_levels[name] = {
                'ma55': level_data_dict[name].iloc[-1]['MA55'],
                'boll_mid': level_data_dict[name].iloc[-1]['BOLL_MID']
            }
    
    # MA55 vs MA55 联合
    ma55_names = list(key_levels.keys())
    for i in range(len(ma55_names)):
        for j in range(i+1, len(ma55_names)):
            n1, n2 = ma55_names[i], ma55_names[j]
            v1 = key_levels[n1]['ma55']
            v2 = key_levels[n2]['ma55']
            diff = abs(v1 - v2)
            if diff < 25:
                avg = (v1 + v2) / 2
                strength = '极强联合' if diff < 5 else '强联合' if diff < 10 else '中等联合'
                ztype = '联合支撑' if avg < current_price else '联合压制'
                zones.append({
                    'type': ztype,
                    'name': f'{n1}.MA55 + {n2}.MA55',
                    'price': round(avg, 2),
                    'diff': round(diff, 2),
                    'strength': strength,
                    'description': f'{ztype}: {n1}MA55({v1:.2f})与{n2}MA55({v2:.2f})差值{diff:.2f}点({strength})'
                })
    
    # MA55 vs BOLL中轨 联合
    for n1 in ma55_names:
        for n2 in ma55_names:
            if n1 == n2:
                continue
            v1 = key_levels[n1]['ma55']
            v2 = key_levels[n2]['boll_mid']
            diff = abs(v1 - v2)
            if diff < 20:
                avg = (v1 + v2) / 2
                strength = '强联合' if diff < 10 else '中等联合'
                ztype = '联合支撑' if avg < current_price else '联合压制'
                zones.append({
                    'type': ztype,
                    'name': f'{n1}.MA55 + {n2}.BOLL',
                    'price': round(avg, 2),
                    'diff': round(diff, 2),
                    'strength': strength,
                    'description': f'{ztype}: {n1}MA55({v1:.2f})与{n2}中轨({v2:.2f})差值{diff:.2f}点({strength})'
                })
    
    # 去重并排序
    seen = set()
    unique_zones = []
    for z in zones:
        key = f"{z['type']}_{z['price']}"
        if key not in seen and z['price'] > 0:
            seen.add(key)
            unique_zones.append(z)
    
    unique_zones.sort(key=lambda x: x['price'])
    return {'unified_zones': unique_zones, 'count': len(unique_zones)}


# =====================================================
# v3.3: 假突破/骗炮识别
# =====================================================

def judge_fake_breakout(df_level, level_name='30F'):
    """假突破/骗炮识别"""
    if len(df_level) < 3:
        return {'usable': False}
    
    latest = df_level.iloc[-1]
    prev = df_level.iloc[-2]
    price = latest['close']
    ma55 = latest['MA55']
    macd = latest['MACD']
    prev_price = prev['close']
    
    recent_hist = df_level['MACD_Hist'].tail(3).values
    is_expanding = len(recent_hist) >= 3 and all(abs(recent_hist[i]) >= abs(recent_hist[i-1]) for i in range(1, len(recent_hist)))
    
    if prev_price < ma55 and price > ma55:
        if macd > 0 and is_expanding:
            return {'type': '真突破', 'is_fake': False, 'description': f'{level_name}真突破', 'action': '追涨'}
        else:
            return {'type': '假突破(骗炮)', 'is_fake': True, 'description': f'{level_name}假突破: 站上55线但MACD<0或柱收敛', 'action': '不追涨'}
    
    if prev_price > ma55 and price < ma55:
        if macd < 0 and is_expanding:
            return {'type': '真跌破', 'is_fake': False, 'description': f'{level_name}真跌破', 'action': '止损'}
        else:
            return {'type': '假跌破', 'is_fake': True, 'description': f'{level_name}假跌破: 跌破55线但MACD>0或柱收敛', 'action': '不恐慌'}
    
    if price > ma55:
        return {'type': '55线上方', 'is_fake': False, 'description': f'{level_name}55线上方+MACD{"+" if macd>0 else ""}{macd:.2f}', 'action': '持仓' if macd>0 else '警惕'}
    
    return {'type': '55线下方', 'is_fake': False, 'description': f'{level_name}55线下方+MACD{"+" if macd>0 else ""}{macd:.2f}', 'action': '清仓' if macd<0 else '关注买点'}


# =====================================================
# v3.3: 二买/二卖识别
# =====================================================

def identify_second_buy(df_level, level_name='30F'):
    """二买/二卖识别"""
    if len(df_level) < 50:
        return {'usable': False}
    
    # 简化版：使用笔的方向判断
    recent = df_level.tail(50)
    highs = recent['high'].values
    lows = recent['low'].values
    
    # 找最近的高低点
    recent_high = np.max(highs[-20:])
    recent_low = np.min(lows[-20:])
    prev_high = np.max(highs[-40:-20]) if len(highs) >= 40 else recent_high
    prev_low = np.min(lows[-40:-20]) if len(lows) >= 40 else recent_low
    
    # 简化判断：回踩不破前低 = 二买雏形
    if recent_low > prev_low * 1.002:
        return {'type': '二买雏形', 'is_valid': True, 'description': f'{level_name}回踩不破前低({prev_low:.2f})', 'action': '关注'}
    elif recent_low < prev_low * 0.998:
        return {'type': '二买失败', 'is_valid': False, 'description': f'{level_name}创新低', 'action': '减仓'}
    
    return {'type': '无', 'is_valid': False, 'description': f'{level_name}无明确二买信号', 'action': '观望'}


# =====================================================
# v3.3: 级别传导链
# =====================================================

def analyze_transmission_chain(level_data_dict):
    """级别传导链分析 (多米诺骨牌效应)"""
    chain = {'steps': [], 'direction': 'neutral', 'description': ''}
    levels_order = ['1F', '3F', '5F', '15F', '30F', '60F', '120F', '日线', '双日']
    
    for lvl_name in levels_order:
        df = level_data_dict.get(lvl_name)
        if df is None or len(df) < 55:
            continue
        latest = df.iloc[-1]
        price = latest['close']
        ma55 = latest['MA55']
        macd = latest['MACD']
        status = 'above' if price > ma55 else 'below'
        
        chain['steps'].append({
            'level': lvl_name,
            'status': status,
            'macd': 'positive' if macd > 0 else 'negative',
            'structure': '主涨' if price > ma55 and macd > 0 else '主跌' if price < ma55 and macd < 0 else 'X段'
        })
    
    # 统计方向
    main_down = sum(1 for s in chain['steps'] if s['structure'] == '主跌')
    main_up = sum(1 for s in chain['steps'] if s['structure'] == '主涨')
    x_count = sum(1 for s in chain['steps'] if 'X段' in s['structure'])
    
    if main_down >= 3:
        chain['direction'] = 'down'
        chain['description'] = f'下跌传导链({main_down}级别主跌)，趋势偏空'
    elif main_up >= 3:
        chain['direction'] = 'up'
        chain['description'] = f'上涨传导链({main_up}级别主涨)，趋势偏多'
    elif x_count >= 3:
        chain['direction'] = 'mixed'
        chain['description'] = f'多级别X段({x_count}个)，震荡格局'
    else:
        chain['description'] = '传导链方向不明，震荡'
    
    return chain


# =====================================================
# v3.3: 双日级别
# =====================================================

def analyze_dual_day(df_dual_day):
    """双日级别分析"""
    if df_dual_day is None or len(df_dual_day) < 3:
        return {'usable': False}
    
    latest = df_dual_day.iloc[-1]
    prev = df_dual_day.iloc[-2] if len(df_dual_day) > 1 else latest
    macd = latest['MACD']
    signal = latest['MACD_Signal']
    hist = latest['MACD_Hist']
    prev_hist = prev['MACD_Hist']
    
    death_cross_risk = hist > 0 and hist < 0.5 and macd > signal
    is_death_cross = hist < 0 and macd < signal
    is_golden_cross = prev.get('MACD', 0) < 0 and macd > 0
    
    if is_golden_cross:
        return {'status': '多头', 'trend': 'golden_cross', 'description': '双日MACD金叉', 'action': '持仓', 'death_risk': False, 'hist': hist}
    elif is_death_cross:
        return {'status': '空头', 'trend': 'death_cross', 'description': '双日MACD死叉', 'action': '清仓', 'death_risk': True, 'hist': hist}
    elif death_cross_risk:
        return {'status': '多头', 'trend': 'death_risk', 'description': f'双日接近死叉 Hist={hist:.2f}', 'action': '警惕', 'death_risk': True, 'hist': hist}
    elif macd > 0 and hist > 0:
        return {'status': '多头', 'trend': 'bull', 'description': f'双日多头 Hist={hist:.2f}', 'action': '持仓', 'death_risk': False, 'hist': hist}
    else:
        return {'status': '空头', 'trend': 'bear', 'description': f'双日空头 Hist={hist:.2f}', 'action': '观望', 'death_risk': False, 'hist': hist}


# =====================================================
# v3.3: 时间窗口
# =====================================================

def judge_time_window(dual_day_status, transmission_chain):
    """时间窗口判断"""
    window = {'is_window_open': False, 'description': '', 'action': '观望'}
    
    if dual_day_status.get('trend') == 'death_cross':
        window['description'] = '双日死叉，需等待3-5天修复'
        window['action'] = '不操作'
        return window
    
    if dual_day_status.get('death_risk'):
        window['description'] = '双日接近死叉，修复需3-5天'
        window['action'] = '不操作'
        return window
    
    if transmission_chain.get('direction') == 'down':
        window['description'] = '下跌传导链中，等待底背离确认'
        window['action'] = '轻仓试多'
        return window
    
    if dual_day_status.get('trend') == 'golden_cross':
        window['is_window_open'] = True
        window['description'] = '双日金叉，正常操作'
        window['action'] = '正常操作'
        return window
    
    window['description'] = '无明确时间窗口'
    return window


# =====================================================
# v3.4: 情景推演
# =====================================================

def scenario_analysis(divergence_results, unified_zone, dual_day, transmission_chain):
    """情景推演/路径分析"""
    scenarios = []
    has_bottom_div = any(d.get('has_bottom_divergence') for d in divergence_results.values() if isinstance(d, dict))
    has_top_div = any(d.get('has_top_divergence') for d in divergence_results.values() if isinstance(d, dict))
    
    dd_death = dual_day.get('death_risk', False) if isinstance(dual_day, dict) else False
    chain_dir = transmission_chain.get('direction', 'neutral') if isinstance(transmission_chain, dict) else 'neutral'
    
    # 支撑/压制区
    support_zone = None
    resistance_zone = None
    if unified_zone and 'unified_zones' in unified_zone:
        for z in unified_zone['unified_zones']:
            if '支撑' in z.get('type', ''):
                support_zone = z
            if '压制' in z.get('type', ''):
                resistance_zone = z
    
    # 强势情景
    if has_bottom_div and support_zone:
        scenarios.append({
            'name': '强势情景',
            'probability': '中等(40%)',
            'condition': '底背离确认 + 联合支撑守住 + 放量突破',
            'action': '加仓至满仓'
        })
    
    # 中性情景
    scenarios.append({
        'name': '中性情景',
        'probability': '最高(50%)',
        'condition': '震荡蓄势 + 在联合区之间震荡',
        'action': '高抛低吸'
    })
    
    # 弱势情景
    if dd_death or chain_dir == 'down':
        scenarios.append({
            'name': '弱势情景',
            'probability': '较低(10%)',
            'condition': '无量反弹 + 二次探底',
            'action': '反弹减仓'
        })
    
    primary = '强势情景' if has_bottom_div and not dd_death else '中性情景'
    
    return {
        'scenarios': scenarios,
        'primary_scenario': primary,
        'recommendation': f'主推: {primary}'
    }


# =====================================================
# 补偿性买点
# =====================================================

def identify_compensation_buy(df_level, level_name='5F'):
    """补偿性买点识别"""
    if len(df_level) < 55:
        return {'usable': False}
    
    latest = df_level.iloc[-1]
    price = latest['close']
    ma55 = latest['MA55']
    mid = latest['BOLL_MID']
    macd = latest['MACD']
    recent = df_level.tail(20)
    
    min_price = recent['low'].min()
    macd_low = recent['MACD'].min()
    is_bottom_div = (price <= min_price * 1.002) and (macd > macd_low * 1.1)
    
    if price < ma55 and is_bottom_div:
        return {
            'is_compensation_zone': True,
            'zone': (ma55 * 0.98, ma55),
            'confirmation': '底背离',
            'target': mid,
            'action': f'{level_name}补偿性买点'
        }
    
    return {'is_compensation_zone': False}


# =====================================================
# 主分析器
# =====================================================

class ChanAnalysisV35:
    """缠论分析器 v3.5 - 完整版"""
    
    def __init__(self, df_1m=None, df_5m=None, df_30m=None, df_60m=None, df_daily=None):
        self.df_1m = df_1m.copy() if df_1m is not None else None
        self.df_5m = df_5m.copy() if df_5m is not None else None
        self.df_30m = df_30m.copy() if df_30m is not None else None
        self.df_60m = df_60m.copy() if df_60m is not None else None
        self.df_daily = df_daily.copy() if df_daily is not None else None
        self._prepare()
    
    def _prepare(self):
        """准备所有级别数据"""
        # 1F/3F 从1分钟合成
        if self.df_1m is not None:
            self.df_1f = calc_all_indicators(self.df_1m)
            self.df_3m = calc_all_indicators(resample_kline(self.df_1m, '3min'))
        
        # 5F/15F 从5分钟合成
        if self.df_5m is not None:
            self.df_5m = calc_all_indicators(self.df_5m)
            self.df_15m = calc_all_indicators(resample_kline(self.df_5m, '15min'))
        
        # 30F/60F/120F 直接数据
        if self.df_30m is not None:
            self.df_30m = calc_all_indicators(self.df_30m)
        
        if self.df_60m is not None:
            self.df_60m = calc_all_indicators(self.df_60m)
        
        # 120F 从60分钟合成 (60m×2=120m)
        if self.df_60m is not None:
            self.df_120f = calc_all_indicators(resample_kline(self.df_60m, '120min'))
        
        # 日线/双日/双周
        if self.df_daily is not None:
            self.df_daily = calc_all_indicators(self.df_daily)
            self.df_biday = calc_all_indicators(resample_kline(self.df_daily, '2D'))
            self.df_biweek = calc_all_indicators(resample_kline(self.df_daily, '10D'))
    
    def _get_level_dict(self):
        """获取所有级别字典"""
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
            if df is not None and len(df) >= 55:
                d[name] = df
        return d
    
    def generate_report(self):
        """生成完整分析报告"""
        level_dict = self._get_level_dict()
        
        # 各级别分析
        line_analysis = {}
        for name, df in level_dict.items():
            line_analysis[name] = analyze_55line(df, name)
        
        # 底背离检测
        divergence = {}
        for name, df in level_dict.items():
            if len(df) >= 40:
                divergence[name] = detect_divergence(df, name)
        
        # 联合区
        unified_zone = analyze_unified_zone(level_dict)
        
        # 双日
        dual_day = analyze_dual_day(self.df_biday if hasattr(self, 'df_biday') else None)
        
        # 传导链
        transmission = analyze_transmission_chain(level_dict)
        
        # 信号优先级
        signal_priority = judge_signal_priority(divergence, unified_zone, dual_day)
        
        # 时间窗口
        time_window = judge_time_window(dual_day, transmission)
        
        # 场景推演
        scenario = scenario_analysis(divergence, unified_zone, dual_day, transmission)
        
        # v3.5 新增
        # X段
        x_segment = {}
        for name, df in level_dict.items():
            x_segment[name] = identify_x_segment(df, name)
        
        # 5F套娃
        taowa = analyze_5f_taowa(
            self.df_5m if hasattr(self, 'df_5m') else None,
            self.df_30m if hasattr(self, 'df_30m') else None
        )
        
        # 120F核心
        f120_core = analyze_120f_core(self.df_120f if hasattr(self, 'df_120f') else None)
        
        # 双周/55周线
        biweek = analyze_biweek_55week(self.df_biweek if hasattr(self, 'df_biweek') else None)
        
        # 假突破
        fake_breakout = {}
        for name, df in level_dict.items():
            fake_breakout[name] = judge_fake_breakout(df, name)
        
        # 二买
        second_buy = {}
        for name, df in level_dict.items():
            if len(df) >= 50:
                second_buy[name] = identify_second_buy(df, name)
        
        # 补偿性买点
        compensation = {}
        if hasattr(self, 'df_5m') and self.df_5m is not None:
            compensation['5F'] = identify_compensation_buy(self.df_5m, '5F')
        if hasattr(self, 'df_30m') and self.df_30m is not None:
            compensation['30F'] = identify_compensation_buy(self.df_30m, '30F')
        
        return {
            'line_analysis': line_analysis,
            'divergence': divergence,
            'unified_zone': unified_zone,
            'dual_day': dual_day,
            'transmission_chain': transmission,
            'signal_priority': signal_priority,
            'time_window': time_window,
            'scenario': scenario,
            'x_segment': x_segment,
            'taowa': taowa,
            'f120_core': f120_core,
            'biweek': biweek,
            'fake_breakout': fake_breakout,
            'second_buy': second_buy,
            'compensation_buy': compensation
        }


# =====================================================
# 报告生成
# =====================================================

def generate_report_text(report, current_price, date_str):
    """生成文字报告"""
    
    # 多级别状态
    level_lines = []
    for name in ['5F', '30F', '60F', '120F', '日线', '双日']:
        if name in report['line_analysis']:
            d = report['line_analysis'][name]
            div = '🔹' if report['divergence'].get(name, {}).get('has_bottom_divergence') or report['divergence'].get(name, {}).get('has_top_divergence') else ''
            x_mark = '⚠️X段' if report['x_segment'].get(name, {}).get('is_x_segment') else ''
            level_lines.append(f"  {name}: {d['structure']} | 55线={d['ma55']:.2f} | MACD={d['macd']:+.2f} {div} {x_mark}")
    
    # 联合区
    zone_lines = []
    for z in report['unified_zone'].get('unified_zones', []):
        icon = '🛡️' if '支撑' in z['type'] else '⛰️'
        zone_lines.append(f"  {icon} {z['strength']}: {z['description']}")
    
    # 120F核心
    f120 = report['f120_core']
    f120_text = f120.get('core_answer', '') if f120.get('usable') else '120F数据不足'
    
    # 5F套娃
    taowa = report['taowa']
    taowa_text = taowa.get('analysis', '') if taowa.get('usable') else '5F套娃分析不可用'
    
    # 双周
    biweek = report['biweek']
    biweek_text = biweek.get('description', '') if biweek.get('usable') else '双周数据不足'
    
    # 传导链
    tc = report['transmission_chain']
    tc_text = tc.get('description', '')
    
    # 时间窗口
    tw = report['time_window']
    tw_text = tw.get('description', '')
    
    # 信号优先级
    sp = report['signal_priority']
    
    # 策略
    daily = report['line_analysis'].get('日线', {})
    structure_daily = daily.get('structure', '未知')
    
    if structure_daily == '主跌段':
        strategy = f"""🎯 核心策略：日线主跌段，空仓/轻仓观望
   操作: 
   • 开盘若跌破5F55线→确认下跌传导，不操作
   • 若反弹到120F中轨遇阻→减仓
   • 耐心等待日线级别底背离+联合支撑区才考虑建仓"""
    elif 'X段' in structure_daily:
        strategy = f"""🎯 核心策略：日线X段，观望为主
   操作:
   • 5F反弹可能是X段，不追涨
   • 关注联合支撑区，等待底背离"""
    else:
        strategy = f"""🎯 核心策略：震荡观望，等待方向确认
   操作:
   • 突破联合压制区→加仓
   • 跌破联合支撑区→清仓"""
    
    report_text = f"""
📊 上证指数缠论多级别联立分析 - v3.5完整版
⏰ 分析时间: {date_str}
📌 当前收盘: {current_price:.2f}点

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
【一、多级别状态联立】
{chr(10).join(level_lines)}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
【二、大周期趋势判断】
{'🔴 日线主跌段 - 大方向偏空' if structure_daily == '主跌段' else '⚠️ 日线X段 - 极弱反弹' if 'X段' in structure_daily else '➡️ 日线震荡 - 等待方向'}

{taowa_text}

📌 120F核心分析:
{f120_text}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
【三、联合支撑/压制区】
{chr(10).join(zone_lines) if zone_lines else '  无显著联合区'}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
【四、级别传导链】
{tc_text}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
【五、双周/55周线】
{biweek_text}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
【六、6.10开盘策略】
{strategy}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
【七、时间窗口】
⏰ {tw_text}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
【八、风控要点】
• 跌破联合支撑区 = 无条件清仓
• 假突破识别：站上55线但MACD<0 → 不追涨
• 5F套娃循环：5F反弹但30F主跌 → 小心是X段

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚠️ 风险提示: 本分析基于缠论技术指标，不构成投资建议。
  市场有风险，投资需谨慎。
"""
    return report_text


# =====================================================
# 主程序
# =====================================================

def main():
    print("="*60)
    print("📊 缠论多级别联立分析 v3.5 - 完整版")
    print("="*60)
    
    ctx = init_api()
    symbol = "000001.SH"
    
    # 获取数据
    print("  获取1分钟数据...")
    df_1m = get_data(ctx, symbol, Period.Min_1, 500)
    
    print("  获取5分钟数据...")
    df_5m = get_data(ctx, symbol, Period.Min_5, 500)
    
    print("  获取30分钟数据...")
    df_30m = get_data(ctx, symbol, Period.Min_30, 300)
    
    print("  获取60分钟数据...")
    df_60m = get_data(ctx, symbol, Period.Min_60, 200)
    
    print("  获取日线数据...")
    df_daily = get_data(ctx, symbol, Period.Day, 600)
    
    current_price = df_5m['close'].iloc[-1] if df_5m is not None else 0
    date_str = datetime.now().strftime('%Y-%m-%d %H:%M')
    
    # 生成报告
    print("  分析中...")
    analyzer = ChanAnalysisV35(df_1m=df_1m, df_5m=df_5m, df_30m=df_30m, df_60m=df_60m, df_daily=df_daily)
    report = analyzer.generate_report()
    
    report_text = generate_report_text(report, current_price, date_str)
    
    print(report_text)
    send_feishu(report_text)
    print("✅ 报告已发送至飞书")


if __name__ == "__main__":
    main()
