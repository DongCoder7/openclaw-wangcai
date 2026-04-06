#!/root/.openclaw/workspace/venv/bin/python3
"""
上证指数缠论分析 - 整合版（结合专业分析框架）

分析框架：
- 30F级别：确定当天强弱（中枢+三买三卖）
- 5F级别：日内分时操作（背驰+买卖点）
- 分层支撑压力：第一支撑/强支撑/极限支撑
"""

import pandas as pd
import numpy as np
from datetime import datetime
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


def calculate_zhongshu_practical(df, window=20):
    """
    实用版中枢计算
    找最近window根K线的高低点30%-70%分位区间
    """
    if len(df) < window:
        window = len(df)
    
    highs = df['high'].values[-window:]
    lows = df['low'].values[-window:]
    
    upper = np.percentile(highs, 70)
    lower = np.percentile(lows, 30)
    center = (upper + lower) / 2
    
    return {
        'lower': round(lower, 2),
        'upper': round(upper, 2),
        'center': round(center, 2),
        'width': round((upper - lower) / center * 100, 2)
    }


def find_key_levels(df, current):
    """
    找关键支撑压力位（分层）
    1. 第一支撑/压力（中枢边界）
    2. 强支撑/压力（前期高低点+中枢重叠区）
    3. 极限支撑/压力（1.618扩展位+双级别共振）
    """
    highs = df['high'].values[-60:]
    lows = df['low'].values[-60:]
    
    # 近期高低点
    recent_high = np.max(highs[-20:])
    recent_low = np.min(lows[-20:])
    prev_high = np.max(highs[-40:-20]) if len(highs) >= 40 else recent_high
    prev_low = np.min(lows[-40:-20]) if len(lows) >= 40 else recent_low
    
    # 中枢
    zhongshu = calculate_zhongshu_practical(df, window=20)
    
    # 分层支撑
    first_support = zhongshu['lower']  # 中枢下沿
    strong_support = min(prev_low, zhongshu['lower'] - (zhongshu['upper'] - zhongshu['lower']) * 0.5)  # 前期低点+扩展
    
    # 1.618扩展位（极限支撑）
    range_size = zhongshu['upper'] - zhongshu['lower']
    extreme_support = zhongshu['lower'] - range_size * 0.618
    
    # 分层压力
    first_pressure = zhongshu['upper']  # 中枢上沿
    strong_pressure = max(prev_high, zhongshu['upper'] + range_size * 0.5)  # 前期高点+扩展
    extreme_pressure = zhongshu['upper'] + range_size * 0.618  # 1.618扩展
    
    return {
        'first_support': round(first_support, 2),
        'strong_support': round(strong_support, 2),
        'extreme_support': round(extreme_support, 2),
        'first_pressure': round(first_pressure, 2),
        'strong_pressure': round(strong_pressure, 2),
        'extreme_pressure': round(extreme_pressure, 2),
        'recent_high': round(recent_high, 2),
        'recent_low': round(recent_low, 2),
        'zhongshu': zhongshu
    }


def analyze_30f_structure(df_30f, current):
    """
    30F级别结构分析
    - 中枢区间
    - 三买三卖判断
    - 走势类型
    """
    zhongshu = calculate_zhongshu_practical(df_30f, window=16)  # 8小时
    
    # 判断位置
    if current > zhongshu['upper']:
        position = "中枢上方"
        signal = "🟢 偏多"
    elif current < zhongshu['lower']:
        position = "中枢下方"
        signal = "🔴 偏空"
    else:
        position = "中枢内部"
        signal = "➡️ 震荡"
    
    # 三买三卖判断逻辑
    sanmai_note = ""
    if current < zhongshu['lower']:
        sanmai_note = f"📉 跌破中枢下沿({zhongshu['lower']})，开盘反抽不回 → 30F三卖确认"
    elif current > zhongshu['upper']:
        sanmai_note = f"📈 突破中枢上沿({zhongshu['upper']})，回踩不破 → 30F三买确认"
    
    return {
        'zhongshu': zhongshu,
        'position': position,
        'signal': signal,
        'sanmai_note': sanmai_note
    }


def analyze_5f_structure(df_5f, current):
    """
    5F级别结构分析
    - 中枢区间
    - 次级别买卖点
    - 背驰判断
    """
    zhongshu = calculate_zhongshu_practical(df_5f, window=24)  # 2小时
    
    # 判断位置
    if current > zhongshu['upper']:
        position = "中枢上方"
        signal = "🟢 偏多"
    elif current < zhongshu['lower']:
        position = "中枢下方"
        signal = "🔴 偏空（可能出三卖）"
    else:
        position = "中枢内部"
        signal = "➡️ 震荡"
    
    # 距离
    dist_to_upper = (zhongshu['upper'] - current) / current * 100
    dist_to_lower = (current - zhongshu['lower']) / current * 100
    
    return {
        'zhongshu': zhongshu,
        'position': position,
        'signal': signal,
        'dist_to_upper': dist_to_upper,
        'dist_to_lower': dist_to_lower
    }


def generate_trading_plan(levels_30f, levels_5f, current, structure_30f, structure_5f):
    """
    生成交易计划
    参考专业分析框架：
    - 低开/下探路径
    - 高开/弱反路径
    - 极简点位表
    """
    
    # 关键位
    zs_30f = structure_30f['zhongshu']
    zs_5f = structure_5f['zhongshu']
    
    # 分层支撑压力
    first_support = zs_30f['lower']  # 3872附近
    strong_support = levels_30f['strong_support']  # 3852附近
    extreme_support = levels_30f['extreme_support']  # 3830-3840
    
    first_pressure = zs_5f['upper']  # 3890附近
    strong_pressure = zs_30f['upper']  # 3924附近
    
    # 交易计划
    plan = f"""
【📊 开盘交易计划】

一、30F级别（决定当天强弱）
  中枢: [{zs_30f['lower']:.0f}, {zs_30f['upper']:.0f}]
  当前: {current:.0f}点 → {structure_30f['position']}
  
  支撑位（下探目标）:
  • {first_support:.0f}（第一支撑）- 30F中枢下沿
    开盘直接破、反抽不回 → 30F三卖确认
  • {strong_support:.0f}（强支撑/一买区）- 前期低点+背驰位
    到这里看 5F底背驰 才考虑低吸
  • {extreme_support:.0f}（极限支撑/黄金坑）
    30F+5F双背驰区，最安全低吸点
  
  压力位（反弹目标）:
  • {first_pressure:.0f}（第一压力）- 5F上沿+套牢盘
    缩量到这里 → 减仓
  • {strong_pressure:.0f}（强压/生死线）- 30F中枢上沿
    放量站稳才叫反转，否则都是反弹

二、5F级别（日内分时操作）
  中枢: [{zs_5f['lower']:.0f}, {zs_5f['upper']:.0f}]
  
  1️⃣ 低开/下探路径（最可能）:
     • 开盘破 {first_support:.0f}
       - 不回中枢 → 30F三卖确认
       - 第一目标: {strong_support:.0f}
       - 5F底背驰+放量 → 日内小多，看{first_pressure:.0f}
       - 无量反抽 → 继续下看 {extreme_support:.0f}
     
     • 到 {extreme_support:.0f}
       - 30F+5F双背驰 → 重仓低吸
       - 不背驰、直接破 → 放弃，看{extreme_support-20:.0f}
  
  2️⃣ 高开/弱反路径（小概率）:
     • 开盘在 {current:.0f}-{first_pressure:.0f}
       - 放量突破 {first_pressure:.0f} → 看 {strong_pressure:.0f}
       - 缩量、不过 {first_pressure:.0f} → 逢高减仓
     
     • 反弹到 {strong_pressure:.0f}
       - 放量站稳+5F三买 → 反转成立
       - 缩量遇阻+顶背驰 → 清仓

三、极简缠论点位表（直接盯盘）
  ┌─────────────────────────────────────┐
  │  强支撑: {strong_support:.0f}、{extreme_support:.0f}      │
  │  弱支撑: {first_support:.0f}                    │
  │  弱压力: {first_pressure:.0f}                    │
  │  强压力: {strong_pressure:.0f}                    │
  └─────────────────────────────────────┘

四、一句话口诀:
  破{first_support:.0f}看{strong_support:.0f}，双背{extreme_support:.0f}重仓吸；
  过{first_pressure:.0f}看{strong_pressure:.0f}，站稳反转否则撤。

五、大反弹条件（概率<15%）:
  必须同时满足:
  1. 开盘不跌破 {first_support:.0f}
  2. 放量突破 {first_pressure:.0f}→{strong_pressure:.0f}
  3. 5F连续三买、不背驰
  
  更大概率:
  先下探{strong_support:.0f}-{extreme_support:.0f}，再走弱反到{first_pressure:.0f}-{strong_pressure:.0f}
"""
    return plan


def main():
    print("=" * 60)
    print("📊 上证指数缠论分析 - 整合专业分析框架")
    print("=" * 60)
    
    ctx = init_api()
    symbol = "000001.SH"
    
    # 获取数据
    print("  获取30分钟数据...")
    df_30f = get_data(ctx, symbol, Period.Min_30, 100)
    
    print("  获取5分钟数据...")
    df_5f = get_data(ctx, symbol, Period.Min_5, 200)
    
    current = df_5f['close'].iloc[-1] if df_5f is not None else None
    
    if current is None:
        print("❌ 数据获取失败")
        return
    
    print(f"  当前指数: {current:.2f}")
    
    # 分析结构
    print("  分析30F结构...")
    structure_30f = analyze_30f_structure(df_30f, current)
    levels_30f = find_key_levels(df_30f, current)
    
    print("  分析5F结构...")
    structure_5f = analyze_5f_structure(df_5f, current)
    levels_5f = find_key_levels(df_5f, current)
    
    # 生成交易计划
    print("  生成交易计划...")
    trading_plan = generate_trading_plan(levels_30f, levels_5f, current, structure_30f, structure_5f)
    
    # 综合报告
    report = f"""
📊 上证指数缠论分析（整合版）
⏰ 数据时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}

【当前结构】
  收盘: {current:.0f}点
  
  30F: 中枢 [{structure_30f['zhongshu']['lower']:.0f}, {structure_30f['zhongshu']['upper']:.0f}]
       {structure_30f['signal']} - {structure_30f['position']}
       {structure_30f['sanmai_note']}
  
  5F:  中枢 [{structure_5f['zhongshu']['lower']:.0f}, {structure_5f['zhongshu']['upper']:.0f}]
       {structure_5f['signal']} - {structure_5f['position']}
       距上轨: {structure_5f['dist_to_upper']:.2f}% | 距下轨: {structure_5f['dist_to_lower']:.2f}%

{trading_plan}

⚠️ 风险提示: 本分析基于缠论技术指标，不构成投资建议。开盘波动剧烈，请严格执行止损。

---
分析框架参考: 30F定强弱 + 5F做分时 + 分层支撑压力
"""
    
    print(report)
    send_feishu(report)
    print("✅ 报告已发送至飞书")


if __name__ == "__main__":
    main()
