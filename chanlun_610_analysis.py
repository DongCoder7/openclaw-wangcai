#!/root/.openclaw/workspace/venv/bin/python3
"""
缠论多级别联立分析 v3.5 - 6.10行情预判与策略
基于SKILL.md v3.5方法论：
- 十级别联立（1F/3F/5F/15F/30F/60F/120F/日线/双日/双周）
- 120F级别核心分析
- X段识别
- 联合支撑/压制区
- 底背离/顶背离检测
- 双周/55周线
- 级别传导链
- 时间窗口
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
        print(f"  ❌ 数据获取失败: {e}")
        return None


def send_feishu(message):
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


def calculate_ma(df, period):
    return df['close'].rolling(window=period).mean()


def calculate_boll(df, period=20):
    ma = df['close'].rolling(window=period).mean()
    std = df['close'].rolling(window=period).std()
    upper = ma + 2 * std
    lower = ma - 2 * std
    return ma, upper, lower


def calculate_macd(df, fast=12, slow=26, signal=9):
    ema_fast = df['close'].ewm(span=fast, adjust=False).mean()
    ema_slow = df['close'].ewm(span=slow, adjust=False).mean()
    dif = ema_fast - ema_slow
    dea = dif.ewm(span=signal, adjust=False).mean()
    hist = 2 * (dif - dea)
    return dif, dea, hist


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


def detect_divergence(df, window=20):
    """
    检测底背离/顶背离
    底背离: 价格创新低，MACD未创新低
    顶背离: 价格创新高，MACD未创新高
    """
    if len(df) < window + 5:
        return None, None
    
    close = df['close'].values
    dif = df['macd_dif'].values if 'macd_dif' in df.columns else None
    
    if dif is None:
        return None, None
    
    # 找近期低点和高点
    recent_low_idx = np.argmin(close[-window:])
    recent_low_idx += len(close) - window
    recent_low_price = close[recent_low_idx]
    recent_low_macd = dif[recent_low_idx]
    
    # 找前一波低点
    if recent_low_idx > 10:
        prev_window = close[max(0, recent_low_idx-20):recent_low_idx-3]
        if len(prev_window) > 5:
            prev_low_idx = np.argmin(prev_window)
            prev_low_idx += max(0, recent_low_idx-20)
            prev_low_price = close[prev_low_idx]
            prev_low_macd = dif[prev_low_idx]
            
            # 底背离判断
            if recent_low_price < prev_low_price * 0.998 and recent_low_macd > prev_low_macd * 1.05:
                return 'bottom_divergence', {
                    'prev_low': round(prev_low_price, 2),
                    'recent_low': round(recent_low_price, 2),
                    'prev_macd': round(prev_low_macd, 4),
                    'recent_macd': round(recent_low_macd, 4),
                    'strength': round((prev_low_macd - recent_low_macd) / abs(prev_low_macd) * 100, 2)
                }
    
    # 顶背离
    recent_high_idx = np.argmax(close[-window:])
    recent_high_idx += len(close) - window
    recent_high_price = close[recent_high_idx]
    recent_high_macd = dif[recent_high_idx]
    
    if recent_high_idx > 10:
        prev_window = close[max(0, recent_high_idx-20):recent_high_idx-3]
        if len(prev_window) > 5:
            prev_high_idx = np.argmax(prev_window)
            prev_high_idx += max(0, recent_high_idx-20)
            prev_high_price = close[prev_high_idx]
            prev_high_macd = dif[prev_high_idx]
            
            if recent_high_price > prev_high_price * 1.002 and recent_high_macd < prev_high_macd * 0.95:
                return 'top_divergence', {
                    'prev_high': round(prev_high_price, 2),
                    'recent_high': round(recent_high_price, 2),
                    'prev_macd': round(prev_high_macd, 4),
                    'recent_macd': round(recent_high_macd, 4),
                    'strength': round((prev_high_macd - recent_high_macd) / abs(prev_high_macd) * 100, 2)
                }
    
    return None, None


def analyze_level(df, level_name, ma_period=55, boll_period=20):
    """分析单个级别的55线、BOLL、MACD状态"""
    if df is None or len(df) < ma_period:
        return {
            'level': level_name,
            'valid': False,
            'data_count': len(df) if df is not None else 0,
            'reason': f'数据不足{ma_period}根'
        }
    
    df['ma55'] = calculate_ma(df, ma_period)
    df['boll_mid'], df['boll_upper'], df['boll_lower'] = calculate_boll(df, boll_period)
    df['macd_dif'], df['macd_dea'], df['macd_hist'] = calculate_macd(df)
    
    current = df['close'].iloc[-1]
    ma55 = df['ma55'].iloc[-1]
    boll_mid = df['boll_mid'].iloc[-1]
    boll_upper = df['boll_upper'].iloc[-1]
    boll_lower = df['boll_lower'].iloc[-1]
    dif = df['macd_dif'].iloc[-1]
    dea = df['macd_dea'].iloc[-1]
    hist = df['macd_hist'].iloc[-1]
    
    # 判断价格与MA55关系
    price_vs_ma55 = 'above' if current > ma55 else 'below'
    macd_sign = 'positive' if dif > 0 else 'negative'
    
    # 结构判断
    if price_vs_ma55 == 'above' and macd_sign == 'positive':
        structure = '主涨段'
        structure_score = 2
    elif price_vs_ma55 == 'below' and macd_sign == 'negative':
        structure = '主跌段'
        structure_score = -2
    elif price_vs_ma55 == 'above' and macd_sign == 'negative':
        structure = '55线上方X段'
        structure_score = -1
    else:
        structure = '55线下方X段'
        structure_score = 1
    
    # 假突破/骗炮判断
    fake_breakout = None
    if price_vs_ma55 == 'above' and macd_sign == 'negative':
        fake_breakout = '假突破/骗炮风险'
    elif price_vs_ma55 == 'below' and macd_sign == 'positive':
        fake_breakout = '假跌破/反弹信号'
    
    # 背离检测
    div_type, div_info = detect_divergence(df)
    
    # 极强期判断（MACD柱状体连续放大）
    hists = df['macd_hist'].values[-5:]
    extreme = False
    if len(hists) >= 3:
        if all(hists[i] > hists[i-1] for i in range(1, len(hists))) and hists[-1] > 0:
            extreme = '多头极强'
        elif all(hists[i] < hists[i-1] for i in range(1, len(hists))) and hists[-1] < 0:
            extreme = '空头极强'
    
    return {
        'level': level_name,
        'valid': True,
        'data_count': len(df),
        'current': round(current, 2),
        'ma55': round(ma55, 2),
        'boll_mid': round(boll_mid, 2),
        'boll_upper': round(boll_upper, 2),
        'boll_lower': round(boll_lower, 2),
        'dif': round(dif, 4),
        'dea': round(dea, 4),
        'hist': round(hist, 4),
        'price_vs_ma55': price_vs_ma55,
        'macd_sign': macd_sign,
        'structure': structure,
        'structure_score': structure_score,
        'fake_breakout': fake_breakout,
        'divergence': div_type,
        'divergence_info': div_info,
        'extreme': extreme,
        'dist_to_ma55_pct': round((current - ma55) / ma55 * 100, 2)
    }


def find_unified_zone(levels_data):
    """
    识别关键联合支撑/压制区
    只关注MA55之间、MA55与BOLL中轨之间的重叠
    """
    zones = []
    current_price = levels_data.get('日线', {}).get('current', 4000)
    
    # 关键级别对比组合（从大到小）
    key_levels = {}
    for name in ['日线', '双日', '120F', '60F', '30F', '5F']:
        if name in levels_data and levels_data[name]['valid']:
            key_levels[name] = {
                'ma55': levels_data[name]['ma55'],
                'boll_mid': levels_data[name]['boll_mid']
            }
    
    # 1. MA55 vs MA55 联合区
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
                    'levels': f"{n1}.MA55 + {n2}.MA55",
                    'zone_type': ztype,
                    'price': round(avg, 2),
                    'diff': round(diff, 2),
                    'strength': strength
                })
    
    # 2. MA55 vs BOLL中轨 联合区（同级或相邻级）
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
                    'levels': f"{n1}.MA55 + {n2}.BOLL中轨",
                    'zone_type': ztype,
                    'price': round(avg, 2),
                    'diff': round(diff, 2),
                    'strength': strength
                })
    
    # 去重并排序
    seen = set()
    unique_zones = []
    for z in zones:
        key = f"{z['zone_type']}_{z['price']}"
        if key not in seen and z['price'] > 0:
            seen.add(key)
            unique_zones.append(z)
    
    unique_zones.sort(key=lambda x: x['price'])
    return unique_zones


def analyze_transmission_chain(levels_data):
    """
    级别传导链分析
    小级别恶化/修复 → 中级别恶化/修复 → 大级别恶化/修复
    """
    chain = []
    
    # 从小级别到大级别检查结构
    level_order = ['1F', '3F', '5F', '15F', '30F', '60F', '120F', '日线', '双日']
    
    for level in level_order:
        if level not in levels_data or not levels_data[level]['valid']:
            continue
        data = levels_data[level]
        
        status = {
            'level': level,
            'structure': data['structure'],
            'score': data['structure_score'],
            'divergence': data['divergence'],
            'fake_breakout': data['fake_breakout']
        }
        chain.append(status)
    
    # 判断传导方向
    scores = [c['score'] for c in chain]
    if len(scores) >= 2:
        if scores[0] < 0 and scores[-1] < 0:
            # 下跌传导
            transmission = '下跌传导链进行中'
        elif scores[0] > 0 and scores[-1] > 0:
            transmission = '上涨传导链进行中'
        elif scores[0] < 0 and scores[-1] > 0:
            transmission = '小级别恶化，大级别仍多（可能反弹）'
        elif scores[0] > 0 and scores[-1] < 0:
            transmission = '小级别修复，大级别仍空（弱反弹）'
        else:
            transmission = '震荡/传导链不明'
    else:
        transmission = '数据不足，无法判断传导链'
    
    return chain, transmission


def generate_strategy_610(levels_data, unified_zones, transmission_chain, transmission_status):
    """
    生成6.10开盘策略
    """
    current = levels_data['日线']['current'] if '日线' in levels_data and levels_data['日线']['valid'] else None
    if current is None:
        return "❌ 数据不足，无法生成策略"
    
    # 找出最关键的联合支撑/压制区
    support_zones = [z for z in unified_zones if z['zone_type'] == '联合支撑']
    pressure_zones = [z for z in unified_zones if z['zone_type'] == '联合压制']
    
    key_support = support_zones[-1] if support_zones else None
    key_pressure = pressure_zones[0] if pressure_zones else None
    
    # 各级别状态摘要
    level_summary = []
    for name in ['5F', '30F', '60F', '120F', '日线', '双日']:
        if name in levels_data and levels_data[name]['valid']:
            d = levels_data[name]
            div_marker = "🔹" if d['divergence'] else ""
            fake_marker = ""
            if d['fake_breakout']:
                if '假突破' in d['fake_breakout'] or '骗炮' in d['fake_breakout']:
                    fake_marker = "⚠️假突破"
                elif '假跌破' in d['fake_breakout'] or '反弹' in d['fake_breakout']:
                    fake_marker = "⚠️假跌"
            level_summary.append(f"  {name}: {d['structure']} | 55线={d['ma55']} | MACD={'+' if d['dif']>0 else ''}{d['dif']:.2f} {div_marker} {fake_marker}")
    
    # 策略判断
    # 检查是否有底背离+联合支撑（P0信号）
    p0_signal = False
    for name in ['30F', '60F', '日线']:
        if name in levels_data and levels_data[name]['valid']:
            if levels_data[name]['divergence'] == 'bottom_divergence' and key_support:
                p0_signal = True
    
    # 检查顶背离+联合压制（P1信号）
    p1_signal = False
    for name in ['30F', '60F', '日线']:
        if name in levels_data and levels_data[name]['valid']:
            if levels_data[name]['divergence'] == 'top_divergence' and key_pressure:
                p1_signal = True
    
    # 核心判断
    daily = levels_data.get('日线', {})
    dual_day = levels_data.get('双日', {})
    
    # 判断当前态势
    if daily.get('structure') == '主跌段':
        trend = '🔴 日线主跌段 - 大方向偏空'
    elif daily.get('structure') == '55线上方X段':
        trend = '⚠️ 日线55线上方X段 - 极弱反弹，警惕回落'
    elif daily.get('structure') == '主涨段':
        trend = '🟢 日线主涨段 - 大方向偏多'
    else:
        trend = '➡️ 日线震荡 - 等待方向'
    
    # 60F/120F判断短期方向
    f60 = levels_data.get('60F', {})
    f120 = levels_data.get('120F', {})
    f30 = levels_data.get('30F', {})
    f5 = levels_data.get('5F', {})
    
    short_trend = []
    if f5.get('valid'):
        if f5['structure'] == '主涨段':
            short_trend.append("5F主涨")
        elif f5['structure'] == '主跌段':
            short_trend.append("5F主跌")
        else:
            short_trend.append("5F震荡")
    
    if f30.get('valid'):
        if f30['structure'] == '主涨段':
            short_trend.append("30F主涨")
        elif f30['structure'] == '主跌段':
            short_trend.append("30F主跌")
        else:
            short_trend.append("30F震荡")
    
    # 5F套娃结构判断（v3.5核心）
    taowa_warning = ""
    if f5.get('valid') and f30.get('valid'):
        if f5['price_vs_ma55'] == 'above' and f30['price_vs_ma55'] == 'below':
            taowa_warning = "⚠️ 5F站稳但30F主跌 → 5F反弹可能是X段，小心套娃循环"
    
    # 120F核心矛盾（v3.5核心）
    f120_note = ""
    if f120.get('valid'):
        if f120['price_vs_ma55'] == 'below':
            f120_note = f"📌 120F主跌段，核心问题：明天能否反抽到120F中轨({f120['boll_mid']})？不能→30F X段回抽后继续新低"
    
    # 生成具体策略
    if p0_signal and key_support:
        strategy = f"""
🎯 核心信号：P0 底背离 + 联合支撑区（高胜率买点）
   位置: {key_support['price']}附近
   操作: 轻仓试多，止损{key_support['price']-15:.0f}"""
    elif p1_signal and key_pressure:
        strategy = f"""
🎯 核心信号：P1 顶背离 + 联合压制区（高胜率卖点）
   位置: {key_pressure['price']}附近
   操作: 减仓/清仓"""
    elif daily.get('structure') == '主跌段':
        strategy = f"""
🎯 核心策略：日线主跌段，空仓/轻仓观望
   操作: 
   • 开盘若跌破5F55线({f5.get('ma55', 'N/A')})→确认下跌传导，不操作
   • 若反弹到120F中轨({f120.get('boll_mid', 'N/A')})遇阻→减仓
   • 耐心等待日线级别底背离+联合支撑区才考虑建仓"""
    elif daily.get('structure') == '55线上方X段':
        strategy = f"""
🎯 核心策略：日线55线上方X段（极弱），观望为主
   操作:
   • 5F反弹可能是X段，不追涨
   • 若跌破5F55线({f5.get('ma55', 'N/A')})→继续套娃下跌
   • 关注联合支撑区: {key_support['price'] if key_support else 'N/A'}"""
    else:
        strategy = f"""
🎯 核心策略：震荡观望，等待方向确认
   操作:
   • 突破联合压制区({key_pressure['price'] if key_pressure else 'N/A'})→加仓
   • 跌破联合支撑区({key_support['price'] if key_support else 'N/A'})→清仓"""
    
    # 具体点位表
    key_levels_text = ""
    if key_support:
        key_levels_text += f"  • 联合支撑: {key_support['price']} ({key_support['strength']})\n"
    if key_pressure:
        key_levels_text += f"  • 联合压制: {key_pressure['price']} ({key_pressure['strength']})\n"
    
    # 时间窗口
    time_window = ""
    if dual_day.get('valid'):
        if dual_day['hist'] < 0.5 and dual_day['dif'] > dual_day['dea']:
            time_window = "⏰ 双日MACD接近死叉，若明日形成死叉需3-5天修复，短期时间窗口未打开"
        elif dual_day['hist'] < 0:
            time_window = "⏰ 双日已死叉，等待金叉时间窗口，短期不操作"
        elif dual_day['hist'] > 1:
            time_window = "⏰ 双日MACD安全，正常操作"
    
    report = f"""
📊 上证指数缠论多级别联立分析 - 6.10行情预判与策略
⏰ 分析时间: 2026-06-09 收盘
📌 当前收盘: {current}点

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
【一、多级别状态联立】
{chr(10).join(level_summary)}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
【二、大周期趋势判断】
{trend}

短期结构: {' | '.join(short_trend)}

{taowa_warning}

{f120_note}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
【三、联合支撑/压制区】
{key_levels_text}
  (联合区 = 两个级别关键价位重叠&lt;20点，力度更强)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
【四、级别传导链】
{transmission_status}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
【五、6.10开盘策略】
{strategy}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
【六、时间窗口】
{time_window}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
【七、风控要点】
• 跌破联合支撑区 = 无条件清仓
• 假突破识别：站上55线但MACD&lt;0 → 不追涨
• 5F套娃循环：5F反弹但30F主跌 → 小心是X段

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚠️ 风险提示: 本分析基于缠论技术指标，不构成投资建议。
  市场有风险，投资需谨慎。
"""
    return report


def main():
    print("=" * 60)
    print("📊 缠论多级别联立分析 v3.5 - 6.10行情预判")
    print("=" * 60)
    
    ctx = init_api()
    symbol = "000001.SH"
    
    # 获取各级别数据
    print("  获取1分钟数据...")
    df_1m = get_data(ctx, symbol, Period.Min_1, 500)
    
    print("  获取5分钟数据...")
    df_5m = get_data(ctx, symbol, Period.Min_5, 500)
    
    print("  获取30分钟数据...")
    df_30m = get_data(ctx, symbol, Period.Min_30, 300)
    
    print("  获取60分钟数据...")
    df_60m = get_data(ctx, symbol, Period.Min_60, 200)
    
    print("  获取日线数据...")
    df_daily = get_data(ctx, symbol, Period.Day, 120)
    
    # 合成3F、15F、120F、双日
    print("  合成3分钟...")
    df_3m = resample_kline(df_1m, '3min') if df_1m is not None else None
    
    print("  合成15分钟...")
    df_15m = resample_kline(df_5m, '15min') if df_5m is not None else None
    
    print("  合成120分钟...")
    df_120m = resample_kline(df_60m, '120min') if df_60m is not None else None
    
    print("  合成双日...")
    df_dual_day = resample_kline(df_daily, '2D') if df_daily is not None else None
    
    # 分析各级别
    print("  分析各级别...")
    levels_data = {}
    
    if df_1m is not None and len(df_1m) >= 55:
        levels_data['1F'] = analyze_level(df_1m, '1F', ma_period=55)
    
    if df_3m is not None and len(df_3m) >= 55:
        levels_data['3F'] = analyze_level(df_3m, '3F', ma_period=55)
    
    if df_5m is not None and len(df_5m) >= 55:
        levels_data['5F'] = analyze_level(df_5m, '5F', ma_period=55)
    
    if df_15m is not None and len(df_15m) >= 55:
        levels_data['15F'] = analyze_level(df_15m, '15F', ma_period=55)
    
    if df_30m is not None and len(df_30m) >= 55:
        levels_data['30F'] = analyze_level(df_30m, '30F', ma_period=55)
    
    if df_60m is not None and len(df_60m) >= 55:
        levels_data['60F'] = analyze_level(df_60m, '60F', ma_period=55)
    
    if df_120m is not None and len(df_120m) >= 55:
        levels_data['120F'] = analyze_level(df_120m, '120F', ma_period=55)
    
    if df_daily is not None and len(df_daily) >= 55:
        levels_data['日线'] = analyze_level(df_daily, '日线', ma_period=55, boll_period=20)
    
    if df_dual_day is not None and len(df_dual_day) >= 55:
        levels_data['双日'] = analyze_level(df_dual_day, '双日', ma_period=55, boll_period=20)
    
    # 识别联合支撑/压制区
    print("  识别联合支撑/压制区...")
    unified_zones = find_unified_zone(levels_data)
    
    # 分析级别传导链
    print("  分析级别传导链...")
    transmission_chain, transmission_status = analyze_transmission_chain(levels_data)
    
    # 生成6.10策略
    print("  生成6.10策略...")
    report = generate_strategy_610(levels_data, unified_zones, transmission_chain, transmission_status)
    
    print(report)
    send_feishu(report)
    print("✅ 报告已发送至飞书")


if __name__ == "__main__":
    main()
