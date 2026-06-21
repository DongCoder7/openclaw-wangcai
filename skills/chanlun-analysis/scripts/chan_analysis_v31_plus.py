"""
缠论多级别联立分析系统 v3.1+
更新日期: 2026-05-25

v3.1+ 核心升级 (基于实际分析对比优化):
  1. 【1F精确级别】支持1分钟数据，实现1F/5F/30F/120F四级别精确联立
  2. 【120F中期趋势】日线×5 = 120F级别，零轴金叉/死叉判断
  3. 【MACD极强期】MACD柱状体连续放大 + DIF/DEA同向 = 极强/极弱形态
  4. 【零轴金叉】MACD在零轴附近金叉，中期趋势转折信号
  5. 【级别重叠】小级别55线与大级别中轨重叠 = 强支撑/压力区域
  6. 【目标价推导】前高/中枢上轨/等距测量推导目标价
  7. 保留v3.1: 55线思维 / 段数分析 / 补偿性买点 / 复合风控
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
# v3.1+ 核心新增: MACD极强期判断
# =====================================================

def judge_macd_extreme(df_level, level_name='30F'):
    """
    MACD极强期判断
    
    极强形态:
    - MACD柱状体连续3根放大
    - DIF > 0 且 DEA > 0（多头极强）
    - 或 DIF < 0 且 DEA < 0（空头极强）
    
    返回:
        {
            'is_extreme': 是否极强形态,
            'direction': 'extreme_up'/'extreme_down'/'normal',
            'strength': 强度评分,
            'description': 描述
        }
    """
    latest = df_level.iloc[-1]
    macd = latest['MACD']
    signal = latest['MACD_Signal']
    hist = latest['MACD_Hist']
    
    # 检查最近3根MACD柱状体趋势
    recent_hist = df_level['MACD_Hist'].tail(3).values
    is_expanding = len(recent_hist) >= 3 and all(
        abs(recent_hist[i]) >= abs(recent_hist[i-1]) 
        for i in range(1, len(recent_hist))
    )
    
    # 判断方向
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
# v3.1+ 核心新增: 零轴金叉/死叉判断
# =====================================================

def judge_zero_axis_cross(df_level, level_name='120F'):
    """
    零轴金叉/死叉判断
    
    金叉: MACD从负值上穿零轴 → 中期趋势转折向上
    死叉: MACD从正值下穿零轴 → 中期趋势转折向下
    
    返回:
        {
            'cross_type': 'golden'/'death'/'none',
            'cross_position': 'zero_axis',
            'description': 描述,
            'importance': 重要性
        }
    """
    if len(df_level) < 3:
        return {'cross_type': 'none', 'description': '数据不足'}
    
    latest = df_level.iloc[-1]
    prev = df_level.iloc[-2]
    prev2 = df_level.iloc[-3]
    
    macd_latest = latest['MACD']
    macd_prev = prev['MACD']
    
    # 金叉: 前一根<0，当前>0
    if macd_prev < 0 and macd_latest > 0:
        return {
            'cross_type': 'golden',
            'cross_position': 'zero_axis',
            'description': f'{level_name} MACD零轴金叉，中期趋势转折向上',
            'importance': 'high'
        }
    
    # 死叉: 前一根>0，当前<0
    if macd_prev > 0 and macd_latest < 0:
        return {
            'cross_type': 'death',
            'cross_position': 'zero_axis',
            'description': f'{level_name} MACD零轴死叉，中期趋势转折向下',
            'importance': 'high'
        }
    
    # 零轴附近（±5%范围内）
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
# v3.1+ 核心新增: 级别重叠分析
# =====================================================

def analyze_level_overlap(df_lower, df_upper, lower_name='5F', upper_name='30F'):
    """
    级别重叠分析
    
    小级别55线 vs 大级别中轨重叠 = 强支撑/压力区域
    
    返回:
        {
            'is_overlap': 是否重叠,
            'overlap_zone': (lower, upper) 重叠区间,
            'strength': 重叠强度,
            'description': 描述
        }
    """
    lower_latest = df_lower.iloc[-1]
    upper_latest = df_upper.iloc[-1]
    
    lower_55 = lower_latest['MA55']
    upper_mid = upper_latest['BOLL_MID']
    
    # 计算偏离度
    deviation = abs(lower_55 - upper_mid) / upper_mid * 100
    
    # 重叠定义: 偏离 < 0.5%
    is_overlap = deviation < 0.5
    
    if is_overlap:
        overlap_zone = (min(lower_55, upper_mid) * 0.995, max(lower_55, upper_mid) * 1.005)
        return {
            'is_overlap': True,
            'overlap_zone': overlap_zone,
            'strength': 1 - deviation / 0.5,  # 偏离越小强度越大
            'description': f'{lower_name}55线({lower_55:.2f})与{upper_name}中轨({upper_mid:.2f})重叠，强支撑/压力区域'
        }
    
    return {
        'is_overlap': False,
        'overlap_zone': None,
        'strength': 0,
        'description': f'{lower_name}55线与{upper_name}中轨无重叠(偏离{deviation:.2f}%)'
    }

# =====================================================
# v3.1+ 核心新增: 目标价推导
# =====================================================

def derive_target_price(df_level, level_name='30F'):
    """
    目标价推导
    
    方法:
    1. 前高: 近期最高点
    2. 中枢上轨: 基于笔段识别的中枢
    3. 等距测量: 55线 + (前高-前低)
    
    返回:
        {
            'target_high': 前高目标,
            'target_fib': 斐波那契扩展目标,
            'target_equal': 等距测量目标,
            'nearest_support': 最近支撑,
            'nearest_resistance': 最近压力
        }
    """
    latest = df_level.iloc[-1]
    price = latest['Close']
    ma55 = latest['MA55']
    
    # 前高/前低
    recent_high = df_level['High'].tail(60).max()
    recent_low = df_level['Low'].tail(60).min()
    
    # 中枢估算（简化版：用布林带中轨区域）
    mid_zone = df_level['BOLL_MID'].tail(20)
    center_high = mid_zone.max()
    center_low = mid_zone.min()
    center_mid = (center_high + center_low) / 2
    
    # 斐波那契扩展
    fib_618 = center_low + (recent_high - recent_low) * 1.618
    
    # 等距测量
    equal_measure = ma55 + (recent_high - recent_low)
    
    # 支撑/压力
    supports = [latest['BOLL_DOWN'], ma55, recent_low]
    resistances = [latest['BOLL_UP'], recent_high, center_high]
    
    # 找出最近的支撑和压力
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
    """分析当前是第几段，是否走完"""
    df_check = df.tail(lookback)
    strokes = find_strokes(df_check)
    
    if len(strokes) == 0:
        return {'total_strokes': 0, 'completed_segments': 0, 'current_segment_strokes': 0,
                'current_segment_status': '无笔', 'is_complete': False, 'trend': 'unclear'}
    
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
        'last_stroke_direction': last_direction
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
# v3.1+ 主分析器
# =====================================================

class ChanAnalysisV31Plus:
    """缠论分析器 v3.1+"""

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
            self.df_30m = calc_all_indicators(synthesize_kline(self.df_5m, 6, "30F"))
        
        if self.df_30m_raw is not None:
            self.df_120f = calc_all_indicators(synthesize_kline(self.df_30m_raw, 4, "120F"))
        elif self.df_daily is not None:
            self.df_120f = calc_all_indicators(synthesize_kline(self.df_daily, 5, "120F"))
        
        if self.df_daily is not None:
            self.df_daily = calc_all_indicators(self.df_daily)
            self.df_biday = calc_all_indicators(synthesize_kline(self.df_daily, 2, "双日"))

    def get_55line_analysis(self):
        """55线思维分析"""
        result = {}
        levels = [
            ('1F', getattr(self, 'df_1f', None)),
            ('5F', getattr(self, 'df_3m', None)),
            ('30F', getattr(self, 'df_30m', None)),
            ('120F', getattr(self, 'df_120f', None)),
            ('日线', self.df_daily)
        ]
        for name, df in levels:
            if df is not None:
                result[name] = judge_55line_status(name, df)
        return result

    def get_macd_extreme(self):
        """MACD极强期判断"""
        result = {}
        levels = [
            ('1F', getattr(self, 'df_1f', None)),
            ('5F', getattr(self, 'df_3m', None)),
            ('30F', getattr(self, 'df_30m', None))
        ]
        for name, df in levels:
            if df is not None:
                result[name] = judge_macd_extreme(df, name)
        return result

    def get_zero_axis_cross(self):
        """零轴金叉/死叉判断"""
        result = {}
        levels = [
            ('30F', getattr(self, 'df_30m', None)),
            ('120F', getattr(self, 'df_120f', None)),
            ('日线', self.df_daily)
        ]
        for name, df in levels:
            if df is not None:
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
        levels = [
            ('30F', getattr(self, 'df_30m', None)),
            ('120F', getattr(self, 'df_120f', None)),
            ('日线', self.df_daily)
        ]
        for name, df in levels:
            if df is not None:
                result[name] = derive_target_price(df, name)
        return result

    def get_segment_analysis(self):
        """段数分析"""
        result = {}
        if hasattr(self, 'df_30m') and self.df_30m is not None:
            result['30F'] = analyze_segment_count(self.df_30m, lookback=50)
        if hasattr(self, 'df_3m') and self.df_3m is not None:
            result['5F'] = analyze_segment_count(self.df_3m, lookback=50)
        if hasattr(self, 'df_1f') and self.df_1f is not None:
            result['1F'] = analyze_segment_count(self.df_1f, lookback=50)
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
        # 日线 vs 30F
        if self.df_daily is not None and hasattr(self, 'df_30m') and self.df_30m is not None:
            risks['日线vs30F'] = check_composite_risk(self.df_daily, self.df_30m)
        # 30F vs 5F
        if hasattr(self, 'df_30m') and self.df_30m is not None and hasattr(self, 'df_3m') and self.df_3m is not None:
            risks['30Fvs5F'] = check_composite_risk(self.df_30m, self.df_3m)
        return risks

    def generate_report(self):
        """生成完整分析报告（v3.1+）"""
        report = {
            '55line_analysis': self.get_55line_analysis(),
            'segment_analysis': self.get_segment_analysis(),
            'compensation_buy': self.get_compensation_buy(),
            'composite_risk': self.get_composite_risk(),
            'macd_extreme': self.get_macd_extreme(),
            'zero_axis_cross': self.get_zero_axis_cross(),
            'level_overlap': self.get_level_overlap(),
            'target_price': self.get_target_price()
        }
        return report


# =====================================================
# 主程序
# =====================================================

def main():
    print("="*60)
    print("缠论分析系统 v3.1+ - 55线思维 + MACD极强期 + 零轴金叉")
    print("="*60)

    df_1m = fetch_data("/mnt/kimi/output/sh_1min.csv")
    df_5m = fetch_data("/mnt/kimi/output/sh_5min_full.csv")
    df_daily = fetch_data("/mnt/kimi/output/sh_1day.csv")

    analyzer = ChanAnalysisV31Plus(df_1m=df_1m, df_5m=df_5m, df_daily=df_daily)
    report = analyzer.generate_report()

    print("\n【55线思维分析】")
    for level, data in report['55line_analysis'].items():
        print(f"\n{level}:")
        print(f"  价格: {data['price']:.2f}  55线: {data['ma55']:.2f}  中轨: {data['mid']:.2f}")
        print(f"  信号: {data['key_signal']}")
        print(f"  结构: {data['structure']}")

    print("\n【MACD极强期判断】")
    for level, data in report['macd_extreme'].items():
        print(f"\n{level}: {data['description']}")
        if data['is_extreme']:
            print(f"  方向: {data['direction']}  强度: {data['strength']:.1f}%")

    print("\n【零轴金叉/死叉】")
    for level, data in report['zero_axis_cross'].items():
        print(f"\n{level}: {data['description']}")
        if data['cross_type'] != 'none':
            print(f"  类型: {data['cross_type']}  重要性: {data['importance']}")

    print("\n【级别重叠分析】")
    for pair, data in report['level_overlap'].items():
        print(f"\n{pair}: {data['description']}")
        if data['is_overlap']:
            print(f"  重叠区间: {data['overlap_zone'][0]:.2f}-{data['overlap_zone'][1]:.2f}  强度: {data['strength']:.2f}")

    print("\n【目标价推导】")
    for level, data in report['target_price'].items():
        print(f"\n{level}:")
        print(f"  {data['description']}")
        print(f"  最近支撑: {data['nearest_support']:.2f}  最近压力: {data['nearest_resistance']:.2f}")

    print("\n【段数分析】")
    for level, data in report['segment_analysis'].items():
        print(f"\n{level}:")
        print(f"  总笔数: {data['total_strokes']}  已完成段: {data['completed_segments']}")
        print(f"  当前段: {data['current_segment_status']}")
        print(f"  趋势: {data['trend']}")

    print("\n【补偿性买点】")
    for level, data in report['compensation_buy'].items():
        if data.get('is_compensation_zone'):
            print(f"\n{level}: ✅ 补偿性买点区域")
            print(f"  区间: {data['zone'][0]:.0f}-{data['zone'][1]:.0f}")
            print(f"  确认: {data['confirmation']}")
            print(f"  操作: {data['action']}")

    print("\n【复合风控】")
    for pair, risk in report['composite_risk'].items():
        print(f"\n{pair}:")
        print(f"  风险等级: {risk['risk_level']} (得分: {risk['risk_score']})")
        print(f"  信号: {risk['signals']}")
        print(f"  操作: {risk['action']}")

if __name__ == "__main__":
    main()
