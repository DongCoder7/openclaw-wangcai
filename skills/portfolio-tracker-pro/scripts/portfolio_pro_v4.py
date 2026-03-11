#!/root/.openclaw/workspace/venv/bin/python3
"""
实盘跟踪Pro V4 - 缠论增强版

升级内容:
1. 缠论支撑压力位 (中枢/分型/走势类型)
2. 超详细操作建议 (含具体价位)
3. 关键价位清单 (买入/止损/止盈/关注)
4. 分批发送至个人飞书

用法:
  ./venv_runner.sh skills/portfolio-tracker-pro/scripts/portfolio_pro_v4.py [session]
"""

import pandas as pd
import numpy as np
from datetime import datetime
import sys
import os
import subprocess

sys.path.insert(0, '/root/.openclaw/workspace/venv/lib/python3.12/site-packages')

from longport.openapi import QuoteContext, Config, AdjustType, Period

# 持仓配置 (含成本价和关键心理价位)
PORTFOLIO = {
    "300750.SZ": {"name": "宁德时代", "shares": 1000, "sector": "新能源", "cost": 380.0,
                  "buy_below": 390, "stop_loss": 370, "take_profit_1": 420, "take_profit_2": 450},
    "300274.SZ": {"name": "阳光电源", "shares": 1500, "sector": "新能源", "cost": 155.0,
                  "buy_below": 165, "stop_loss": 150, "take_profit_1": 185, "take_profit_2": 200},
    "688676.SH": {"name": "金盘科技", "shares": 2000, "sector": "电力设备", "cost": 98.0,
                  "buy_below": 95, "stop_loss": 90, "take_profit_1": 105, "take_profit_2": 110},
    "600875.SH": {"name": "东方电气", "shares": 3000, "sector": "电力设备", "cost": 40.0,
                  "buy_below": 40, "stop_loss": 38, "take_profit_1": 44, "take_profit_2": 48},
    "601088.SH": {"name": "中国神华", "shares": 3000, "sector": "能源", "cost": 46.0,
                  "buy_below": 47, "stop_loss": 44, "take_profit_1": 50, "take_profit_2": 53},
    "603986.SH": {"name": "兆易创新", "shares": 1500, "sector": "半导体", "cost": 285.0,
                  "buy_below": 275, "stop_loss": 260, "take_profit_1": 300, "take_profit_2": 320},
    "688008.SH": {"name": "澜起科技", "shares": 2000, "sector": "半导体", "cost": 145.0,
                  "buy_below": 145, "stop_loss": 135, "take_profit_1": 160, "take_profit_2": 175},
    "603920.SH": {"name": "世运电路", "shares": 4000, "sector": "PCB", "cost": 57.0,
                  "buy_below": 56, "stop_loss": 53, "take_profit_1": 62, "take_profit_2": 66},
    "002463.SZ": {"name": "沪电股份", "shares": 3000, "sector": "PCB", "cost": 75.0,
                  "buy_below": 75, "stop_loss": 70, "take_profit_1": 82, "take_profit_2": 88},
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


# ========================================
# 缠论支撑压力计算
# ========================================

def calculate_zhongshu_sr(df, window=20):
    """计算中枢支撑压力 (简化版)"""
    if len(df) < window:
        return {}
    
    recent = df.tail(window)
    highs = recent['high'].values
    lows = recent['low'].values
    
    # 找价格密集区 (中枢)
    price_range = np.linspace(lows.min(), highs.max(), 20)
    time_at_level = []
    
    for level in price_range:
        mask = (lows <= level) & (highs >= level)
        time_at_level.append(mask.sum())
    
    # 中枢中心 = 停留时间最长的价位
    max_idx = np.argmax(time_at_level)
    zhongshu_center = price_range[max_idx]
    
    # 中枢上下轨 (±10%区间)
    idx_low = max(0, max_idx - 2)
    idx_high = min(len(price_range) - 1, max_idx + 2)
    zhongshu_low = price_range[idx_low]
    zhongshu_high = price_range[idx_high]
    
    return {
        'zhongshu_high': float(zhongshu_high),
        'zhongshu_center': float(zhongshu_center),
        'zhongshu_low': float(zhongshu_low),
    }


def calculate_fenxing_sr(df):
    """分型支撑压力"""
    if len(df) < 5:
        return {}
    
    highs = df['high'].values
    lows = df['low'].values
    
    # 找顶分型 (压力位)
    resistance_levels = []
    for i in range(2, len(df)-2):
        if (highs[i] > highs[i-1] and highs[i] > highs[i-2] and 
            highs[i] > highs[i+1] and highs[i] > highs[i+2]):
            resistance_levels.append(highs[i])
    
    # 找底分型 (支撑位)
    support_levels = []
    for i in range(2, len(df)-2):
        if (lows[i] < lows[i-1] and lows[i] < lows[i-2] and 
            lows[i] < lows[i+1] and lows[i] < lows[i+2]):
            support_levels.append(lows[i])
    
    result = {}
    if resistance_levels:
        result['fenxing_resistance'] = float(max(resistance_levels[-3:]))  # 最近3个
    if support_levels:
        result['fenxing_support'] = float(min(support_levels[-3:]))
    
    return result


def calculate_ma_sr(df):
    """均线支撑压力"""
    if len(df) < 60:
        return {}
    
    closes = df['close'].values
    
    return {
        'ma5': float(np.mean(closes[-5:])),
        'ma10': float(np.mean(closes[-10:])),
        'ma20': float(np.mean(closes[-20:])),
        'ma60': float(np.mean(closes[-60:])) if len(closes) >= 60 else float(closes.mean()),
    }


def calculate_pivot_sr(df):
    """枢轴点支撑压力 (经典方法)"""
    if len(df) < 2:
        return {}
    
    prev = df.iloc[-2]
    high = prev['high']
    low = prev['low']
    close = prev['close']
    
    pivot = (high + low + close) / 3
    
    r1 = 2 * pivot - low
    r2 = pivot + (high - low)
    s1 = 2 * pivot - high
    s2 = pivot - (high - low)
    
    return {
        'pivot': float(pivot),
        'r1': float(r1),
        'r2': float(r2),
        's1': float(s1),
        's2': float(s2),
    }


def calculate_all_sr(df_1min, df_5min, df_day):
    """综合计算所有支撑压力位"""
    results = {}
    
    # 各周期计算
    if df_1min is not None and len(df_1min) >= 20:
        results.update(calculate_zhongshu_sr(df_1min, 20))
        results.update(calculate_fenxing_sr(df_1min))
        results.update(calculate_ma_sr(df_1min))
    
    if df_5min is not None and len(df_5min) >= 10:
        sr_5m = calculate_zhongshu_sr(df_5min, 10)
        results['zhongshu_high_5m'] = sr_5m.get('zhongshu_high')
        results['zhongshu_low_5m'] = sr_5m.get('zhongshu_low')
    
    if df_day is not None and len(df_day) >= 5:
        results.update(calculate_pivot_sr(df_day))
    
    # 综合最强支撑/压力 (多方法验证)
    supports = [v for k, v in results.items() if 'support' in k.lower() or 'low' in k.lower() or 's1' in k or 's2' in k or 'ma' in k]
    resistances = [v for k, v in results.items() if 'resistance' in k.lower() or 'high' in k.lower() or 'r1' in k or 'r2' in k]
    
    if supports:
        results['strong_support'] = float(np.median([s for s in supports if s is not None]))
    if resistances:
        results['strong_resistance'] = float(np.median([r for r in resistances if r is not None]))
    
    return results


# ========================================
# 主分析函数
# ========================================

def analyze_stock_v4(ctx, symbol, info):
    """V4超详细分析"""
    name = info['name']
    shares = info['shares']
    sector = info.get('sector', '')
    cost = info.get('cost', 0)
    
    # 预设关键价位
    buy_below = info.get('buy_below', 0)
    stop_loss = info.get('stop_loss', 0)
    take_profit_1 = info.get('take_profit_1', 0)
    take_profit_2 = info.get('take_profit_2', 0)
    
    print(f"\n  分析 {name} ({symbol})...")
    
    # 获取多周期数据
    df_1min = get_data(ctx, symbol, Period.Min_1, 240)
    df_5min = get_data(ctx, symbol, Period.Min_5, 48)
    df_day = get_data(ctx, symbol, Period.Day, 20)
    
    if df_1min is None or len(df_1min) < 5:
        return None
    
    # ===== 基础数据 =====
    latest = df_1min.iloc[-1]
    current = latest['close']
    prev_close = df_day.iloc[-1]['close'] if df_day is not None and len(df_day) > 0 else current
    
    # 盈亏计算
    pnl = (current - cost) * shares if cost > 0 else 0
    pnl_pct = (current - cost) / cost * 100 if cost > 0 else 0
    market_value = current * shares
    
    # 当日数据
    today_data = df_1min[df_1min['datetime'].dt.date == latest['datetime'].date()]
    if len(today_data) == 0:
        today_data = df_1min.tail(60)
    
    today_open = today_data.iloc[0]['open']
    today_high = today_data['high'].max()
    today_low = today_data['low'].min()
    today_vol = today_data['volume'].sum()
    
    change_pct = (current - prev_close) / prev_close * 100
    today_change_pct = (current - today_open) / today_open * 100
    
    # ===== 缠论支撑压力计算 =====
    sr_levels = calculate_all_sr(df_1min, df_5min, df_day)
    
    # ===== 量能分析 =====
    recent_vol = df_1min.tail(20)['volume'].mean()
    older_vol = df_1min.tail(60).head(40)['volume'].mean()
    volume_ratio = recent_vol / older_vol if older_vol > 0 else 1
    
    buy_vol = today_data[today_data['close'] > today_data['open']]['volume'].sum()
    sell_vol = today_data[today_data['close'] < today_data['open']]['volume'].sum()
    net_flow = buy_vol - sell_vol
    
    # ===== 技术指标 =====
    ma5 = df_1min['close'].tail(5).mean()
    ma10 = df_1min['close'].tail(10).mean()
    ma20 = df_1min['close'].tail(20).mean()
    
    # ===== 生成详细报告 =====
    report = []
    report.append(f"📊 {name} ({symbol}) - {sector}")
    report.append(f"⏰ 数据时间: {latest['datetime'].strftime('%H:%M:%S')}")
    report.append("")
    
    # 价格与盈亏
    report.append("【价格与盈亏】")
    report.append(f"  当前价: {current:.2f}元")
    report.append(f"  涨跌幅: {change_pct:+.2f}% | 今日: {today_change_pct:+.2f}%")
    report.append(f"  今日区间: {today_low:.2f} - {today_high:.2f}")
    report.append(f"  持仓: {shares}股 = {market_value/10000:.2f}万")
    if cost > 0:
        emoji = "📈" if pnl >= 0 else "📉"
        report.append(f"  {emoji} 盈亏: {pnl:+.0f}元 ({pnl_pct:+.2f}%)")
    report.append("")
    
    # 缠论支撑压力位
    report.append("【缠论支撑压力位】")
    if 'zhongshu_center' in sr_levels:
        report.append(f"  中枢区间: [{sr_levels.get('zhongshu_low', 0):.2f}, {sr_levels.get('zhongshu_high', 0):.2f}]")
        report.append(f"  中枢中心: {sr_levels['zhongshu_center']:.2f}元")
    if 'fenxing_support' in sr_levels:
        report.append(f"  分型支撑: {sr_levels['fenxing_support']:.2f}元")
    if 'fenxing_resistance' in sr_levels:
        report.append(f"  分型压力: {sr_levels['fenxing_resistance']:.2f}元")
    if 'strong_support' in sr_levels:
        report.append(f"  ⚡ 强支撑: {sr_levels['strong_support']:.2f}元 (多方法验证)")
    if 'strong_resistance' in sr_levels:
        report.append(f"  ⚡ 强压力: {sr_levels['strong_resistance']:.2f}元 (多方法验证)")
    report.append("")
    
    # 均线支撑压力
    report.append("【均线支撑压力】")
    report.append(f"  MA5:  {ma5:.2f}元 {'📈支撑' if current > ma5 else '📉压力'}")
    report.append(f"  MA10: {ma10:.2f}元 {'📈支撑' if current > ma10 else '📉压力'}")
    report.append(f"  MA20: {ma20:.2f}元 {'📈支撑' if current > ma20 else '📉压力'}")
    report.append("")
    
    # 量能
    report.append("【量能分析】")
    vol_emoji = "⚡放量" if volume_ratio > 1.5 else "💧缩量" if volume_ratio < 0.8 else "➡️正常"
    report.append(f"  量比: {volume_ratio:.2f} {vol_emoji}")
    flow_emoji = "📈流入" if net_flow > 0 else "📉流出"
    report.append(f"  资金: {flow_emoji} {abs(net_flow)/10000:.0f}万手")
    report.append("")
    
    # ===== 关键价位清单 (核心!) =====
    report.append("【关键价位清单】")
    report.append("")
    
    # 买入价位
    report.append("💰 买入价位:")
    if buy_below > 0:
        distance = (current - buy_below) / buy_below * 100
        status = "✅已跌破，可买入" if current <= buy_below else f"还需跌{distance:.1f}%"
        report.append(f"  建议买入: ≤{buy_below:.2f}元 ({status})")
    if 'strong_support' in sr_levels:
        report.append(f"  缠论支撑: {sr_levels['strong_support']:.2f}元 (回调至此关注)")
    if 's1' in sr_levels:
        report.append(f"  枢轴S1: {sr_levels['s1']:.2f}元")
    report.append("")
    
    # 止损价位
    report.append("🛑 止损价位:")
    if stop_loss > 0:
        distance = (current - stop_loss) / stop_loss * 100
        status = "🔴已触发，立即止损" if current <= stop_loss else f"还有{distance:.1f}%空间"
        report.append(f"  预设止损: {stop_loss:.2f}元 ({status})")
    if 's2' in sr_levels:
        report.append(f"  枢轴S2: {sr_levels['s2']:.2f}元 (强支撑跌破则清仓)")
    if 'fenxing_support' in sr_levels:
        report.append(f"  分型低点: {sr_levels['fenxing_support']:.2f}元")
    report.append("")
    
    # 止盈价位
    report.append("✅ 止盈价位:")
    if take_profit_1 > 0:
        distance = (take_profit_1 - current) / current * 100
        status = "✅已触及，可考虑减仓" if current >= take_profit_1 else f"还需涨{distance:.1f}%"
        report.append(f"  第一止盈: {take_profit_1:.2f}元 ({status})")
    if take_profit_2 > 0:
        distance = (take_profit_2 - current) / current * 100
        status = "✅已触及，建议清仓" if current >= take_profit_2 else f"还需涨{distance:.1f}%"
        report.append(f"  第二止盈: {take_profit_2:.2f}元 ({status})")
    if 'strong_resistance' in sr_levels:
        report.append(f"  强压力位: {sr_levels['strong_resistance']:.2f}元 (突破后可持有)")
    report.append("")
    
    # 关注价位
    report.append("👀 关注价位 (实时监控):")
    if 'zhongshu_high' in sr_levels:
        status = "已突破✅" if current > sr_levels['zhongshu_high'] else "未突破"
        report.append(f"  中枢上轨: {sr_levels['zhongshu_high']:.2f}元 ({status}) - 突破加仓")
    if 'zhongshu_low' in sr_levels:
        status = "已跌破🔴" if current < sr_levels['zhongshu_low'] else "未跌破"
        report.append(f"  中枢下轨: {sr_levels['zhongshu_low']:.2f}元 ({status}) - 跌破减仓")
    if 'r1' in sr_levels:
        report.append(f"  枢轴R1: {sr_levels['r1']:.2f}元 - 短期压力")
    if 'pivot' in sr_levels:
        pivot_pos = "上方📈" if current > sr_levels['pivot'] else "下方📉"
        report.append(f"  枢轴点: {sr_levels['pivot']:.2f}元 (当前{pivot_pos})")
    report.append("")
    
    # ===== 操作建议 (核心!) =====
    report.append("【操作建议】")
    report.append("")
    
    # 综合评分
    score = 0
    reasons = []
    
    if current > ma5 > ma10:
        score += 1
        reasons.append("均线多头排列")
    elif current < ma5 < ma10:
        score -= 1
        reasons.append("均线空头排列")
    
    if volume_ratio > 1.5 and change_pct > 0:
        score += 1
        reasons.append("放量上涨")
    elif volume_ratio > 1.5 and change_pct < 0:
        score -= 1
        reasons.append("放量下跌")
    
    if net_flow > 0:
        score += 0.5
        reasons.append("资金流入")
    else:
        score -= 0.5
        reasons.append("资金流出")
    
    # 根据价格位置调整
    if stop_loss > 0 and current <= stop_loss * 1.02:
        score -= 2
        reasons.append("接近止损位")
    
    if take_profit_1 > 0 and current >= take_profit_1:
        score += 0.5
        reasons.append("已达第一止盈")
    
    # 生成操作建议
    report.append(f"  技术评分: {score:.1f}分")
    report.append(f"  判断依据: {'; '.join(reasons)}")
    report.append("")
    
    # 具体操作
    if current <= stop_loss:
        action = "🔴 立即止损"
        detail = f"价格已跌破止损位{stop_loss:.2f}元，立即清仓"
        next_steps = [f"1. 立即以市价卖出", f"2. 卖出价位约{current:.2f}元", f"3. 预计亏损{(current-cost)/cost*100:.1f}%"]
    elif score >= 1.5:
        action = "✅ 加仓/持有"
        detail = "技术面强势，可持有或逢低加仓"
        next_steps = [f"1. 回踩{sr_levels.get('strong_support', ma10):.2f}元可加仓", 
                     f"2. 突破{sr_levels.get('strong_resistance', take_profit_1):.2f}元继续加仓",
                     f"3. 跌破{stop_loss:.2f}元止损"]
    elif score >= 0.5:
        action = "➡️ 持有观望"
        detail = "趋势尚可，继续持有观察"
        next_steps = [f"1. 关注能否突破{sr_levels.get('strong_resistance', 0):.2f}元",
                     f"2. 跌破{sr_levels.get('strong_support', stop_loss):.2f}元减仓",
                     f"3. 达到{take_profit_1:.2f}元减仓1/3"]
    elif score >= -0.5:
        action = "⏸️ 减仓观望"
        detail = "方向不明，建议减仓避险"
        next_steps = [f"1. 减仓1/3-1/2",
                     f"2. 等待回调至{sr_levels.get('strong_support', buy_below):.2f}元",
                     f"3. 跌破{stop_loss:.2f}元清仓"]
    elif score >= -1.5:
        action = "⚠️ 减仓避险"
        detail = "走弱信号明显，减仓保护本金"
        next_steps = [f"1. 立即减仓至半仓以下",
                     f"2. 反弹至{ma10:.2f}元清仓",
                     f"3. 严格止损{stop_loss:.2f}元"]
    else:
        action = "🔻 清仓止损"
        detail = "技术面恶化，建议清仓"
        next_steps = [f"1. 立即清仓", 
                     f"2. 卖出价位{current:.2f}元",
                     f"3. 下次买入点{buy_below:.2f}元以下"]
    
    report.append(f"  🎯 操作建议: {action}")
    report.append(f"  📝 详细说明: {detail}")
    report.append("")
    report.append("  📋 下一步操作:")
    for step in next_steps:
        report.append(f"    {step}")
    
    report.append("")
    report.append("-" * 50)
    
    return '\n'.join(report)


def main():
    if len(sys.argv) < 2:
        print("用法: portfolio_pro_v4.py [morning|noon|afternoon|close|all]")
        return
    
    session = sys.argv[1]
    session_names = {
        "morning": "🌅 早盘分析 (缠论增强版)",
        "noon": "☀️ 午盘分析 (缠论增强版)",
        "afternoon": "🌤️ 下午分析 (缠论增强版)",
        "close": "🌇 尾盘分析 (缠论增强版)",
        "all": "📊 完整持仓分析 (缠论增强版)"
    }
    
    print(f"开始 {session_names.get(session)} ...")
    print(f"目标: 个人飞书 ({FEISHU_USER})")
    print(f"特点: 缠论支撑压力 + 详细操作建议 + 关键价位清单")
    
    ctx = init_api()
    
    # 发送报告头
    header = f"📊 实盘跟踪Pro V4 - {session_names.get(session)}\n📚 缠论支撑压力 + 详细操作建议\n⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n{'='*50}\n\n开始发送详细分析 (每只1条消息)..."
    send_feishu(header)
    
    # 逐个分析并发送
    for symbol, info in PORTFOLIO.items():
        report = analyze_stock_v4(ctx, symbol, info)
        if report:
            send_feishu(report)
            print(f"  ✅ {info['name']} 分析已发送")
        else:
            error_msg = f"❌ {info['name']} ({symbol}) 分析失败\n"
            send_feishu(error_msg)
    
    # 发送结束语
    footer = f"{'='*50}\n✅ 全部 {len(PORTFOLIO)} 只股票分析完成\n📚 缠论支撑压力计算方法见: study/chanlun/\n⏰ 分析时间: {datetime.now().strftime('%H:%M:%S')}"
    send_feishu(footer)
    
    print(f"\n✅ 全部完成，已发送至个人飞书")


if __name__ == '__main__':
    main()
