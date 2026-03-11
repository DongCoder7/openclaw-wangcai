#!/root/.openclaw/workspace/venv/bin/python3
"""
实盘跟踪Pro - 分钟级调仓建议系统

核心升级:
1. 分钟级K线数据 (1分钟/5分钟)
2. 量能分析 (量比/换手率/资金流向)
3. 5浪理论 (艾略特波浪自动识别)
4. 盘中实时监控与调仓建议

用法:
  ./venv_runner.sh skills/portfolio-tracker-pro/scripts/portfolio_pro.py [morning|noon|afternoon|close]

执行时间:
  9:30  - 开盘分析 (早盘机会)
  11:00 - 午盘前分析 (早盘总结)
  13:30 - 下午开盘分析 (午后机会)
  14:50 - 收盘前分析 (尾盘调仓)
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import sys
import os
import json

sys.path.insert(0, '/root/.openclaw/workspace/venv/lib/python3.12/site-packages')

from longport.openapi import QuoteContext, Config, AdjustType, Period

# 持仓配置
PORTFOLIO = {
    "300750.SZ": {"name": "宁德时代", "shares": 1000},
    "300274.SZ": {"name": "阳光电源", "shares": 1500},
    "688676.SH": {"name": "金盘科技", "shares": 2000},
    "600875.SH": {"name": "东方电气", "shares": 3000},
    "601088.SH": {"name": "中国神华", "shares": 3000},
    "603986.SH": {"name": "兆易创新", "shares": 1500},
    "688008.SH": {"name": "澜起科技", "shares": 2000},
    "603920.SH": {"name": "世运电路", "shares": 4000},
    "002463.SZ": {"name": "沪电股份", "shares": 3000},
}


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


def get_minute_data(ctx, symbol, period=Period.Min_1, count=240):
    """获取分钟级数据"""
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
        print(f"❌ {symbol} 分钟数据获取失败: {e}")
        return None


def analyze_volume(df):
    """量能分析"""
    if df is None or len(df) < 20:
        return {}
    
    latest = df.iloc[-1]
    avg_vol_20 = df['volume'].rolling(20).mean().iloc[-1]
    avg_vol_5 = df['volume'].tail(5).mean()
    
    # 量比 (当前成交量/前5日均量)
    volume_ratio = latest['volume'] / avg_vol_5 if avg_vol_5 > 0 else 1
    
    # 量价关系
    price_change = (latest['close'] - df.iloc[-2]['close']) / df.iloc[-2]['close'] * 100 if len(df) > 1 else 0
    
    volume_signal = "中性"
    if volume_ratio > 2 and price_change > 2:
        volume_signal = "放量上涨"
    elif volume_ratio > 2 and price_change < -2:
        volume_signal = "放量下跌"
    elif volume_ratio < 0.5:
        volume_signal = "缩量整理"
    
    return {
        'volume_ratio': volume_ratio,
        'avg_volume': avg_vol_20,
        'latest_volume': latest['volume'],
        'signal': volume_signal
    }


def detect_elliott_wave(df):
    """简化的5浪理论检测"""
    if df is None or len(df) < 30:
        return {}
    
    closes = df['close'].values
    highs = df['high'].values
    lows = df['low'].values
    
    # 找到最近的高点和低点
    recent_highs = []
    recent_lows = []
    
    for i in range(5, len(highs) - 5):
        if highs[i] == max(highs[i-5:i+6]):
            recent_highs.append((i, highs[i]))
        if lows[i] == min(lows[i-5:i+6]):
            recent_lows.append((i, lows[i]))
    
    wave_analysis = "无法识别"
    wave_position = "未知"
    
    # 简单判断趋势位置
    if len(recent_highs) >= 2 and len(recent_lows) >= 2:
        last_high = recent_highs[-1][1]
        prev_high = recent_highs[-2][1]
        last_low = recent_lows[-1][1]
        
        current_price = closes[-1]
        
        # 判断是否在第5浪
        if last_high > prev_high and current_price < last_high * 0.98:
            wave_position = "可能在第5浪末期"
            wave_analysis = "⚠️ 警惕回调"
        elif current_price > last_high:
            wave_position = "突破新高"
            wave_analysis = "📈 趋势延续"
        elif current_price < last_low:
            wave_position = "跌破前低"
            wave_analysis = "📉 趋势转弱"
    
    return {
        'position': wave_position,
        'analysis': wave_analysis,
        'recent_highs': len(recent_highs),
        'recent_lows': len(recent_lows)
    }


def analyze_intraday_trend(df):
    """盘中趋势分析"""
    if df is None or len(df) < 5:
        return {}
    
    latest = df.iloc[-1]
    opens = df['open'].values
    closes = df['close'].values
    highs = df['high'].values
    lows = df['low'].values
    
    # 计算今日涨跌幅
    today_open = opens[0]
    current = latest['close']
    change_pct = (current - today_open) / today_open * 100
    
    # 判断趋势强度
    up_count = sum(1 for i in range(len(closes)-1) if closes[i+1] > closes[i])
    down_count = len(closes) - 1 - up_count
    
    trend_strength = "中性"
    if up_count > down_count * 2:
        trend_strength = "强势上涨"
    elif down_count > up_count * 2:
        trend_strength = "强势下跌"
    elif up_count > down_count:
        trend_strength = "偏弱上涨"
    elif down_count > up_count:
        trend_strength = "偏弱下跌"
    
    # 支撑压力位 (当日)
    day_high = max(highs)
    day_low = min(lows)
    
    return {
        'change_pct': change_pct,
        'day_high': day_high,
        'day_low': day_low,
        'trend_strength': trend_strength,
        'up_bars': up_count,
        'down_bars': down_count
    }


def generate_trading_signal(symbol, name, shares, ctx, session_type):
    """生成交易信号"""
    # 获取数据
    df_1min = get_minute_data(ctx, symbol, Period.Min_1, 240)  # 240分钟 = 4小时
    df_5min = get_minute_data(ctx, symbol, Period.Min_5, 48)   # 48根 = 4小时
    
    if df_1min is None:
        return None
    
    # 各项分析
    volume_analysis = analyze_volume(df_1min)
    wave_analysis = detect_elliott_wave(df_5min)
    trend_analysis = analyze_intraday_trend(df_1min)
    
    # 当前价格
    current_price = df_1min.iloc[-1]['close']
    market_value = current_price * shares
    
    # 根据时间段生成建议
    action = "持有"
    reason = ""
    urgency = "正常"
    
    if session_type == "morning":  # 9:30
        if trend_analysis.get('change_pct', 0) > 3:
            action = "观察"
            reason = "高开3%+，观察是否冲高回落"
        elif trend_analysis.get('change_pct', 0) < -3:
            action = "关注"
            reason = "低开3%+，关注是否反弹"
            
    elif session_type == "noon":  # 11:00
        if wave_analysis.get('analysis', '').startswith('⚠️') and trend_analysis.get('change_pct', 0) < -2:
            action = "减仓"
            reason = "5浪末期+早盘弱势，建议减仓避险"
            urgency = "⚠️ 紧急"
        elif volume_analysis.get('volume_ratio', 1) > 3 and trend_analysis.get('change_pct', 0) > 2:
            action = "持有"
            reason = "放量上涨，趋势良好"
            
    elif session_type == "afternoon":  # 13:30
        if trend_analysis.get('trend strength', '') == "强势下跌":
            action = "减仓"
            reason = "午后继续弱势，减仓避险"
        elif trend_analysis.get('trend strength', '') == "强势上涨":
            action = "持有/加仓"
            reason = "午后强势，可加仓"
            
    elif session_type == "close":  # 14:50
        if trend_analysis.get('change_pct', 0) > 5:
            action = "减仓"
            reason = "尾盘大涨5%+，适当减仓锁定利润"
        elif trend_analysis.get('change_pct', 0) < -5:
            action = "止损/减仓"
            reason = "尾盘大跌5%+，建议止损或减仓"
            urgency = "🔴 紧急"
    
    return {
        'symbol': symbol,
        'name': name,
        'shares': shares,
        'price': current_price,
        'market_value': market_value,
        'change_pct': trend_analysis.get('change_pct', 0),
        'volume_signal': volume_analysis.get('signal', '中性'),
        'volume_ratio': volume_analysis.get('volume_ratio', 1),
        'wave_position': wave_analysis.get('position', '未知'),
        'trend_strength': trend_analysis.get('trend_strength', '中性'),
        'action': action,
        'reason': reason,
        'urgency': urgency
    }


def send_feishu_alert(message, target="user:ou_efbad805767f4572e8f93ebafa8d5402"):
    """发送飞书通知"""
    import subprocess
    cmd = [
        "openclaw", "message", "send",
        "--channel", "feishu",
        "--target", target,
        "--message", message
    ]
    try:
        subprocess.run(cmd, timeout=30)
        return True
    except:
        return False


def main():
    if len(sys.argv) < 2:
        print("用法: portfolio_pro.py [morning|noon|afternoon|close]")
        return
    
    session_type = sys.argv[1]
    session_names = {
        "morning": "🌅 早盘分析 (9:30)",
        "noon": "☀️ 午盘前分析 (11:00)",
        "afternoon": "🌤️ 下午开盘分析 (13:30)",
        "close": "🌇 尾盘分析 (14:50)"
    }
    
    print("="*70)
    print(f"📊 实盘跟踪Pro - {session_names.get(session_type, '分析')}")
    print("="*70)
    print(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("="*70)
    
    ctx = init_api()
    
    results = []
    for symbol, info in PORTFOLIO.items():
        result = generate_trading_signal(symbol, info['name'], info['shares'], ctx, session_type)
        if result:
            results.append(result)
    
    # 生成报告
    report_lines = []
    report_lines.append(f"📊 实盘跟踪Pro - {session_names.get(session_type, '分析')}")
    report_lines.append(f"时间: {datetime.now().strftime('%H:%M')}")
    report_lines.append("="*50)
    
    # 紧急调仓
    urgent = [r for r in results if '紧急' in r['urgency'] or '🔴' in r['urgency']]
    if urgent:
        report_lines.append("\n🔴 紧急调仓:")
        for r in urgent:
            report_lines.append(f"  {r['name']}: {r['action']} - {r['reason']}")
    
    # 关注调仓
    normal = [r for r in results if r['action'] != '持有' and r not in urgent]
    if normal:
        report_lines.append("\n⚠️ 关注调仓:")
        for r in normal:
            report_lines.append(f"  {r['name']}: {r['action']}")
            report_lines.append(f"    现价:{r['price']:.2f} 涨跌:{r['change_pct']:+.2f}% 量比:{r['volume_ratio']:.1f}")
            report_lines.append(f"    原因: {r['reason']}")
    
    # 持仓概览
    report_lines.append("\n📈 持仓概览:")
    for r in results:
        emoji = "📈" if r['change_pct'] > 0 else "📉" if r['change_pct'] < 0 else "➡️"
        report_lines.append(f"  {emoji} {r['name']}: {r['price']:.2f} ({r['change_pct']:+.2f}%) {r['action']}")
    
    report = '\n'.join(report_lines)
    print(report)
    
    # 发送飞书
    send_feishu_alert(report)
    print("\n✅ 报告已发送至飞书")


if __name__ == '__main__':
    main()
