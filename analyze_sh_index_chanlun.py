#!/root/.openclaw/workspace/venv/bin/python3
"""
上证指数缠论分析 - 开盘前瞻
使用缠论技术分析上证指数走势
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
                    os.environ[key] = value.strip('"')
    config = Config.from_env()
    return QuoteContext(config)


def get_data(ctx, symbol, period, count):
    """获取数据"""
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
        return pd.DataFrame(data).sort_values('datetime').reset_index(drop=True)
    except Exception as e:
        print(f"  ❌ 数据获取失败: {e}")
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


def calculate_ma(data, periods=[5, 10, 20, 60]):
    """计算均线"""
    mas = {}
    for p in periods:
        mas[f'MA{p}'] = data['close'].rolling(window=p).mean().iloc[-1]
    return mas


def calculate_zhongshu(df, window=20):
    """
    缠论中枢计算
    中枢 = 价格停留时间最长的区间
    """
    highs = df['high'].values[-window:]
    lows = df['low'].values[-window:]
    
    # 创建价格区间
    price_min = lows.min()
    price_max = highs.max()
    price_range = np.linspace(price_min, price_max, 30)
    
    # 计算每个价位的停留时间
    time_at_level = []
    for level in price_range:
        # 统计K线包含该价位的数量
        mask = (lows <= level) & (highs >= level)
        time_at_level.append(mask.sum())
    
    # 找到停留时间最长的区间
    max_idx = np.argmax(time_at_level)
    center = price_range[max_idx]
    
    # 中枢区间 (上下轨)
    threshold = max(time_at_level) * 0.7
    valid_levels = price_range[np.array(time_at_level) >= threshold]
    
    if len(valid_levels) >= 2:
        lower = valid_levels.min()
        upper = valid_levels.max()
    else:
        lower = center * 0.99
        upper = center * 1.01
    
    return {
        'center': round(center, 2),
        'lower': round(lower, 2),
        'upper': round(upper, 2)
    }


def calculate_fenxing(df):
    """
    缠论分型计算
    顶分型: 中间高点高于两边
    底分型: 中间低点低于两边
    """
    highs = df['high'].values
    lows = df['low'].values
    
    resistance_levels = []
    support_levels = []
    
    # 找顶分型 (压力位)
    for i in range(2, len(highs) - 2):
        if (highs[i] > highs[i-1] and highs[i] > highs[i-2] and 
            highs[i] > highs[i+1] and highs[i] > highs[i+2]):
            resistance_levels.append(highs[i])
    
    # 找底分型 (支撑位)
    for i in range(2, len(lows) - 2):
        if (lows[i] < lows[i-1] and lows[i] < lows[i-2] and 
            lows[i] < lows[i+1] and lows[i] < lows[i+2]):
            support_levels.append(lows[i])
    
    # 取最近的3个
    recent_resistance = sorted(resistance_levels[-5:]) if resistance_levels else []
    recent_support = sorted(support_levels[-5:], reverse=True) if support_levels else []
    
    return {
        'resistance': round(recent_resistance[0], 2) if recent_resistance else None,
        'support': round(recent_support[0], 2) if recent_support else None,
        'resistance_list': [round(x, 2) for x in recent_resistance[-3:]],
        'support_list': [round(x, 2) for x in recent_support[-3:]]
    }


def calculate_pivot_points(high, low, close):
    """计算枢轴点"""
    pivot = (high + low + close) / 3
    r1 = 2 * pivot - low
    r2 = pivot + (high - low)
    s1 = 2 * pivot - high
    s2 = pivot - (high - low)
    
    return {
        'pivot': round(pivot, 2),
        'r1': round(r1, 2),
        'r2': round(r2, 2),
        's1': round(s1, 2),
        's2': round(s2, 2)
    }


def analyze_zoushi_type(df):
    """
    缠论走势类型分析
    上涨/下跌/盘整
    """
    closes = df['close'].values[-20:]
    highs = df['high'].values[-20:]
    lows = df['low'].values[-20:]
    
    # 计算趋势
    ma5 = np.mean(closes[-5:])
    ma10 = np.mean(closes[-10:])
    ma20 = np.mean(closes[-20:])
    
    # 判断走势类型
    if ma5 > ma10 > ma20:
        zoushi = "上涨"
        direction = "📈"
        score = 1
    elif ma5 < ma10 < ma20:
        zoushi = "下跌"
        direction = "📉"
        score = -1
    else:
        zoushi = "盘整"
        direction = "➡️"
        score = 0
    
    # 判断震荡幅度
    amplitude = (highs.max() - lows.min()) / closes.mean() * 100
    
    return {
        'type': zoushi,
        'direction': direction,
        'score': score,
        'amplitude': round(amplitude, 2)
    }


def generate_report(symbol, name):
    """生成上证指数缠论分析报告"""
    print(f"  分析 {name} ({symbol})...")
    
    ctx = init_api()
    
    # 获取日线数据
    df_day = get_data(ctx, symbol, Period.Day, 120)
    if df_day is None or len(df_day) < 60:
        return None
    
    # 获取60分钟数据
    df_60 = get_data(ctx, symbol, Period.Min_60, 240)
    
    # 当前价格
    current = df_day['close'].iloc[-1]
    prev_close = df_day['close'].iloc[-2]
    change = (current - prev_close) / prev_close * 100
    
    # 今日区间
    today_high = df_day['high'].iloc[-1]
    today_low = df_day['low'].iloc[-1]
    
    # 均线
    ma = calculate_ma(df_day)
    
    # 缠论中枢
    zhongshu = calculate_zhongshu(df_day, window=30)
    
    # 分型
    fenxing = calculate_fenxing(df_day)
    
    # 枢轴点
    pivot = calculate_pivot_points(
        df_day['high'].iloc[-5:].max(),
        df_day['low'].iloc[-5:].min(),
        df_day['close'].iloc[-1]
    )
    
    # 走势类型
    zoushi = analyze_zoushi_type(df_day)
    
    # 强支撑/压力 (多方法验证)
    strong_support_candidates = [fenxing['support'], zhongshu['lower'], ma['MA20'], pivot['s1']]
    strong_support_candidates = [x for x in strong_support_candidates if x is not None]
    strong_support = np.median(strong_support_candidates) if strong_support_candidates else current * 0.98
    
    strong_resistance_candidates = [fenxing['resistance'], zhongshu['upper'], ma['MA5'], pivot['r1']]
    strong_resistance_candidates = [x for x in strong_resistance_candidates if x is not None]
    strong_resistance = np.median(strong_resistance_candidates) if strong_resistance_candidates else current * 1.02
    
    # 技术评分
    score = 0
    score_factors = []
    
    # 走势类型
    score += zoushi['score']
    score_factors.append(f"走势:{zoushi['type']}({zoushi['score']:+.0f})")
    
    # 中枢位置
    if current > zhongshu['upper']:
        score += 0.5
        score_factors.append("突破中枢(+0.5)")
    elif current < zhongshu['lower']:
        score -= 0.5
        score_factors.append("跌破中枢(-0.5)")
    else:
        score_factors.append("中枢内部(0)")
    
    # 均线排列
    if ma['MA5'] > ma['MA10'] > ma['MA20']:
        score += 0.5
        score_factors.append("均线多头排列(+0.5)")
    elif ma['MA5'] < ma['MA10'] < ma['MA20']:
        score -= 0.5
        score_factors.append("均线空头排列(-0.5)")
    
    # 相对强支撑位置
    dist_to_support = (current - strong_support) / current * 100
    if dist_to_support < 1:
        score += 0.5
        score_factors.append("接近强支撑(+0.5)")
    elif dist_to_support > 5:
        score -= 0.3
        score_factors.append("远离支撑(-0.3)")
    
    # 操作建议
    if score >= 1.0:
        advice = "📈 偏多操作"
        advice_detail = "缠论信号偏多，可考虑逢低加仓"
    elif score >= 0.3:
        advice = "➡️ 偏多观望"
        advice_detail = "中枢上方运行，等待回调机会"
    elif score > -0.3:
        advice = "➡️ 震荡观望"
        advice_detail = "中枢内部震荡，等待方向选择"
    elif score > -1.0:
        advice = "⚠️ 偏空减仓"
        advice_detail = "中枢下方运行，减仓保护本金"
    else:
        advice = "📉 偏空避险"
        advice_detail = "走势偏弱，建议减仓或清仓"
    
    # 关键点位判断
    above_upper = current > zhongshu['upper']
    below_lower = current < zhongshu['lower']
    
    # 构建报告
    report = f"""
📊 {name} ({symbol}) - 缠论技术分析
⏰ 数据时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}

【当前状态】
  最新指数: {current:.2f}点
  涨跌幅: {change:+.2f}%
  今日区间: {today_low:.2f} - {today_high:.2f}
  振幅: {zoushi['amplitude']:.2f}%

【缠论走势类型】
  当前走势: {zoushi['direction']} {zoushi['type']}
  中枢区间: [{zhongshu['lower']:.2f}, {zhongshu['upper']:.2f}]
  中枢中心: {zhongshu['center']:.2f}点
  
  {'🔴 跌破中枢下轨' if below_lower else ('🟢 突破中枢上轨' if above_upper else '➡️ 中枢内部震荡')}

【分型支撑压力】
  分型支撑: {fenxing['support']:.2f}点 {'✅' if fenxing['support'] and current > fenxing['support'] else '❌'}
  分型压力: {fenxing['resistance']:.2f}点 {'⬆️ 上方' if fenxing['resistance'] and current < fenxing['resistance'] else '⬇️ 已突破'}
  
  强支撑: {strong_support:.2f}点 (多方法验证)
  强压力: {strong_resistance:.2f}点 (多方法验证)

【均线系统】
  MA5:  {ma['MA5']:.2f}点 {'📈支撑' if current > ma['MA5'] else '📉压力'}
  MA10: {ma['MA10']:.2f}点 {'📈支撑' if current > ma['MA10'] else '📉压力'}
  MA20: {ma['MA20']:.2f}点 {'📈支撑' if current > ma['MA20'] else '📉压力'}
  MA60: {ma['MA60']:.2f}点 {'📈支撑' if current > ma['MA60'] else '📉压力'}

【枢轴点系统】
  R2 (强压力): {pivot['r2']:.2f}点
  R1 (压力):   {pivot['r1']:.2f}点
  Pivot:       {pivot['pivot']:.2f}点 {'📈上方' if current > pivot['pivot'] else '📉下方'}
  S1 (支撑):   {pivot['s1']:.2f}点
  S2 (强支撑): {pivot['s2']:.2f}点

【关键价位清单】

👀 关注价位 (开盘监控):
  中枢上轨: {zhongshu['upper']:.2f}点 ({'已突破✅' if above_upper else '上方' + str(round((zhongshu['upper']-current)/current*100, 2)) + '%'})
  中枢下轨: {zhongshu['lower']:.2f}点 ({'已跌破🔴' if below_lower else '下方' + str(round((current-zhongshu['lower'])/current*100, 2)) + '%'})
  强支撑:   {strong_support:.2f}点
  强压力:   {strong_resistance:.2f}点
  枢轴R1:   {pivot['r1']:.2f}点
  枢轴S1:   {pivot['s1']:.2f}点

【技术评分】
  综合评分: {score:+.1f}分
  评分因素: {'; '.join(score_factors)}

【开盘操作建议】
  {advice}
  {advice_detail}

📋 开盘操作清单:
  1. 竞价观察: 开在{zhongshu['lower']:.2f}-{zhongshu['upper']:.2f}中枢区间何处
  2. 关键突破: 突破{zhongshu['upper']:.2f}可加仓，跌破{zhongshu['lower']:.2f}需减仓
  3. 严格风控: 跌破{strong_support:.2f}强支撑，减仓避险
  4. 目标位: 突破{strong_resistance:.2f}强压力，可看高一线

==================================================
"""
    return report


def main():
    print("=" * 60)
    print("📊 上证指数缠论分析报告")
    print("=" * 60)
    
    # 分析上证指数
    symbol = "000001.SH"
    name = "上证指数"
    
    report = generate_report(symbol, name)
    
    if report:
        print(report)
        send_feishu(report)
        print("✅ 报告已发送至飞书")
    else:
        print("❌ 分析失败")


if __name__ == "__main__":
    main()
