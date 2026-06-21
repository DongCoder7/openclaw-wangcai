
"""
缠论多级别联立分析系统 v3.1
更新日期: 2026-05-24

v3.1 核心改进 (基于与原文对比优化):
  1. 【55线思维】30F55线/5F55线作为核心分水岭, 替代中轨思维
  2. 【段数分析】分析当前是第几段, 是否走完, 不是只看结构
  3. 【补偿性买点】5F55线以下定义为经典缠论补偿性买点
  4. 【复合风控】30F55压制+5F顶背离 = 兑现多头 (非单一指标)
  5. 【筹码分析】量能+换手率分析筹码松动 (预留接口)
  6. 保留v3.0: 分型-笔-段识别 / 中枢识别 / 五层滤网
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

# =====================================================
# 数据获取 & 级别合成 (同v3.0)
# =====================================================

def fetch_yahoo_data(ticker="000001.SS", period="1mo", interval="5m", file_path=None):
    if file_path is None:
        file_path = f"/mnt/kimi/output/sh_{interval.replace('m','min').replace('d','day')}.csv"
    df = pd.read_csv(file_path)
    df['Date'] = pd.to_datetime(df['Date']).dt.tz_localize(None)
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
# 指标计算 (同v3.0)
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
    df['MA55'] = df['Close'].rolling(window=55, min_periods=1).mean()
    df['Vol_MA5'] = df['Volume'].rolling(window=5, min_periods=1).mean()
    return df

# =====================================================
# 分型-笔-段识别 (v3.0)
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
                        'kline_count': i - last['idx'] + 1,
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
# v3.1 核心新增: 段数分析
# =====================================================

def analyze_segment_count(df, lookback=50):
    """
    v3.1核心: 分析当前是第几段, 是否走完

    返回:
        {
            'total_strokes': 总笔数,
            'completed_segments': 已完成段数,
            'current_segment_strokes': 当前段已走笔数,
            'current_segment_status': '进行中'/'可能完成',
            'is_complete': 当前段是否已构成完整段,
            'trend': 'up'/'down'/'unclear'
        }
    """
    df_check = df.tail(lookback)
    strokes = find_strokes(df_check)

    if len(strokes) == 0:
        return {'total_strokes': 0, 'completed_segments': 0, 'current_segment_strokes': 0,
                'current_segment_status': '无笔', 'is_complete': False, 'trend': 'unclear'}

    # 统计段数 (3笔=1段)
    completed_segments = len(strokes) // 3
    current_segment_strokes = len(strokes) % 3

    # 判断当前段是否可能完成
    if current_segment_strokes == 0 and len(strokes) >= 3:
        # 检查最后3笔是否构成完整段
        last_3 = strokes[-3:]
        directions = [s['direction'] for s in last_3]
        is_alternating = all(directions[j] != directions[j+1] for j in range(2))
        total_klines = last_3[-1]['end_idx'] - last_3[0]['start_idx'] + 1
        is_complete = is_alternating and total_klines >= 7
    else:
        is_complete = False

    # 判断趋势方向 (根据最近一笔)
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
        'last_stroke_range': (strokes[-1]['start_price'], strokes[-1]['end_price'])
    }


# =====================================================
# v3.1 核心新增: 55线思维分水岭判断
# =====================================================

def judge_55line_status(level_name, df_level):
    """
    v3.1核心: 55线作为牛熊分水岭, 替代中轨思维

    返回:
        {
            'price': 当前价格,
            'ma55': 55线位置,
            'mid': 中轨位置,
            'status_55': '55线上方'/'55线下方',
            'status_mid': '中轨上方'/'中轨下方',
            'key_signal': '突破55线'/'跌破55线'/'55线压制'/'55线支撑',
            'structure': 结构判断
        }
    """
    latest = df_level.iloc[-1]
    price = latest['Close']
    ma55 = latest['MA55']
    mid = latest['BOLL_MID']
    macd = latest['MACD']

    status_55 = '55线上方' if price > ma55 else '55线下方'
    status_mid = '中轨上方' if price > mid else '中轨下方'

    # 关键信号判断
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

    # 结构判断 (基于55线, 不是中轨!)
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
        'status_mid': status_mid,
        'key_signal': key_signal,
        'structure': structure,
        'macd': macd
    }


# =====================================================
# v3.1 核心新增: 补偿性买点识别
# =====================================================

def identify_compensation_buy(df_level, level_name='5F'):
    """
    v3.1核心: 识别补偿性买点

    经典缠论买点结构:
        跌破55线 → 回踩确认 → 突破中轨 → 突破上级55线

    补偿性买点定义:
        价格跌破MA55后, 在MA55下方形成企稳信号
        + MACD底背离或缩量
        + 后续向上突破中轨时确认

    返回:
        {
            'is_compensation_zone': 是否在补偿性买点区域,
            'zone': (lower, upper) 买点区间,
            'confirmation': 确认信号,
            'target': 突破目标
        }
    """
    latest = df_level.iloc[-1]
    price = latest['Close']
    ma55 = latest['MA55']
    mid = latest['BOLL_MID']
    macd = latest['MACD']

    # 检查近期是否跌破过55线
    recent = df_level.tail(20)
    min_price = recent['Low'].min()

    is_below_55 = price < ma55
    was_below_55 = min_price < ma55 * 0.99

    # 底背离检查
    price_low = recent['Low'].min()
    macd_low = recent['MACD'].min()
    is_bottom_div = (price <= price_low * 1.002) and (macd > macd_low * 1.1)

    # 缩量检查
    vol_ratio = latest['Volume'] / latest['Vol_MA5'] if latest['Vol_MA5'] > 0 else 1
    is_shrink = vol_ratio < 0.8

    # 补偿性买点条件
    if was_below_55 and (is_bottom_div or is_shrink):
        return {
            'is_compensation_zone': True,
            'zone': (ma55 * 0.98, ma55),
            'confirmation': '底背离' if is_bottom_div else '缩量',
            'target': mid,
            'next_target': '上级55线',
            'action': f'在{level_name}55线({ma55:.0f})下方低吸, 突破{level_name}中轨({mid:.0f})确认, 目标上级55线'
        }

    return {'is_compensation_zone': False}


# =====================================================
# v3.1 核心新增: 复合风控信号
# =====================================================

def check_composite_risk(df_upper, df_lower):
    """
    v3.1核心: 复合风控信号

    原文经典信号:
        30F55线压制 + 5F顶背离 = 兑现一部分多头

    参数:
        df_upper: 上级DataFrame (如30F)
        df_lower: 下级DataFrame (如5F)

    返回:
        {'risk_level': 'high'/'medium'/'low', 'signals': [], 'action': ''}
    """
    signals = []
    risk_score = 0

    # 检查1: 上级55线压制
    upper_latest = df_upper.iloc[-1]
    upper_price = upper_latest['Close']
    upper_ma55 = upper_latest['MA55']
    upper_macd = upper_latest['MACD']

    if upper_price < upper_ma55 and upper_macd < 0:
        signals.append(f'{df_upper.name if hasattr(df_upper, "name") else "上级"}55线压制+MACD<0')
        risk_score += 40
    elif upper_price < upper_ma55:
        signals.append(f'{df_upper.name if hasattr(df_upper, "name") else "上级"}55线压制')
        risk_score += 25

    # 检查2: 下级顶背离
    lower_recent = df_lower.tail(20)
    lower_price_high = lower_recent['High'].max()
    lower_macd_high = lower_recent['MACD'].max()
    lower_current_price = df_lower.iloc[-1]['Close']
    lower_current_macd = df_lower.iloc[-1]['MACD']

    is_top_div = (lower_current_price >= lower_price_high * 0.998) and (lower_current_macd < lower_macd_high * 0.9)
    if is_top_div:
        signals.append(f'{df_lower.name if hasattr(df_lower, "name") else "下级"}顶背离')
        risk_score += 35

    # 检查3: 量能异常
    lower_latest = df_lower.iloc[-1]
    vol_ratio = lower_latest['Volume'] / lower_latest['Vol_MA5'] if lower_latest['Vol_MA5'] > 0 else 1
    if vol_ratio > 1.5:
        signals.append(f'放量{vol_ratio:.1f}倍')
        risk_score += 15

    # 风险等级
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
# v3.1 主分析器
# =====================================================

class ChanAnalysisV31:
    """缠论分析器 v3.1"""

    def __init__(self, df_1m=None, df_5m=None, df_daily=None):
        self.df_1m = df_1m.copy() if df_1m is not None else None
        self.df_5m = df_5m.copy() if df_5m is not None else None
        self.df_daily = df_daily.copy() if df_daily is not None else None
        self._prepare()

    def _prepare(self):
        # 合成级别
        if self.df_1m is not None:
            self.df_3m = synthesize_kline(self.df_1m, 3, "3F")
            self.df_3m = calc_all_indicators(self.df_3m)
        if self.df_5m is not None:
            self.df_15m = synthesize_kline(self.df_5m, 3, "15F")
            self.df_30m = synthesize_kline(self.df_5m, 6, "30F")
            self.df_60m = synthesize_kline(self.df_5m, 12, "60F")
            self.df_15m = calc_all_indicators(self.df_15m)
            self.df_30m = calc_all_indicators(self.df_30m)
            self.df_60m = calc_all_indicators(self.df_60m)
        if self.df_daily is not None:
            self.df_daily = calc_all_indicators(self.df_daily)
            self.df_biday = synthesize_kline(self.df_daily, 2, "双日")
            self.df_weekly = synthesize_kline(self.df_daily, 5, "周线")
            self.df_biweekly = synthesize_kline(self.df_daily, 10, "双周")
            self.df_biday = calc_all_indicators(self.df_biday)
            self.df_biweekly = calc_all_indicators(self.df_biweekly)

    def get_55line_analysis(self):
        """v3.1核心: 55线思维分析"""
        result = {}
        levels = [
            ('5F', getattr(self, 'df_3m', None)),
            ('30F', getattr(self, 'df_30m', None)),
            ('120F', self.df_daily),
            ('双日', getattr(self, 'df_biday', None)),
            ('双周', getattr(self, 'df_biweekly', None))
        ]
        for name, df in levels:
            if df is not None:
                result[name] = judge_55line_status(name, df)
        return result

    def get_segment_analysis(self):
        """v3.1核心: 段数分析"""
        result = {}
        if hasattr(self, 'df_30m') and self.df_30m is not None:
            result['30F'] = analyze_segment_count(self.df_30m, lookback=50)
        if hasattr(self, 'df_3m') and self.df_3m is not None:
            result['5F'] = analyze_segment_count(self.df_3m, lookback=50)
        return result

    def get_compensation_buy(self):
        """v3.1核心: 补偿性买点"""
        result = {}
        if hasattr(self, 'df_3m') and self.df_3m is not None:
            result['5F'] = identify_compensation_buy(self.df_3m, '5F')
        if hasattr(self, 'df_30m') and self.df_30m is not None:
            result['30F'] = identify_compensation_buy(self.df_30m, '30F')
        return result

    def get_composite_risk(self):
        """v3.1核心: 复合风控"""
        if hasattr(self, 'df_30m') and self.df_30m is not None and hasattr(self, 'df_3m') and self.df_3m is not None:
            return check_composite_risk(self.df_30m, self.df_3m)
        return None

    def generate_report(self):
        """生成完整分析报告"""
        report = {
            '55line_analysis': self.get_55line_analysis(),
            'segment_analysis': self.get_segment_analysis(),
            'compensation_buy': self.get_compensation_buy(),
            'composite_risk': self.get_composite_risk()
        }
        return report


# =====================================================
# 主程序
# =====================================================

def main():
    print("="*60)
    print("缠论分析系统 v3.1 - 55线思维 + 段数分析 + 补偿性买点")
    print("="*60)

    df_1m = fetch_yahoo_data(interval="1m", period="5d")
    df_5m = fetch_yahoo_data(interval="5m", period="1mo")
    df_daily = fetch_yahoo_data(interval="1d", period="3mo")

    analyzer = ChanAnalysisV31(df_1m=df_1m, df_5m=df_5m, df_daily=df_daily)
    report = analyzer.generate_report()

    print("\n【55线思维分析】")
    for level, data in report['55line_analysis'].items():
        print(f"\n{level}:")
        print(f"  价格: {data['price']:.2f}  55线: {data['ma55']:.2f}  中轨: {data['mid']:.2f}")
        print(f"  信号: {data['key_signal']}")
        print(f"  结构: {data['structure']}")

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
    risk = report['composite_risk']
    if risk:
        print(f"  风险等级: {risk['risk_level']} (得分: {risk['risk_score']})")
        print(f"  信号: {risk['signals']}")
        print(f"  操作: {risk['action']}")

if __name__ == "__main__":
    main()
