#!/root/.openclaw/workspace/venv/bin/python3
"""
上证指数缠论分析 - 30分钟+5分钟级别 (开盘前瞻)
专注于短周期缠论结构，给出可操作的开盘建议
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


def calculate_zhongshu_5f(df, window=12):
    """
    5分钟级别中枢计算
    取最近12根K线（1小时）的价格密集区
    """
    if len(df) < window:
        window = len(df)
    
    highs = df['high'].values[-window:]
    lows = df['low'].values[-window:]
    closes = df['close'].values[-window:]
    
    # 简化中枢 = 最近N根的均价区间
    avg_high = np.mean(highs)
    avg_low = np.mean(lows)
    avg_close = np.mean(closes)
    
    # 中枢 = 高低点之间的密集区 (取60%位置)
    center = (avg_high + avg_low) / 2
    upper = avg_high * 0.95 + avg_low * 0.05  # 偏高点
    lower = avg_high * 0.05 + avg_low * 0.95  # 偏低点
    
    return {
        'center': round(center, 2),
        'upper': round(upper, 2),
        'lower': round(lower, 2),
        'width': round((upper - lower) / center * 100, 2)  # 中枢宽度%
    }


def calculate_zhongshu_30f(df, window=16):
    """
    30分钟级别中枢计算
    取最近16根K线（8小时，约2个交易日）
    """
    if len(df) < window:
        window = len(df)
    
    highs = df['high'].values[-window:]
    lows = df['low'].values[-window:]
    
    # 中枢 = 高低点的50%-60%区间
    center = (np.max(highs) + np.min(lows)) / 2
    upper = np.percentile(highs, 60)
    lower = np.percentile(lows, 40)
    
    return {
        'center': round(center, 2),
        'upper': round(upper, 2),
        'lower': round(lower, 2),
        'width': round((upper - lower) / center * 100, 2)
    }


def calculate_fenxing_5f(df):
    """
    5分钟分型识别
    顶分型: 中间K线高点最高
    底分型: 中间K线低点最低
    """
    if len(df) < 5:
        return None
    
    highs = df['high'].values
    lows = df['low'].values
    
    # 找最近的顶分型
    top_fenxing = None
    for i in range(len(highs)-3, 2, -1):
        if (highs[i] > highs[i-1] and highs[i] > highs[i-2] and 
            highs[i] > highs[i+1] and highs[i] > highs[i+2]):
            top_fenxing = highs[i]
            break
    
    # 找最近的底分型
    bottom_fenxing = None
    for i in range(len(lows)-3, 2, -1):
        if (lows[i] < lows[i-1] and lows[i] < lows[i-2] and 
            lows[i] < lows[i+1] and lows[i] < lows[i+2]):
            bottom_fenxing = lows[i]
            break
    
    return {
        'top': round(top_fenxing, 2) if top_fenxing else None,
        'bottom': round(bottom_fenxing, 2) if bottom_fenxing else None
    }


def analyze_5f_trend(df):
    """5分钟趋势分析"""
    if len(df) < 10:
        return {'trend': 'unknown', 'strength': 0}
    
    closes = df['close'].values[-10:]
    
    # 短期均线
    ma3 = np.mean(closes[-3:])
    ma5 = np.mean(closes[-5:])
    ma10 = np.mean(closes)
    
    # 趋势判断
    if ma3 > ma5 > ma10:
        trend = '上涨'
        strength = 2
    elif ma3 > ma5:
        trend = '偏弱上涨'
        strength = 1
    elif ma3 < ma5 < ma10:
        trend = '下跌'
        strength = -2
    elif ma3 < ma5:
        trend = '偏弱下跌'
        strength = -1
    else:
        trend = '震荡'
        strength = 0
    
    return {'trend': trend, 'strength': strength, 'ma3': round(ma3, 2)}


def analyze_30f_trend(df):
    """30分钟趋势分析"""
    if len(df) < 10:
        return {'trend': 'unknown', 'strength': 0}
    
    closes = df['close'].values[-10:]
    highs = df['high'].values[-10:]
    lows = df['low'].values[-10:]
    
    # 均线
    ma5 = np.mean(closes[-5:])
    ma10 = np.mean(closes)
    
    # 高低点序列
    higher_highs = highs[-1] > highs[-5]
    higher_lows = lows[-1] > lows[-5]
    
    if higher_highs and higher_lows:
        trend = '上升趋势'
        strength = 2
    elif not higher_highs and not higher_lows:
        trend = '下降趋势'
        strength = -2
    elif ma5 > ma10:
        trend = '偏强震荡'
        strength = 1
    else:
        trend = '偏弱震荡'
        strength = -1
    
    return {'trend': trend, 'strength': strength, 'ma5': round(ma5, 2), 'ma10': round(ma10, 2)}


def generate_5f_report(df_5f, current):
    """生成5分钟级别报告"""
    if df_5f is None or len(df_5f) < 20:
        return "5分钟数据不足"
    
    # 中枢
    zhongshu = calculate_zhongshu_5f(df_5f, window=12)
    
    # 分型
    fenxing = calculate_fenxing_5f(df_5f)
    
    # 趋势
    trend = analyze_5f_trend(df_5f)
    
    # 关键位判断
    above_upper = current > zhongshu['upper']
    below_lower = current < zhongshu['lower']
    in_zhongshu = not above_upper and not below_lower
    
    # 距离
    dist_to_upper = (zhongshu['upper'] - current) / current * 100 if not above_upper else 0
    dist_to_lower = (current - zhongshu['lower']) / current * 100 if not below_lower else 0
    
    report = f"""
【5分钟级别缠论结构】
  中枢区间: [{zhongshu['lower']:.2f}, {zhongshu['upper']:.2f}] (宽{zhongshu['width']:.2f}%)
  中枢中心: {zhongshu['center']:.2f}点
  
  当前位置: {'🔴跌破下轨' if below_lower else ('🟢突破上轨' if above_upper else '➡️中枢内部')}
  距上轨: {dist_to_upper:.2f}% | 距下轨: {dist_to_lower:.2f}%
  
  5F趋势: {trend['trend']} (强度{trend['strength']:+d})
  MA3: {trend['ma3']:.2f}点
  
  最近顶分型: {fenxing['top']:.2f}点 {'📉压力' if fenxing['top'] and current < fenxing['top'] else ''}
  最近底分型: {fenxing['bottom']:.2f}点 {'📈支撑' if fenxing['bottom'] and current > fenxing['bottom'] else ''}
"""
    return report, zhongshu, trend, fenxing


def generate_30f_report(df_30f, current):
    """生成30分钟级别报告"""
    if df_30f is None or len(df_30f) < 10:
        return "30分钟数据不足"
    
    # 中枢
    zhongshu = calculate_zhongshu_30f(df_30f, window=16)
    
    # 趋势
    trend = analyze_30f_trend(df_30f)
    
    # 关键位判断
    above_upper = current > zhongshu['upper']
    below_lower = current < zhongshu['lower']
    
    # 走势类型判断
    if trend['strength'] >= 2:
        zoushi = "5F上涨" if above_upper else "5F中枢上移"
    elif trend['strength'] <= -2:
        zoushi = "5F下跌" if below_lower else "5F中枢下移"
    else:
        zoushi = "5F盘整"
    
    report = f"""
【30分钟级别缠论结构】
  中枢区间: [{zhongshu['lower']:.2f}, {zhongshu['upper']:.2f}] (宽{zhongshu['width']:.2f}%)
  走势类型: {zoushi}
  
  30F趋势: {trend['trend']}
  MA5: {trend['ma5']:.2f}点 | MA10: {trend['ma10']:.2f}点
  
  {'📈 MA5>MA10，短期偏多' if trend['ma5'] > trend['ma10'] else '📉 MA5<MA10，短期偏空'}
"""
    return report, zhongshu, trend


def generate_kai_pan_strategy(current, zhongshu_5f, trend_5f, fenxing_5f, zhongshu_30f, trend_30f):
    """生成开盘操作策略"""
    
    # 当前相对5F中枢位置
    in_5f_upper = current > zhongshu_5f['upper']
    in_5f_lower = current < zhongshu_5f['lower']
    
    # 30F趋势强度
    trend_30f_strength = trend_30f['strength']
    trend_5f_strength = trend_5f['strength']
    
    # 综合判断
    if in_5f_upper and trend_30f_strength > 0:
        main_strategy = "🟢 偏多操作"
        detail = "5F突破+30F向上，可持仓或小幅加仓"
        key_level = f"回踩{zhongshu_5f['upper']:.2f}不破可买"
    elif in_5f_lower and trend_30f_strength < 0:
        main_strategy = "🔴 偏空减仓"
        detail = "5F跌破+30F向下，减仓避险"
        key_level = f"反弹{zhongshu_5f['lower']:.2f}不过减仓"
    elif in_5f_lower and trend_30f_strength >= 0:
        main_strategy = "⚠️ 观察等待"
        detail = "5F跌破但30F仍强，观察是否假跌破"
        key_level = f"快速收回{zhongshu_5f['lower']:.2f}可持仓"
    elif in_5f_upper and trend_30f_strength <= 0:
        main_strategy = "⚠️ 警惕回调"
        detail = "5F突破但30F偏弱，防止假突破"
        key_level = f"跌破{zhongshu_5f['upper']:.2f}要减仓"
    else:
        main_strategy = "➡️ 中枢震荡"
        detail = "5F中枢内部，等待方向选择"
        key_level = f"突破{zhongshu_5f['upper']:.2f}做多，跌破{zhongshu_5f['lower']:.2f}做空"
    
    # 分型关键位
    fenxing_notes = ""
    if fenxing_5f['top']:
        fenxing_notes += f"  • 顶分型压力: {fenxing_5f['top']:.2f}点\n"
    if fenxing_5f['bottom']:
        fenxing_notes += f"  • 底分型支撑: {fenxing_5f['bottom']:.2f}点\n"
    
    strategy = f"""
【开盘缠论操作策略】

🎯 主要策略: {main_strategy}
  {detail}

📍 关键价位 (开盘监控):
  • 5F中枢上轨: {zhongshu_5f['upper']:.2f}点 ({'上方' if current < zhongshu_5f['upper'] else '已突破'})
  • 5F中枢下轨: {zhongshu_5f['lower']:.2f}点 ({'下方' if current > zhongshu_5f['lower'] else '已跌破'})
  • 5F中枢中心: {zhongshu_5f['center']:.2f}点
{fenxing_notes}
  • 30F MA5: {trend_30f['ma5']:.2f}点
  • 30F MA10: {trend_30f['ma10']:.2f}点

📋 开盘操作清单:
  1. 竞价定位: 开在{zhongshu_5f['lower']:.0f}-{zhongshu_5f['upper']:.0f}区间何处
  2. 突破策略: 突破{zhongshu_5f['upper']:.0f}追多，跌破{zhongshu_5f['lower']:.0f}开空
  3. 止损设置: 反向突破中枢另一边止损
  4. 目标预期: {zhongshu_5f['upper']:.0f}→{zhongshu_5f['upper']+10:.0f}或{zhongshu_5f['lower']:.0f}→{zhongshu_5f['lower']-10:.0f}

⏰ 时间窗口:
  • 9:30-9:45: 观察开盘方向选择
  • 10:00前: 确认5F趋势方向
  • 10:30: 根据30F结构决定是否持仓
"""
    return strategy


def main():
    print("=" * 60)
    print("📊 上证指数缠论分析 (30F+5F)")
    print("=" * 60)
    
    ctx = init_api()
    symbol = "000001.SH"
    
    # 获取30分钟和5分钟数据
    print("  获取30分钟数据...")
    df_30f = get_data(ctx, symbol, Period.Min_30, 100)
    
    print("  获取5分钟数据...")
    df_5f = get_data(ctx, symbol, Period.Min_5, 200)
    
    # 当前价格
    current = df_5f['close'].iloc[-1] if df_5f is not None else None
    
    if current is None:
        print("❌ 数据获取失败")
        return
    
    print(f"  当前指数: {current:.2f}")
    
    # 生成各级别报告
    report_5f, zhongshu_5f, trend_5f, fenxing_5f = generate_5f_report(df_5f, current)
    report_30f, zhongshu_30f, trend_30f = generate_30f_report(df_30f, current)
    
    # 生成开盘策略
    strategy = generate_kai_pan_strategy(current, zhongshu_5f, trend_5f, fenxing_5f, zhongshu_30f, trend_30f)
    
    # 组合完整报告
    full_report = f"""
📊 上证指数缠论分析 (30F+5F级别)
⏰ 数据时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}

【当前状态】
  最新指数: {current:.2f}点

{report_30f}
{report_5f}
{strategy}

⚠️ 风险提示: 本分析基于缠论技术指标，不构成投资建议。开盘波动剧烈，请严格执行止损。
"""
    
    print(full_report)
    send_feishu(full_report)
    print("✅ 报告已发送至飞书")


if __name__ == "__main__":
    main()
