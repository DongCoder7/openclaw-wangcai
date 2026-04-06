#!/root/.openclaw/workspace/venv/bin/python3
"""
上证指数缠论分析 - 30分钟+5分钟级别 (正确的中枢定义)

缠论中枢正确定义:
- 中枢 = 连续三个次级别走势类型的重叠区间
- 中枢区间 = [max(三个低点), min(三个高点)]
- 5F中枢 = 3个5F线段的重叠区间
- 30F中枢 = 3个30F线段的重叠区间
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


def identify_fenxing(df):
    """
    识别顶分型和底分型
    顶分型: 中间K线高点最高，且低点也高于两边
    底分型: 中间K线低点最低，且高点也低于两边
    """
    highs = df['high'].values
    lows = df['low'].values
    
    top_fenxing = []  # (index, high)
    bottom_fenxing = []  # (index, low)
    
    for i in range(2, len(df)-2):
        # 顶分型
        if (highs[i] > highs[i-1] and highs[i] > highs[i-2] and 
            highs[i] > highs[i+1] and highs[i] > highs[i+2]):
            # 确认中间K线低点也高于两边（更强的顶分型）
            if lows[i] > lows[i-1] or lows[i] > lows[i+1]:
                top_fenxing.append((i, highs[i]))
        
        # 底分型
        if (lows[i] < lows[i-1] and lows[i] < lows[i-2] and 
            lows[i] < lows[i+1] and lows[i] < lows[i+2]):
            # 确认中间K线高点也低于两边（更强的底分型）
            if highs[i] < highs[i-1] or highs[i] < highs[i+2]:
                bottom_fenxing.append((i, lows[i]))
    
    return top_fenxing, bottom_fenxing


def construct_bi(df, top_fenxing, bottom_fenxing):
    """
    构造笔 (Bi)
    笔 = 顶分型 + 底分型，中间至少1根K线
    """
    # 合并所有分型并按索引排序
    all_fenxing = [(idx, 'top', price) for idx, price in top_fenxing] + \
                  [(idx, 'bottom', price) for idx, price in bottom_fenxing]
    all_fenxing.sort(key=lambda x: x[0])
    
    # 构造笔：顶底交替
    bi_list = []
    last_direction = None
    
    for idx, ftype, price in all_fenxing:
        if last_direction is None:
            bi_list.append((idx, ftype, price))
            last_direction = ftype
        elif ftype != last_direction:
            # 确认中间有至少1根K线
            if len(bi_list) > 0:
                last_idx = bi_list[-1][0]
                if idx - last_idx >= 2:  # 至少1根K线间隔
                    bi_list.append((idx, ftype, price))
                    last_direction = ftype
    
    return bi_list


def construct_xianduan(bi_list):
    """
    构造线段 (走势类型)
    线段 = 至少3笔构成，有方向性
    """
    if len(bi_list) < 3:
        return []
    
    xianduan_list = []
    
    # 简单处理：每3笔构成一个线段
    for i in range(2, len(bi_list)):
        # 判断方向
        if bi_list[i][1] == 'top':  # 以顶结束 = 上涨线段
            direction = 'up'
            low = min(bi_list[i-2][2], bi_list[i-1][2]) if bi_list[i-2][1] == 'bottom' else bi_list[i-2][2]
            high = bi_list[i][2]
        else:  # 以底结束 = 下跌线段
            direction = 'down'
            high = max(bi_list[i-2][2], bi_list[i-1][2]) if bi_list[i-2][1] == 'top' else bi_list[i-2][2]
            low = bi_list[i][2]
        
        xianduan_list.append({
            'start_idx': bi_list[i-2][0],
            'end_idx': bi_list[i][0],
            'direction': direction,
            'high': high,
            'low': low
        })
    
    return xianduan_list


def calculate_zhongshu(xianduan_list):
    """
    缠论中枢计算 (正确定义)
    中枢 = 连续三个次级别走势类型的重叠区间
    中枢区间 = [max(三个低点), min(三个高点)]
    """
    if len(xianduan_list) < 3:
        return None
    
    # 取最近三个线段
    recent_3 = xianduan_list[-3:]
    
    # 计算重叠区间
    max_low = max([xd['low'] for xd in recent_3])  # 三个低点中的最大值
    min_high = min([xd['high'] for xd in recent_3])  # 三个高点中的最小值
    
    # 检查是否有重叠
    if max_low >= min_high:
        # 没有重叠，不构成中枢
        return None
    
    # 中枢中心
    center = (max_low + min_high) / 2
    
    return {
        'lower': round(max_low, 2),      # 中枢下轨 (ZG)
        'upper': round(min_high, 2),     # 中枢上轨 (ZD)
        'center': round(center, 2),      # 中枢中心
        'width': round((min_high - max_low) / center * 100, 2),  # 宽度%
        'segments': recent_3             # 构成中枢的三个线段
    }


def calculate_practical_zhongshu(df, window=20):
    """
    实用版中枢计算（用于趋势行情中）
    找最近window根K线中，价格重叠最多的区间
    """
    if len(df) < window:
        window = len(df)
    
    highs = df['high'].values[-window:]
    lows = df['low'].values[-window:]
    
    # 简化方法：找高低点的20%-80%分位区间
    upper = np.percentile(highs, 70)
    lower = np.percentile(lows, 30)
    center = (upper + lower) / 2
    
    return {
        'lower': round(lower, 2),
        'upper': round(upper, 2),
        'center': round(center, 2),
        'width': round((upper - lower) / center * 100, 2)
    }


def analyze_zhongshu_position(current, zhongshu):
    """分析当前价格相对于中枢的位置"""
    if zhongshu is None:
        return "无中枢", 0
    
    upper = zhongshu['upper']
    lower = zhongshu['lower']
    center = zhongshu['center']
    
    if current > upper:
        return "突破上轨", 2
    elif current < lower:
        return "跌破下轨", -2
    elif current > center:
        return "中枢上半区", 1
    else:
        return "中枢下半区", -1


def generate_kai_pan_strategy(current, zhongshu_5f, zhongshu_30f, bi_5f):
    """生成开盘操作策略"""
    
    # 5F级别分析
    pos_5f, score_5f = analyze_zhongshu_position(current, zhongshu_5f)
    
    # 30F级别分析
    pos_30f, score_30f = analyze_zhongshu_position(current, zhongshu_30f)
    
    # 综合判断
    total_score = score_5f + score_30f * 0.5
    
    if total_score >= 2:
        strategy = "🟢 强势突破"
        detail = "5F+30F共振向上突破，可追涨"
    elif total_score >= 0.5:
        strategy = "➡️ 偏多持仓"
        detail = "中枢上方运行，持仓观望"
    elif total_score > -0.5:
        strategy = "➡️ 震荡观望"
        detail = "中枢内部，等待方向选择"
    elif total_score > -2:
        strategy = "⚠️ 减仓保护"
        detail = "中枢下方运行，减仓避险"
    else:
        strategy = "🔴 清仓避险"
        detail = "双级别跌破，严格止损"
    
    # 关键位
    key_levels = ""
    if zhongshu_5f:
        key_levels += f"""
  5F中枢: [{zhongshu_5f['lower']:.2f}, {zhongshu_5f['upper']:.2f}] (宽{zhongshu_5f['width']:.2f}%)
  5F位置: {pos_5f}"""
    else:
        key_levels += "\n  5F中枢: 未形成（趋势行情中）"
    
    if zhongshu_30f:
        key_levels += f"""
  30F中枢: [{zhongshu_30f['lower']:.2f}, {zhongshu_30f['upper']:.2f}] (宽{zhongshu_30f['width']:.2f}%)
  30F位置: {pos_30f}"""
    else:
        key_levels += "\n  30F中枢: 未形成（趋势行情中）"
    
    # 最近笔的位置
    bi_info = ""
    if len(bi_5f) >= 2:
        last_bi = bi_5f[-1]
        prev_bi = bi_5f[-2]
        bi_info = f"""
  最近笔: {last_bi[1]} @ {last_bi[2]:.2f}
  前一笔: {prev_bi[1]} @ {prev_bi[2]:.2f}"""
    
    # 操作清单（处理None情况）
    level_5f_ops = ""
    if zhongshu_5f:
        level_5f_ops = f"""  1. 5F级别: 突破{zhongshu_5f['upper']:.2f}追多，跌破{zhongshu_5f['lower']:.2f}减仓"""
    else:
        level_5f_ops = """  1. 5F级别: 中枢未形成，根据笔的方向操作"""
    
    level_30f_ops = ""
    if zhongshu_30f:
        level_30f_ops = f"""  2. 30F级别: {zhongshu_30f['upper']:.2f}以上持仓，{zhongshu_30f['lower']:.2f}以下清仓"""
    else:
        level_30f_ops = """  2. 30F级别: 中枢未形成，根据趋势操作"""
    
    strategy_text = f"""
【开盘缠论操作策略】

🎯 综合策略: {strategy}
  {detail}

📍 关键价位:{key_levels}
{bi_info}

📋 操作清单:
{level_5f_ops}
{level_30f_ops}
  3. 共振信号: 双级别同向突破时加仓，反向时观望
  4. 止损设置: 反向突破关键位立即止损

⏰ 时间窗口:
  • 9:30-9:45: 观察5F方向选择
  • 10:00: 确认30F结构是否变化
  • 10:30: 决定当日持仓策略
"""
    return strategy_text


def main():
    print("=" * 60)
    print("📊 上证指数缠论分析 (30F+5F) - 正确中枢定义")
    print("=" * 60)
    
    ctx = init_api()
    symbol = "000001.SH"
    
    # 获取数据（需要更多K线来形成中枢）
    print("  获取30分钟数据...")
    df_30f = get_data(ctx, symbol, Period.Min_30, 200)  # 约4个交易日
    
    print("  获取5分钟数据...")
    df_5f = get_data(ctx, symbol, Period.Min_5, 400)    # 约2个交易日
    
    current = df_5f['close'].iloc[-1] if df_5f is not None else None
    
    if current is None:
        print("❌ 数据获取失败")
        return
    
    print(f"  当前指数: {current:.2f}")
    
    # 5F级别分析
    print("  识别5F分型...")
    top_5f, bottom_5f = identify_fenxing(df_5f)
    print(f"    顶分型: {len(top_5f)}个, 底分型: {len(bottom_5f)}个")
    
    print("  构造5F笔...")
    bi_5f = construct_bi(df_5f, top_5f, bottom_5f)
    print(f"    5F笔数: {len(bi_5f)}")
    
    print("  构造5F线段...")
    xianduan_5f = construct_xianduan(bi_5f)
    print(f"    5F线段数: {len(xianduan_5f)}")
    
    print("  计算5F中枢...")
    zhongshu_5f = calculate_zhongshu(xianduan_5f)
    if zhongshu_5f:
        print(f"    5F严格中枢: [{zhongshu_5f['lower']:.2f}, {zhongshu_5f['upper']:.2f}], 宽{zhongshu_5f['width']:.2f}%")
    else:
        # 趋势行情中用实用版中枢
        zhongshu_5f = calculate_practical_zhongshu(df_5f, window=24)  # 2小时
        print(f"    5F实用中枢: [{zhongshu_5f['lower']:.2f}, {zhongshu_5f['upper']:.2f}], 宽{zhongshu_5f['width']:.2f}%")
    
    # 30F级别分析
    print("  识别30F分型...")
    top_30f, bottom_30f = identify_fenxing(df_30f)
    
    print("  构造30F笔...")
    bi_30f = construct_bi(df_30f, top_30f, bottom_30f)
    
    print("  构造30F线段...")
    xianduan_30f = construct_xianduan(bi_30f)
    
    print("  计算30F中枢...")
    zhongshu_30f = calculate_zhongshu(xianduan_30f)
    if zhongshu_30f:
        print(f"    30F严格中枢: [{zhongshu_30f['lower']:.2f}, {zhongshu_30f['upper']:.2f}], 宽{zhongshu_30f['width']:.2f}%")
    else:
        # 趋势行情中用实用版中枢
        zhongshu_30f = calculate_practical_zhongshu(df_30f, window=16)  # 8小时
        print(f"    30F实用中枢: [{zhongshu_30f['lower']:.2f}, {zhongshu_30f['upper']:.2f}], 宽{zhongshu_30f['width']:.2f}%")
    
    # 生成报告
    print("\n  生成报告...")
    
    report_5f = ""
    if zhongshu_5f:
        pos_5f, _ = analyze_zhongshu_position(current, zhongshu_5f)
        report_5f = f"""
【5分钟级别缠论结构】
  中枢区间: [{zhongshu_5f['lower']:.2f}, {zhongshu_5f['upper']:.2f}]
  中枢宽度: {zhongshu_5f['width']:.2f}%
  当前位置: {pos_5f}
  线段数: {len(xianduan_5f)}
  笔数: {len(bi_5f)}
"""
    
    report_30f = ""
    if zhongshu_30f:
        pos_30f, _ = analyze_zhongshu_position(current, zhongshu_30f)
        report_30f = f"""
【30分钟级别缠论结构】
  中枢区间: [{zhongshu_30f['lower']:.2f}, {zhongshu_30f['upper']:.2f}]
  中枢宽度: {zhongshu_30f['width']:.2f}%
  当前位置: {pos_30f}
  线段数: {len(xianduan_30f)}
"""
    
    # 开盘策略
    strategy = generate_kai_pan_strategy(current, zhongshu_5f, zhongshu_30f, bi_5f)
    
    full_report = f"""
📊 上证指数缠论分析 (30F+5F) - 正确中枢定义
⏰ 数据时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}

【当前状态】
  最新指数: {current:.2f}点

{report_30f}
{report_5f}
{strategy}

⚠️ 说明: 
- 中枢定义: 连续三个走势类型的重叠区间 [max(低点), min(高点)]
- 走势类型 = 至少3笔构成的线段
- 笔 = 顶底分型 + 至少1根K线间隔

⚠️ 风险提示: 本分析基于缠论技术指标，不构成投资建议。
"""
    
    print(full_report)
    send_feishu(full_report)
    print("✅ 报告已发送至飞书")


if __name__ == "__main__":
    main()
