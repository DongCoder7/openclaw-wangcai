"""
缠论多级别联立分析系统 v3.3
更新日期: 2026-05-28

v3.3 核心升级 (基于操作手册优化):
  1. 【联合支撑/压制区】多级别关键价位重叠识别
  2. 【假突破/骗炮识别】MACD验证真假突破
  3. 【二买/二卖结构】下跌段完成后回踩不创新低
  4. 【级别传导链】3F→双日的多米诺骨牌监控
  5. 【双日级别分析】大周期战略级别判断
  6. 【时间窗口】不是每天可操作，等待特定窗口
  7. 【数据完整性检查】每级别≥55根硬性要求
  8. 保留v3.1+: 55线思维 / 段数分析 / 补偿性买点 / 复合风控
                / MACD极强期 / 零轴金叉 / 级别重叠 / 目标价
"""

import pandas as pd
import numpy as np

# =====================================================
# 数据获取 & 级别合成
# =====================================================

def fetch_data(file_path):
    """读取CSV数据"""
    df = pd.read_csv(file_path)
    df['Date'] = pd.to_datetime(df['Date'])
    return df

def synthesize_kline(df_source, n, name=""):
    """K线级别合成"""
    df = df_source.copy()
    df['Group'] = df.index // n
    df_target = df.groupby('Group').agg({
        'Date': 'last', 'Open': 'first', 'High': 'max',
        'Low': 'min', 'Close': 'last', 'Volume': 'sum'
    }).reset_index(drop=True)
    return df_target

# =====================================================
# v3.3 新增: 数据完整性检查
# =====================================================

def check_data_integrity(df, level_name='未知'):
    """
    数据完整性检查 (v3.3核心)
    
    硬性规则:
    - 数据不足55根 → MA55计算失真, 不可用于决策!
    - 数据不足20根 → 布林带中轨/上轨/下轨失真!
    - 双日级别必须≥55根 → 否则无法判断双日趋势
    """
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
    """计算所有技术指标"""
    df = df.copy()
    # 布林带
    df['BOLL_MID'] = df['Close'].rolling(window=20, min_periods=1).mean()
    df['BOLL_STD'] = df['Close'].rolling(window=20, min_periods=1).std()
    df['BOLL_UP'] = df['BOLL_MID'] + df['BOLL_STD'] * 2
    df['BOLL_DOWN'] = df['BOLL_MID'] - df['BOLL_STD'] * 2
    # MACD
    ema_fast = df['Close'].ewm(span=12, adjust=False).mean()
    ema_slow = df['Close'].ewm(span=26, adjust=False).mean()
    df['MACD'] = ema_fast - ema_slow
    df['MACD_Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
    df['MACD_Hist'] = df['MACD'] - df['MACD_Signal']
    # 均线
    df['MA5'] = df['Close'].rolling(window=5, min_periods=1).mean()
    df['MA10'] = df['Close'].rolling(window=10, min_periods=1).mean()
    df['MA20'] = df['Close'].rolling(window=20, min_periods=1).mean()
    df['MA55'] = df['Close'].rolling(window=55, min_periods=1).mean()
    # 量能
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
# v3.3 新增: 假突破/骗炮识别
# =====================================================

def judge_fake_breakout(df_level, level_name='30F'):
    """
    假突破/骗炮识别 (v3.3核心)
    
    判断标准:
    - 站上55线 + MACD>0 + MACD柱放大 → 真突破 ✅
    - 站上55线 + MACD<0 或 MACD柱收敛 → 假突破 ⚠️ (骗炮)
    - 跌破55线 + MACD<0 + MACD柱放大 → 真跌破 ❌
    - 跌破55线 + MACD>0 或 MACD柱收敛 → 假跌破 ⚠️
    
    实战教训: 2026-05-26收盘站上30F55线(4134)但MACD=-0.70<0
    → 假突破/骗炮! → 次日(05-27)开盘直接跌破, 全天大跌
    """
    if len(df_level) < 3:
        return {'usable': False, 'description': '数据不足'}
    
    latest = df_level.iloc[-1]
    prev = df_level.iloc[-2]
    price = latest['Close']
    ma55 = latest['MA55']
    macd = latest['MACD']
    hist = latest['MACD_Hist']
    
    # 检查MACD柱趋势
    recent_hist = df_level['MACD_Hist'].tail(3).values
    is_expanding = len(recent_hist) >= 3 and all(
        abs(recent_hist[i]) >= abs(recent_hist[i-1]) 
        for i in range(1, len(recent_hist))
    )
    is_contracting = len(recent_hist) >= 3 and all(
        abs(recent_hist[i]) <= abs(recent_hist[i-1]) 
        for i in range(1, len(recent_hist))
    )
    
    prev_price = prev['Close']
    
    # 站上55线情况
    if prev_price < ma55 and price > ma55:
        if macd > 0 and is_expanding:
            return {
                'type': '真突破',
                'is_fake': False,
                'description': f'{level_name}真突破: 站上55线+MACD>0+柱放大 ✅',
                'action': '追涨，止损55线下方1%'
            }
        else:
            return {
                'type': '假突破(骗炮)',
                'is_fake': True,
                'description': f'{level_name}假突破⚠️: 站上55线但MACD<0或柱收敛',
                'action': '不追涨，等待回踩确认或回落'
            }
    
    # 跌破55线情况
    if prev_price > ma55 and price < ma55:
        if macd < 0 and is_expanding:
            return {
                'type': '真跌破',
                'is_fake': False,
                'description': f'{level_name}真跌破❌: 跌破55线+MACD<0+柱放大',
                'action': '止损，等待补偿性买点'
            }
        else:
            return {
                'type': '假跌破',
                'is_fake': True,
                'description': f'{level_name}假跌破⚠️: 跌破55线但MACD>0或柱收敛',
                'action': '不恐慌，等待反弹确认'
            }
    
    # 55线上方运行
    if price > ma55:
        if macd > 0:
            return {'type': '55线上方运行', 'is_fake': False, 'description': f'{level_name}55线上方+MACD>0 主涨段 ✅', 'action': '持仓'}
        else:
            return {'type': 'X段', 'is_fake': False, 'description': f'{level_name}55线上方+MACD<0 X段 ⚠️', 'action': '警惕回落'}
    
    # 55线下方运行
    if price < ma55:
        if macd < 0:
            return {'type': '55线下方运行', 'is_fake': False, 'description': f'{level_name}55线下方+MACD<0 主跌段 ❌', 'action': '清仓/观望'}
        else:
            return {'type': 'X段', 'is_fake': False, 'description': f'{level_name}55线下方+MACD>0 X段 ⚠️', 'action': '关注补偿性买点'}
    
    return {'type': '胶着', 'is_fake': False, 'description': f'{level_name}55线附近胶着', 'action': '观望'}

# =====================================================
# v3.3 新增: 二买/二卖结构识别
# =====================================================

def identify_second_buy(strokes, level_name='30F'):
    """
    二买/二卖结构识别 (v3.3核心)
    
    二买判断:
    - 下跌段已完成 (3笔结构完整)
    - 第1笔up: 从低点反弹 (一买后的反弹)
    - 第2笔down: 回踩, 不创新低 (>一买低点)
    - 第3笔up: 确认二买成立
    
    实战: 2026-05-27 30F第1笔down(4153→4104)+第2笔up(4104→4133)+第3笔down(4133→4077)
    → 第3笔down低点4077 < 第1笔down低点4104 → 二买失败! ❌
    """
    if len(strokes) < 3:
        return {'usable': False, 'description': '笔数不足，无法判断二买/二卖'}
    
    # 取最近3笔判断
    last_3 = strokes[-3:]
    directions = [s['direction'] for s in last_3]
    
    # 二买结构: down-up-down (下跌段后的回踩)
    if directions == ['down', 'up', 'down']:
        first_down_low = min(last_3[0]['start_price'], last_3[0]['end_price'])
        second_down_low = min(last_3[2]['start_price'], last_3[2]['end_price'])
        
        if second_down_low > first_down_low:
            return {
                'type': '二买成立',
                'is_valid': True,
                'description': f'{level_name}二买成立 ✅: 第2笔down未创新低({second_down_low:.2f} > {first_down_low:.2f})',
                'action': '加仓，止损一买低点下方1%'
            }
        else:
            return {
                'type': '二买失败',
                'is_valid': False,
                'description': f'{level_name}二买失败 ❌: 第2笔down创新低({second_down_low:.2f} < {first_down_low:.2f})',
                'action': '减仓，等待新的买点'
            }
    
    # 二卖结构: up-down-up (上涨段后的反弹)
    if directions == ['up', 'down', 'up']:
        first_up_high = max(last_3[0]['start_price'], last_3[0]['end_price'])
        second_up_high = max(last_3[2]['start_price'], last_3[2]['end_price'])
        
        if second_up_high < first_up_high:
            return {
                'type': '二卖成立',
                'is_valid': True,
                'description': f'{level_name}二卖成立 ❌: 第2笔up未创新高({second_up_high:.2f} < {first_up_high:.2f})',
                'action': '减仓'
            }
        else:
            return {
                'type': '二卖失败',
                'is_valid': False,
                'description': f'{level_name}二卖失败 ✅: 第2笔up创新高({second_up_high:.2f} > {first_up_high:.2f})',
                'action': '持仓'
            }
    
    return {'type': '非二买二卖结构', 'is_valid': False, 'description': f'{level_name}最近3笔为{"-".join(directions)}，不构成二买/二卖', 'action': '观望'}

# =====================================================
# v3.3 新增: 联合支撑/联合压制区
# =====================================================

def analyze_unified_zone(level_data_dict):
    """
    联合支撑/联合压制区识别 (v3.3核心)
    
    跨级别关键价位重叠或接近(<10点)形成联合区
    - 日线55线 + 双日55线 → 联合支撑区
    - 60F55线 + 日线中轨 → 联合压制区
    """
    zones = []
    
    # 定义要检查的联合对
    pairs = [
        ('日线55线', 'MA55', '双日55线', 'MA55'),
        ('60F55线', 'MA55', '日线中轨', 'BOLL_MID'),
        ('30F55线', 'MA55', '60F中轨', 'BOLL_MID'),
        ('日线中轨', 'BOLL_MID', '双日中轨', 'BOLL_MID'),
    ]
    
    for name1, key1, name2, key2 in pairs:
        parts1 = name1.split('55线')[0] if '55线' in name1 else name1.replace('中轨','').replace('线','')
        parts2 = name2.split('55线')[0] if '55线' in name2 else name2.replace('中轨','').replace('线','')
        
        # 在level_data_dict中查找对应级别
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
                    
                    # 判断联合强度
                    if diff < 5:
                        strength = '极强联合'
                    elif diff < 10:
                        strength = '强联合'
                    elif diff < 20:
                        strength = '中等联合'
                    else:
                        strength = None
                    
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
    
    return {
        'unified_zones': zones,
        'count': len(zones),
        'has_strong_zone': any(z['strength'] in ['极强联合', '强联合'] for z in zones)
    }

# =====================================================
# v3.3 新增: 级别传导链
# =====================================================

def analyze_transmission_chain(level_data_dict):
    """
    级别传导链监控 (v3.3核心)
    
    多米诺骨牌效应:
    小级别恶化 → 中级别恶化 → 大级别恶化
    小级别修复 → 中级别修复 → 大级别修复
    """
    chain = {
        'steps': [],
        'direction': 'neutral',
        'risk_level': 'low',
        'description': ''
    }
    
    # 从3F开始检查传导
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
        macd_status = 'positive' if macd > 0 else 'negative'
        
        # 判断是否有传导
        if prev_status is not None:
            if prev_status == 'below' and status == 'below':
                chain['steps'].append({
                    'level': lvl_name,
                    'status': f'{status}+macd_{macd_status}',
                    'transmission': True,
                    'direction': 'down'
                })
            elif prev_status == 'above' and status == 'above':
                chain['steps'].append({
                    'level': lvl_name,
                    'status': f'{status}+macd_{macd_status}',
                    'transmission': True,
                    'direction': 'up'
                })
            else:
                chain['steps'].append({
                    'level': lvl_name,
                    'status': f'{status}+macd_{macd_status}',
                    'transmission': False,
                    'direction': 'mixed'
                })
        else:
            chain['steps'].append({
                'level': lvl_name,
                'status': f'{status}+macd_{macd_status}',
                'transmission': False,
                'direction': 'start'
            })
        
        prev_status = status
    
    # 判断整体传导方向
    down_steps = sum(1 for s in chain['steps'] if s.get('direction') == 'down')
    up_steps = sum(1 for s in chain['steps'] if s.get('direction') == 'up')
    
    if down_steps >= 3:
        chain['direction'] = 'down'
        chain['risk_level'] = 'high'
        chain['description'] = f'下跌传导链启动({down_steps}步共振) → 跟随减仓'
    elif up_steps >= 3:
        chain['direction'] = 'up'
        chain['risk_level'] = 'low'
        chain['description'] = f'上涨传导链启动({up_steps}步共振) → 跟随加仓'
    else:
        chain['description'] = '传导链未形成明确方向，震荡观望'
    
    return chain

# =====================================================
# v3.3 新增: 双日级别分析
# =====================================================

def analyze_dual_day(df_dual_day):
    """
    双日级别分析 (v3.3核心)
    
    双日级别 = 战略级别, 日线 = 战术级别
    - 双日MACD>0+Hist>0 → 中长期多头
    - 双日MACD接近死叉 → 警惕
    - 双日MACD死叉 → 中长期转空, 清仓
    """
    if df_dual_day is None or len(df_dual_day) < 3:
        return {'usable': False, 'description': '双日数据不足'}
    
    latest = df_dual_day.iloc[-1]
    prev = df_dual_day.iloc[-2] if len(df_dual_day) > 1 else latest
    
    macd = latest.get('MACD', 0)
    signal = latest.get('MACD_Signal', 0)
    hist = latest.get('MACD_Hist', 0)
    price = latest['Close']
    ma55 = latest.get('MA55', price)
    
    prev_hist = prev.get('MACD_Hist', 0)
    
    # 判断死叉风险
    death_cross_risk = hist > 0 and hist < 0.5 and macd > signal
    is_death_cross = hist < 0 and macd < signal
    
    # 判断金叉
    is_golden_cross = prev.get('MACD', 0) < 0 and macd > 0
    
    status = '多头' if macd > 0 else '空头'
    
    if is_golden_cross:
        return {
            'status': status,
            'trend': 'golden_cross',
            'description': '双日MACD零轴金叉 ✅ 中长期趋势转多',
            'action': '持仓/加仓',
            'death_risk': False,
            'hist': hist
        }
    elif is_death_cross:
        return {
            'status': status,
            'trend': 'death_cross',
            'description': '双日MACD死叉 ❌ 中长期趋势转空',
            'action': '清仓，需3-5天修复',
            'death_risk': True,
            'hist': hist
        }
    elif death_cross_risk:
        return {
            'status': status,
            'trend': 'death_risk',
            'description': f'双日MACD接近死叉 ⚠️ Hist={hist:.2f}，明日可能死叉',
            'action': '警惕，减仓',
            'death_risk': True,
            'hist': hist
        }
    elif macd > 0 and hist > 0:
        return {
            'status': status,
            'trend': 'bull',
            'description': f'双日MACD多头运行 ✅ Hist={hist:.2f}',
            'action': '持仓',
            'death_risk': False,
            'hist': hist
        }
    else:
        return {
            'status': status,
            'trend': 'bear',
            'description': f'双日MACD空头运行 ❌ Hist={hist:.2f}',
            'action': '观望/清仓',
            'death_risk': False,
            'hist': hist
        }

# =====================================================
# v3.3 新增: 时间窗口判断
# =====================================================

def judge_time_window(dual_day_status, transmission_chain):
    """
    时间窗口判断 (v3.3核心)
    
    不是每天都可以操作，需要等待特定时间窗口。
    时间窗口由大级别结构决定:
    - 双日MACD接近死叉 → 需要3-5天修复
    - 双日MACD死叉形成 → 等待金叉时间窗口
    - 传导链下跌完成 → 等待底背离+突破中轨
    
    实战: "双日死叉明天形成的话，要等到下周一才能度过了"
         "在周五下午/周一上午，看到底背离+突破中轨后，可以尝试做多"
    """
    window = {
        'is_window_open': False,
        'window_type': None,
        'description': '',
        'conditions': [],
        'action': '观望，不操作'
    }
    
    # 情况1: 双日死叉刚形成 → 等待修复
    if dual_day_status.get('trend') == 'death_cross':
        window['description'] = '双日MACD死叉形成，需等待3-5天修复，时间窗口未到'
        window['conditions'] = ['等待双日MACD金叉', '等待底背离+突破中轨']
        return window
    
    # 情况2: 双日接近死叉 → 暂时观望
    if dual_day_status.get('death_risk') and dual_day_status.get('hist', 1) > 0:
        window['description'] = '双日MACD接近死叉，修复需3-5天，暂不操作'
        window['conditions'] = ['观察明日是否死叉', '等待传导链逆转信号']
        return window
    
    # 情况3: 下跌传导链完成 + 底背离 → 时间窗口到来
    if transmission_chain.get('direction') == 'down' and len(transmission_chain.get('steps', [])) >= 4:
        window['is_window_open'] = True
        window['window_type'] = '下跌后反弹窗口'
        window['description'] = '下跌传导链已完成多步，等待底背离+突破中轨的时间窗口'
        window['conditions'] = ['底背离出现', '突破中轨确认', '放量阳线']
        window['action'] = '轻仓试多，止损联合支撑下沿'
        return window
    
    # 情况4: 双日金叉运行 → 正常操作窗口
    if dual_day_status.get('trend') == 'golden_cross':
        window['is_window_open'] = True
        window['window_type'] = '正常操作窗口'
        window['description'] = '双日MACD金叉运行，时间窗口开放'
        window['conditions'] = ['按55线思维正常操作']
        window['action'] = '正常买卖操作'
        return window
    
    # 情况5: 上涨传导链 → 持仓窗口
    if transmission_chain.get('direction') == 'up':
        window['is_window_open'] = True
        window['window_type'] = '上涨持仓窗口'
        window['description'] = '上涨传导链启动，时间窗口开放'
        window['conditions'] = ['顺势持仓', '遇联合压制减仓']
        window['action'] = '持仓/突破联合压制加仓'
        return window
    
    window['description'] = '无明确时间窗口，继续观望等待'
    return window

# =====================================================
# v3.1+ 核心: MACD极强期判断
# =====================================================

def judge_macd_extreme(df_level, level_name='30F'):
    """MACD极强期判断"""
    latest = df_level.iloc[-1]
    macd = latest['MACD']
    signal = latest['MACD_Signal']
    hist = latest['MACD_Hist']
    
    recent_hist = df_level['MACD_Hist'].tail(3).values
    is_expanding = len(recent_hist) >= 3 and all(
        abs(recent_hist[i]) >= abs(recent_hist[i-1]) 
        for i in range(1, len(recent_hist))
    )
    
    is_up_extreme = macd > 0 and signal > 0 and is_expanding
    is_down_extreme = macd < 0 and signal < 0 and is_expanding
    
    if is_up_extreme:
        strength = abs(hist) / abs(macd) * 100 if macd != 0 else 0
        return {
            'is_extreme': True,
            'direction': 'extreme_up',
            'strength': min(strength, 100),
            'description': f'{level_name} MACD极强形态(多头)，柱状体持续放大'
        }
    elif is_down_extreme:
        strength = abs(hist) / abs(macd) * 100 if macd != 0 else 0
        return {
            'is_extreme': True,
            'direction': 'extreme_down',
            'strength': min(strength, 100),
            'description': f'{level_name} MACD极强形态(空头)，柱状体持续放大'
        }
    
    return {
        'is_extreme': False,
        'direction': 'normal',
        'strength': 0,
        'description': f'{level_name} MACD正常状态'
    }

# =====================================================
# v3.1+ 核心: 零轴金叉/死叉判断
# =====================================================

def judge_zero_axis_cross(df_level, level_name='120F'):
    """零轴金叉/死叉判断"""
    if len(df_level) < 3:
        return {'cross_type': 'none', 'description': '数据不足'}
    
    latest = df_level.iloc[-1]
    prev = df_level.iloc[-2]
    
    macd_latest = latest['MACD']
    macd_prev = prev['MACD']
    
    if macd_prev < 0 and macd_latest > 0:
        return {
            'cross_type': 'golden',
            'cross_position': 'zero_axis',
            'description': f'{level_name} MACD零轴金叉，中期趋势转折向上',
            'importance': 'high'
        }
    
    if macd_prev > 0 and macd_latest < 0:
        return {
            'cross_type': 'death',
            'cross_position': 'zero_axis',
            'description': f'{level_name} MACD零轴死叉，中期趋势转折向下',
            'importance': 'high'
        }
    
    macd_range = df_level['MACD'].max() - df_level['MACD'].min()
    zero_threshold = abs(macd_range) * 0.05
    if abs(macd_latest) < zero_threshold:
        return {
            'cross_type': 'near_zero',
            'cross_position': 'zero_axis',
            'description': f'{level_name} MACD在零轴附近，关注方向选择',
            'importance': 'medium'
        }
    
    return {
        'cross_type': 'none',
        'cross_position': 'away_zero',
        'description': f'{level_name} MACD远离零轴，趋势延续',
        'importance': 'low'
    }

# =====================================================
# v3.1+ 核心: 级别重叠分析
# =====================================================

def analyze_level_overlap(df_lower, df_upper, lower_name='5F', upper_name='30F'):
    """级别重叠分析"""
    lower_latest = df_lower.iloc[-1]
    upper_latest = df_upper.iloc[-1]
    
    lower_55 = lower_latest['MA55']
    upper_mid = upper_latest['BOLL_MID']
    
    deviation = abs(lower_55 - upper_mid) / upper_mid * 100
    is_overlap = deviation < 0.5
    
    if is_overlap:
        overlap_zone = (min(lower_55, upper_mid) * 0.995, max(lower_55, upper_mid) * 1.005)
        return {
            'is_overlap': True,
            'overlap_zone': overlap_zone,
            'strength': 1 - deviation / 0.5,
            'description': f'{lower_name}55线({lower_55:.2f})与{upper_name}中轨({upper_mid:.2f})重叠，强支撑/压力区域'
        }
    
    return {
        'is_overlap': False,
        'overlap_zone': None,
        'strength': 0,
        'description': f'{lower_name}55线与{upper_name}中轨无重叠(偏离{deviation:.2f}%)'
    }

# =====================================================
# v3.1+ 核心: 目标价推导
# =====================================================

def derive_target_price(df_level, level_name='30F'):
    """目标价推导"""
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
    
    nearest_support = max([s for s in supports if s < price], default=price * 0.95)
    nearest_resistance = min([r for r in resistances if r > price], default=price * 1.05)
    
    return {
        'target_high': recent_high,
        'target_fib': fib_618,
        'target_equal': equal_measure,
        'nearest_support': nearest_support,
        'nearest_resistance': nearest_resistance,
        'description': f'{level_name}级别目标: 前高{recent_high:.2f}/斐波那契{fib_618:.2f}/等距{equal_measure:.2f}'
    }

# =====================================================
# v3.1 核心: 段数分析
# =====================================================

def analyze_segment_count(df, lookback=50):
    """段数分析"""
    df_check = df.tail(lookback)
    strokes = find_strokes(df_check)
    
    if len(strokes) == 0:
        return {'total_strokes': 0, 'completed_segments': 0, 'current_segment_strokes': 0,
                'current_segment_status': '无笔', 'is_complete': False, 'trend': 'unclear', 'strokes': []}
    
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
        'strokes': strokes  # v3.3: 返回strokes供二买分析
    }

# =====================================================
# v3.1 核心: 55线思维分水岭判断
# =====================================================

def judge_55line_status(level_name, df_level):
    """55线作为牛熊分水岭"""
    latest = df_level.iloc[-1]
    price = latest['Close']
    ma55 = latest['MA55']
    mid = latest['BOLL_MID']
    macd = latest['MACD']

    status_55 = '55线上方' if price > ma55 else '55线下方'

    prev = df_level.iloc[-2] if len(df_level) > 1 else latest
    prev_price = prev['Close']

    if prev_price < ma55 and price > ma55:
        key_signal = '突破55线 ✅'
    elif prev_price > ma55 and price < ma55:
        key_signal = '跌破55线 ❌'
    elif price > ma55 * 0.995 and price < ma55 * 1.005:
        key_signal = '55线胶着 ⚠️'
    elif price > ma55:
        key_signal = '55线上方运行 ✅'
    else:
        key_signal = '55线下方运行 ❌'

    if price > ma55 and macd > 0:
        structure = '主涨段(55线思维) ✅'
    elif price < ma55 and macd < 0:
        structure = '主跌段(55线思维) ❌'
    else:
        structure = 'X段(55线思维) ⚠️'

    return {
        'level': level_name,
        'price': price,
        'ma55': ma55,
        'mid': mid,
        'status_55': status_55,
        'key_signal': key_signal,
        'structure': structure,
        'macd': macd
    }

# =====================================================
# v3.1 核心: 补偿性买点识别
# =====================================================

def identify_compensation_buy(df_level, level_name='5F'):
    """识别补偿性买点"""
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
        return {
            'is_compensation_zone': True,
            'zone': (ma55 * 0.98, ma55),
            'confirmation': '底背离' if is_bottom_div else '缩量',
            'target': mid,
            'action': f'在{level_name}55线({ma55:.0f})下方低吸, 突破{level_name}中轨({mid:.0f})确认, 目标上级55线'
        }

    return {'is_compensation_zone': False}

# =====================================================
# v3.1 核心: 复合风控信号
# =====================================================

def check_composite_risk(df_upper, df_lower):
    """复合风控信号"""
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
        risk_level = 'high'
        action = '兑现一部分多头 (减仓1/3-1/2)'
    elif risk_score >= 40:
        risk_level = 'medium'
        action = '警惕, 减仓1/3'
    elif risk_score >= 20:
        risk_level = 'low'
        action = '观察, 不操作'
    else:
        risk_level = 'none'
        action = '持仓'

    return {
        'risk_level': risk_level,
        'risk_score': risk_score,
        'signals': signals,
        'action': action
    }

# =====================================================
# v3.3 主分析器
# =====================================================

class ChanAnalysisV33:
    """缠论分析器 v3.3"""

    def __init__(self, df_1m=None, df_5m=None, df_30m=None, df_daily=None):
        self.df_1m = df_1m.copy() if df_1m is not None else None
        self.df_5m = df_5m.copy() if df_5m is not None else None
        self.df_30m_raw = df_30m.copy() if df_30m is not None else None
        self.df_daily = df_daily.copy() if df_daily is not None else None
        self._prepare()

    def _prepare(self):
        # 合成级别
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
        """获取所有级别DataFrame字典"""
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

    # ---------- v3.3 新增方法 ----------

    def get_data_integrity(self):
        """数据完整性检查"""
        result = {}
        for name, df in self._get_level_dict().items():
            result[name] = check_data_integrity(df, name)
        return result

    def get_fake_breakout(self):
        """假突破/骗炮识别"""
        result = {}
        for name, df in self._get_level_dict().items():
            if len(df) >= 3:
                result[name] = judge_fake_breakout(df, name)
        return result

    def get_second_buy(self):
        """二买/二卖结构识别"""
        result = {}
        for name, df in self._get_level_dict().items():
            if len(df) >= 50:
                seg = analyze_segment_count(df, lookback=50)
                if seg.get('strokes'):
                    result[name] = identify_second_buy(seg['strokes'], name)
        return result

    def get_unified_zone(self):
        """联合支撑/联合压制区"""
        return analyze_unified_zone(self._get_level_dict())

    def get_transmission_chain(self):
        """级别传导链"""
        return analyze_transmission_chain(self._get_level_dict())

    def get_dual_day(self):
        """双日级别分析"""
        if hasattr(self, 'df_biday') and self.df_biday is not None:
            return analyze_dual_day(self.df_biday)
        return {'usable': False, 'description': '无双日数据'}

    def get_time_window(self):
        """时间窗口判断"""
        dual_day = self.get_dual_day()
        chain = self.get_transmission_chain()
        return judge_time_window(dual_day, chain)

    # ---------- v3.1+ 保留方法 ----------

    def get_55line_analysis(self):
        """55线思维分析"""
        result = {}
        for name, df in self._get_level_dict().items():
            result[name] = judge_55line_status(name, df)
        return result

    def get_macd_extreme(self):
        """MACD极强期判断"""
        result = {}
        for name, df in self._get_level_dict().items():
            if len(df) >= 3:
                result[name] = judge_macd_extreme(df, name)
        return result

    def get_zero_axis_cross(self):
        """零轴金叉/死叉判断"""
        result = {}
        for name, df in self._get_level_dict().items():
            if len(df) >= 3:
                result[name] = judge_zero_axis_cross(df, name)
        return result

    def get_level_overlap(self):
        """级别重叠分析"""
        result = {}
        pairs = [
            ('1F', '5F', getattr(self, 'df_1f', None), getattr(self, 'df_3m', None)),
            ('5F', '30F', getattr(self, 'df_3m', None), getattr(self, 'df_30m', None))
        ]
        for lower_name, upper_name, df_lower, df_upper in pairs:
            if df_lower is not None and df_upper is not None:
                result[f'{lower_name}_{upper_name}'] = analyze_level_overlap(df_lower, df_upper, lower_name, upper_name)
        return result

    def get_target_price(self):
        """目标价推导"""
        result = {}
        for name, df in [
            ('30F', getattr(self, 'df_30m', None)),
            ('120F', getattr(self, 'df_120f', None)),
            ('日线', self.df_daily)
        ]:
            if df is not None:
                result[name] = derive_target_price(df, name)
        return result

    def get_segment_analysis(self):
        """段数分析"""
        result = {}
        for name, df in [
            ('1F', getattr(self, 'df_1f', None)),
            ('5F', getattr(self, 'df_3m', None)),
            ('30F', getattr(self, 'df_30m', None)),
            ('60F', getattr(self, 'df_60m', None)),
            ('日线', self.df_daily)
        ]:
            if df is not None:
                result[name] = analyze_segment_count(df, lookback=50)
        return result

    def get_compensation_buy(self):
        """补偿性买点"""
        result = {}
        if hasattr(self, 'df_3m') and self.df_3m is not None:
            result['5F'] = identify_compensation_buy(self.df_3m, '5F')
        if hasattr(self, 'df_30m') and self.df_30m is not None:
            result['30F'] = identify_compensation_buy(self.df_30m, '30F')
        return result

    def get_composite_risk(self):
        """复合风控"""
        risks = {}
        if self.df_daily is not None and hasattr(self, 'df_30m') and self.df_30m is not None:
            risks['日线vs30F'] = check_composite_risk(self.df_daily, self.df_30m)
        if hasattr(self, 'df_30m') and self.df_30m is not None and hasattr(self, 'df_3m') and self.df_3m is not None:
            risks['30Fvs5F'] = check_composite_risk(self.df_30m, self.df_3m)
        return risks

    # ---------- 报告生成 ----------

    def generate_report(self):
        """生成完整分析报告（v3.3）"""
        report = {
            'data_integrity': self.get_data_integrity(),       # v3.3: 数据完整性
            '55line_analysis': self.get_55line_analysis(),       # 55线状态
            'fake_breakout': self.get_fake_breakout(),           # v3.3: 假突破/骗炮
            'unified_zone': self.get_unified_zone(),             # v3.3: 联合支撑/压制区
            'second_buy': self.get_second_buy(),                 # v3.3: 二买/二卖
            'segment_analysis': self.get_segment_analysis(),       # 段数统计
            'transmission_chain': self.get_transmission_chain(),  # v3.3: 传导链
            'dual_day': self.get_dual_day(),                     # v3.3: 双日级别
            'time_window': self.get_time_window(),                 # v3.3: 时间窗口
            'compensation_buy': self.get_compensation_buy(),     # 补偿性买点
            'composite_risk': self.get_composite_risk(),         # 复合风控
            'macd_extreme': self.get_macd_extreme(),             # MACD极强期
            'zero_axis_cross': self.get_zero_axis_cross(),       # 零轴金叉/死叉
            'level_overlap': self.get_level_overlap(),           # 级别重叠
            'target_price': self.get_target_price()              # 目标价推导
        }
        return report


# =====================================================
# 主程序
# =====================================================

def main():
    print("="*60)
    print("缠论分析系统 v3.3 - 联合区/假突破/二买/传导链/双日/时间窗口")
    print("="*60)

    try:
        df_1m = fetch_data("/mnt/kimi/output/sh_1min.csv")
        df_5m = fetch_data("/mnt/kimi/output/sh_5min_full.csv")
        df_daily = fetch_data("/mnt/kimi/output/sh_1day.csv")

        analyzer = ChanAnalysisV33(df_1m=df_1m, df_5m=df_5m, df_daily=df_daily)
        report = analyzer.generate_report()

        print("\n【数据完整性检查】")
        for level, data in report['data_integrity'].items():
            status = "✅" if data['usable'] else "❌"
            print(f"  {status} {level}: {data['total_rows']}根 {data.get('warning', '')}")

        print("\n【假突破/骗炮识别】")
        for level, data in report['fake_breakout'].items():
            icon = "⚠️" if data.get('is_fake') else ("✅" if "真突破" in data.get('type','') else ("❌" if "真跌破" in data.get('type','') else ""))
            print(f"  {icon} {level}: {data['type']} - {data['action']}")

        print("\n【联合支撑/联合压制区】")
        uz = report['unified_zone']
        if uz['count'] > 0:
            for z in uz['unified_zones']:
                print(f"  {z['strength']}: {z['description']}")
        else:
            print("  无强联合区")

        print("\n【二买/二卖结构】")
        for level, data in report['second_buy'].items():
            icon = "✅" if data.get('is_valid') else ("❌" if "失败" in data.get('type','') else "⏳")
            print(f"  {icon} {level}: {data.get('type','')} - {data.get('action','')}")

        print("\n【级别传导链】")
        tc = report['transmission_chain']
        print(f"  方向: {tc['direction']} 风险: {tc['risk_level']}")
        print(f"  {tc['description']}")
        for step in tc['steps'][:6]:
            print(f"    {step['level']}: {step['status']} {'→' if step.get('transmission') else '·'}")

        print("\n【双日级别分析】")
        dd = report['dual_day']
        if dd.get('usable', True):
            icon = "❌" if dd.get('death_risk') else ("✅" if dd.get('trend') == 'bull' else "⚠️")
            print(f"  {icon} {dd['description']}")
            print(f"     操作: {dd['action']}")

        print("\n【时间窗口】")
        tw = report['time_window']
        icon = "✅" if tw['is_window_open'] else "⛔"
        print(f"  {icon} {tw['description']}")
        print(f"     操作: {tw['action']}")
        if tw['conditions']:
            print(f"     条件: {'; '.join(tw['conditions'])}")

        print("\n【55线思维分析】")
        for level, data in report['55line_analysis'].items():
            print(f"\n  {level}: 价格{data['price']:.2f} 55线{data['ma55']:.2f} {data['key_signal']}")
            print(f"     结构: {data['structure']}")

        print("\n【MACD极强期】")
        for level, data in report['macd_extreme'].items():
            if data['is_extreme']:
                print(f"  🔥 {level}: {data['description']} 强度{data['strength']:.0f}%")

        print("\n【复合风控】")
        for pair, risk in report['composite_risk'].items():
            print(f"  {pair}: {risk['risk_level'].upper()} (得分{risk['risk_score']}) → {risk['action']}")

    except Exception as e:
        print(f"\n分析出错: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
