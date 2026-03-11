#!/root/.openclaw/workspace/venv/bin/python3
"""
实盘跟踪Pro V3 - 超详细分钟级实时分析

每只股票包含:
1. 实时价格/涨跌幅/振幅
2. 分钟级技术指标 (MA5/MA10/布林带)
3. 当日分时走势分析 (开盘/最高/最低/当前)
4. 量价关系 (量比/资金流入流出)
5. 支撑压力位 (当日+近期)
6. 实时操作建议

如果报告太长，自动分批发送
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import sys
import os
import json
import subprocess

sys.path.insert(0, '/root/.openclaw/workspace/venv/lib/python3.12/site-packages')

from longport.openapi import QuoteContext, Config, AdjustType, Period

# 持仓配置
PORTFOLIO = {
    "300750.SZ": {"name": "宁德时代", "shares": 1000, "sector": "新能源", "cost": 380.0},
    "300274.SZ": {"name": "阳光电源", "shares": 1500, "sector": "新能源", "cost": 155.0},
    "688676.SH": {"name": "金盘科技", "shares": 2000, "sector": "电力设备", "cost": 98.0},
    "600875.SH": {"name": "东方电气", "shares": 3000, "sector": "电力设备", "cost": 40.0},
    "601088.SH": {"name": "中国神华", "shares": 3000, "sector": "能源", "cost": 46.0},
    "603986.SH": {"name": "兆易创新", "shares": 1500, "sector": "半导体", "cost": 285.0},
    "688008.SH": {"name": "澜起科技", "shares": 2000, "sector": "半导体", "cost": 145.0},
    "603920.SH": {"name": "世运电路", "shares": 4000, "sector": "PCB", "cost": 57.0},
    "002463.SZ": {"name": "沪电股份", "shares": 3000, "sector": "PCB", "cost": 75.0},
}

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


def analyze_stock_detailed(ctx, symbol, info):
    """超详细单股票分析"""
    name = info['name']
    shares = info['shares']
    sector = info.get('sector', '')
    cost = info.get('cost', 0)
    
    print(f"\n  分析 {name} ({symbol})...")
    
    # 获取多周期数据
    df_1min = get_data(ctx, symbol, Period.Min_1, 240)   # 4小时
    df_5min = get_data(ctx, symbol, Period.Min_5, 48)    # 4小时
    df_day = get_data(ctx, symbol, Period.Day, 20)       # 20日
    
    if df_1min is None or len(df_1min) < 5:
        return None
    
    # ===== 基础数据 =====
    latest = df_1min.iloc[-1]
    prev_close = df_day.iloc[-1]['close'] if df_day is not None else latest['close']
    current = latest['close']
    
    # 计算持仓盈亏
    pnl = (current - cost) * shares if cost > 0 else 0
    pnl_pct = (current - cost) / cost * 100 if cost > 0 else 0
    market_value = current * shares
    
    # 当日数据
    today_data = df_1min[df_1min['datetime'].dt.date == latest['datetime'].date()]
    if len(today_data) == 0:
        today_data = df_1min.tail(60)  # 取最近60分钟
    
    today_open = today_data.iloc[0]['open']
    today_high = today_data['high'].max()
    today_low = today_data['low'].min()
    today_vol = today_data['volume'].sum()
    
    # 涨跌幅
    change_pct = (current - prev_close) / prev_close * 100
    today_change_pct = (current - today_open) / today_open * 100
    amplitude = (today_high - today_low) / today_open * 100
    
    # ===== 分钟级技术指标 =====
    # MA5/MA10 (1分钟)
    ma5_1m = df_1min['close'].tail(5).mean()
    ma10_1m = df_1min['close'].tail(10).mean()
    ma20_1m = df_1min['close'].tail(20).mean()
    
    # MA5/MA10 (5分钟)
    ma5_5m = df_5min['close'].tail(5).mean() if df_5min is not None else 0
    ma10_5m = df_5min['close'].tail(10).mean() if df_5min is not None else 0
    
    # 布林带 (5分钟)
    if df_5min is not None and len(df_5min) >= 20:
        bb_mid = df_5min['close'].tail(20).mean()
        bb_std = df_5min['close'].tail(20).std()
        bb_upper = bb_mid + 2 * bb_std
        bb_lower = bb_mid - 2 * bb_std
    else:
        bb_upper = bb_lower = 0
    
    # ===== 量能分析 =====
    # 量比
    recent_vol = df_1min.tail(20)['volume'].mean()
    older_vol = df_1min.tail(60).head(40)['volume'].mean()
    volume_ratio = recent_vol / older_vol if older_vol > 0 else 1
    
    # 资金流入流出
    buy_vol = today_data[today_data['close'] > today_data['open']]['volume'].sum()
    sell_vol = today_data[today_data['close'] < today_data['open']]['volume'].sum()
    net_flow = buy_vol - sell_vol
    
    # ===== 支撑压力位 =====
    # 当日支撑压力
    day_support = today_low
    day_resistance = today_high
    
    # 近期支撑压力 (用5分钟数据)
    if df_5min is not None and len(df_5min) >= 20:
        recent_5m = df_5min.tail(20)
        near_support = recent_5m['low'].min()
        near_resistance = recent_5m['high'].max()
    else:
        near_support = near_resistance = 0
    
    # 更远期支撑 (用日线)
    if df_day is not None and len(df_day) >= 5:
        week_low = df_day.tail(5)['low'].min()
        week_high = df_day.tail(5)['high'].max()
    else:
        week_low = week_high = 0
    
    # ===== 生成报告 =====
    report = []
    report.append(f"📊 {name} ({symbol}) - {sector}")
    report.append(f"⏰ 数据时间: {latest['datetime'].strftime('%H:%M:%S')}")
    report.append("")
    
    # 价格与盈亏
    report.append("【价格与盈亏】")
    report.append(f"  当前价: {current:.2f}元")
    report.append(f"  涨跌幅: {change_pct:+.2f}% (较昨日)")
    report.append(f"  今日涨跌: {today_change_pct:+.2f}% (较开盘)")
    report.append(f"  今日振幅: {amplitude:.2f}%")
    report.append(f"  持仓: {shares}股 | 市值: {market_value/10000:.2f}万")
    if cost > 0:
        pnl_emoji = "📈" if pnl >= 0 else "📉"
        report.append(f"  {pnl_emoji} 盈亏: {pnl:+.0f}元 ({pnl_pct:+.2f}%)")
    report.append("")
    
    # 当日走势
    report.append("【当日分时走势】")
    report.append(f"  开盘: {today_open:.2f}元")
    report.append(f"  最高: {today_high:.2f}元 (+{(today_high-today_open)/today_open*100:.2f}%)")
    report.append(f"  最低: {today_low:.2f}元 ({(today_low-today_open)/today_open*100:.2f}%)")
    report.append(f"  当前: {current:.2f}元")
    
    # 位置判断
    position = (current - today_low) / (today_high - today_low) * 100 if today_high > today_low else 50
    report.append(f"  位置: 当日区间{position:.0f}%处 {'(高位⚠️)' if position > 70 else '(低位💡)' if position < 30 else '(中位)'}")
    report.append("")
    
    # 分钟级技术指标
    report.append("【分钟级技术指标】")
    report.append(f"  1分钟MA5/MA10/MA20: {ma5_1m:.2f} / {ma10_1m:.2f} / {ma20_1m:.2f}")
    
    # 趋势判断
    trend_1m = "上涨" if current > ma5_1m > ma10_1m else "下跌" if current < ma5_1m < ma10_1m else "震荡"
    report.append(f"  1分钟趋势: {trend_1m}")
    
    if df_5min is not None:
        report.append(f"  5分钟MA5/MA10: {ma5_5m:.2f} / {ma10_5m:.2f}")
        trend_5m = "上涨" if current > ma5_5m > ma10_5m else "下跌" if current < ma5_5m < ma10_5m else "震荡"
        report.append(f"  5分钟趋势: {trend_5m}")
    
    if bb_upper > 0:
        bb_pos = "上轨附近⚠️" if current > bb_upper * 0.98 else "下轨附近💡" if current < bb_lower * 1.02 else "中轨"
        report.append(f"  布林带(5m): [{bb_lower:.2f}, {bb_upper:.2f}] - 当前{bb_pos}")
    report.append("")
    
    # 量能分析
    report.append("【量能分析】")
    report.append(f"  今日总成交量: {today_vol/10000:.0f}万手")
    report.append(f"  量比: {volume_ratio:.2f} {'(放量⚡)' if volume_ratio > 1.5 else '(缩量)' if volume_ratio < 0.8 else '(正常)'}")
    report.append(f"  主动买入: {buy_vol/10000:.0f}万手")
    report.append(f"  主动卖出: {sell_vol/10000:.0f}万手")
    flow_emoji = "📈流入" if net_flow > 0 else "📉流出"
    report.append(f"  资金净{flow_emoji}: {abs(net_flow)/10000:.0f}万手")
    report.append("")
    
    # 支撑压力位
    report.append("【支撑压力位】")
    report.append(f"  当日压力: {day_resistance:.2f}元 (今日高点)")
    report.append(f"  当日支撑: {day_support:.2f}元 (今日低点)")
    if near_resistance > 0:
        report.append(f"  近期压力: {near_resistance:.2f}元 (20根5分钟线)")
        report.append(f"  近期支撑: {near_support:.2f}元 (20根5分钟线)")
    if week_high > 0:
        report.append(f"  周内压力: {week_high:.2f}元 (5日高点)")
        report.append(f"  周内支撑: {week_low:.2f}元 (5日低点)")
    report.append("")
    
    # 综合判断与建议
    report.append("【综合判断与建议】")
    
    # 评分逻辑
    score = 0
    reasons = []
    
    if trend_1m == "上涨":
        score += 1
        reasons.append("1分钟趋势向上")
    elif trend_1m == "下跌":
        score -= 1
        reasons.append("1分钟趋势向下")
    
    if volume_ratio > 1.5 and change_pct > 0:
        score += 1
        reasons.append("放量上涨")
    elif volume_ratio > 1.5 and change_pct < 0:
        score -= 1
        reasons.append("放量下跌")
    
    if net_flow > 0:
        score += 0.5
        reasons.append("资金净流入")
    elif net_flow < 0:
        score -= 0.5
        reasons.append("资金净流出")
    
    if position > 80:
        score -= 0.5
        reasons.append("处于当日高位")
    elif position < 20:
        score += 0.5
        reasons.append("处于当日低位")
    
    # 建议
    if score >= 1.5:
        action = "✅ 持有/加仓"
        detail = "强势，可逢低加仓"
    elif score >= 0.5:
        action = "➡️ 持有"
        detail = "趋势尚可，继续持有"
    elif score >= -0.5:
        action = "⏸️ 观望"
        detail = "方向不明，等待信号"
    elif score >= -1.5:
        action = "⚠️ 减仓"
        detail = "走弱，建议减仓"
    else:
        action = "🔻 止损"
        detail = "强势下跌，考虑止损"
    
    report.append(f"  技术评分: {score:.1f}分")
    report.append(f"  判断依据: {'; '.join(reasons)}")
    report.append("")
    report.append(f"  🎯 操作建议: {action}")
    report.append(f"  📝 详细说明: {detail}")
    
    # 关键价位提醒
    if current < near_support * 1.02:
        report.append(f"  ⚠️ 跌破近期支撑{near_support:.2f}元，注意风险")
    if current > near_resistance * 0.98:
        report.append(f"  ⚠️ 接近近期压力{near_resistance:.2f}元，关注能否突破")
    
    report.append("")
    report.append("-" * 50)
    
    return '\n'.join(report)


def main():
    if len(sys.argv) < 2:
        print("用法: portfolio_pro_v3.py [morning|noon|afternoon|close|all]")
        return
    
    session = sys.argv[1]
    session_names = {
        "morning": "🌅 早盘分析 (9:30)",
        "noon": "☀️ 午盘分析 (11:00)",
        "afternoon": "🌤️ 下午分析 (13:30)",
        "close": "🌇 尾盘分析 (14:50)",
        "all": "📊 完整持仓分析"
    }
    
    print(f"开始 {session_names.get(session)} ...")
    print(f"目标: 个人飞书 ({FEISHU_USER})")
    
    ctx = init_api()
    
    # 发送报告头
    header = f"📊 实盘跟踪Pro V3 - {session_names.get(session)}\n⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n{'='*50}\n\n开始发送详细分析..."
    send_feishu(header)
    
    # 逐个分析并发送
    for symbol, info in PORTFOLIO.items():
        report = analyze_stock_detailed(ctx, symbol, info)
        if report:
            send_feishu(report)
            print(f"  ✅ {info['name']} 分析已发送")
        else:
            error_msg = f"❌ {info['name']} ({symbol}) 分析失败\n"
            send_feishu(error_msg)
    
    # 发送结束语
    footer = f"{'='*50}\n✅ 全部 {len(PORTFOLIO)} 只股票分析完成\n📊 数据来源: 长桥API实时分钟数据\n⏰ 分析时间: {datetime.now().strftime('%H:%M:%S')}"
    send_feishu(footer)
    
    print(f"\n✅ 全部完成，已发送至个人飞书")


if __name__ == '__main__':
    main()
