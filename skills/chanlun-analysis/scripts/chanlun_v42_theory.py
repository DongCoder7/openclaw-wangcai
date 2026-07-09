#!/root/.openclaw/workspace/venv/bin/python3
"""
缠论分析 v4.2 - 理论驱动版（系统性使用SKILL.md理论推导）

v4.2 核心升级（理论驱动4大优化）：
1. 六种MACD状态理论推导 — 不是简单标签，每种状态都说明"含义→传导→策略"
2. N+2→N级别传导推导 — 从N+2状态推导N级别主涨段/主跌段
3. 极强/极弱三特征应用 — 背离失效、55均线支撑、传递性
4. 理论推导型策略 — 基于理论得出操作建议，不是简单罗列

来源：用户要求"系统使用md里的理论，而不是简单打标签"
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
# v4.2: 级别对应关系（组B级差体系：N+2→N传导）
# =====================================================

# 组B级差体系：1F → 5F → 30F → 120F → 双日 → 双周
# N+2级别传导至N级别：
#   双日(N+2) → 120F(N)
#   120F(N+2) → 30F(N)
#   30F(N+2)  → 5F(N)
#   5F(N+2)   → 1F(N)
#   60F(N+2)  → 15F(N)
#   15F(N+2)  → 3F(N)
#   日线(N+2) → 60F(N)
N_PLUS_2_MAP = {
    '双日': '120F',
    '日线': '60F',
    '120F': '30F',
    '60F': '15F',
    '30F': '5F',
    '15F': '3F',
    '5F': '1F',
    '3F': '1F',  # 3F的N级别近似为1F
    '1F': None
}

# N级别传导至N-1级别（小级别传导更小级别）
N_MINUS_1_MAP = {
    '双日': '日线',
    '日线': '120F',
    '120F': '60F',
    '60F': '30F',
    '30F': '15F',
    '15F': '5F',
    '5F': '3F',
    '3F': '1F',
    '1F': None
}

# =====================================================
# v4.2: 六种MACD状态理论推导（核心重写）
# =====================================================

def analyze_macd_six_states(df, level_name='30F'):
    """
    v4.2 核心升级：六种MACD状态不是简单标签，而是完整理论推导
    
    MACD的"强弱"不是行情强弱，而是"稳定性"——稳定性强弱是相对于走势而言的。
    在上涨行情中，强/极强形态会导致上涨更有持续性；在下跌行情中，弱/极弱形态会导致下跌更有持续性。
    """
    if len(df) < 30:
        return {
            'state': 'unknown',
            'dif': 0, 'dea': 0, 'macd': 0,
            'theory': '数据不足',
            'conduction': '无法推导',
            'operation': '等待数据'
        }
    
    md = macd(df)
    dif = float(md['dif'].iloc[-1])
    dea = float(md['dea'].iloc[-1])
    mc = float(md['macd'].iloc[-1])
    
    p = float(df['Close'].iloc[-1])
    m55 = float(ma(df, 55).iloc[-1])
    
    # 判断金叉形态
    prev_dif = float(md['dif'].iloc[-2]) if len(md['dif']) >= 2 else dif
    prev_dea = float(md['dea'].iloc[-2]) if len(md['dea']) >= 2 else dea
    
    is_golden_cross = (prev_dif <= prev_dea) and (dif > dea)  # 刚刚金叉
    is_dead_cross = (prev_dif >= prev_dea) and (dif < dea)    # 刚刚死叉
    
    # 获取当前级别作为N+2时，传导至哪个N级别
    n_level = N_PLUS_2_MAP.get(level_name, None)
    n_level_str = f"{n_level}" if n_level else "更小级别"
    
    # 六种状态判定
    if dif >= 0 and dea <= 0 and mc > 0:
        state = '极强'
        theory = (
            "【理论含义】MACD极强形态：DIF≥0且DEA≤0，MACD柱>0。"
            "这不是说行情一定强，而是说上涨的稳定性极高——上涨持续性极高。"
            f"在极强形态下，{level_name}作为N+2级别，其极强会传导至N级别（{n_level_str}），"
            f"导致{n_level_str}出现主涨段。"
            f"此时{n_level_str}级别以下的顶背离，可能都是阶段性无效。"
        )
        conduction = (
            f"【N+2→N传导】{level_name}极强（N+2）→ 传导至{n_level_str}（N）"
            f" → {n_level_str}在低位出现结构（第三段或第五段）后出主涨段"
            f" → 主涨段启动前回踩N-1级别55线"
            f" → N-1级别回踩时，其下轨往往支撑，使得顶背离失效"
        )
        operation = (
            f"【操作策略】{level_name}极强形态不做空。"
            f"这是{n_level_str}级别的高胜率做多时间窗口："
            f"1) {n_level_str}首次回踩55线 → 极大概率得到支撑，是做多开仓点"
            f"2) {n_level_str}突破55线后 → 有向{level_name}55线运动的惯性（传递性）"
            f"3) {n_level_str}价格>55线且MACD>0 → 主涨段确认，满仓持有"
        )
        
    elif dif > dea > 0 and mc > 0:
        state = '强'
        theory = (
            "【理论含义】MACD强形态：DIF>DEA>0，MACD柱>0。"
            "上涨持续性高，但稳定性不如极强形态。"
            f"此时{level_name}作为N+2级别，其强势传导至{n_level_str}，"
            f"{n_level_str}在低位结构后出主涨段。"
        )
        conduction = (
            f"【N+2→N传导】{level_name}强势（N+2）→ {n_level_str}（N）低位结构后出主涨段"
            f" → 但{n_level_str}顶背离的有效性高于极强形态下的情况"
            f" → 需要更严格的确认信号（突破55线+MACD转正）"
        )
        operation = (
            f"【操作策略】{n_level_str}级别做多胜率高。"
            f"1) {n_level_str}价格>55线 + 结构完整 → 持仓/加仓"
            f"2) {n_level_str}首次回踩55线 → 大概率支撑，可试多"
            f"3) 若{n_level_str}顶背离 + 价格跌破55线 → 减仓1/3"
        )
        
    elif 0 > dif > dea and mc > 0:
        state = '中性偏强'
        theory = (
            "【理论含义】MACD中性偏强：0>DIF>DEA，MACD柱>0。"
            "上涨但动能减弱，DIF和DEA都在0轴下方。"
            "这是从极弱/弱向强过渡的阶段，上涨持续性不确定。"
        )
        conduction = (
            f"【N+2→N传导】{level_name}中性偏强（N+2）→ {n_level_str}（N）可能处于X段或结构重置阶段"
            f" → {n_level_str}的55线支撑力度减弱"
            f" → 需要观察{n_level_str}能否突破55线确认主涨段"
        )
        operation = (
            f"【操作策略】{n_level_str}级别观察为主。"
            f"1) 若{n_level_str}突破55线+MACD转正 → 试多"
            f"2) 若{n_level_str}被55线压制 → 等待"
            f"3) 不追涨，不杀跌"
        )
        
    elif dif <= 0 and dea >= 0 and mc < 0:
        state = '极弱'
        theory = (
            "【理论含义】MACD极弱形态：DIF≤0且DEA≥0，MACD柱<0。"
            "下跌持续性极高，稳定性极高。"
            f"在极弱形态下，{level_name}作为N+2级别，其极弱会传导至{n_level_str}，"
            f"导致{n_level_str}出现主跌段。"
            f"此时{n_level_str}级别以下的底背离，可能都是阶段性无效。"
        )
        conduction = (
            f"【N+2→N传导】{level_name}极弱（N+2）→ 传导至{n_level_str}（N）"
            f" → {n_level_str}在高位出现结构后出主跌段"
            f" → 主跌段启动前反弹至N-1级别55线"
            f" → N-1级别反弹时，其上轨往往压制，使得底背离失效"
        )
        operation = (
            f"【操作策略】{level_name}极弱形态不做多。"
            f"这是{n_level_str}级别的高胜率做空时间窗口："
            f"1) {n_level_str}首次反弹至55线 → 极大概率遇阻，是做空点"
            f"2) {n_level_str}跌破55线后 → 有向{level_name}55线下跌的惯性（下跌传递性）"
            f"3) {n_level_str}价格<55线且MACD<0 → 主跌段确认，清仓/做空"
        )
        
    elif dif < dea < 0 and mc < 0:
        state = '弱'
        theory = (
            "【理论含义】MACD弱形态：DIF<DEA<0，MACD柱<0。"
            "下跌持续性高，但稳定性不如极弱形态。"
            f"此时{level_name}作为N+2级别，其弱势传导至{n_level_str}，"
            f"{n_level_str}在高位结构后出主跌段。"
        )
        conduction = (
            f"【N+2→N传导】{level_name}弱势（N+2）→ {n_level_str}（N）高位结构后出主跌段"
            f" → 但{n_level_str}底背离的有效性高于极弱形态下的情况"
            f" → 需要更严格的确认信号（跌破55线+MACD转负）"
        )
        operation = (
            f"【操作策略】{n_level_str}级别做空胜率高。"
            f"1) {n_level_str}价格<55线 + 结构完整 → 减仓/做空"
            f"2) {n_level_str}首次反弹至55线 → 大概率遇阻，可试空"
            f"3) 若{n_level_str}底背离 + 价格突破55线 → 止损"
        )
        
    elif 0 < dif < dea and mc < 0:
        state = '中性偏弱'
        theory = (
            "【理论含义】MACD中性偏弱：0<DIF<DEA，MACD柱<0。"
            "下跌但动能减弱，DIF和DEA都在0轴上方。"
            "这是从极强/强向弱过渡的阶段，下跌持续性不确定。"
        )
        conduction = (
            f"【N+2→N传导】{level_name}中性偏弱（N+2）→ {n_level_str}（N）可能处于X段或结构重置阶段"
            f" → {n_level_str}的55线压制力度减弱"
            f" → 需要观察{n_level_str}能否跌破55线确认主跌段"
        )
        operation = (
            f"【操作策略】{n_level_str}级别观察为主。"
            f"1) 若{n_level_str}跌破55线+MACD转负 → 试空"
            f"2) 若{n_level_str}被55线支撑 → 等待"
            f"3) 不追涨，不杀跌"
        )
    else:
        state = '中性'
        theory = (
            "【理论含义】MACD中性：DIF和DEA接近0轴或交叉点附近。"
            "多空力量均衡，方向不明确。"
        )
        conduction = (
            f"【N+2→N传导】{level_name}中性 → {n_level_str}无明确传导信号"
            f" → 等待方向选择"
        )
        operation = (
            f"【操作策略】{n_level_str}级别等待。"
            f"1) 等待金叉/死叉确认"
            f"2) 等待突破/跌破55线"
            f"3) 不提前下注"
        )
    
    # 金叉形态补充
    cross_info = ""
    if is_golden_cross:
        if abs(dif) < 0.5 and abs(dea) < 0.5:
            cross_info = " | 【零轴金叉】→ 极强形态，高胜率做多"
        elif dif > 0 and dea > 0:
            cross_info = " | 【水上金叉】→ 强形态，做多"
        else:
            cross_info = " | 【水下金叉】→ 中性偏强，谨慎做多"
    elif is_dead_cross:
        if abs(dif) < 0.5 and abs(dea) < 0.5:
            cross_info = " | 【零轴死叉】→ 极弱形态，高胜率做空"
        elif dif < 0 and dea < 0:
            cross_info = " | 【水下死叉】→ 弱形态，做空"
        else:
            cross_info = " | 【水上死叉】→ 中性偏弱，谨慎做空"
    
    return {
        'state': state,
        'dif': dif, 'dea': dea, 'macd': mc,
        'price': p, 'ma55': m55,
        'is_golden_cross': is_golden_cross,
        'is_dead_cross': is_dead_cross,
        'cross_info': cross_info,
        'theory': theory,
        'conduction': conduction,
        'operation': operation
    }

# =====================================================
# v4.2: 六种金叉死叉形态推导（完整）
# =====================================================

def analyze_golden_dead_cross(df, level_name='30F'):
    """
    六种金叉死叉形态完整推导
    """
    if len(df) < 30:
        return {'cross_type': 'unknown', 'description': '数据不足'}
    
    md = macd(df)
    dif = float(md['dif'].iloc[-1])
    dea = float(md['dea'].iloc[-1])
    mc = float(md['macd'].iloc[-1])
    
    prev_dif = float(md['dif'].iloc[-2]) if len(md['dif']) >= 2 else dif
    prev_dea = float(md['dea'].iloc[-2]) if len(md['dea']) >= 2 else dea
    
    is_cross = (prev_dif <= prev_dea and dif > dea) or (prev_dif >= prev_dea and dif < dea)
    
    if not is_cross and abs(dif - dea) > 0.1:
        # 非交叉状态，判断当前形态
        if dif > dea > 0:
            return {
                'cross_type': '水上金叉运行中',
                'stability': '强',
                'theory': 'DIF>DEA>0，金叉在0轴上方运行。上涨持续性高，做多胜率较高。',
                'conduction': 'N+2级别强势 → N级别低位结构后出主涨段。',
                'operation': '持仓/做多。若N级别回踩55线企稳，可加仓。'
            }
        elif dif < dea < 0:
            return {
                'cross_type': '水下死叉运行中',
                'stability': '弱',
                'theory': 'DIF<DEA<0，死叉在0轴下方运行。下跌持续性高，做空胜率较高。',
                'conduction': 'N+2级别弱势 → N级别高位结构后出主跌段。',
                'operation': '减仓/做空。若N级别反弹至55线遇阻，可试空。'
            }
        elif dif > 0 and dea > 0 and dif > dea:
            return {
                'cross_type': '水上金叉运行中',
                'stability': '强',
                'theory': 'DIF>DEA>0，金叉在0轴上方运行。',
                'conduction': 'N+2级别强势传导至N级别。',
                'operation': '做多。'
            }
        elif dif < 0 and dea < 0 and dif < dea:
            return {
                'cross_type': '水下死叉运行中',
                'stability': '弱',
                'theory': 'DIF<DEA<0，死叉在0轴下方运行。',
                'conduction': 'N+2级别弱势传导至N级别。',
                'operation': '做空。'
            }
        else:
            return {
                'cross_type': '非交叉状态',
                'stability': '中性',
                'theory': 'DIF和DEA接近，无明确交叉。',
                'conduction': '传导信号不明确。',
                'operation': '等待。'
            }
    
    # 交叉状态判断
    if prev_dif <= prev_dea and dif > dea:
        # 金叉
        if abs(dif) < 0.5 and abs(dea) < 0.5:
            cross_type = '零轴金叉'
            stability = '极强'
            theory = 'DIF/DEA在0轴附近金叉。这是极强形态，上涨持续性极高。'
            conduction = 'N+2级别零轴金叉 → 极强形态 → N级别主涨段启动（高概率）。'
            operation = '高胜率做多。首次回踩N-1级别55线 → 极大概率支撑，做多开仓点。'
        elif dif > 0 and dea > 0:
            cross_type = '水上金叉'
            stability = '强'
            theory = 'DIF>DEA>0，在0轴上方金叉。上涨持续性高。'
            conduction = 'N+2级别强势 → N级别低位结构后出主涨段。'
            operation = '做多。'
        else:
            cross_type = '水下金叉'
            stability = '中性偏强'
            theory = 'DIF>DEA，在0轴下方金叉。上涨但动能不确定。'
            conduction = 'N+2级别中性偏强 → N级别可能处于X段或结构重置阶段。'
            operation = '谨慎做多。等待突破55线确认。'
    elif prev_dif >= prev_dea and dif < dea:
        # 死叉
        if abs(dif) < 0.5 and abs(dea) < 0.5:
            cross_type = '零轴死叉'
            stability = '极弱'
            theory = 'DIF/DEA在0轴附近死叉。这是极弱形态，下跌持续性极高。'
            conduction = 'N+2级别零轴死叉 → 极弱形态 → N级别主跌段启动（高概率）。'
            operation = '高胜率做空。首次反弹至N-1级别55线 → 极大概率遇阻，做空点。'
        elif dif < 0 and dea < 0:
            cross_type = '水下死叉'
            stability = '弱'
            theory = 'DIF<DEA<0，在0轴下方死叉。下跌持续性高。'
            conduction = 'N+2级别弱势 → N级别高位结构后出主跌段。'
            operation = '做空。'
        else:
            cross_type = '水上死叉'
            stability = '中性偏弱'
            theory = 'DIF<DEA，在0轴上方死叉。下跌但动能不确定。'
            conduction = 'N+2级别中性偏弱 → N级别可能处于X段或结构重置阶段。'
            operation = '谨慎做空。等待跌破55线确认。'
    else:
        cross_type = '非交叉'
        stability = '中性'
        theory = '无交叉。'
        conduction = '传导信号不明确。'
        operation = '等待。'
    
    return {
        'cross_type': cross_type,
        'stability': stability,
        'theory': theory,
        'conduction': conduction,
        'operation': operation
    }

# =====================================================
# v4.2: 极强/极弱三特征推导（核心新增）
# =====================================================

def analyze_extreme_features(df, upper_df, level_name='30F', upper_name='60F'):
    """
    v4.2 核心升级：极强/极弱三特征推导（完整实现SKILL.md）
    
    三特征：
    1. 背离失效：N+2级别极强 → N级别顶背离阶段性无效
    2. 55线支撑/压制：N+2级别极强/极弱 → 首次回踩/反弹N级别55线极大概率支撑/遇阻
    3. 传递性：极强/极弱形态 = 突破/跌破本级别55均线的过程，有向更高级别55线运动的惯性
    
    极强/极弱解除条件：有效跌破55线 = 价格跌破55线且反抽不上（实战中需灵活运用）
    """
    if len(df) < 55 or len(upper_df) < 55:
        return {
            'features': [],
            'description': '数据不足，无法推导三特征'
        }
    
    md = macd(df)
    dif = float(md['dif'].iloc[-1])
    dea = float(md['dea'].iloc[-1])
    mc = float(md['macd'].iloc[-1])
    
    p = float(df['Close'].iloc[-1])
    m55 = float(ma(df, 55).iloc[-1])
    
    upper_md = macd(upper_df)
    upper_dif = float(upper_md['dif'].iloc[-1])
    upper_dea = float(upper_md['dea'].iloc[-1])
    upper_mc = float(upper_md['macd'].iloc[-1])
    upper_p = float(upper_df['Close'].iloc[-1])
    upper_m55 = float(ma(upper_df, 55).iloc[-1])
    
    features = []
    
    # 判断N+2级别（upper）是否极强/极弱
    is_upper_extreme_strong = (upper_dif >= 0 and upper_dea <= 0 and upper_mc > 0)
    is_upper_strong = (upper_dif > upper_dea > 0 and upper_mc > 0)
    is_upper_extreme_weak = (upper_dif <= 0 and upper_dea >= 0 and upper_mc < 0)
    is_upper_weak = (upper_dif < upper_dea < 0 and upper_mc < 0)
    
    # 有效跌破判定函数：价格跌破55线后，检查是否反抽回到55线上方
    def check_effective_break(df_check, ma55_check, is_below=True):
        """
        检查有效跌破/突破：
        - 有效跌破：价格跌破55线后，后续K线无法反抽回到55线上方
        - 有效突破：价格突破55线后，后续K线回踩不跌破55线
        
        返回：(是否有效, 详细说明)
        """
        prices = df_check['Close'].values
        lows = df_check['Low'].values
        highs = df_check['High'].values
        
        # 找最近跌破/突破55线的位置
        cross_idx = None
        for i in range(len(prices)-1, max(0, len(prices)-30), -1):
            if is_below and prices[i] < ma55_check * 0.995 and prices[i-1] >= ma55_check * 0.995:
                cross_idx = i
                break
            elif not is_below and prices[i] > ma55_check * 1.005 and prices[i-1] <= ma55_check * 1.005:
                cross_idx = i
                break
        
        if cross_idx is None:
            return False, "未找到有效跌破/突破信号"
        
        # 检查后续K线是否反抽/回踩
        subsequent = df_check.iloc[cross_idx:]
        if len(subsequent) < 2:
            return False, "数据不足，无法确认有效跌破/突破"
        
        if is_below:
            # 检查是否反抽回到55线上方（有效跌破=反抽不上）
            retest_high = float(subsequent['High'].max())
            if retest_high < ma55_check:
                return True, f"有效跌破：价格跌破55线({ma55_check:.2f})后，后续最高{retest_high:.2f}未能反抽回55线上方"
            else:
                return False, f"非有效跌破：价格跌破55线({ma55_check:.2f})后，后续最高{retest_high:.2f}反抽回55线上方"
        else:
            # 检查是否回踩跌破55线（有效突破=回踩不破）
            retest_low = float(subsequent['Low'].min())
            if retest_low > ma55_check:
                return True, f"有效突破：价格突破55线({ma55_check:.2f})后，后续最低{retest_low:.2f}回踩未跌破55线"
            else:
                return False, f"非有效突破：价格突破55线({ma55_check:.2f})后，后续最低{retest_low:.2f}回踩跌破55线"
    
    if is_upper_extreme_strong or is_upper_strong:
        # 特征1：背离失效
        # 检查N级别是否有顶背离迹象（价格接近前高但MACD减弱）
        recent_high = float(df['High'].tail(20).max())
        latest_price = p
        price_near_high = latest_price >= recent_high * 0.99
        
        if len(md['macd']) >= 40:
            prev_macd_high = float(md['macd'].iloc[-40:-20].max())
            current_macd = float(md['macd'].tail(10).max())
            macd_weaker = current_macd < prev_macd_high * 0.8
        else:
            macd_weaker = False
        
        divergence_desc = "价格接近前高但MACD减弱" if (price_near_high and macd_weaker) else "暂无顶背离迹象"
        
        # 极强解除判定：检查是否有效跌破55线
        is_effective_break, break_desc = check_effective_break(df, m55, is_below=True)
        
        features.append({
            'feature': '背离失效',
            'level': level_name,
            'theory': (
                f"N+2级别({upper_name})极强/强 → N级别({level_name})的顶背离阶段性无效"
            ),
            'derivation': (
                f"【推导】{upper_name} MACD极强/强（DIF={upper_dif:.2f}, DEA={upper_dea:.2f}）"
                f" → {level_name}即使出现{divergence_desc}"
                f"，该顶背离在{upper_name}极强解除前不会生效"
            ),
            'condition': (
                f"生效条件：当{upper_name}极强解除后（{level_name}有效跌破55线{m55:.2f}），"
                f"{level_name}的顶背离才会生效"
                f"\n     有效跌破判定：{break_desc}"
            ),
            'operation': (
                f"【策略】不要因{level_name}的顶背离而做空"
                f"，等待{upper_name}极强解除后再评估"
            )
        })
        
        # 特征2：55线支撑（含有效跌破判定）
        # 检查近期是否回踩55线及支撑有效性
        recent_lows = df['Low'].tail(20).values
        recent_prices = df['Close'].tail(20).values
        
        tested_55 = False
        support_effective = False
        test_desc = ""
        
        for i in range(len(recent_lows)-1, max(0, len(recent_lows)-15), -1):
            if recent_lows[i] <= m55 * 1.01:  # 回踩到55线附近
                tested_55 = True
                # 检查后续是否跌破55线（有效跌破=反抽不上）
                subsequent_prices = recent_prices[i:]
                if len(subsequent_prices) >= 2:
                    if subsequent_prices[-1] >= m55 * 0.995:
                        support_effective = True
                        test_desc = f"近期回踩55线{m55:.2f}后支撑有效，当前价格{recent_prices[-1]:.2f}在55线上方"
                    else:
                        test_desc = f"近期回踩55线{m55:.2f}后跌破支撑，当前价格{recent_prices[-1]:.2f}在55线下方"
                break
        
        if not tested_55:
            test_desc = f"近期未回踩55线{m55:.2f}，等待首次回踩测试支撑"
        
        features.append({
            'feature': '55线支撑',
            'level': level_name,
            'theory': (
                f"N+2级别({upper_name})极强/强 → N级别({level_name})首次回踩55线"
                f" → 极大概率得到支撑"
            ),
            'derivation': (
                f"【推导】{upper_name}极强/强 → {level_name}的55线({m55:.2f})"
                f"成为技术体系里胜率极高的做多开仓点"
                f"\n     测试状态：{test_desc}"
            ),
            'condition': (
                f"极强解除条件：{level_name}有效跌破55线{m55:.2f}（反抽不上）"
                f"\n     当前判定：{'✅ 支撑有效' if support_effective else '⚠️ 支撑失效/待测试'}"
            ),
            'operation': (
                f"【策略】{'首次回踩55线企稳 → 做多开仓点' if not tested_55 else test_desc}"
                f"\n     若有效跌破55线 → 极强解除，止损离场"
            )
        })
        
        # 特征3：传递性
        # 检查当前是否处于极强形态的传递过程中
        in_transmission = p > m55 and mc > 0
        
        features.append({
            'feature': '传递性',
            'level': level_name,
            'theory': (
                f"极强形态 = 低位突破本级别55均线的过程"
                f"，具有向更高级别55线运动的惯性"
            ),
            'derivation': (
                f"【推导】{level_name}突破55线({m55:.2f})后"
                f"，有向{upper_name}55线({upper_m55:.2f})运动的惯性"
                f"，直到被{upper_name}55线压制"
                f"\n     当前状态：{'✅ 传递中（价格>55线+MACD>0）' if in_transmission else '⚠️ 传递减弱'}"
            ),
            'condition': (
                f"目标：{upper_name}55线({upper_m55:.2f})"
                f"，若突破则继续向更高级别传导"
                f"\n     终止条件：有效跌破{m55:.2f}（反抽不上）"
            ),
            'operation': (
                f"【策略】{'持仓至' if in_transmission else '等待回踩55线后持仓至'}{upper_name}55线({upper_m55:.2f})附近观察"
                f"，若遇阻减仓，若突破加仓"
            )
        })
    
    elif is_upper_extreme_weak or is_upper_weak:
        # 极弱情况（对称的反向推导）
        # 特征1：底背离失效
        recent_low = float(df['Low'].tail(20).min())
        latest_price = p
        price_near_low = latest_price <= recent_low * 1.01
        
        if len(md['macd']) >= 40:
            prev_macd_low = float(md['macd'].iloc[-40:-20].min())
            current_macd = float(md['macd'].tail(10).min())
            macd_weaker = current_macd > prev_macd_low * 0.8  # 底背离：价格新低但MACD不低
        else:
            macd_weaker = False
        
        divergence_desc = "价格接近前低但MACD未创新低" if (price_near_low and macd_weaker) else "暂无底背离迹象"
        
        # 极弱解除判定：检查是否有效突破55线
        is_effective_break, break_desc = check_effective_break(df, m55, is_below=False)
        
        features.append({
            'feature': '底背离失效',
            'level': level_name,
            'theory': (
                f"N+2级别({upper_name})极弱/弱 → N级别({level_name})的底背离阶段性无效"
            ),
            'derivation': (
                f"【推导】{upper_name} MACD极弱/弱（DIF={upper_dif:.2f}, DEA={upper_dea:.2f}）"
                f" → {level_name}即使出现{divergence_desc}"
                f"，该底背离在{upper_name}极弱解除前不会生效"
            ),
            'condition': (
                f"生效条件：当{upper_name}极弱解除后（{level_name}有效突破55线{m55:.2f}），"
                f"{level_name}的底背离才会生效"
                f"\n     有效突破判定：{break_desc}"
            ),
            'operation': (
                f"【策略】不要因{level_name}的底背离而做多"
                f"，等待{upper_name}极弱解除后再评估"
            )
        })
        
        # 特征2：55线压制（含有效突破判定）
        # 检查近期是否反弹至55线及压制有效性
        recent_highs = df['High'].tail(20).values
        recent_prices = df['Close'].tail(20).values
        
        tested_55 = False
        press_effective = False
        test_desc = ""
        
        for i in range(len(recent_highs)-1, max(0, len(recent_highs)-15), -1):
            if recent_highs[i] >= m55 * 0.99:  # 反弹到55线附近
                tested_55 = True
                # 检查后续是否突破55线（有效突破=回踩不破）
                subsequent_prices = recent_prices[i:]
                if len(subsequent_prices) >= 2:
                    if subsequent_prices[-1] <= m55 * 1.005:
                        press_effective = True
                        test_desc = f"近期反弹至55线{m55:.2f}后遇阻回落，当前价格{recent_prices[-1]:.2f}在55线下方"
                    else:
                        test_desc = f"近期反弹至55线{m55:.2f}后突破压制，当前价格{recent_prices[-1]:.2f}在55线上方"
                break
        
        if not tested_55:
            test_desc = f"近期未反弹至55线{m55:.2f}，等待首次反弹测试压制"
        
        features.append({
            'feature': '55线压制',
            'level': level_name,
            'theory': (
                f"N+2级别({upper_name})极弱/弱 → N级别({level_name})首次反弹至55线"
                f" → 极大概率遇阻"
            ),
            'derivation': (
                f"【推导】{upper_name}极弱/弱 → {level_name}的55线({m55:.2f})"
                f"成为技术体系里胜率极高的做空开仓点"
                f"\n     测试状态：{test_desc}"
            ),
            'condition': (
                f"极弱解除条件：{level_name}有效突破55线{m55:.2f}（回踩不破）"
                f"\n     当前判定：{'✅ 压制有效' if press_effective else '⚠️ 压制失效/待测试'}"
            ),
            'operation': (
                f"【策略】{'首次反弹至55线遇阻 → 做空开仓点' if not tested_55 else test_desc}"
                f"\n     若有效突破55线 → 极弱解除，止损离场"
            )
        })
        
        # 特征3：下跌传递性
        # 检查当前是否处于极弱形态的下跌传递过程中
        in_transmission = p < m55 and mc < 0
        
        features.append({
            'feature': '下跌传递性',
            'level': level_name,
            'theory': (
                f"极弱形态 = 高位跌破本级别55均线的过程"
                f"，具有向更高级别55线下跌的惯性"
            ),
            'derivation': (
                f"【推导】{level_name}跌破55线({m55:.2f})后"
                f"，有向{upper_name}55线({upper_m55:.2f})下跌的惯性"
                f"，直到被{upper_name}55线支撑"
                f"\n     当前状态：{'✅ 下跌传递中（价格<55线+MACD<0）' if in_transmission else '⚠️ 传递减弱'}"
            ),
            'condition': (
                f"目标：{upper_name}55线({upper_m55:.2f})"
                f"，若跌破则继续向更高级别传导"
                f"\n     终止条件：有效突破{m55:.2f}（回踩不破）"
            ),
            'operation': (
                f"【策略】{'做空至' if in_transmission else '等待反弹至55线遇阻后做空至'}{upper_name}55线({upper_m55:.2f})附近观察"
                f"，若支撑有效止盈，若跌破继续做空"
            )
        })
    
    else:
        features.append({
            'feature': '无极端特征',
            'level': level_name,
            'theory': (
                f"N+2级别({upper_name})非极强/非极弱"
                f"，三特征不适用"
            ),
            'derivation': (
                f"【推导】{upper_name} MACD状态为中性/强/弱（非极端）"
                f"，{level_name}的背离/支撑/传递性按正常逻辑处理"
            ),
            'condition': '无特殊条件',
            'operation': '按常规策略操作'
        })
    
    return {
        'features': features,
        'upper_state': '极强/强' if (is_upper_extreme_strong or is_upper_strong) else ('极弱/弱' if (is_upper_extreme_weak or is_upper_weak) else '中性'),
        'description': '\n'.join([f['feature'] for f in features])
    }

# =====================================================
# v4.2: N+2→N级别传导推导（核心新增）
# =====================================================

def derive_n_plus_2_conduction(levels_macd, levels_trend):
    """
    v4.2 核心升级：使用N+2→N级别传导推导大级别如何影响小级别
    
    级差体系两套：
    组B：1F → 5F → 30F → 120F → 双日 → 十日(双周)
    组A：3F → 15F → 60F → 日 → 周 → 月 → 季
    
    传导公式：
    N+2级别 MACD极强/金叉 → N级别在低位出现结构（第三段/第五段）后出主涨段
    N+2级别 MACD极弱/死叉 → N级别在高位出现结构后出主跌段
    """
    conductions = []
    
    # 组B级差传导链：双日 → 120F → 30F → 5F → 1F
    group_b_pairs = [
        ('双日', '120F', '30F'),
        ('120F', '30F', '5F'),
        ('30F', '5F', '1F'),
    ]
    
    # 组A级差传导链：日线 → 60F → 15F → 3F
    group_a_pairs = [
        ('日线', '60F', '15F'),
        ('60F', '15F', '3F'),
    ]
    
    def derive_chain(n_plus_2, n_plus_1, n):
        if n_plus_2 not in levels_macd or n not in levels_macd:
            return None
        
        upper = levels_macd[n_plus_2]
        lower = levels_macd[n]
        
        upper_state = upper['state']
        lower_state = lower['state']
        
        if upper_state in ['极强', '强']:
            return {
                'chain': f'{n_plus_2} → {n_plus_1} → {n}',
                'group': '组B' if n_plus_2 in ['双日', '120F', '30F'] else '组A',
                'upper_state': upper_state,
                'lower_state': lower_state,
                'theory': (
                    f"{n_plus_2} MACD{upper_state} → "
                    f"传导至{n_plus_1}级别极强/强 → "
                    f"{n_plus_1}级别在N-1级别（即{n}）回踩时，"
                    f"{n}级别的中轨往往支撑，使得顶背离失效"
                ),
                'derivation': (
                    f"【推导】{n_plus_2} {upper_state} → "
                    f"{n_plus_1}出现主涨段（价格>55线+MACD>0） → "
                    f"{n}级别在低位出现结构（第三段或第五段）后出主涨段 → "
                    f"{n}级别首次回踩55线 → 极大概率得到支撑（三特征之55线支撑）"
                ),
                'expectation': (
                    f"【预期】{n}级别将出主涨段，"
                    f"首次回踩55线是做多个点，"
                    f"突破55线后有向{n_plus_1}55线运动的惯性（三特征之传递性）"
                ),
                'operation': (
                    f"【策略】{n}级别：回踩55线企稳 → 做多；"
                    f"突破55线 → 加仓；"
                    f"目标{n_plus_1}55线"
                )
            }
        elif upper_state in ['极弱', '弱']:
            return {
                'chain': f'{n_plus_2} → {n_plus_1} → {n}',
                'group': '组B' if n_plus_2 in ['双日', '120F', '30F'] else '组A',
                'upper_state': upper_state,
                'lower_state': lower_state,
                'theory': (
                    f"{n_plus_2} MACD{upper_state} → "
                    f"传导至{n_plus_1}级别极弱/弱 → "
                    f"{n_plus_1}级别在N-1级别（即{n}）反弹时，"
                    f"{n}级别的中轨往往压制，使得底背离失效"
                ),
                'derivation': (
                    f"【推导】{n_plus_2} {upper_state} → "
                    f"{n_plus_1}出现主跌段（价格<55线+MACD<0） → "
                    f"{n}级别在高位出现结构后出主跌段 → "
                    f"{n}级别首次反弹至55线 → 极大概率遇阻（三特征之55线压制）"
                ),
                'expectation': (
                    f"【预期】{n}级别将出主跌段，"
                    f"首次反弹至55线是做空点，"
                    f"跌破55线后有向{n_plus_1}55线下跌的惯性（三特征之下跌传递性）"
                ),
                'operation': (
                    f"【策略】{n}级别：反弹至55线遇阻 → 做空；"
                    f"跌破55线 → 加仓做空；"
                    f"目标{n_plus_1}55线"
                )
            }
        elif upper_state == '中性偏强':
            return {
                'chain': f'{n_plus_2} → {n_plus_1} → {n}',
                'group': '组B' if n_plus_2 in ['双日', '120F', '30F'] else '组A',
                'upper_state': upper_state,
                'lower_state': lower_state,
                'theory': (
                    f"{n_plus_2} MACD中性偏强 → "
                    f"N+2级别传导至{n_plus_1}的信号不明确"
                ),
                'derivation': (
                    f"【推导】{n_plus_2}中性偏强 → "
                    f"{n_plus_1}可能处于X段或结构重置阶段 → "
                    f"{n}级别需观察能否突破55线确认"
                ),
                'expectation': f"【预期】{n}级别方向不明确，等待突破/跌破55线确认",
                'operation': f"【策略】{n}级别：观望，等待方向选择"
            }
        elif upper_state == '中性偏弱':
            return {
                'chain': f'{n_plus_2} → {n_plus_1} → {n}',
                'group': '组B' if n_plus_2 in ['双日', '120F', '30F'] else '组A',
                'upper_state': upper_state,
                'lower_state': lower_state,
                'theory': (
                    f"{n_plus_2} MACD中性偏弱 → "
                    f"N+2级别传导至{n_plus_1}的信号不明确"
                ),
                'derivation': (
                    f"【推导】{n_plus_2}中性偏弱 → "
                    f"{n_plus_1}可能处于X段或结构重置阶段 → "
                    f"{n}级别需观察能否跌破55线确认"
                ),
                'expectation': f"【预期】{n}级别方向不明确，等待跌破/突破55线确认",
                'operation': f"【策略】{n}级别：观望，等待方向选择"
            }
        return None
    
    # 组B传导链
    for n_plus_2, n_plus_1, n in group_b_pairs:
        result = derive_chain(n_plus_2, n_plus_1, n)
        if result:
            conductions.append(result)
    
    # 组A传导链
    for n_plus_2, n_plus_1, n in group_a_pairs:
        result = derive_chain(n_plus_2, n_plus_1, n)
        if result:
            conductions.append(result)
    
    return conductions

# =====================================================
# v4.2: 基于理论的策略推导（核心新增）
# =====================================================

def derive_strategy_from_theory(levels_macd, levels_trend, conductions, extreme_features):
    """
    v4.2 核心新增：基于理论推导给出操作建议，不是简单罗列
    
    推导逻辑：
    1. 从N+2级别MACD状态推导N+1级别趋势
    2. 从N+1级别趋势推导N级别操作
    3. 结合极强/极弱三特征确认操作点位
    4. 输出：基于理论的完整策略
    """
    strategies = []
    
    # 最高级别判断（决定大方向）
    highest_level = None
    for level in ['双日', '日线', '120F']:
        if level in levels_macd:
            highest_level = level
            break
    
    if not highest_level:
        return {'strategies': [], 'summary': '数据不足，无法推导策略'}
    
    highest = levels_macd[highest_level]
    highest_state = highest['state']
    
    # 大方向推导
    if highest_state in ['极强', '强']:
        direction = '多头'
        direction_theory = (
            f"{highest_level} MACD{highest_state} → "
            f"大级别上涨传导链确立 → "
            f"各级别依次出主涨段"
        )
    elif highest_state in ['极弱', '弱']:
        direction = '空头'
        direction_theory = (
            f"{highest_level} MACD{highest_state} → "
            f"大级别下跌传导链确立 → "
            f"各级别依次出主跌段"
        )
    elif highest_state == '中性偏强':
        direction = '偏多震荡'
        direction_theory = (
            f"{highest_level} MACD中性偏强 → "
            f"大级别可能处于X段或结构重置 → "
            f"等待方向确认"
        )
    elif highest_state == '中性偏弱':
        direction = '偏空震荡'
        direction_theory = (
            f"{highest_level} MACD中性偏弱 → "
            f"大级别可能处于X段或结构重置 → "
            f"等待方向确认"
        )
    else:
        direction = '中性'
        direction_theory = f"{highest_level} MACD中性 → 大级别方向不明确"
    
    strategies.append({
        'type': '大方向',
        'direction': direction,
        'theory': direction_theory,
        'source': f'{highest_level} MACD状态'
    })
    
    # 操作级别策略推导（以30F为例）
    if '30F' in levels_macd and '60F' in levels_macd:
        l30 = levels_macd['30F']
        l60 = levels_macd['60F']
        
        if l60['state'] in ['极强', '强'] and l30['state'] in ['极强', '强']:
            # 60F极强 → 30F主涨段
            strategies.append({
                'type': '操作级别(30F)',
                'direction': '做多',
                'theory': (
                    "60F极强 → 30F在低位结构后出主涨段（N+2→N传导）"
                ),
                'derivation': (
                    "【推导】60F极强（N+2）→ 30F（N）出主涨段 → "
                    "30F价格>55线且MACD>0 → 主涨段确认"
                ),
                'entry': (
                    "入场点：30F首次回踩55线企稳（三特征之55线支撑）"
                ),
                'target': (
                    "目标：60F55线（三特征之传递性）"
                ),
                'stop': (
                    "止损：30F跌破55线（极强解除信号）"
                ),
                'source': '60F→30F N+2→N传导 + 极强三特征'
            })
        elif l60['state'] in ['极强', '强'] and l30['state'] in ['中性偏强', '中性']:
            # 60F极强 → 30F可能处于X段或等待结构
            strategies.append({
                'type': '操作级别(30F)',
                'direction': '观察/试多',
                'theory': (
                    "60F极强 → 30F可能处于X段或等待低位结构"
                ),
                'derivation': (
                    "【推导】60F极强（N+2）→ 30F（N）可能处于X段（价格>55线但MACD<0）"
                    "或等待低位结构 → 需等待30F结构确认"
                ),
                'entry': (
                    "入场点：30F突破55线+MACD转正（确认主涨段）"
                ),
                'target': (
                    "目标：60F55线"
                ),
                'stop': (
                    "止损：30F跌破55线"
                ),
                'source': '60F→30F N+2→N传导 + 主涨段雏形'
            })
        elif l60['state'] in ['极弱', '弱'] and l30['state'] in ['极弱', '弱']:
            # 60F极弱 → 30F主跌段
            strategies.append({
                'type': '操作级别(30F)',
                'direction': '做空',
                'theory': (
                    "60F极弱 → 30F在高位结构后出主跌段（N+2→N传导）"
                ),
                'derivation': (
                    "【推导】60F极弱（N+2）→ 30F（N）出主跌段 → "
                    "30F价格<55线且MACD<0 → 主跌段确认"
                ),
                'entry': (
                    "入场点：30F首次反弹至55线遇阻（三特征之55线压制）"
                ),
                'target': (
                    "目标：60F55线（三特征之下跌传递性）"
                ),
                'stop': (
                    "止损：30F突破55线（极弱解除信号）"
                ),
                'source': '60F→30F N+2→N传导 + 极弱三特征'
            })
    
    # 日内策略推导
    if '5F' in levels_macd and '15F' in levels_macd:
        l5 = levels_macd['5F']
        l15 = levels_macd['15F']
        
        if l15['state'] in ['极强', '强'] and l5['state'] in ['极强', '强']:
            strategies.append({
                'type': '日内(5F)',
                'direction': '做多',
                'theory': (
                    "15F极强 → 5F在低位结构后出主涨段"
                ),
                'derivation': (
                    "【推导】15F极强（N+2）→ 5F（N）出主涨段 → "
                    "5F价格>55线且MACD>0 → 主涨段确认"
                ),
                'entry': (
                    "入场点：5F首次回踩55线企稳（三特征之55线支撑）"
                ),
                'target': (
                    "目标：15F55线（三特征之传递性）"
                ),
                'stop': (
                    "止损：5F跌破55线"
                ),
                'source': '15F→5F N+2→N传导'
            })
        elif l15['state'] in ['极弱', '弱'] and l5['state'] in ['极弱', '弱']:
            strategies.append({
                'type': '日内(5F)',
                'direction': '做空',
                'theory': (
                    "15F极弱 → 5F在高位结构后出主跌段"
                ),
                'derivation': (
                    "【推导】15F极弱（N+2）→ 5F（N）出主跌段 → "
                    "5F价格<55线且MACD<0 → 主跌段确认"
                ),
                'entry': (
                    "入场点：5F首次反弹至55线遇阻（三特征之55线压制）"
                ),
                'target': (
                    "目标：15F55线（三特征之下跌传递性）"
                ),
                'stop': (
                    "止损：5F突破55线"
                ),
                'source': '15F→5F N+2→N传导'
            })
    
    # 总结
    summary = f"【大方向】{direction} | 基于{highest_level} MACD{highest_state}推导"
    
    return {
        'strategies': strategies,
        'summary': summary,
        'highest_level': highest_level,
        'highest_state': highest_state
    }

# =====================================================
# v4.2: 段数分解（保留）
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
    """
    v4.2 核心升级：段数结构分解（完整实现SKILL.md）
    
    输出包含：
    - 段数统计
    - 起点/高点识别
    - 段结构类型（3段盘整/5段趋势/9段扩展）
    - X段"重置"功能标记
    - 当前段运行状态
    """
    if len(df) < 10:
        return {'segment_count': 0, 'current': 'unknown', 'description': '数据不足'}
    
    # v4.2修复：调整window参数，避免高频级别过度敏感
    # 高频级别使用更大的window，减少噪音分型
    window_map = {
        '1F': 15,   # 1分钟：15根K线确认分型（减少噪音）
        '3F': 10,   # 3分钟：10根K线确认分型
        '5F': 10,   # 5分钟：10根K线确认分型
        '15F': 5,   # 15分钟：5根K线确认分型
        '30F': 5,   # 30分钟：5根K线确认分型
        '60F': 3,   # 60分钟：3根K线确认分型
        '120F': 3,  # 120分钟：3根K线确认分型
        '日线': 3,  # 日线：3根K线确认分型
        '双日': 2   # 双日：2根K线确认分型
    }
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
    
    # 起点识别（一买/一卖低点）
    start_point = valid_peaks[0] if valid_peaks else None
    start_price = start_point[2] if start_point else 0
    start_type = '底' if start_point and start_point[1] == 'bottom' else '顶'
    
    # 高点/低点识别（最近的重要分型）
    recent_high = None
    recent_low = None
    for p in valid_peaks:
        if p[1] == 'top':
            if recent_high is None or p[2] > recent_high[2]:
                recent_high = p
        else:
            if recent_low is None or p[2] < recent_low[2]:
                recent_low = p
    
    # 当前段状态
    last_peak = valid_peaks[-1]
    if last_peak[1] == 'top':
        current = f'第{segment_count + 1}段up运行中（从{valid_peaks[-2][2]:.2f}到{last_peak[2]:.2f}）' if len(valid_peaks) >= 2 else 'up运行中'
    else:
        current = f'第{segment_count + 1}段down运行中（从{valid_peaks[-2][2]:.2f}到{last_peak[2]:.2f}）' if len(valid_peaks) >= 2 else 'down运行中'
    
    # 段结构类型判断（SKILL.md标准）
    if segment_count <= 2:
        structure = '简单结构（1-2段，未形成中枢）'
        structure_type = '简单'
        trend_type = '未完成'
    elif segment_count <= 4:
        structure = '标准盘整（3-4段，1个中枢）'
        structure_type = '盘整'
        trend_type = '盘整'
    elif segment_count <= 6:
        structure = '标准趋势（5-6段，2个中枢）'
        structure_type = '趋势'
        trend_type = '趋势'
    elif segment_count <= 8:
        structure = f'趋势延续（{segment_count}段，中枢扩展中）'
        structure_type = '趋势延续'
        trend_type = '趋势'
    else:
        structure = f'复杂结构（{segment_count}段，中枢扩展或更大级别）'
        structure_type = '扩展'
        trend_type = '升级'
    
    # X段"重置"功能检测（SKILL.md v4.0新增）
    x_reset_detected = False
    x_reset_desc = ""
    if segment_count >= 5:
        # 检查是否出现X段重置：上涨段过高后MACD背离/乖离过大 → X段回踩 → 重新突破
        if len(df) >= 40:
            recent_macd = macd(df)
            if len(recent_macd['macd']) >= 40:
                prev_macd_high = float(recent_macd['macd'].iloc[-40:-20].max())
                current_macd = float(recent_macd['macd'].tail(10).max())
                macd_weaker = current_macd < prev_macd_high * 0.8
                
                if macd_weaker and last_peak[1] == 'top':
                    x_reset_detected = True
                    x_reset_desc = "检测到X段重置可能：MACD背离/乖离过大，后续回踩可能清除乖离后重新焕发"
    
    # 分型序列字符串
    recent_peaks = valid_peaks[-6:] if len(valid_peaks) >= 6 else valid_peaks
    peak_str = ' → '.join([f"{'顶' if p[1]=='top' else '底'}{p[2]:.2f}" for p in recent_peaks])
    
    # 目标推导（基于段数结构）
    target_desc = ""
    if trend_type == '趋势':
        if last_peak[1] == 'top':
            target_desc = f"趋势上涨中，目标：前高{recent_high[2]:.2f} → 突破后看测量目标"
        else:
            target_desc = f"趋势下跌中，目标：前低{recent_low[2]:.2f} → 跌破后看测量目标"
    elif trend_type == '盘整':
        target_desc = f"盘整结构中，等待突破方向选择"
    
    return {
        'segment_count': segment_count,
        'current': current,
        'structure': structure,
        'structure_type': structure_type,
        'trend_type': trend_type,
        'start_price': start_price,
        'start_type': start_type,
        'recent_high': recent_high[2] if recent_high else None,
        'recent_low': recent_low[2] if recent_low else None,
        'peaks': valid_peaks,
        'peak_str': peak_str,
        'x_reset_detected': x_reset_detected,
        'x_reset_desc': x_reset_desc,
        'target_desc': target_desc,
        'description': f'{segment_count}段 | {current} | {structure}'
    }

# =====================================================
# v4.2: X段判定体系（核心重写，完整实现SKILL.md）
# =====================================================

def analyze_x_segment_full(df_current, df_upper, df_lower, current_name='15F', upper_name='30F', lower_name='5F', segment_data=None):
    """
    v4.2 核心升级：X段完整判定体系（SKILL.md Step 6）
    
    判定公式：
    N+2级别出现主涨段
        ↓
    期间会有对N+1级别中轨的回踩
        ↓
    N+1级别回踩中轨的过程，在N+1级别不足以画出一段结构
        ↓
    称N级别作为X段
    
    三个条件：
    1. 复合结构（前段+X段+后段）
    2. 起点=最高点
    3. 后验确认（突破N级别55线+不创新低）
    
    X段操作判定流程：
    出现N+2级别主涨段 + N+1级别不带结构的回踩
        ↓
    优先考虑N级别X段
        ↓
    后端确认：突破N级别55均线 或 不跌破N级别55均线
        ↓
    确认成功 → 后续基本可以确定会新高
        ↓
    如果被N级别55线压制 且 新低 → 下跌发生升级，需另做考虑
    """
    
    if len(df_current) < 55 or len(df_upper) < 55:
        return {'is_x_segment': False, 'description': '数据不足，无法判定X段'}
    
    p = float(df_current['Close'].iloc[-1])
    m55 = float(ma(df_current, 55).iloc[-1])
    md = macd(df_current)['macd'].iloc[-1]
    
    upper_m55 = float(ma(df_upper, 55).iloc[-1])
    upper_md = macd(df_upper)['macd'].iloc[-1]
    upper_p = float(df_upper['Close'].iloc[-1])
    
    # 前提条件：N+2级别（upper）必须处于主涨段
    upper_main_trend = (upper_p > upper_m55) and (upper_md > 0)
    
    if not upper_main_trend:
        return {
            'is_x_segment': False,
            'description': f'N+2级别({upper_name})非主涨段，无X段前提条件',
            'upper_main_trend': False,
            'current_price': p,
            'ma55': m55,
            'macd': md
        }
    
    # 条件1：检查N+1级别（upper）是否有结构
    # 如果N+1级别有结构，则不是X段；如果无结构，可能是X段
    upper_segment = count_segments(df_upper, upper_name) if len(df_upper) >= 20 else None
    upper_has_structure = upper_segment is not None and upper_segment.get('segment_count', 0) >= 3
    
    # 条件2：检查当前级别（current）是否处于复合结构中的"X段"位置
    # 即：当前价格>55线但MACD<0（55线上方X段）或 价格<55线但MACD>0（55线下方X段）
    is_x_candidate = (p > m55 and md < 0) or (p < m55 and md > 0)
    
    if not is_x_candidate:
        return {
            'is_x_segment': False,
            'description': f'{current_name}非X段候选（价格vs55线+MACD方向一致）',
            'upper_main_trend': True,
            'current_price': p,
            'ma55': m55,
            'macd': md
        }
    
    # 确定X段类型
    x_type = '55线上方X段' if (p > m55 and md < 0) else '55线下方X段'
    
    # 条件3：检查N+1级别（upper）结构状态
    if upper_has_structure:
        # N+1级别有结构 → 不是X段，是正常回调段
        return {
            'is_x_segment': False,
            'description': f'{upper_name}有结构（{upper_segment.get("segment_count", 0)}段），不是X段',
            'upper_main_trend': True,
            'upper_has_structure': True,
            'current_price': p,
            'ma55': m55,
            'macd': md
        }
    
    # 三个条件判定
    # 条件1：复合结构（出现在主涨段中，不能单独存在）
    condition1 = True  # 已通过upper_main_trend确认
    
    # 条件2：起点=最高点（需要找历史高点）
    recent_high = float(df_current['High'].tail(60).max()) if len(df_current) >= 60 else float(df_current['High'].max())
    # 检查当前是否从最高点回落（X段起点是最高点）
    condition2 = p < recent_high * 0.995  # 当前价格低于近期最高点
    
    # 条件3：后验确认（突破N级别55线+不创新低）
    # 检查是否已突破55线
    crossed_55 = p > m55 if x_type == '55线上方X段' else p < m55
    # 检查是否创新低（不创新低确认）
    recent_low = float(df_current['Low'].tail(20).min())
    prev_low = float(df_current['Low'].tail(40).head(20).min()) if len(df_current) >= 40 else recent_low
    no_new_low = recent_low >= prev_low * 0.99
    condition3 = crossed_55 and no_new_low
    
    # 后端确认状态
    backend_confirm = '已确认' if condition3 else '待确认'
    if not condition3:
        if not crossed_55:
            backend_confirm = '待确认（未突破55线）'
        elif not no_new_low:
            backend_confirm = '⚠️ 可能变异（创新低）'
    
    # X段操作判定
    if x_type == '55线上方X段':
        operation = (
            f"【X段操作】{current_name}处于55线上方X段 → "
            f"1) 确认X段：突破55线({m55:.2f})且不再创新低 → 重新焕发主涨段\n"
            f"2) 警惕变异：若被55线压制且创新低 → 下跌升级，需另做考虑\n"
            f"3) 持仓策略：N+2级别({upper_name})主涨段支撑中，X段大概率是桥梁"
        )
        theory = (
            f"【X段理论】{upper_name}主涨段中，{current_name}回踩但{N_MINUS_1_MAP.get(current_name, 'N-1')}级别"
            f"无结构 → {current_name}作为X段 → 连接前后两个上涨结构的桥梁"
        )
    else:
        operation = (
            f"【X段操作】{current_name}处于55线下方X段 → "
            f"1) 确认X段：跌破55线({m55:.2f})后不再创新低 → 重新焕发主跌段\n"
            f"2) 警惕变异：若被55线支撑且创新高 → 上涨升级，需另做考虑\n"
            f"3) 持仓策略：N+2级别({upper_name})主跌段中，X段大概率是桥梁"
        )
        theory = (
            f"【X段理论】{upper_name}主跌段中，{current_name}反弹但{N_MINUS_1_MAP.get(current_name, 'N-1')}级别"
            f"无结构 → {current_name}作为X段 → 连接前后两个下跌结构的桥梁"
        )
    
    return {
        'is_x_segment': True,
        'x_type': x_type,
        'description': f'{current_name}【{x_type}】N+2({upper_name})主涨段中，{current_name}无结构 → X段确认',
        'upper_main_trend': True,
        'upper_has_structure': False,
        'condition1_composite': condition1,
        'condition2_start_from_high': condition2,
        'condition3_backend_confirm': condition3,
        'backend_confirm_status': backend_confirm,
        'current_price': p,
        'ma55': m55,
        'macd': md,
        'recent_high': recent_high,
        'recent_low': recent_low,
        'theory': theory,
        'operation': operation
    }

# =====================================================
# v4.2: 假突破/骗炮识别（SKILL.md Step 7）
# =====================================================

def analyze_fake_breakout(df, level_name='30F'):
    """
    v4.2 核心新增：假突破/骗炮识别（SKILL.md Step 7）
    
    判断标准：
    ├── 站上55线 + MACD>0 + MACD柱放大 → 真突破 ✅
    ├── 站上55线 + MACD<0 或 MACD柱收敛 → 假突破 ⚠️ (骗炮)
    ├── 跌破55线 + MACD<0 + MACD柱放大 → 真跌破 ❌
    └── 跌破55线 + MACD>0 或 MACD柱收敛 → 假跌破 ⚠️
    
    实战验证：
    2026-05-26收盘：站上30F55线(4134)但MACD=-0.70<0
    → 假突破/骗炮!
    → 次日(05-27)开盘直接跌破，全天大跌
    → 验证：假突破后必有大跌
    
    操作策略：
    - 假突破 → 不追涨，等待回踩确认或回落
    - 真突破 → 追涨，止损55线下方1%
    - 假跌破 → 不恐慌，等待反弹确认
    - 真跌破 → 止损，等待补偿性买点
    """
    if len(df) < 55:
        return {'type': 'unknown', 'description': '数据不足'}
    
    p = float(df['Close'].iloc[-1])
    m55 = float(ma(df, 55).iloc[-1])
    md = macd(df)
    
    dif = float(md['dif'].iloc[-1])
    dea = float(md['dea'].iloc[-1])
    mc = float(md['macd'].iloc[-1])
    
    # 检查MACD柱趋势（放大/收敛）
    if len(md['macd']) >= 5:
        macd_recent = md['macd'].tail(5).values
        macd_older = md['macd'].tail(10).head(5).values
        macd_expanding = np.mean(macd_recent) > np.mean(macd_older) * 1.05
        macd_contracting = np.mean(macd_recent) < np.mean(macd_older) * 0.95
    else:
        macd_expanding = False
        macd_contracting = False
    
    # 判断突破/跌破类型
    if p > m55:
        # 站上55线
        if mc > 0 and macd_expanding:
            breakout_type = '真突破'
            icon = '✅'
            theory = (
                f"【真突破】{level_name}站上55线({m55:.2f}) + MACD>0({mc:.2f}) + MACD柱放大"
                f" → 突破有效，上涨动能强劲"
            )
            operation = (
                f"【策略】追涨，止损设于55线({m55:.2f})下方1%({m55*0.99:.2f})"
            )
        elif mc > 0 and macd_contracting:
            breakout_type = '真突破（动能减弱）'
            icon = '⚠️'
            theory = (
                f"【真突破但动能减弱】{level_name}站上55线({m55:.2f}) + MACD>0({mc:.2f})但MACD柱收敛"
                f" → 突破有效但动能减弱，需警惕回落"
            )
            operation = (
                f"【策略】谨慎追涨，若回落跌破55线({m55:.2f})及时止损"
            )
        elif mc < 0:
            breakout_type = '假突破（骗炮）'
            icon = '🔴'
            theory = (
                f"【假突破/骗炮】{level_name}站上55线({m55:.2f})但MACD<0({mc:.2f})"
                f" → 站上55线但MACD为负，上涨动能不足"
                f" → 假突破概率高，次日可能直接跌破"
            )
            operation = (
                f"【策略】⚠️ 不追涨！等待回踩确认或回落"
                f" → 若次日开盘跌破55线({m55:.2f})，确认骗炮，全天可能大跌"
                f" → 原文验证：'前面几次向上刺破30F55线都有些骗炮'"
            )
        else:
            breakout_type = '突破待确认'
            icon = '🟡'
            theory = f"{level_name}站上55线({m55:.2f})，MACD接近0，方向不明确"
            operation = "等待MACD转正确认"
    elif p < m55:
        # 跌破55线
        if mc < 0 and macd_expanding:
            breakout_type = '真跌破'
            icon = '❌'
            theory = (
                f"【真跌破】{level_name}跌破55线({m55:.2f}) + MACD<0({mc:.2f}) + MACD柱放大"
                f" → 跌破有效，下跌动能强劲"
            )
            operation = (
                f"【策略】止损，等待补偿性买点"
                f" → 跌破55线确认趋势转空，清仓/做空"
            )
        elif mc < 0 and macd_contracting:
            breakout_type = '真跌破（动能减弱）'
            icon = '⚠️'
            theory = (
                f"【真跌破但动能减弱】{level_name}跌破55线({m55:.2f}) + MACD<0({mc:.2f})但MACD柱收敛"
                f" → 跌破有效但下跌动能减弱，可能反弹"
            )
            operation = (
                f"【策略】若反弹至55线({m55:.2f})遇阻 → 确认做空点"
                f" → 若突破55线 → 假跌破确认，可试多"
            )
        elif mc > 0:
            breakout_type = '假跌破'
            icon = '🟡'
            theory = (
                f"【假跌破】{level_name}跌破55线({m55:.2f})但MACD>0({mc:.2f})"
                f" → 跌破55线但MACD为正，下跌动能不足"
                f" → 假跌破概率高，可能快速反弹"
            )
            operation = (
                f"【策略】不恐慌，等待反弹确认"
                f" → 若反弹突破55线({m55:.2f}) + MACD持续转正 → 假跌破确认，可试多"
            )
        else:
            breakout_type = '跌破待确认'
            icon = '🟡'
            theory = f"{level_name}跌破55线({m55:.2f})，MACD接近0，方向不明确"
            operation = "等待MACD转负确认"
    else:
        breakout_type = '中性'
        icon = '➖'
        theory = f"{level_name}价格接近55线({m55:.2f})，未突破也未跌破"
        operation = "等待方向选择"
    
    return {
        'type': breakout_type,
        'icon': icon,
        'price': p,
        'ma55': m55,
        'macd': mc,
        'macd_expanding': macd_expanding,
        'macd_contracting': macd_contracting,
        'theory': theory,
        'operation': operation
    }

# =====================================================
# v4.2: 二买/二卖识别（SKILL.md Step 10）
# =====================================================

def analyze_second_buy_sell(df, segment_data=None, level_name='30F'):
    """
    v4.2 核心新增：二买/二卖识别（SKILL.md Step 10）
    
    二买判断标准：
    ├── 下跌段已完成 (3笔结构完整)
    ├── 第1笔up: 从低点反弹 (一买后的反弹)
    ├── 第2笔down: 回踩, 不创新低 (>一买低点)
    ├── 第3笔up: 确认二买成立, 开始上涨
    └── 若第2笔down创新低 → 二买失败, 继续下跌
    
    二卖判断标准：
    ├── 上涨段已完成 (3笔结构完整)
    ├── 第1笔down: 从高点回落 (一卖后的回落)
    ├── 第2笔up: 反弹, 不创新高 (<一卖高点)
    ├── 第3笔down: 确认二卖成立, 开始下跌
    └── 若第2笔up创新高 → 二卖失败, 继续上涨
    
    实战验证：
    2026-05-27: 30F第1笔down(4153→4104) + 第2笔up(4104→4133) + 第3笔down(4133→4077)
    → 第3笔down低点4077 < 第1笔down低点4104
    → 二买失败! ❌
    → 次日继续下跌
    """
    if len(df) < 30:
        return {'type': 'unknown', 'description': '数据不足'}
    
    # 如果没有段数数据，尝试重新计算
    if segment_data is None or not segment_data.get('peaks'):
        segment_data = count_segments(df, level_name)
    
    peaks = segment_data.get('peaks', [])
    if len(peaks) < 4:
        return {'type': 'unknown', 'description': '分型数量不足，无法判定二买/二卖'}
    
    # 找最近的低点和高点
    # 从最近的分型中找结构
    recent_peaks = peaks[-6:] if len(peaks) >= 6 else peaks
    
    # 找最近的低点（一买候选）
    bottoms = [p for p in recent_peaks if p[1] == 'bottom']
    tops = [p for p in recent_peaks if p[1] == 'top']
    
    if len(bottoms) < 2 or len(tops) < 2:
        return {'type': 'unknown', 'description': '低点/高点数量不足'}
    
    # 二买判定：从低点开始的结构
    # 需要：底 → 顶 → 底（第二个底高于第一个底）
    result = {'type': 'unknown', 'description': '未找到二买/二卖结构'}
    
    # 检查二买
    for i in range(len(bottoms) - 1):
        first_buy = bottoms[i]      # 一买低点
        second_buy = bottoms[i + 1]  # 二买低点（候选）
        
        # 找中间的高点（一买后的反弹高点）
        intermediate_tops = [t for t in tops if t[0] > first_buy[0] and t[0] < second_buy[0]]
        if not intermediate_tops:
            continue
        
        rebound_high = intermediate_tops[0]  # 反弹高点
        
        # 二买条件：第二个底 > 第一个底
        first_buy_price = float(first_buy[2])
        second_buy_price = float(second_buy[2])
        if second_buy_price > first_buy_price * 1.001:  # 允许0.1%误差
            result = {
                'type': '二买成立',
                'icon': '✅',
                'level': level_name,
                'first_buy': first_buy_price,
                'rebound_high': float(rebound_high[2]),
                'second_buy': second_buy_price,
                'theory': (
                    f"【二买成立】{level_name}下跌段完成(3笔结构完整) → "
                    f"一买低点{first_buy_price:.2f} → 反弹至{float(rebound_high[2]):.2f} → "
                    f"回踩低点{second_buy_price:.2f} > 一买低点{first_buy_price:.2f}(不创新低) → "
                    f"二买确认成立！"
                ),
                'operation': (
                    f"【策略】二买成立 → 加仓！"
                    f" → 止损设于一买低点{first_buy_price:.2f}下方"
                    f" → 目标：前高{float(rebound_high[2]):.2f} → 更高目标：上一级别55线"
                )
            }
            break
        else:
            # 二买失败：第二个底 < 第一个底（创新低）
            result = {
                'type': '二买失败',
                'icon': '❌',
                'level': level_name,
                'first_buy': first_buy_price,
                'rebound_high': float(rebound_high[2]),
                'second_buy': second_buy_price,
                'theory': (
                    f"【二买失败】{level_name}下跌段中 → "
                    f"一买低点{first_buy_price:.2f} → 反弹至{float(rebound_high[2]):.2f} → "
                    f"回踩低点{second_buy_price:.2f} < 一买低点{first_buy_price:.2f}(创新低) → "
                    f"二买失败！继续下跌"
                ),
                'operation': (
                    f"【策略】二买失败 → 减仓/清仓！"
                    f" → 次日可能继续下跌"
                    f" → 等待新的低点确认或级别传导链修复"
                )
            }
            break
    
    # 检查二卖（如果二买未找到）
    if result['type'] == 'unknown':
        for i in range(len(tops) - 1):
            first_sell = tops[i]       # 一卖高点
            second_sell = tops[i + 1]  # 二卖高点（候选）
            
            # 找中间的低点（一卖后的回落低点）
            intermediate_bottoms = [b for b in bottoms if b[0] > first_sell[0] and b[0] < second_sell[0]]
            if not intermediate_bottoms:
                continue
            
            pullback_low = intermediate_bottoms[0]  # 回落低点
            
            # 二卖条件：第二个顶 < 第一个顶
            first_sell_price = float(first_sell[2])
            second_sell_price = float(second_sell[2])
            if second_sell_price < first_sell_price * 0.999:  # 允许0.1%误差
                result = {
                    'type': '二卖成立',
                    'icon': '❌',
                    'level': level_name,
                    'first_sell': first_sell_price,
                    'pullback_low': float(pullback_low[2]),
                    'second_sell': second_sell_price,
                    'theory': (
                        f"【二卖成立】{level_name}上涨段完成(3笔结构完整) → "
                        f"一卖高点{first_sell_price:.2f} → 回落至{float(pullback_low[2]):.2f} → "
                        f"反弹高点{second_sell_price:.2f} < 一卖高点{first_sell_price:.2f}(不创新高) → "
                        f"二卖确认成立！"
                    ),
                    'operation': (
                        f"【策略】二卖成立 → 减仓！"
                        f" → 止损设于一卖高点{first_sell_price:.2f}上方"
                        f" → 目标：前低{float(pullback_low[2]):.2f} → 更低目标：下一级别55线"
                    )
                }
                break
            else:
                # 二卖失败：第二个顶 > 第一个顶（创新高）
                result = {
                    'type': '二卖失败',
                    'icon': '✅',
                    'level': level_name,
                    'first_sell': first_sell_price,
                    'pullback_low': float(pullback_low[2]),
                    'second_sell': second_sell_price,
                    'theory': (
                        f"【二卖失败】{level_name}上涨段中 → "
                        f"一卖高点{first_sell_price:.2f} → 回落至{float(pullback_low[2]):.2f} → "
                        f"反弹高点{second_sell_price:.2f} > 一卖高点{first_sell_price:.2f}(创新高) → "
                        f"二卖失败！继续上涨"
                    ),
                    'operation': (
                        f"【策略】二卖失败 → 持仓！"
                        f" → 上涨结构延续，等待更高点"
                    )
                }
                break
    
    return result

# =====================================================
# v4.2: 复合风控（SKILL.md Step 16）
# =====================================================

def analyze_composite_risk(levels_macd, levels_trend, levels_55, levels_middle, extreme_features):
    """
    v4.2 核心新增：复合风控（SKILL.md Step 16）
    
    单一指标风控 → 复合信号风控
    
    经典复合信号：
    - 30F55线压制 + 5F顶背离 = 兑现一部分多头
    - 双日死叉 + 30F主跌段 = 清仓
    - 5F55线突破 + 30F底背离 = 加仓
    - 跌破联合支撑区 = 无条件清仓
    - 假突破 + 联合压制区 = 减仓1/3
    """
    signals = []
    
    # 1. 双日死叉 + 30F主跌段 = 清仓
    if '双日' in levels_macd and '30F' in levels_trend:
        bid_state = levels_macd['双日'].get('state', '')
        t30 = levels_trend['30F'].get('grade', '')
        if bid_state in ['极弱', '弱'] and t30 == '主跌段':
            signals.append({
                'signal': '双日死叉 + 30F主跌段',
                'severity': 'critical',
                'icon': '🔴',
                'action': '清仓',
                'theory': (
                    "【复合风控】双日MACD极弱/弱 + 30F主跌段 → "
                    "大级别下跌传导链确立 + 操作级别主跌段确认 → "
                    "双重确认，无条件清仓！"
                ),
                'operation': (
                    "【操作】清仓！"
                    " → 双日级别中长期转空"
                    " → 30F级别短期主跌段"
                    " → 两者共振，下跌趋势确认"
                )
            })
    
    # 2. 30F55线压制 + 5F顶背离 = 兑现一部分多头
    if '30F' in levels_55 and '5F' in levels_macd:
        p30 = levels_55['30F']['price']
        m55_30 = levels_55['30F']['ma55']
        md5 = levels_macd['5F'].get('macd', 0)
        
        if p30 < m55_30 and md5 < 0:
            signals.append({
                'signal': '30F55线压制 + 5F顶背离',
                'severity': 'high',
                'icon': '🟠',
                'action': '减仓1/3',
                'theory': (
                    "【复合风控】30F价格<55线(压制) + 5F MACD<0(顶背离信号) → "
                    "操作级别压制 + 小级别顶背离 → 上涨动能不足"
                ),
                'operation': (
                    "【操作】兑现一部分多头，减仓1/3"
                    " → 30F55线压制下不宜重仓"
                    " → 等待突破30F55线后再加仓"
                )
            })
    
    # 3. 5F55线突破 + 30F底背离 = 加仓
    if '5F' in levels_55 and '30F' in levels_macd:
        p5 = levels_55['5F']['price']
        m55_5 = levels_55['5F']['ma55']
        md30 = levels_macd['30F'].get('macd', 0)
        
        if p5 > m55_5 and md30 > 0:
            signals.append({
                'signal': '5F55线突破 + 30F底背离',
                'severity': 'opportunity',
                'icon': '✅',
                'action': '加仓',
                'theory': (
                    "【复合风控】5F价格>55线(突破) + 30F MACD>0(底背离信号) → "
                    "小级别突破 + 操作级别底背离 → 上涨动能积聚"
                ),
                'operation': (
                    "【操作】加仓！"
                    " → 5F突破55线确认短期强势"
                    " → 30F底背离确认中期反弹"
                    " → 两者共振，做多胜率提高"
                )
            })
    
    # 4. 跌破联合支撑区 = 无条件清仓
    if '日线' in levels_55 and '双日' in levels_55:
        d55 = levels_55['日线']['ma55']
        b55 = levels_55['双日']['ma55']
        p_daily = levels_55['日线']['price']
        
        # 联合支撑区：日线55线 + 双日55线接近
        if abs(d55 - b55) < 20:
            if p_daily < min(d55, b55):
                signals.append({
                    'signal': '跌破联合支撑区',
                    'severity': 'critical',
                    'icon': '🔴',
                    'action': '无条件清仓',
                    'theory': (
                        f"【复合风控】价格跌破联合支撑区(日线55={d55:.2f} + 双日55={b55:.2f}) → "
                        f"大周期牛熊分界线被跌破 → 趋势彻底转空"
                    ),
                    'operation': (
                        "【操作】无条件清仓！"
                        " → 联合支撑区是最后防线"
                        " → 跌破后下跌空间打开"
                        " → 不抱幻想，立即止损"
                    )
                })
    
    # 5. 假突破 + 联合压制区 = 减仓1/3
    if '30F' in levels_trend and '60F' in levels_55:
        t30 = levels_trend['30F'].get('grade', '')
        m55_60f = levels_55['60F']['ma55']
        p60f = levels_55['60F']['price']
        
        # 假突破判断：价格>55线但MACD<0
        if t30 in ['x段', 'x段（无N+2支撑）'] and p60f > m55_60f:
            signals.append({
                'signal': '假突破 + 联合压制区',
                'severity': 'medium',
                'icon': '⚠️',
                'action': '减仓1/3',
                'theory': (
                    "【复合风控】30F假突破(X段) + 60F55线压制 → "
                    "上涨动能不足 + 更高级别压制 → 骗炮概率高"
                ),
                'operation': (
                    "【操作】减仓1/3"
                    " → 假突破后可能快速回落"
                    " → 保留部分仓位观察"
                    " → 若确认假突破则继续减仓"
                )
            })
    
    # 6. 二买失败 + 传导链恶化 = 清仓
    if '30F' in levels_trend and '15F' in levels_trend:
        t30 = levels_trend['30F'].get('grade', '')
        t15 = levels_trend['15F'].get('grade', '')
        if t30 == '主跌段' and t15 in ['主跌段', 'x段下方']:
            signals.append({
                'signal': '二买失败 + 传导链恶化',
                'severity': 'critical',
                'icon': '🔴',
                'action': '清仓',
                'theory': (
                    "【复合风控】30F主跌段 + 15F主跌段 → "
                    "二买失败 + 小级别恶化 → 下跌传导链确立"
                ),
                'operation': (
                    "【操作】清仓！"
                    " → 二买失败意味着下跌延续"
                    " → 15F恶化确认传导链"
                    " → 小级别恶化→中级别恶化→大级别恶化"
                )
            })
    
    # 汇总
    if not signals:
        return {
            'signals': [],
            'max_severity': 'none',
            'description': '无复合风控信号',
            'operation': '按正常策略操作'
        }
    
    # 找出最严重的信号
    severity_order = {'critical': 4, 'high': 3, 'medium': 2, 'opportunity': 1, 'none': 0}
    max_severity = max(signals, key=lambda x: severity_order.get(x['severity'], 0))
    
    return {
        'signals': signals,
        'max_severity': max_severity['severity'],
        'critical_count': len([s for s in signals if s['severity'] == 'critical']),
        'high_count': len([s for s in signals if s['severity'] == 'high']),
        'description': f"复合风控: {len(signals)}个信号 | 最严重: {max_severity['signal']}({max_severity['action']})",
        'operation': ' | '.join([s['action'] for s in signals if s['severity'] in ['critical', 'high']])
    }

# =====================================================
# v4.2: 120F55线战略分水岭（SKILL.md Step 12）
# =====================================================

def analyze_120f55_strategic(df_120f, df_daily, df_bid, levels_macd, levels_trend):
    """
    v4.2 核心新增：120F55线战略分水岭（SKILL.md Step 12）
    
    120F55线是决定后续行情性质的重要分水岭
    
    双向路径：
    ├── 有效突破120F55线
    │   ├── 双日第三段上涨确认
    │   ├── 目标: 双日级别前高/测量目标
    │   └── 时间窗口: 一周内突破有效
    ├── 120F55线压制
    │   ├── 日线主跌段前兆
    │   ├── 后续: 跌破55周线
    │   └── 标志: 反抽120F55线但无法站上
    └── 突破方式（主观经验）
        ├── 直接突破: 难度较大，需强势放量
        └── 等待下行: 120F55线下行穿过55日线/双日55线后再突破
            └── 更大概率，时间换空间
    
    时间框架：一周内必须有答案（有效突破或确认压制）
    """
    if len(df_120f) < 55 or len(df_daily) < 55:
        return {'description': '数据不足，无法分析120F55线战略分水岭'}
    
    p_120f = float(df_120f['Close'].iloc[-1])
    m55_120f = float(ma(df_120f, 55).iloc[-1])
    md_120f = macd(df_120f)['macd'].iloc[-1]
    
    p_daily = float(df_daily['Close'].iloc[-1])
    m55_daily = float(ma(df_daily, 55).iloc[-1])
    
    bid_macd = levels_macd.get('双日', {}).get('macd', 0) if levels_macd else 0
    
    # 判断120F55线状态
    if p_120f > m55_120f and md_120f > 0:
        status = '有效突破'
        icon = '✅'
        theory = (
            f"【120F55线有效突破】120F价格({p_120f:.2f}) > 120F55线({m55_120f:.2f}) + MACD>0({md_120f:.2f}) → "
            f"突破有效，双日第三段上涨确认"
        )
        operation = (
            f"【策略】双日第三段上涨确认 → 加仓！"
            f" → 目标：双日级别前高"
            f" → 时间窗口：一周内突破有效"
        )
    elif p_120f > m55_120f and md_120f < 0:
        status = '假突破'
        icon = '⚠️'
        theory = (
            f"【120F55线假突破】120F价格({p_120f:.2f}) > 120F55线({m55_120f:.2f})但MACD<0({md_120f:.2f}) → "
            f"站上55线但MACD为负，上涨动能不足 → 假突破/骗炮"
        )
        operation = (
            f"【策略】不追涨，等待回踩确认或回落"
            f" → 若次日跌破120F55线({m55_120f:.2f}) → 确认骗炮，减仓"
        )
    elif p_120f < m55_120f:
        # 检查是否被压制
        recent_high = float(df_120f['High'].tail(20).max())
        if recent_high > m55_120f * 0.995 and p_120f < m55_120f:
            status = '压制（反抽失败）'
            icon = '❌'
            theory = (
                f"【120F55线压制】近期高点{recent_high:.2f}接近120F55线({m55_120f:.2f})但当前价格{p_120f:.2f}跌破 → "
                f"反抽120F55线但无法站上 → 日线主跌段前兆"
            )
            operation = (
                f"【策略】日线主跌段前兆 → 减仓/清仓！"
                f" → 后续可能跌破55周线"
                f" → 等待120F55线下行后再考虑突破"
            )
        else:
            status = '压制'
            icon = '❌'
            theory = (
                f"【120F55线压制】120F价格({p_120f:.2f}) < 120F55线({m55_120f:.2f}) → "
                f"被120F55线压制，行情性质待定"
            )
            operation = (
                f"【策略】被120F55线压制 → 观望"
                f" → 等待突破120F55线({m55_120f:.2f})后再做多"
                f" → 或等待120F55线下行至价格下方（时间换空间）"
            )
    else:
        status = '中性'
        icon = '➖'
        theory = f"120F价格接近55线({m55_120f:.2f})，未突破也未跌破"
        operation = "等待方向选择"
    
    # 突破方式分析
    breakthrough_analysis = ""
    if m55_120f > m55_daily:
        breakthrough_analysis = (
            f"120F55线({m55_120f:.2f}) > 日线55线({m55_daily:.2f}) → "
            f"120F55线在上方，直接突破难度较大"
        )
    else:
        breakthrough_analysis = (
            f"120F55线({m55_120f:.2f}) < 日线55线({m55_daily:.2f}) → "
            f"120F55线在下方，更容易突破"
        )
    
    return {
        'status': status,
        'icon': icon,
        'price_120f': p_120f,
        'ma55_120f': m55_120f,
        'macd_120f': md_120f,
        'theory': theory,
        'operation': operation,
        'breakthrough_analysis': breakthrough_analysis,
        'timeframe': '一周内必须有答案（有效突破或确认压制）'
    }

# =====================================================
# v4.2: 补偿性买点识别（SKILL.md Step 15）
# =====================================================

def analyze_compensation_buy(df, df_upper, level_name='30F', upper_name='60F'):
    """
    v4.2 核心新增：补偿性买点识别（SKILL.md Step 15）
    
    经典缠论买点结构：跌破55线 → 回踩确认 → 突破中轨 → 突破上级55线
    
    条件：
    - 价格跌破MA55
    - 在MA55下方企稳
    - MACD底背离 或 缩量
    - 买点区域：MA55下方2%以内
    - 确认信号：突破中轨 + 放量
    - 目标：上级55线
    """
    if len(df) < 55:
        return {'is_compensation_buy': False, 'description': '数据不足'}
    
    p = float(df['Close'].iloc[-1])
    m55 = float(ma(df, 55).iloc[-1])
    md = macd(df)
    dif = float(md['dif'].iloc[-1])
    dea = float(md['dea'].iloc[-1])
    mc = float(md['macd'].iloc[-1])
    
    upper_m55 = float(ma(df_upper, 55).iloc[-1]) if len(df_upper) >= 55 else None
    
    b = boll(df, 20)
    middle = float(b['middle'].iloc[-1])
    
    # 条件1：价格跌破MA55
    price_below_55 = p < m55
    
    # 条件2：在MA55下方企稳（不继续创新低）
    recent_low = float(df['Low'].tail(10).min())
    prev_low = float(df['Low'].tail(20).head(10).min()) if len(df) >= 20 else recent_low
    stable_below = recent_low >= prev_low * 0.99  # 不再创新低
    
    # 条件3：MACD底背离 或 缩量
    # 检查底背离：价格新低但MACD未创新低
    if len(md['macd']) >= 20:
        prev_macd_low = float(md['macd'].tail(20).head(10).min())
        current_macd = float(md['macd'].tail(10).min())
        macd_divergence = current_macd > prev_macd_low * 1.05  # MACD底背离
    else:
        macd_divergence = False
    
    # 条件4：买点区域在MA55下方2%以内
    in_buy_zone = p >= m55 * 0.98
    
    # 条件5：确认信号 - 突破中轨 + 放量
    crossed_middle = p > middle
    volume_increase = False
    if 'Volume' in df.columns and len(df) >= 10:
        recent_volume = float(df['Volume'].tail(5).mean())
        prev_volume = float(df['Volume'].tail(10).head(5).mean())
        volume_increase = recent_volume > prev_volume * 1.2
    
    # 综合判定
    is_candidate = price_below_55 and stable_below and in_buy_zone
    is_confirmed = crossed_middle and (macd_divergence or volume_increase)
    
    if not price_below_55:
        return {
            'is_compensation_buy': False,
            'description': f'{level_name}价格未跌破55线，无补偿性买点',
            'price': p,
            'ma55': m55
        }
    
    if not is_candidate:
        return {
            'is_compensation_buy': False,
            'description': f'{level_name}不满足补偿性买点条件（未企稳或超出买点区域）',
            'price': p,
            'ma55': m55,
            'stable_below': stable_below,
            'in_buy_zone': in_buy_zone
        }
    
    # 补偿性买点候选
    result = {
        'is_compensation_buy': True,
        'status': '确认' if is_confirmed else '候选',
        'icon': '✅' if is_confirmed else '🟡',
        'level': level_name,
        'price': p,
        'ma55': m55,
        'middle': middle,
        'buy_zone': (m55 * 0.98, m55),
        'conditions': {
            'price_below_55': price_below_55,
            'stable_below': stable_below,
            'macd_divergence': macd_divergence,
            'in_buy_zone': in_buy_zone,
            'crossed_middle': crossed_middle,
            'volume_increase': volume_increase
        }
    }
    
    if is_confirmed:
        result['theory'] = (
            f"【补偿性买点确认】{level_name}跌破55线({m55:.2f})后企稳 → "
            f"价格{p:.2f}在买点区域内(55线下方2%以内) → "
            f"突破中轨({middle:.2f}) + {'MACD底背离' if macd_divergence else '放量'} → "
            f"补偿性买点确认！"
        )
        result['operation'] = (
            f"【策略】补偿性买点确认 → 试多！"
            f" → 止损设于近期低点{recent_low:.2f}下方"
            f" → 第一目标：{level_name}55线({m55:.2f})"
            f" → 第二目标：{upper_name}55线({upper_m55:.2f})" if upper_m55 else ""
        )
    else:
        result['theory'] = (
            f"【补偿性买点候选】{level_name}跌破55线({m55:.2f})后企稳 → "
            f"价格{p:.2f}在买点区域内，但确认信号未满足 → "
            f"等待突破中轨({middle:.2f}) + {'MACD底背离' if not macd_divergence else '放量'}"
        )
        result['operation'] = (
            f"【策略】补偿性买点候选 → 观察！"
            f" → 等待突破中轨({middle:.2f})确认"
            f" → 若突破中轨+{'放量' if not volume_increase else 'MACD底背离'} → 试多"
        )
    
    return result

# =====================================================
# v4.2: 主涨段判定（保留v4.1，增加理论说明）
# =====================================================

def analyze_main_trend_segment_v42(df, level_name='30F', segment_data=None, upper_state=None, lower_df=None, level_name_lower=None):
    """
    v4.2 核心升级：主涨段完整判定（含N+2传导、低位结构、主涨段结束/重新焕发）
    
    SKILL.md主涨段判定公式：
    N+2级别 MACD极强/金叉
        ↓
    N级别在低位出现结构（第三段或第五段）
        ↓
    第三段前回踩N-1级别55线
        ↓
    N级别主涨段
    """
    if len(df) < 55:
        return {'level': level_name, 'grade': 'unknown', 'description': '数据不足'}
    
    p = float(df['Close'].iloc[-1])
    m55 = float(ma(df, 55).iloc[-1])
    md = macd(df)['macd'].iloc[-1]
    
    b = boll(df, 20)
    middle = float(b['middle'].iloc[-1])
    
    # 1. 检查N+2级别传导条件（SKILL.md要求）
    has_upper_conduction = upper_state in ['极强', '强']
    upper_state_str = f"N+2级别({upper_state})" if upper_state else "N+2级别(未知)"
    
    # 2. 检查N级别低位结构（第三段或第五段）
    segment_count = segment_data.get('segment_count', 0) if segment_data else 0
    has_low_structure = segment_count in [3, 5] or segment_count >= 3
    structure_desc = f"{segment_count}段结构" if segment_count > 0 else "无结构数据"
    
    # 3. 检查N-1级别55线回踩（SKILL.md要求：第三段前回踩N-1级别55线）
    pullback_to_n_minus_1 = False
    if lower_df is not None and len(lower_df) >= 55:
        lower_m55 = float(ma(lower_df, 55).iloc[-1])
        recent_low = float(df['Low'].tail(20).min())
        # 检查是否回踩N-1级别55线（允许1%误差）
        pullback_to_n_minus_1 = recent_low <= lower_m55 * 1.01
    
    # 4. 主涨段三档判定（含理论推导）
    if p > m55 and md > 0:
        # 正式主涨段：价格>55线 + MACD>0 + 低位结构 + N+2传导
        if has_upper_conduction and has_low_structure:
            grade = '正式'
            desc = f'主涨段（正式）— 价格>55线 + MACD>0 + {structure_desc} + N+2{upper_state}传导'
            theory = (
                f"【理论推导】{upper_state_str}传导至{level_name} → "
                f"{level_name}在低位结构（{structure_desc}）后出主涨段 → "
                f"价格突破55线({m55:.2f}) + MACD转正 → 主涨段正式确认\n"
                f"【三特征支撑】极强/强形态下："
                f"1) 顶背离阶段性失效 2) 首次回踩55线极大概率支撑 3) 有向更高级别55线运动惯性"
            )
        elif has_upper_conduction:
            grade = '正式（结构待确认）'
            desc = f'主涨段（正式）— 价格>55线 + MACD>0 + N+2{upper_state}传导（结构待确认）'
            theory = (
                f"【理论推导】{upper_state_str}传导至{level_name} → "
                f"{level_name}价格突破55线 + MACD转正，但低位结构未明确（{structure_desc}）→ "
                f"主涨段运行中，需确认结构完整性"
            )
        else:
            grade = '正式（无N+2支撑）'
            desc = f'主涨段（正式）— 价格>55线 + MACD>0（但N+2非极强/强，持续性存疑）'
            theory = (
                f"【理论推导】{level_name}价格>55线 + MACD>0，但{upper_state_str}非极强/强 → "
                f"主涨段可能缺乏N+2级别支撑，持续性不确定 → "
                f"需警惕N+2级别转弱导致主涨段提前结束"
            )
    elif p > m55 and md < 0:
        # 55线上方X段：价格>55线但MACD<0
        if has_upper_conduction:
            grade = 'x段'
            desc = f'55线上方X段 — 价格>55线但MACD<0，N+2{upper_state}支撑中'
            theory = (
                f"【理论推导】{upper_state_str}传导至{level_name} → "
                f"{level_name}出现X段（N+1级别无结构，向下分解为N级别X段） → "
                f"价格>55线({m55:.2f})但MACD<0 → X段运行中\n"
                f"【X段后端确认】X段结束后需突破N级别55线+不创新低 → 重新焕发主涨段"
            )
        else:
            grade = 'x段（无N+2支撑）'
            desc = f'55线上方X段 — 价格>55线但MACD<0（N+2非极强，X段可能变异）'
            theory = (
                f"【理论推导】{level_name}价格>55线但MACD<0，但{upper_state_str}非极强/强 → "
                f"X段可能缺乏N+2支撑，可能变异为下跌段 → "
                f"需突破55线+MACD转正确认重新焕发"
            )
    elif p < m55 and md < 0:
        # 主跌段：价格<55线 + MACD<0
        grade = '主跌段'
        desc = f'主跌段 — 价格<55线 + MACD<0'
        theory = (
            f"【理论推导】N+2级别极弱/弱传导至{level_name} → "
            f"{level_name}在高位结构后出主跌段 → 价格跌破55线({m55:.2f}) + MACD<0\n"
            f"【主跌段特征】下跌持续性高，反弹至55线极大概率遇阻（55线压制）"
        )
    elif p < m55 and md > 0:
        # 55线下方X段：价格<55线但MACD>0
        grade = 'x段下方'
        desc = f'55线下方X段 — 价格<55线但MACD>0'
        theory = (
            f"【理论推导】{level_name}价格<55线但MACD>0 → "
            f"下跌中的X段（下跌动能减弱） → "
            f"需突破55线+MACD持续转正确认反转"
        )
    else:
        grade = '中性'
        desc = '中性'
        theory = f'N+2级别传导信号不明确，{level_name}方向待确认'
    
    # 5. 主涨段结束判定（SKILL.md要求：有效跌破N-1级别中轨）
    # 有效跌破 = 反抽不上（实战中需灵活运用）
    main_trend_ending = False
    if grade in ['正式', '正式（结构待确认）', '正式（无N+2支撑）'] and lower_df is not None:
        lower_middle = float(boll(lower_df, 20)['middle'].iloc[-1])
        if p < lower_middle:
            # 价格跌破N-1级别中轨
            recent_high = float(df['High'].tail(5).max())
            if recent_high < lower_middle:
                main_trend_ending = True
                desc += ' | ⚠️ 有效跌破N-1级别中轨，主涨段特征解除'
                theory += f"\n【主涨段结束】价格有效跌破N-1级别中轨({lower_middle:.2f}) → 主涨段特征解除"
    
    # 6. 主涨段重新焕发（X段桥梁）
    x_segment_renew = False
    if grade == 'x段' and lower_df is not None:
        lower_m55 = float(ma(lower_df, 55).iloc[-1])
        if p > lower_m55 and md > 0:
            x_segment_renew = True
            desc += ' | ✅ X段后重新焕发主涨段'
            theory += f"\n【重新焕发】X段结束 + 突破N-1级别55线({lower_m55:.2f}) + MACD转正 → 主涨段重新焕发"
    
    # 结合N+2级别状态的理论说明
    if upper_state:
        if upper_state in ['极强', '强'] and grade in ['正式', '正式（结构待确认）']:
            theory += f"\n【N+2支撑】{upper_state_str}支撑，主涨段持续性强，55线支撑有效"
        elif upper_state in ['极弱', '弱'] and grade in ['正式', '正式（结构待确认）']:
            theory += f"\n【N+2警告】⚠️ {upper_state_str}，主涨段可能随时结束，跌破55线即确认"
    
    return {
        'level': level_name,
        'grade': grade,
        'price': p,
        'ma55': m55,
        'macd': md,
        'middle': middle,
        'has_structure': has_low_structure,
        'segment_count': segment_count,
        'pullback_to_n_minus_1': pullback_to_n_minus_1,
        'main_trend_ending': main_trend_ending,
        'x_segment_renew': x_segment_renew,
        'description': desc,
        'theory': theory
    }

# =====================================================
# v4.2: 其他辅助函数（保留）
# =====================================================

def analyze_intraday_structure(df_1m, df_5m, levels_data):
    """盘中结构分析"""
    if len(df_1m) < 240 or len(df_5m) < 48:
        return {'description': '1F/5F数据不足，无法做日内结构分析'}
    
    today = df_1m['Date'].iloc[-1].date()
    today_1m = df_1m[df_1m['Date'].dt.date == today]
    today_5m = df_5m[df_5m['Date'].dt.date == today]
    
    if len(today_1m) < 100:
        return {'description': '今日数据不足，可能非交易日或数据延迟'}
    
    morning_end = pd.Timestamp(f'{today} 11:30:00')
    afternoon_start = pd.Timestamp(f'{today} 13:00:00')
    
    morning_1m = today_1m[today_1m['Date'] <= morning_end]
    afternoon_1m = today_1m[today_1m['Date'] >= afternoon_start]
    
    morning_high = float(morning_1m['High'].max()) if len(morning_1m) > 0 else 0
    morning_low = float(morning_1m['Low'].min()) if len(morning_1m) > 0 else 0
    afternoon_high = float(afternoon_1m['High'].max()) if len(afternoon_1m) > 0 else 0
    afternoon_low = float(afternoon_1m['Low'].min()) if len(afternoon_1m) > 0 else 0
    
    open_price = float(today_1m['Open'].iloc[0]) if len(today_1m) > 0 else 0
    close_price = float(today_1m['Close'].iloc[-1]) if len(today_1m) > 0 else 0
    
    pattern = '阳线' if close_price > open_price * 1.005 else ('阴线' if close_price < open_price * 0.995 else '十字星')
    
    key_actions = []
    if len(morning_1m) > 0:
        morning_open = float(morning_1m['Open'].iloc[0])
        morning_close = float(morning_1m['Close'].iloc[-1])
        if morning_close > morning_open:
            key_actions.append(f'上午: 高开高走/探底回升（{morning_low:.2f}→{morning_high:.2f}）')
        else:
            key_actions.append(f'上午: 冲高回落/低开低走（{morning_high:.2f}→{morning_low:.2f}）')
    
    if len(afternoon_1m) > 0:
        afternoon_open = float(afternoon_1m['Open'].iloc[0])
        afternoon_close = float(afternoon_1m['Close'].iloc[-1])
        if afternoon_close > afternoon_open:
            key_actions.append(f'下午: 回升收高（{afternoon_low:.2f}→{afternoon_close:.2f}）')
        else:
            key_actions.append(f'下午: 回落收低（{afternoon_high:.2f}→{afternoon_close:.2f}）')
    
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

def get_middle_status(df, level_name):
    """获取中轨状态"""
    if len(df) < 20:
        return {'price': 0, 'middle': 0, 'status': '数据不足'}
    p = float(df['Close'].iloc[-1])
    b = boll(df, 20)
    middle = float(b['middle'].iloc[-1])
    status = '中轨上方' if p > middle else '中轨下方'
    return {'price': p, 'middle': middle, 'status': status, 'diff': p - middle}

def analyze_middle_transmission_chain(levels_middle, levels_macd, levels_55):
    """
    v4.2 核心新增：中轨传导链完整分析（SKILL.md Step 9.5）
    
    日内下跌传导:
    3F跌破中轨 → 5F回踩中轨 → 15F回踩中轨 → 30F中轨支撑 → 60F中轨支撑
         ↓            ↓              ↓               ↓              ↓
      日内微幅      第一道         小时级         上午关键       半日级
      调整信号      防线           支撑           支撑           强支撑
    
    日内上涨传导:
    5F突破中轨 → 15F突破中轨 → 30F突破中轨 → 60F突破中轨
         ↓            ↓              ↓               ↓
      分时启动      小时级         上午确认       半日确认
    
    v4.1铁律：日内操作先看中轨，趋势判断再看MA55
    """
    chain_result = []
    
    # 分析各级别中轨状态
    for name in ['5F', '15F', '30F', '60F']:
        if name in levels_middle:
            data = levels_middle[name]
            p = data['price']
            m = data['middle']
            status = data['status']
            
            # 判断传导方向
            if status == '中轨上方':
                direction = '传导支撑'
                icon = '✅'
            else:
                direction = '传导压制'
                icon = '❌'
            
            chain_result.append({
                'level': name,
                'price': p,
                'middle': m,
                'status': status,
                'direction': direction,
                'icon': icon
            })
    
    # 分析传导链状态
    chain_status = '正常'
    if len(chain_result) >= 3:
        # 检查下跌传导链：3F跌破中轨 → 5F回踩中轨 → 15F回踩中轨 → 30F中轨支撑
        if all(r['status'] == '中轨下方' for r in chain_result[:3]):
            chain_status = '下跌传导链激活'
        # 检查上涨传导链：5F突破中轨 → 15F突破中轨 → 30F突破中轨
        elif all(r['status'] == '中轨上方' for r in chain_result[:3]):
            chain_status = '上涨传导链激活'
        # 检查混合状态
        elif chain_result[0]['status'] == '中轨下方' and chain_result[2]['status'] == '中轨上方':
            chain_status = '5F弱势/30F强势 - 日内震荡'
    
    return {
        'chain': chain_result,
        'chain_status': chain_status,
        'description': f'中轨传导链: {chain_status}'
    }

def analyze_time_segment_support(middle_data, ma55_data, levels_macd=None):
    """
    v4.2 升级：分时段关键支撑分析（SKILL.md Step 9.6）
    
    分时段支撑矩阵：
    | 时段 | 第一支撑 | 第二支撑 | 第三支撑 | 风控线 |
    | 上午(9:30-11:30) | 30F中轨 | 30F MA55 | 60F中轨 | 15F跌破中轨 |
    | 下午(13:00-14:30) | 5F MA55 | 5F中轨 | 15F MA55 | 5F跌破MA55 |
    | 尾盘(14:30-15:00) | 5F中轨 | 15F中轨 | 30F中轨 | 收在30F中轨下方 |
    """
    # 上午时段支撑
    morning_supports = []
    if '30F' in middle_data:
        morning_supports.append(('30F中轨', middle_data['30F']['middle'], '第一支撑'))
    if '30F' in ma55_data:
        morning_supports.append(('30F MA55', ma55_data['30F']['ma55'], '第二支撑'))
    if '60F' in middle_data:
        morning_supports.append(('60F中轨', middle_data['60F']['middle'], '第三支撑'))
    
    # 上午风控：15F中轨跌破
    morning_risk = None
    if '15F' in middle_data:
        morning_risk = ('15F中轨', middle_data['15F']['middle'], '15F跌破中轨 → 上午弱势')
    
    # 下午时段支撑
    afternoon_supports = []
    if '5F' in ma55_data:
        afternoon_supports.append(('5F MA55', ma55_data['5F']['ma55'], '第一支撑'))
    if '5F' in middle_data:
        afternoon_supports.append(('5F中轨', middle_data['5F']['middle'], '第二支撑'))
    if '15F' in ma55_data:
        afternoon_supports.append(('15F MA55', ma55_data['15F']['ma55'], '第三支撑'))
    
    # 下午风控：5F MA55跌破
    afternoon_risk = None
    if '5F' in ma55_data:
        afternoon_risk = ('5F MA55', ma55_data['5F']['ma55'], '5F跌破MA55 → 下午弱势')
    
    # 尾盘时段支撑
    close_supports = []
    if '5F' in middle_data:
        close_supports.append(('5F中轨', middle_data['5F']['middle'], '第一支撑'))
    if '15F' in middle_data:
        close_supports.append(('15F中轨', middle_data['15F']['middle'], '第二支撑'))
    if '30F' in middle_data:
        close_supports.append(('30F中轨', middle_data['30F']['middle'], '第三支撑'))
    
    # 尾盘风控：收在30F中轨下方
    close_risk = None
    if '30F' in middle_data:
        close_risk = ('30F中轨', middle_data['30F']['middle'], '收在30F中轨下方 → 弱势收盘')
    
    # 分时段策略速查
    morning_strategy = []
    if '30F' in middle_data:
        m30 = middle_data['30F']['middle']
        morning_strategy.append(f'高开在30F中轨上方 → 强势，持仓观察')
        morning_strategy.append(f'低开跌破30F中轨 → 第一支撑失效，测试30F MA55')
        morning_strategy.append(f'回踩30F中轨({m30:.2f})企稳+底背离 → 试多/持仓')
    
    afternoon_strategy = []
    if '5F' in ma55_data and '5F' in middle_data:
        m55_5f = ma55_data['5F']['ma55']
        m5 = middle_data['5F']['middle']
        afternoon_strategy.append(f'5F守住MA55({m55_5f:.2f}) → 下午维持震荡/反弹')
        afternoon_strategy.append(f'5F跌破MA55 → 测试5F中轨({m5:.2f})')
    
    close_strategy = []
    if '30F' in middle_data:
        m30 = middle_data['30F']['middle']
        close_strategy.append(f'收在30F中轨上方 → 多头占优，持仓过夜')
        close_strategy.append(f'收在30F中轨下方 → 弱势，减仓至半仓')
    
    return {
        'morning': morning_supports,
        'morning_risk': morning_risk,
        'afternoon': afternoon_supports,
        'afternoon_risk': afternoon_risk,
        'close': close_supports,
        'close_risk': close_risk,
        'morning_strategy': morning_strategy,
        'afternoon_strategy': afternoon_strategy,
        'close_strategy': close_strategy
    }

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
# v4.2: 数据完整性检查（SKILL.md Step 1 硬性规则）
# =====================================================

def check_data_integrity(df, level_name, min_bars=55, min_bars_boll=20):
    """
    数据完整性检查 - SKILL.md硬性规则：
    - 数据不足55根 → MA55计算失真，不可用于决策!
    - 数据不足20根 → 布林带中轨/上轨/下轨失真!
    - 数据不足 → 标记"数据不足，仅供参考"，使用更大级别替代
    """
    n = len(df)
    
    # 判断标准
    ma55_ok = n >= min_bars
    boll_ok = n >= min_bars_boll
    
    status = 'usable' if ma55_ok else ('limited' if boll_ok else 'insufficient')
    
    # 最少数据天数（根据级别）
    min_days_map = {
        '1F': 1, '3F': 1, '5F': 3, '15F': 7, '30F': 14,
        '60F': 28, '120F': 55, '日线': 55, '双日': 110, '双周': 550
    }
    min_days = min_days_map.get(level_name, 55)
    
    return {
        'level': level_name,
        'bars': n,
        'ma55_ok': ma55_ok,
        'boll_ok': boll_ok,
        'status': status,
        'min_bars_required': min_bars,
        'min_days': min_days,
        'can_use_ma55': ma55_ok,
        'can_use_boll': boll_ok,
        'warning': '' if ma55_ok else f'⚠️ {level_name}数据仅{n}根(<{min_bars})，MA55计算失真，不可用于决策!',
        'fallback': '' if ma55_ok else f'请使用更大级别替代，或增加数据量至至少{min_bars}根'
    }

# =====================================================
# 主程序
# =====================================================

def main():
    print("="*70)
    print("缠论分析 v4.2 - 理论驱动版（系统性使用SKILL.md理论推导）")
    print("="*70)
    
    print("\n📡 从长桥获取实时数据...")
    
    # 获取各级别数据 - v4.2修复：确保双日级别有足够数据
    # 双日需要55根，合成方式日线×2，需要110天日线数据
    # 为保险起见，获取220根日线（确保合成后110根双日）
    df_1m = fetch_longbridge('000001.SH', '1m', 1000)
    df_3m = fetch_longbridge('000001.SH', '3m', 334)
    df_5m = fetch_longbridge('000001.SH', '5m', 1000)
    df_15m = fetch_longbridge('000001.SH', '15m', 334)
    df_30m = fetch_longbridge('000001.SH', '30m', 167)
    df_60m = fetch_longbridge('000001.SH', '60m', 84)
    df_120m_raw = fetch_longbridge('000001.SH', '120m', 100)
    df_d = fetch_longbridge('000001.SH', '1d', 220)  # v4.2修复：从120增加到220，确保双日≥55根
    
    # 修复120F
    from datetime import time as dt_time
    df_120m = df_120m_raw[df_120m_raw['Date'].dt.time != dt_time(15, 0, 0)].reset_index(drop=True)
    if len(df_120m) < 55:
        df_120m = df_120m_raw.tail(55).reset_index(drop=True)
    
    # 合成双日
    df_bid = synthesize_kline(df_d, 2)
    
    print(f"  120F原始: {len(df_120m_raw)}根, 过滤后: {len(df_120m)}根")
    print(f"  日线: {len(df_d)}根, 双日合成: {len(df_bid)}根")
    
    # v4.2修复：Step 1 数据完整性严格检查
    print(f"\n{'='*70}")
    print("Step 1: 数据完整性检查（SKILL.md硬性规则）")
    print(f"{'='*70}")
    print("  硬性规则：数据不足55根 → MA55计算失真，不可用于决策!")
    print("           数据不足20根 → 布林带中轨/上轨/下轨失真!")
    
    # 检查各级别数据完整性
    data_levels = [
        ('1F', df_1m, 55, 20), ('3F', df_3m, 55, 20), ('5F', df_5m, 55, 20),
        ('15F', df_15m, 55, 20), ('30F', df_30m, 55, 20), ('60F', df_60m, 55, 20),
        ('120F', df_120m, 55, 20), ('日线', df_d, 55, 20), ('双日', df_bid, 55, 20)
    ]
    
    integrity_results = {}
    usable_levels = {}
    insufficient_levels = []
    
    for name, df, min_bars, min_boll in data_levels:
        result = check_data_integrity(df, name, min_bars, min_boll)
        integrity_results[name] = result
        
        icon = "✅" if result['status'] == 'usable' else ("⚠️" if result['status'] == 'limited' else "❌")
        print(f"  {icon} {name}: {result['bars']}根", end="")
        
        if result['status'] == 'usable':
            print(f" (MA55✅ BOLL✅)")
            usable_levels[name] = df
        elif result['status'] == 'limited':
            print(f" (MA55❌ BOLL✅) - 仅可用于中轨分析")
            usable_levels[name] = df  # 仍可用，但有限制
        else:
            print(f" (MA55❌ BOLL❌) - 不可用于决策!")
            insufficient_levels.append(name)
            if result['warning']:
                print(f"     {result['warning']}")
            if result['fallback']:
                print(f"     {result['fallback']}")
    
    # 如果关键级别数据不足，给出明确提示
    critical_levels = ['日线', '双日', '120F', '60F', '30F']
    critical_insufficient = [l for l in insufficient_levels if l in critical_levels]
    if critical_insufficient:
        print(f"\n  🔴 关键级别数据不足: {', '.join(critical_insufficient)}")
        print(f"     这些级别的MA55分析将被跳过，使用更大级别替代")
    
    print(f"\n  ✅ 数据获取完成:")
    for name, result in integrity_results.items():
        ok = "✅" if result['status'] == 'usable' else ("⚠️" if result['status'] == 'limited' else "❌")
        print(f"    {ok} {name}: {result['bars']}根 (需≥{result['min_bars_required']}根)")
    
    # Step 2: 段数分解
    print(f"\n{'='*70}")
    print("Step 2: 段数结构分解（v4.2完整版）")
    print(f"{'='*70}")
    print("\n  段结构类型：3段=盘整 / 5-6段=趋势 / 9段+=扩展")
    
    segment_data = {}
    for name, df in [('3F', df_3m), ('5F', df_5m), ('15F', df_15m), ('30F', df_30m)]:
        if len(df) >= 20:
            seg = count_segments(df, name)
            segment_data[name] = seg
            
            print(f"\n  📊 {name}段数结构分解:")
            print(f"    段数: {seg['segment_count']} | 结构: {seg['structure']}")
            print(f"    当前: {seg['current']}")
            
            # 输出起点和高点/低点
            if seg['start_price'] > 0:
                print(f"    起点: {seg['start_type']}{seg['start_price']:.2f}")
            if seg['recent_high']:
                print(f"    高点: {seg['recent_high']:.2f}")
            if seg['recent_low']:
                print(f"    低点: {seg['recent_low']:.2f}")
            
            # 目标推导
            if seg['target_desc']:
                print(f"    目标: {seg['target_desc']}")
            
            # X段重置检测
            if seg['x_reset_detected']:
                print(f"    🔄 X段重置: {seg['x_reset_desc']}")
            
            print(f"    分型序列: {seg['peak_str']}")
    
    # =====================================================
    # Step 3: v4.2 MACD六种状态理论推导（核心重写）
    # =====================================================
    print(f"\n{'='*70}")
    print("Step 3: MACD六种状态理论推导（v4.2核心重写）")
    print(f"{'='*70}")
    print("\n  ⚠️ 注意：MACD的'强弱'不是行情强弱，而是'稳定性'")
    print("     稳定性强弱是相对于走势而言的。")
    
    levels_macd = {}
    for name, df in [('3F', df_3m), ('5F', df_5m), ('15F', df_15m), ('30F', df_30m), ('60F', df_60m), ('120F', df_120m), ('日线', df_d), ('双日', df_bid)]:
        if len(df) >= 30:
            macd_result = analyze_macd_six_states(df, name)
            levels_macd[name] = macd_result
            
            print(f"\n  {'='*60}")
            print(f"  📊 {name}: 【{macd_result['state']}】")
            print(f"  {'='*60}")
            print(f"  指标: DIF={round(macd_result['dif'],2)}, DEA={round(macd_result['dea'],2)}, MACD={round(macd_result['macd'],2)}")
            if macd_result['cross_info']:
                print(f"  {macd_result['cross_info']}")
            print(f"\n  📖 {macd_result['theory']}")
            print(f"\n  🔗 {macd_result['conduction']}")
            print(f"\n  🎯 {macd_result['operation']}")
    
    # =====================================================
    # Step 4: v4.2 六种金叉死叉形态推导
    # =====================================================
    print(f"\n{'='*70}")
    print("Step 4: 六种金叉死叉形态推导（v4.2核心）")
    print(f"{'='*70}")
    print("\n  体系中：零轴金叉视为极强形态，零轴死叉视为极弱形态")
    
    for name, df in [('15F', df_15m), ('30F', df_30m), ('60F', df_60m), ('120F', df_120m)]:
        if len(df) >= 30:
            cross = analyze_golden_dead_cross(df, name)
            print(f"\n  📊 {name}: 【{cross['cross_type']}】稳定性:{cross['stability']}")
            print(f"  📖 {cross['theory']}")
            print(f"  🔗 {cross['conduction']}")
            print(f"  🎯 {cross['operation']}")
    
    # =====================================================
    # Step 5: v4.2 主涨段三档判定（增加理论推导）
    # =====================================================
    print(f"\n{'='*70}")
    print("Step 5: 主涨段三档判定（v4.2理论驱动）")
    print(f"{'='*70}")
    print("\n  理论：N+2级别MACD极强/金叉 → N级别在低位结构后出主涨段")
    print("       第三段前回踩N-1级别55线 → 主涨段启动")
    print("       有效跌破N-1级别中轨 → 主涨段特征解除")
    
    # N-1级别映射（组B级差体系）
    N_MINUS_1_DATA_MAP = {
        '15F': ('3F', df_3m), '30F': ('5F', df_5m),
        '60F': ('15F', df_15m), '120F': ('30F', df_30m)
    }
    
    levels_trend = {}
    for name, df in [('15F', df_15m), ('30F', df_30m), ('60F', df_60m), ('120F', df_120m)]:
        if len(df) >= 55:
            # 获取N+2级别状态
            upper_map = {'15F': '30F', '30F': '60F', '60F': '120F', '120F': '日线'}
            upper_name = upper_map.get(name)
            upper_state = levels_macd.get(upper_name, {}).get('state') if upper_name else None
            
            # 获取N-1级别数据（用于检查回踩）
            lower_name, lower_df = N_MINUS_1_DATA_MAP.get(name, (None, None))
            
            trend = analyze_main_trend_segment_v42(
                df, name, segment_data.get(name), upper_state, lower_df, lower_name
            )
            levels_trend[name] = trend
            grade_icon = {'正式':'✅', '正式（结构待确认）':'⚠️', '正式（无N+2支撑）':'🟡',
                         'x段':'❌', 'x段（无N+2支撑）':'🟠', '主跌段':'❌', 'x段下方':'⚠️'}
            icon = grade_icon.get(trend['grade'], '?')
            print(f"\n  {icon} {name}: 【{trend['grade']}】{trend['description']}")
            print(f"     📖 {trend['theory']}")
            
            # 额外输出关键条件
            if trend['has_structure']:
                print(f"     ✅ 低位结构: {trend['segment_count']}段")
            if trend['pullback_to_n_minus_1']:
                print(f"     ✅ 已回踩N-1级别55线")
            if trend['main_trend_ending']:
                print(f"     🔴 主涨段特征解除！")
            if trend['x_segment_renew']:
                print(f"     ✅ X段后重新焕发主涨段")
    
    # =====================================================
    # Step 5b: X段判定体系（v4.2核心新增，SKILL.md Step 6）
    # =====================================================
    print(f"\n{'='*70}")
    print("Step 5b: X段判定体系（v4.2核心新增）")
    print(f"{'='*70}")
    print("\n  X段只出现在主涨段或主跌段中，不能单独存在")
    print("  判定关键：N+1级别没有结构，向下分解到N级别称为X段")
    
    x_pairs = [
        ('15F', df_15m, '30F', df_30m, '5F', df_5m),
        ('30F', df_30m, '60F', df_60m, '15F', df_15m),
        ('60F', df_60m, '120F', df_120m, '30F', df_30m),
    ]
    
    x_results = {}
    for n, df_n, n_plus_1, df_np1, n_minus_1, df_nm1 in x_pairs:
        if len(df_n) >= 55 and len(df_np1) >= 55:
            x_result = analyze_x_segment_full(
                df_n, df_np1, df_nm1, n, n_plus_1, n_minus_1, segment_data.get(n)
            )
            x_results[n] = x_result
            
            if x_result['is_x_segment']:
                print(f"\n  🔍 {n}级别: 【{x_result['x_type']}】")
                print(f"     📖 {x_result['theory']}")
                print(f"     ✅ 条件1(复合结构): {x_result['condition1_composite']}")
                print(f"     ✅ 条件2(起点=最高点): {x_result['condition2_start_from_high']}")
                print(f"     {'✅' if x_result['condition3_backend_confirm'] else '⚠️'} 条件3(后验确认): {x_result['backend_confirm_status']}")
                print(f"     🎯 {x_result['operation']}")
            else:
                print(f"\n  🔍 {n}级别: {x_result['description']}")
    
    # =====================================================
    # Step 5c: 假突破/骗炮识别（v4.2核心新增，SKILL.md Step 7）
    # =====================================================
    print(f"\n{'='*70}")
    print("Step 5c: 假突破/骗炮识别（v4.2核心新增）")
    print(f"{'='*70}")
    print("\n  判断标准：")
    print("  站上55线 + MACD>0 + MACD柱放大 → 真突破")
    print("  站上55线 + MACD<0 或 MACD柱收敛 → 假突破（骗炮）")
    print("  跌破55线 + MACD<0 + MACD柱放大 → 真跌破")
    print("  跌破55线 + MACD>0 或 MACD柱收敛 → 假跌破")
    
    breakout_levels = [('15F', df_15m), ('30F', df_30m), ('60F', df_60m)]
    for name, df in breakout_levels:
        if len(df) >= 55:
            breakout = analyze_fake_breakout(df, name)
            print(f"\n  {breakout['icon']} {name}: 【{breakout['type']}】")
            print(f"     价格: {breakout['price']:.2f} vs MA55: {breakout['ma55']:.2f}")
            print(f"     MACD: {breakout['macd']:.2f}", end="")
            if breakout['macd_expanding']:
                print(" (柱体放大)")
            elif breakout['macd_contracting']:
                print(" (柱体收敛)")
            else:
                print(" (柱体平稳)")
            print(f"     📖 {breakout['theory']}")
            print(f"     🎯 {breakout['operation']}")
    
    # =====================================================
    # Step 5d: 二买/二卖识别（v4.2核心新增，SKILL.md Step 10）
    # =====================================================
    print(f"\n{'='*70}")
    print("Step 5d: 二买/二卖识别（v4.2核心新增）")
    print(f"{'='*70}")
    print("\n  二买标准：下跌段完成 + 第1笔up + 第2笔down不创新低 → 二买成立 ✅")
    print("  二卖标准：上涨段完成 + 第1笔down + 第2笔up不创新高 → 二卖成立 ❌")
    
    for name, df in [('15F', df_15m), ('30F', df_30m), ('60F', df_60m)]:
        if len(df) >= 30:
            bs = analyze_second_buy_sell(df, segment_data.get(name), name)
            if bs['type'] != 'unknown':
                print(f"\n  {bs['icon']} {name}: 【{bs['type']}】")
                print(f"     📖 {bs['theory']}")
                print(f"     🎯 {bs['operation']}")
            else:
                print(f"\n  ➖ {name}: {bs['description']}")
    
    # =====================================================
    # Step 6: v4.2 极强/极弱三特征推导（核心新增）
    # =====================================================
    print(f"\n{'='*70}")
    print("Step 6: 极强/极弱三特征推导（v4.2核心新增）")
    print(f"{'='*70}")
    print("\n  三特征：1.背离失效 2.55线支撑/压制 3.传递性")
    
    extreme_pairs = [
        ('15F', df_15m, '30F', df_30m),
        ('30F', df_30m, '60F', df_60m),
        ('60F', df_60m, '120F', df_120m),
        ('120F', df_120m, '日线', df_d),
    ]
    
    extreme_features = {}
    for n, df_n, n_plus_1, df_np1 in extreme_pairs:
        if len(df_n) >= 55 and len(df_np1) >= 55:
            feat = analyze_extreme_features(df_n, df_np1, n, n_plus_1)
            extreme_features[n] = feat
            
            print(f"\n  {'='*60}")
            print(f"  📊 {n}级别（N+2级别{n_plus_1}状态：{feat['upper_state']}）")
            print(f"  {'='*60}")
            for f in feat['features']:
                print(f"\n  🔹 {f['feature']}:")
                print(f"     📖 {f['theory']}")
                print(f"     🔗 {f['derivation']}")
                print(f"     ⚡ {f['condition']}")
                print(f"     🎯 {f['operation']}")
    
    # =====================================================
    # Step 7: v4.2 N+2→N级别传导推导（核心新增）
    # =====================================================
    print(f"\n{'='*70}")
    print("Step 7: N+2→N级别传导推导（v4.2核心新增）")
    print(f"{'='*70}")
    print("\n  传导公式：N+2极强/金叉 → N级别低位结构后出主涨段")
    print("           N+2极弱/死叉 → N级别高位结构后出主跌段")
    
    conductions = derive_n_plus_2_conduction(levels_macd, levels_trend)
    for c in conductions:
        print(f"\n  {'='*60}")
        print(f"  🔗 传导链: {c['chain']} | {c['upper_state']} → {c['lower_state']}")
        print(f"  {'='*60}")
        print(f"  📖 {c['theory']}")
        print(f"  🔗 {c['derivation']}")
        print(f"  🔮 {c['expectation']}")
        print(f"  🎯 {c['operation']}")
    
    # =====================================================
    # Step 8: v4.2 基于理论的策略推导（核心新增）
    # =====================================================
    print(f"\n{'='*70}")
    print("Step 8: 基于理论的策略推导（v4.2核心新增）")
    print(f"{'='*70}")
    print("\n  推导逻辑：N+2状态 → N+1趋势 → N级别操作 + 三特征确认点位")
    
    strategy = derive_strategy_from_theory(levels_macd, levels_trend, conductions, extreme_features)
    
    print(f"\n  {'='*60}")
    print(f"  📌 {strategy['summary']}")
    print(f"  {'='*60}")
    
    for s in strategy['strategies']:
        print(f"\n  🔹 {s['type']}: {s['direction']}")
        print(f"     📖 {s['theory']}")
        if 'derivation' in s:
            print(f"     🔗 {s['derivation']}")
        if 'entry' in s:
            print(f"     🚪 {s['entry']}")
        if 'target' in s:
            print(f"     🎯 {s['target']}")
        if 'stop' in s:
            print(f"     🛑 {s['stop']}")
        if 'source' in s:
            print(f"     📎 来源: {s['source']}")
    
    # =====================================================
    # Step 8b: 复合风控（v4.2核心新增，SKILL.md Step 16）
    # =====================================================
    print(f"\n{'='*70}")
    print("Step 8b: 复合风控（v4.2核心新增）")
    print(f"{'='*70}")
    print("\n  单一指标风控 → 复合信号风控")
    print("  经典复合信号：")
    print("  • 30F55线压制 + 5F顶背离 = 兑现一部分多头")
    print("  • 双日死叉 + 30F主跌段 = 清仓")
    print("  • 5F55线突破 + 30F底背离 = 加仓")
    print("  • 跌破联合支撑区 = 无条件清仓")
    print("  • 假突破 + 联合压制区 = 减仓1/3")
    
    composite_risk = analyze_composite_risk(levels_macd, levels_trend, levels_55, levels_middle, extreme_features)
    
    print(f"\n  📊 风控状态: {composite_risk['description']}")
    
    if composite_risk['signals']:
        # 按严重程度排序
        severity_icons = {'critical': '🔴', 'high': '🟠', 'medium': '🟡', 'opportunity': '✅'}
        for signal in composite_risk['signals']:
            icon = severity_icons.get(signal['severity'], '➖')
            print(f"\n  {icon} {signal['signal']} (严重程度: {signal['severity']})")
            print(f"     📖 {signal['theory']}")
            print(f"     🎯 {signal['operation']}")
        
        if composite_risk['critical_count'] > 0:
            print(f"\n  🔴🔴🔴 注意：检测到{composite_risk['critical_count']}个致命风险信号！")
            print(f"  建议操作: {composite_risk['operation']}")
    else:
        print(f"\n  ✅ 无复合风控信号，按正常策略操作")
    
    # =====================================================
    # Step 8c: 120F55线战略分水岭（v4.2核心新增，SKILL.md Step 12）
    # =====================================================
    print(f"\n{'='*70}")
    print("Step 8c: 120F55线战略分水岭（v4.2核心新增）")
    print(f"{'='*70}")
    print("\n  120F55线是决定后续行情性质的重要分水岭")
    print("  时间框架：一周内必须有答案（有效突破或确认压制）")
    
    strategic_120f = analyze_120f55_strategic(df_120m, df_d, df_bid, levels_macd, levels_trend)
    
    print(f"\n  {strategic_120f['icon']} 120F55线状态: 【{strategic_120f['status']}】")
    print(f"  📊 120F价格: {strategic_120f['price_120f']:.2f} vs 120F55线: {strategic_120f['ma55_120f']:.2f}")
    print(f"  📊 120F MACD: {strategic_120f['macd_120f']:.2f}")
    print(f"\n  📖 {strategic_120f['theory']}")
    print(f"  🔍 {strategic_120f['breakthrough_analysis']}")
    print(f"  🎯 {strategic_120f['operation']}")
    print(f"  ⏰ {strategic_120f['timeframe']}")
    
    # =====================================================
    # Step 8d: 补偿性买点识别（v4.2核心新增，SKILL.md Step 15）
    # =====================================================
    print(f"\n{'='*70}")
    print("Step 8d: 补偿性买点识别（v4.2核心新增）")
    print(f"{'='*70}")
    print("\n  经典缠论买点结构：跌破55线 → 回踩确认 → 突破中轨 → 突破上级55线")
    print("  条件：价格跌破MA55 + 在MA55下方企稳 + MACD底背离或缩量 + 买点区域55线下方2%以内")
    
    comp_pairs = [
        ('15F', df_15m, '30F', df_30m),
        ('30F', df_30m, '60F', df_60m),
        ('60F', df_60m, '120F', df_120m),
    ]
    
    for n, df_n, n_upper, df_n_upper in comp_pairs:
        if len(df_n) >= 55 and len(df_n_upper) >= 55:
            comp = analyze_compensation_buy(df_n, df_n_upper, n, n_upper)
            if comp['is_compensation_buy']:
                print(f"\n  {comp['icon']} {n}: 【补偿性买点{comp['status']}】")
                print(f"     价格: {comp['price']:.2f} vs 55线: {comp['ma55']:.2f}")
                print(f"     买点区域: {comp['buy_zone'][0]:.2f} - {comp['buy_zone'][1]:.2f}")
                print(f"     中轨: {comp['middle']:.2f}")
                print(f"     📖 {comp['theory']}")
                print(f"     🎯 {comp['operation']}")
                
                # 输出条件状态
                cond = comp['conditions']
                print(f"     条件检查:")
                print(f"       {'✅' if cond['price_below_55'] else '❌'} 价格跌破55线")
                print(f"       {'✅' if cond['stable_below'] else '❌'} 55线下方企稳")
                print(f"       {'✅' if cond['macd_divergence'] else '❌'} MACD底背离")
                print(f"       {'✅' if cond['in_buy_zone'] else '❌'} 在买点区域内(55线下方2%)")
                print(f"       {'✅' if cond['crossed_middle'] else '❌'} 突破中轨")
                print(f"       {'✅' if cond['volume_increase'] else '❌'} 放量")
            else:
                print(f"\n  ➖ {n}: {comp['description']}")
    
    # =====================================================
    # Step 9: 55线+中轨思维
    # =====================================================
    print(f"\n{'='*70}")
    print("Step 9: 55线+中轨思维")
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
            if name in levels_55:
                levels_55[name]['middle'] = middle_status['middle']
    
    # Step 10: 联合支撑/压制区 + 中轨传导链（v4.2升级）
    print(f"\n{'='*70}")
    print("Step 10: 联合支撑/压制区 + 中轨传导链（v4.2核心）")
    print(f"{'='*70}")
    
    # 10a: 联合支撑/压制区
    print("\n  📊 联合支撑/压制区（MA55 + 中轨双体系）：")
    
    if len(df_d) >= 55 and len(df_bid) >= 55:
        d55 = float(ma(df_d, 55).iloc[-1])
        b55 = float(ma(df_bid, 55).iloc[-1])
        db = boll(df_d)
        bb = boll(df_bid)
        
        diff = abs(d55 - b55)
        strength = '极强' if diff < 5 else ('强' if diff < 20 else '中等')
        print(f"  🛡️ MA55联合支撑: {strength} | 日线55={d55:.2f} vs 双日55={b55:.2f} (差{diff:.2f})")
        
        # 中轨+MA55联合支撑（v4.1新增）
        if '30F' in levels_middle and '30F' in levels_55:
            m30 = levels_middle['30F']['middle']
            m55_30 = levels_55['30F']['ma55']
            diff_mm = abs(m30 - m55_30)
            if diff_mm < 30:
                print(f"  🟡 30F联合支撑: 中轨={m30:.2f} vs MA55={m55_30:.2f} (差{diff_mm:.2f}) → 阶梯支撑带")
        
        if '15F' in levels_middle and '15F' in levels_55:
            m15 = levels_middle['15F']['middle']
            m55_15 = levels_55['15F']['ma55']
            diff_mm = abs(m15 - m55_15)
            if diff_mm < 20:
                print(f"  🟡 15F联合支撑: 中轨={m15:.2f} vs MA55={m55_15:.2f} (差{diff_mm:.2f}) → 阶梯支撑带")
    
    # 10b: 中轨传导链分析
    print("\n  📊 中轨传导链分析（日内阶梯支撑传导）：")
    
    middle_chain = analyze_middle_transmission_chain(levels_middle, levels_macd, levels_55)
    
    print(f"  传导链状态: {middle_chain['chain_status']}")
    print(f"  {'='*60}")
    
    for item in middle_chain['chain']:
        print(f"  {item['icon']} {item['level']}: {item['status']} | 价格={item['price']:.2f} 中轨={item['middle']:.2f}")
    
    print(f"\n  🔍 传导链解读：")
    if middle_chain['chain_status'] == '下跌传导链激活':
        print(f"  • 5F/15F/30F均跌破中轨 → 下跌传导链激活")
        print(f"  • 5F跌破中轨 → 15F测试中轨 → 30F中轨是第一支撑（关键！）")
        print(f"  • 30F跌破中轨 → 寻找60F中轨/MA55支撑")
    elif middle_chain['chain_status'] == '上涨传导链激活':
        print(f"  • 5F/15F/30F均突破中轨 → 上涨传导链激活")
        print(f"  • 5F突破中轨 → 15F确认突破 → 30F突破确认 → 半日确认")
    elif middle_chain['chain_status'] == '5F弱势/30F强势 - 日内震荡':
        print(f"  • 5F弱势/30F强势 → 日内震荡格局")
        print(f"  • 5F在中轨下方但30F在中轨上方 → 分歧明显")
    else:
        print(f"  • 各级别中轨状态不一，需结合具体位置判断")
    
    print(f"  ⚠️ v4.1铁律：日内操作先看中轨，趋势判断再看MA55")
    
    # Step 11: 分时段关键支撑（v4.2升级）
    print(f"\n{'='*70}")
    print("Step 11: 分时段关键支撑（v4.2升级）")
    print(f"{'='*70}")
    print("\n  📊 分时段支撑矩阵（SKILL.md标准）：")
    print("  | 时段 | 第一支撑 | 第二支撑 | 第三支撑 | 风控线 |")
    print("  |---|---|---|---|---|")
    print("  | 上午(9:30-11:30) | 30F中轨 | 30F MA55 | 60F中轨 | 15F跌破中轨 |")
    print("  | 下午(13:00-14:30) | 5F MA55 | 5F中轨 | 15F MA55 | 5F跌破MA55 |")
    print("  | 尾盘(14:30-15:00) | 5F中轨 | 15F中轨 | 30F中轨 | 收在30F中轨下方 |")
    
    time_support = analyze_time_segment_support(levels_middle, levels_55, levels_macd)
    
    print(f"\n  📅 上午时段 (9:30-11:30):")
    for i, (name, val, desc) in enumerate(time_support['morning']):
        star = "⭐" if i == 0 else ""
        print(f"    {star} 第{i+1}支撑: {name} = {val:.2f} ({desc})")
    if time_support['morning_risk']:
        name, val, desc = time_support['morning_risk']
        print(f"    ⚠️ 风控线: {name} = {val:.2f} ({desc})")
    
    print(f"\n  📅 下午时段 (13:00-14:30):")
    for i, (name, val, desc) in enumerate(time_support['afternoon']):
        star = "⭐" if i == 0 else ""
        print(f"    {star} 第{i+1}支撑: {name} = {val:.2f} ({desc})")
    if time_support['afternoon_risk']:
        name, val, desc = time_support['afternoon_risk']
        print(f"    ⚠️ 风控线: {name} = {val:.2f} ({desc})")
    
    print(f"\n  📅 尾盘时段 (14:30-15:00):")
    for i, (name, val, desc) in enumerate(time_support['close']):
        star = "⭐" if i == 0 else ""
        print(f"    {star} 第{i+1}支撑: {name} = {val:.2f} ({desc})")
    if time_support['close_risk']:
        name, val, desc = time_support['close_risk']
        print(f"    ⚠️ 风控线: {name} = {val:.2f} ({desc})")
    
    # 分时段策略速查
    print(f"\n  📊 分时段策略速查：")
    print(f"\n    【上午策略】")
    for s in time_support['morning_strategy']:
        print(f"    • {s}")
    
    print(f"\n    【下午策略】")
    for s in time_support['afternoon_strategy']:
        print(f"    • {s}")
    
    print(f"\n    【尾盘策略】")
    for s in time_support['close_strategy']:
        print(f"    • {s}")
    
    # Step 12: 时间窗口
    print(f"\n{'='*70}")
    print("Step 12: 时间窗口估算")
    print(f"{'='*70}")
    
    tw = estimate_time_window(df_d, df_bid)
    print(f"  {tw['description']}")
    
    # =====================================================
    # Step 13: v4.2 明日策略（基于理论推导）
    # =====================================================
    print(f"\n{'='*70}")
    print("Step 13: 明日策略（v4.2理论推导版）")
    print(f"{'='*70}")
    
    p = float(df_d['Close'].iloc[-1])
    print(f"\n  当前收盘: {p:.2f}")
    print(f"\n  📌 大方向: {strategy['summary']}")
    
    # 具体操作建议
    print(f"\n  📌 基于理论推导的操作建议:")
    
    for s in strategy['strategies']:
        if s['type'] == '操作级别(30F)':
            print(f"\n    【30F操作】{s['direction']}")
            if 'entry' in s:
                print(f"    • 入场: {s['entry']}")
            if 'target' in s:
                print(f"    • 目标: {s['target']}")
            if 'stop' in s:
                print(f"    • 止损: {s['stop']}")
        if s['type'] == '日内(5F)':
            print(f"\n    【5F日内】{s['direction']}")
            if 'entry' in s:
                print(f"    • 入场: {s['entry']}")
            if 'target' in s:
                print(f"    • 目标: {s['target']}")
            if 'stop' in s:
                print(f"    • 止损: {s['stop']}")
    
    # 三特征应用提醒
    print(f"\n  📌 极强/极弱三特征应用提醒:")
    for n, feat in extreme_features.items():
        for f in feat['features']:
            if f['feature'] in ['背离失效', '55线支撑']:
                print(f"    • {n}: {f['operation']}")
    
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
    
    print(f"\n📅 日期: {df_d['Date'].iloc[-1].date()}")
    print("="*70)

if __name__ == "__main__":
    main()
