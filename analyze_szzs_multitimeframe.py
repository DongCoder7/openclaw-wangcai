#!/root/.openclaw/workspace/venv/bin/python3
"""
上证指数多周期技术分析 - 计算55均线和布林带中轨
"""
import os
import sys
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# 加载长桥环境变量
env_path = '/root/.openclaw/workspace/.longbridge.env'
if os.path.exists(env_path):
    with open(env_path) as f:
        for line in f:
            if '=' in line and not line.startswith('#'):
                key, value = line.strip().split('=', 1)
                os.environ[key] = value

from longport.openapi import Config, QuoteContext, Period, AdjustType

def calculate_ma(prices, period):
    """计算简单移动平均"""
    if len(prices) < period:
        return None
    return np.mean(prices[-period:])

def calculate_bollinger(prices, period=20, std_dev=2):
    """计算布林带"""
    if len(prices) < period:
        return None, None, None
    
    recent_prices = prices[-period:]
    ma = np.mean(recent_prices)
    std = np.std(recent_prices)
    
    upper = ma + std_dev * std  # 上轨
    middle = ma                  # 中轨
    lower = ma - std_dev * std   # 下轨
    
    return upper, middle, lower

def get_candle_data(ctx, symbol, period, count):
    """获取K线数据"""
    try:
        resp = ctx.candlesticks(symbol, period=period, count=count, adjust_type=AdjustType.NoAdjust)
        data = []
        for candle in resp:
            data.append({
                'timestamp': candle.timestamp,
                'open': float(candle.open),
                'high': float(candle.high),
                'low': float(candle.low),
                'close': float(candle.close),
                'volume': int(candle.volume)
            })
        return pd.DataFrame(data)
    except Exception as e:
        print(f"获取数据失败 {period}: {e}")
        return None

def analyze_timeframe(df, name):
    """分析单个时间周期"""
    if df is None or len(df) < 55:
        return None
    
    closes = df['close'].values
    current_price = closes[-1]
    
    # 计算55均线
    ma55 = calculate_ma(closes, 55)
    
    # 计算布林带 (20周期)
    upper, middle, lower = calculate_bollinger(closes, 20)
    
    # 计算MACD
    exp1 = pd.Series(closes).ewm(span=12, adjust=False).mean()
    exp2 = pd.Series(closes).ewm(span=26, adjust=False).mean()
    macd = exp1 - exp2
    signal = macd.ewm(span=9, adjust=False).mean()
    hist = macd - signal
    
    return {
        'name': name,
        'current_price': current_price,
        'ma55': ma55,
        'boll_upper': upper,
        'boll_middle': middle,
        'boll_lower': lower,
        'macd': macd.iloc[-1],
        'signal': signal.iloc[-1],
        'hist': hist.iloc[-1],
        'data_count': len(df)
    }

def main():
    print("=" * 70)
    print("上证指数多周期技术分析报告")
    print(f"分析时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)
    
    # 初始化长桥API
    config = Config.from_env()
    ctx = QuoteContext(config)
    
    symbol = "000001.SH"  # 上证指数
    
    # 获取各周期数据
    print("\n【1】获取各时间周期K线数据...")
    
    # 日线数据 (需要至少55根)
    df_daily = get_candle_data(ctx, symbol, Period.Day, 100)
    
    # 60分钟数据
    df_60min = get_candle_data(ctx, symbol, Period.Min_60, 200)
    
    # 30分钟数据
    df_30min = get_candle_data(ctx, symbol, Period.Min_30, 200)
    
    # 15分钟数据
    df_15min = get_candle_data(ctx, symbol, Period.Min_15, 300)
    
    # 5分钟数据
    df_5min = get_candle_data(ctx, symbol, Period.Min_5, 300)
    
    # 3分钟数据
    df_3min = get_candle_data(ctx, symbol, Period.Min_3, 300)
    
    # 分析各周期
    results = {}
    
    if df_daily is not None:
        results['日线'] = analyze_timeframe(df_daily, '日线')
        print(f"  ✓ 日线数据: {len(df_daily)}根K线")
    
    if df_60min is not None:
        results['60分钟'] = analyze_timeframe(df_60min, '60分钟')
        print(f"  ✓ 60分钟数据: {len(df_60min)}根K线")
    
    if df_30min is not None:
        results['30分钟'] = analyze_timeframe(df_30min, '30分钟')
        print(f"  ✓ 30分钟数据: {len(df_30min)}根K线")
    
    if df_15min is not None:
        results['15分钟'] = analyze_timeframe(df_15min, '15分钟')
        print(f"  ✓ 15分钟数据: {len(df_15min)}根K线")
    
    if df_5min is not None:
        results['5分钟'] = analyze_timeframe(df_5min, '5分钟')
        print(f"  ✓ 5分钟数据: {len(df_5min)}根K线")
    
    if df_3min is not None:
        results['3分钟'] = analyze_timeframe(df_3min, '3分钟')
        print(f"  ✓ 3分钟数据: {len(df_3min)}根K线")
    
    # 打印各周期关键数据
    print("\n" + "=" * 70)
    print("【2】各时间周期关键技术指标")
    print("=" * 70)
    
    print("\n{:<12} {:>10} {:>12} {:>12} {:>12}".format(
        "周期", "当前价", "55均线", "布林中轨", "MACD柱状"
    ))
    print("-" * 70)
    
    for name, data in results.items():
        if data:
            print("{:<12} {:>10.2f} {:>12.2f} {:>12.2f} {:>12.4f}".format(
                data['name'],
                data['current_price'],
                data['ma55'] if data['ma55'] else 0,
                data['boll_middle'] if data['boll_middle'] else 0,
                data['hist']
            ))
    
    # 详细分析
    print("\n" + "=" * 70)
    print("【3】详细技术分析")
    print("=" * 70)
    
    for name, data in results.items():
        if data:
            print(f"\n【{data['name']}】")
            print(f"  当前价格: {data['current_price']:.2f}")
            print(f"  55均线:   {data['ma55']:.2f} (价格{'高于' if data['current_price'] > data['ma55'] else '低于'}均线)")
            print(f"  布林上轨: {data['boll_upper']:.2f}")
            print(f"  布林中轨: {data['boll_middle']:.2f}")
            print(f"  布林下轨: {data['boll_lower']:.2f}")
            print(f"  MACD柱状: {data['hist']:.4f} ({'红柱' if data['hist'] > 0 else '绿柱'})")
    
    # 用户问题分析
    print("\n" + "=" * 70)
    print("【4】针对用户问题的技术分析")
    print("=" * 70)
    
    if '15分钟' in results and '30分钟' in results and '60分钟' in results:
        d15 = results['15分钟']
        d30 = results['30分钟']
        d60 = results['60分钟']
        d5 = results.get('5分钟')
        d3 = results.get('3分钟')
        d_daily = results.get('日线')
        
        print(f"""
【关键价位分析】

1. 15分钟级别55线: {d15['ma55']:.2f}点
   - 这是用户提到的"15F55线"
   - 当前价格{d15['current_price']:.2f} {'已突破' if d15['current_price'] > d15['ma55'] else '未突破'}该线

2. 15分钟级别布林中轨: {d15['boll_middle']:.2f}点
   - 这是用户提到的"15F中轨"
   - 当前价格距离中轨: {d15['current_price'] - d15['boll_middle']:.2f}点

3. 30分钟级别布林中轨: {d30['boll_middle']:.2f}点
   - 这是用户提到的"30F中轨"
   - 用于判断主跌段是否解除

4. 30分钟级别55线: {d30['ma55']:.2f}点
   - 这是用户提到的"30F55线"
   - 双日极弱形成的压力位

5. 60分钟级别分析:
   - 当前价: {d60['current_price']:.2f}
   - 55线: {d60['ma55']:.2f}
   - 布林中轨: {d60['boll_middle']:.2f}
   - 这是判断"60F主跌"的关键级别
""")
        
        if d3 and d5:
            print(f"""
【两个止盈点位的计算】

止盈点1: 突破15F中轨后，跌破3F中轨
  - 15F中轨: {d15['boll_middle']:.2f}点
  - 3F中轨:  {d3['boll_middle']:.2f}点
  - 逻辑: 突破15F中轨后，如果不能继续突破30F中轨（主跌段未解除），
          则可能在15F55线({d15['ma55']:.2f})遇阻回落，
          一旦跌破3F中轨({d3['boll_middle']:.2f})，短期反弹结束

止盈点2: 突破30F中轨后，在30F55线附近跌破5F中轨
  - 30F中轨: {d30['boll_middle']:.2f}点（突破=解除主跌段）
  - 30F55线: {d30['ma55']:.2f}点（双日极弱压力）
  - 5F中轨:  {d5['boll_middle']:.2f}点
  - 逻辑: 突破30F中轨解除主跌段后，反弹目标看向30F55线({d30['ma55']:.2f})，
          这是双日极弱形成的重要压力位，
          如果在该位置附近跌破5F中轨({d5['boll_middle']:.2f})，
          说明反弹力度不足，新一轮主跌可能开始
""")
        
        if d_daily:
            print(f"""
【日线级别背景】
  - 日线55线: {d_daily['ma55']:.2f}点
  - 日线布林中轨: {d_daily['boll_middle']:.2f}点
  - MACD柱状: {d_daily['hist']:.4f}
  - "日线极弱"通常指价格远低于55线且MACD绿柱扩大
""")
    
    print("\n" + "=" * 70)
    print("【5】缠论视角的补充分析")
    print("=" * 70)
    print("""
缠论关键概念解释:

1. "极弱"的定义:
   - 在缠论中，"极弱"通常指某级别走势远离中枢，处于背驰段
   - 日线极弱 = 价格远低于日线中枢，且出现背驰迹象
   - 双日极弱 = 连续两个日线周期都呈现弱势特征

2. "主跌段"的定义:
   - 指当前下跌走势中力度最强的一段
   - 通常表现为连续跌破多个支撑位，无有效反弹
   - 解除主跌段的标志: 突破该级别布林中轨

3. 各周期的关系:
   - 大周期(日线)决定方向
   - 中周期(30/60分钟)决定波段
   - 小周期(5/15分钟)决定入场点

4. 布林带中轨在缠论中的意义:
   - 中轨 ≈ 该级别走势的中枢中轨
   - 价格在中轨上方 = 该级别强势
   - 价格在中轨下方 = 该级别弱势
""")
    
    print("\n" + "=" * 70)
    print("分析完成")
    print("=" * 70)

if __name__ == "__main__":
    main()
