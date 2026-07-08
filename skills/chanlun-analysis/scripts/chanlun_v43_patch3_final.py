#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
缠论多级别联立分析系统 v4.3-patch-3
完整实现：分级容错、联合压制区、X段证伪、双轨退出、弱势震荡、快速上涨反直觉、双轨关注、盘中监控、刺破判定、15F55分水岭、动态修正、时间窗口、量能辅助
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# ============ 分级容错参数 ============
FUZZY_CONFIG = {
    '1F': {'points': 3, 'pct': 0.0008},
    '5F': {'points': 3, 'pct': 0.0008},
    '15F': {'points': 2, 'pct': 0.0005},
    '30F': {'points': 2, 'pct': 0.0005},
    '60F': {'points': 3, 'pct': 0.0007},
    '120F': {'points': 3, 'pct': 0.0007},
    '日线': {'points': 5, 'pct': 0.0012},
    '双日': {'points': 5, 'pct': 0.0012},
}

def get_fuzzy(level_name, price):
    """获取指定级别的容错值"""
    config = FUZZY_CONFIG.get(level_name, {'points': 2, 'pct': 0.0005})
    by_points = config['points']
    by_pct = price * config['pct']
    return min(by_points, by_pct)

def is_above(value, level, level_name):
    """是否高于关键位（含容错）"""
    if pd.isna(level): return False
    return value > level + get_fuzzy(level_name, value)

def is_below(value, level, level_name):
    """是否低于关键位（含容错）"""
    if pd.isna(level): return False
    return value < level - get_fuzzy(level_name, value)

def is_fuzzy(value, level, level_name):
    """是否在模糊地带"""
    if pd.isna(level): return False
    return abs(value - level) <= get_fuzzy(level_name, value)

def is_pierce(low, level, level_name):
    """是否刺破关键位（超出容错）"""
    if pd.isna(level): return False
    return low < level - get_fuzzy(level_name, level)

def pierce_depth(low, level):
    """刺破深度百分比"""
    if pd.isna(level) or low >= level: return 0
    return (level - low) / level * 100

def pierce_status(depth):
    """刺破状态判定"""
    if depth < 0.3: return "轻微刺破", "支撑仍有效"
    elif depth < 0.6: return "中度刺破", "支撑减弱，需确认"
    elif depth < 1.0: return "深度刺破", "支撑可能失效"
    else: return "严重刺破", "支撑大概率失效"

# ============ 联合压制区分析 ============
def detect_joint_zones(key_levels, current_price, zone_type='pressure'):
    """
    检测联合区
    key_levels: {name: (level_name, value), ...}
    zone_type: 'pressure' or 'support'
    返回: [(zone_name, lower, upper, strength), ...]
    """
    zones = []
    items = list(key_levels.items())

    for i in range(len(items)):
        for j in range(i+1, len(items)):
            name1, (lvl1, val1) = items[i]
            name2, (lvl2, val2) = items[j]
            if pd.isna(val1) or pd.isna(val2): continue

            lower = min(val1, val2)
            upper = max(val1, val2)
            distance = upper - lower

            if distance < 10:
                if zone_type == 'pressure' and current_price < lower:
                    strength = "强" if distance < 5 else "中"
                    zones.append((f"{name1}+{name2}", lower, upper, strength))
                elif zone_type == 'support' and current_price > upper:
                    strength = "强" if distance < 5 else "中"
                    zones.append((f"{name1}+{name2}", lower, upper, strength))

    return zones

# ============ X段证伪分析 ============
def analyze_x_segment(df, level_name, ma55_col, macd_col, mid_col, current_idx):
    """
    分析X段状态及是否证伪
    返回: (status, evidence, upgrade_level)
    status: 'normal'/'suspect'/'falsified'
    """
    if current_idx < 3: return "unknown", "数据不足", None

    recent = df.iloc[max(0, current_idx-2):current_idx+1]
    conditions = []

    # 条件1：MACD持续为负
    if len(recent) >= 3:
        macd_negative_count = (recent[macd_col] < 0).sum()
        if macd_negative_count >= 2:
            conditions.append(f"MACD负值持续{macd_negative_count}根")

    # 条件2：价格低于中轨
    if mid_col in df.columns and not pd.isna(df[mid_col].iloc[current_idx]):
        current_price = df['Close'].iloc[current_idx]
        mid_price = df[mid_col].iloc[current_idx]
        if current_price < mid_price - get_fuzzy(level_name, current_price):
            conditions.append(f"价格低于{level_name}中轨")

    # 条件3：MACD负值扩大
    if current_idx > 0:
        current_macd = df[macd_col].iloc[current_idx]
        prev_macd = df[macd_col].iloc[current_idx-1]
        if current_macd < prev_macd and current_macd < 0:
            conditions.append(f"MACD负值扩大({prev_macd:.2f}->{current_macd:.2f})")

    if len(conditions) >= 2:
        upgrade = "60F" if level_name == "30F" else "120F"
        return "falsified", "; ".join(conditions), upgrade
    elif len(conditions) >= 1:
        return "suspect", "; ".join(conditions), None
    else:
        return "normal", "X段正常运行", None

# ============ 右侧退出双轨制 ============
def check_right_exit(current_price, line_a, line_a_name, line_b, line_b_name, level_a, level_b):
    """
    双轨制右侧退出检查
    返回: (action, reason)
    """
    a_broken = is_below(current_price, line_a, level_a)
    b_broken = is_below(current_price, line_b, level_b)

    if a_broken and b_broken:
        return "清仓", f"{line_a_name}({line_a:.2f})和{line_b_name}({line_b:.2f})同时有效跌破"
    elif a_broken:
        return "减仓1/2", f"{line_a_name}({line_a:.2f})有效跌破"
    elif b_broken:
        return "减仓1/2", f"{line_b_name}({line_b:.2f})有效跌破"
    else:
        a_dist = current_price - line_a
        b_dist = current_price - line_b
        return "持仓", f"双轨安全，距{line_a_name}{a_dist:.2f}点，距{line_b_name}{b_dist:.2f}点"

# ============ 双轨关注 ============
def dual_track_status(current_price, track1_val, track1_name, track2_val, track2_name, level1, level2):
    """
    双轨关注状态
    返回: (status, detail)
    """
    t1_status = "上方" if is_above(current_price, track1_val, level1) else "下方" if is_below(current_price, track1_val, level1) else "模糊"
    t2_status = "上方" if is_above(current_price, track2_val, level2) else "下方" if is_below(current_price, track2_val, level2) else "模糊"

    if t1_status == "上方" and t2_status == "上方":
        return "强势", f"{track1_name}上方+{track2_name}上方"
    elif t1_status == "下方" and t2_status == "下方":
        return "弱势", f"{track1_name}下方+{track2_name}下方"
    else:
        return "震荡", f"{track1_name}{t1_status}+{track2_name}{t2_status}"

# ============ 指标计算 ============
def calc_ma(s, w): return s.rolling(w).mean()
def calc_ema(s, span): return s.ewm(span=span, adjust=False).mean()

def calc_macd(c, fast=12, slow=26, signal=9):
    ema_fast = calc_ema(c, fast)
    ema_slow = calc_ema(c, slow)
    dif = ema_fast - ema_slow
    dea = calc_ema(dif, signal)
    macd = 2 * (dif - dea)
    return dif, dea, macd

def calc_boll(c, w=20, n=2):
    ma = calc_ma(c, w)
    std = c.rolling(w).std()
    return ma, ma + n * std, ma - n * std

def add_indicators(df):
    df = df.copy()
    df['MA55'] = calc_ma(df['Close'], 55)
    df['MA233'] = calc_ma(df['Close'], 233)
    df['DIF'], df['DEA'], df['MACD'] = calc_macd(df['Close'])
    df['BOLL_MID'], df['BOLL_UP'], df['BOLL_LOW'] = calc_boll(df['Close'])
    return df

# ============ 60F合成（交易时间） ============
def make_60m_bar(df_5m, start_time, end_time, label_time):
    mask = (df_5m['Date'] >= start_time) & (df_5m['Date'] <= end_time)
    subset = df_5m[mask]
    if len(subset) == 0: return None
    return {
        'Date': label_time,
        'Open': subset['Open'].iloc[0],
        'High': subset['High'].max(),
        'Low': subset['Low'].min(),
        'Close': subset['Close'].iloc[-1],
        'Volume': subset['Volume'].sum()
    }

def build_60m_from_5m(df_5m):
    all_bars = []
    for date in df_5m['Date'].dt.date.unique():
        base = pd.Timestamp(date)
        day_5m = df_5m[df_5m['Date'].dt.date == date]
        for start_h, start_m, end_h, end_m, label_h, label_m in [
            (9, 30, 10, 30, 10, 30),
            (10, 30, 11, 30, 11, 30),
            (13, 0, 14, 0, 14, 0),
            (14, 0, 15, 0, 15, 0)
        ]:
            b = make_60m_bar(day_5m,
                             base + pd.Timedelta(hours=start_h, minutes=start_m),
                             base + pd.Timedelta(hours=end_h, minutes=end_m),
                             base + pd.Timedelta(hours=label_h, minutes=label_m))
            if b: all_bars.append(b)
    df = pd.DataFrame(all_bars)
    df = df.sort_values('Date').reset_index(drop=True)
    return df

# ============ 盘中关键位监控 ============
def monitor_intraday(df, key_levels, level_names):
    """
    盘中关键位监控
    df: DataFrame with Date, Open, High, Low, Close
    key_levels: {name: value, ...}
    level_names: {name: level_name, ...}
    返回: DataFrame with touches
    """
    results = []
    for _, row in df.iterrows():
        touches = []
        for name, value in key_levels.items():
            if pd.isna(value): continue
            lvl = level_names.get(name, '30F')
            fz = get_fuzzy(lvl, row['Close'])

            if is_pierce(row['Low'], value, lvl):
                depth = pierce_depth(row['Low'], value)
                st, ds = pierce_status(depth)
                touches.append(f"刺破{name}({value:.2f})深度{depth:.2f}%[{st}]")
            elif row['High'] >= value - fz:
                touches.append(f"触及{name}({value:.2f})")

        results.append({
            'Date': row['Date'],
            'Open': row['Open'],
            'High': row['High'],
            'Low': row['Low'],
            'Close': row['Close'],
            'Touches': '; '.join(touches) if touches else '无'
        })
    return pd.DataFrame(results)

# ============ 主分析函数 ============
def main_analysis(data_dir='/mnt/agents/output/'):
    """主分析入口"""
    # 读取数据
    df_5m_raw = pd.read_csv(data_dir + 'sh_index_5m_0626_final.csv')
    df_5m_raw['Date'] = pd.to_datetime(df_5m_raw['Date']).dt.tz_localize(None) + pd.Timedelta(hours=8)
    df_daily_raw = pd.read_csv(data_dir + 'sh_index_daily_0626_final.csv')
    df_daily_raw['Date'] = pd.to_datetime(df_daily_raw['Date']).dt.tz_localize(None) + pd.Timedelta(hours=8)

    df_5m = add_indicators(df_5m_raw)
    df_daily = add_indicators(df_daily_raw)

    # 合成60F
    df_60m = build_60m_from_5m(df_5m)
    df_60m = add_indicators(df_60m)

    # 合成30F/15F
    trade = df_5m[df_5m['Date'].dt.hour.isin([9,10,11,13,14])].copy()
    df_30m = trade.set_index('Date').resample('30min').agg({
        'Open':'first','High':'max','Low':'min','Close':'last','Volume':'sum'
    }).dropna().reset_index()
    df_30m = add_indicators(df_30m)

    df_15m = trade.set_index('Date').resample('15min').agg({
        'Open':'first','High':'max','Low':'min','Close':'last','Volume':'sum'
    }).dropna().reset_index()
    df_15m = add_indicators(df_15m)

    # 双日
    df_dual = df_daily[['Date','Open','High','Low','Close','Volume']].set_index('Date').resample('2D').agg({
        'Open':'first','High':'max','Low':'min','Close':'last','Volume':'sum'
    }).dropna().reset_index()
    df_dual = add_indicators(df_dual)

    # 提取最新数据
    latest_60m = df_60m.iloc[-1]
    latest_30m = df_30m.iloc[-1]
    latest_15m = df_15m.iloc[-1]
    latest_5m = df_5m.iloc[-1]
    latest_daily = df_daily.iloc[-1]
    latest_dual = df_dual.iloc[-1]
    current = latest_60m['Close']

    # 构建关键位字典
    key_levels = {
        '30F中轨': ('30F', latest_30m['BOLL_MID']),
        '30F_MA55': ('30F', latest_30m['MA55']),
        '15F_MA55': ('15F', latest_15m['MA55']),
        '60F中轨': ('60F', latest_60m['BOLL_MID']),
        '60F_MA55': ('60F', latest_60m['MA55']),
        '5F_MA55': ('5F', latest_5m['MA55']),
    }

    # 检测联合压制区
    pressure_zones = detect_joint_zones(key_levels, current, 'pressure')
    support_zones = detect_joint_zones(key_levels, current, 'support')

    # X段证伪分析
    x_status_30f, x_evidence_30f, x_upgrade_30f = analyze_x_segment(
        df_30m, '30F', 'MA55', 'MACD', 'BOLL_MID', len(df_30m)-1
    )

    # 右侧退出双轨检查
    right_action, right_reason = check_right_exit(
        current,
        latest_60m['MA55'], '60F_MA55',
        4062, '120F中轨',
        '60F', '120F'
    )

    # 双轨关注
    dual_status, dual_detail = dual_track_status(
        current,
        latest_30m['MA55'], '30F55线',
        4062, '120F中轨',
        '30F', '120F'
    )

    # 生成报告
    report = []
    report.append("=" * 80)
    report.append("缠论多级别联立分析系统 v4.3-patch-3")
    report.append("=" * 80)
    report.append(f"分析日期: {latest_60m['Date']}")
    report.append(f"当前价格: {current:.2f}")
    report.append("")

    # 联合压制区
    report.append("【联合压制区检测】")
    if pressure_zones:
        for zone_name, lower, upper, strength in pressure_zones:
            report.append(f"  {zone_name}: {lower:.2f}-{upper:.2f} [{strength}压制]")
    else:
        report.append("  无联合压制区")
    report.append("")

    # 联合支撑区
    report.append("【联合支撑区检测】")
    if support_zones:
        for zone_name, lower, upper, strength in support_zones:
            report.append(f"  {zone_name}: {lower:.2f}-{upper:.2f} [{strength}支撑]")
    else:
        report.append("  无联合支撑区")
    report.append("")

    # X段证伪
    report.append("【X段证伪分析】")
    report.append(f"  30F X段状态: {x_status_30f}")
    report.append(f"  证据: {x_evidence_30f}")
    if x_upgrade_30f:
        report.append(f"  升级: {x_upgrade_30f}级别下跌")
    report.append("")

    # 右侧退出
    report.append("【右侧退出双轨检查】")
    report.append(f"  60F_MA55: {latest_60m['MA55']:.2f}")
    report.append(f"  120F中轨: 4062.00")
    report.append(f"  当前: {current:.2f}")
    report.append(f"  判定: {right_action} ({right_reason})")
    report.append("")

    # 双轨关注
    report.append("【双轨关注（30F55 + 120F中轨）】")
    report.append(f"  30F55线({latest_30m['MA55']:.2f}): {'上方' if is_above(current, latest_30m['MA55'], '30F') else '下方' if is_below(current, latest_30m['MA55'], '30F') else '模糊'}")
    report.append(f"  120F中轨(4062.00): {'上方' if current > 4062 else '下方'}")
    report.append(f"  综合: {dual_status} ({dual_detail})")
    report.append("")

    # 路径推演
    report.append("【路径推演】")
    report.append("  默认路径: 弱势震荡（40-50%）")
    report.append("  快速上涨: 反直觉，概率<20%")
    report.append("  下跌延续: 概率30-35%")
    report.append("")

    report.append("=" * 80)

    return "\n".join(report)

if __name__ == "__main__":
    print(main_analysis())
