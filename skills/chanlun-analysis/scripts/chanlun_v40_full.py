#!/root/.openclaw/workspace/venv/bin/python3
"""
缠论分析 v4.0 - 实时数据完整版
修复：
1. 去掉手动加载.env（venv_runner.sh已加载）
2. symbol格式改为000001.SH
3. 增加完整分析输出
"""

import pandas as pd
import numpy as np
from datetime import datetime

from longport.openapi import Config, QuoteContext, Period, AdjustType

def fetch_longbridge(symbol, period, count):
    """从长桥获取K线 - 直接Config.from_env()"""
    config = Config.from_env()
    ctx = QuoteContext(config)
    
    period_map = {
        '1m': Period.Min_1, '5m': Period.Min_5,
        '30m': Period.Min_30, '60m': Period.Min_60, '1d': Period.Day
    }
    p = period_map.get(period, Period.Day)
    
    resp = ctx.candlesticks(symbol, p, count, AdjustType.NoAdjust)
    
    data = []
    for c in resp:
        data.append({
            'Date': pd.to_datetime(c.timestamp),
            'Open': c.open, 'High': c.high, 'Low': c.low,
            'Close': c.close, 'Volume': c.volume
        })
    return pd.DataFrame(data).sort_values('Date').reset_index(drop=True)

def synthesize_kline(df, n):
    df = df.copy()
    df['Group'] = df.index // n
    return df.groupby('Group').agg({
        'Date': 'last', 'Open': 'first', 'High': 'max',
        'Low': 'min', 'Close': 'last', 'Volume': 'sum'
    }).reset_index(drop=True)

def ma(df, w): return df['Close'].rolling(window=w).mean()

def boll(df, w=20):
    m = df['Close'].rolling(window=w).mean()
    s = df['Close'].rolling(window=w).std()
    return {'upper': m + s*2, 'middle': m, 'lower': m - s*2}

def macd(df, f=12, s=26, sig=9):
    ef = df['Close'].ewm(span=f, adjust=False).mean()
    es = df['Close'].ewm(span=s, adjust=False).mean()
    dif = ef - es
    dea = dif.ewm(span=sig, adjust=False).mean()
    return {'dif': dif, 'dea': dea, 'macd': (dif - dea)*2}

def analyze_55(df, name):
    m55 = ma(df, 55).iloc[-1]
    md = macd(df)
    p = df['Close'].iloc[-1]
    mc = md['macd'].iloc[-1]
    if p > m55 and mc > 0: st = '✅ 主涨段'
    elif p < m55 and mc < 0: st = '❌ 主跌段'
    elif p > m55 and mc < 0: st = '⚠️ 55线上方X段'
    elif p < m55 and mc > 0: st = '⚠️ 55线下方X段'
    else: st = '中性'
    return {'price': p, 'ma55': m55, 'macd': mc, 'structure': st}

def analyze_macd_stability(df, name):
    md = macd(df)
    dif, dea, mc = md['dif'].iloc[-1], md['dea'].iloc[-1], md['macd'].iloc[-1]
    if dif >= 0 and dea <= 0 and mc > 0: state = '极强（零轴金叉）'
    elif dif > dea > 0 and mc > 0: state = '强（水上金叉）'
    elif 0 > dif > dea and mc > 0: state = '中性偏强（水下金叉）'
    elif dif <= 0 and dea >= 0 and mc < 0: state = '极弱（零轴死叉）'
    elif dif < dea < 0 and mc < 0: state = '弱（水下死叉）'
    elif 0 < dif < dea and mc < 0: state = '中性偏弱（水上死叉）'
    else: state = '中性'
    return {'state': state, 'dif': round(dif,2), 'dea': round(dea,2), 'macd': round(mc,2)}

def main():
    print("="*60)
    print("缠论分析系统 v4.0 - 实时数据完整版")
    print("="*60)
    
    print("\n📡 从长桥获取实时数据...")
    df_1m = fetch_longbridge('000001.SH', '1m', 1000)
    df_5m = fetch_longbridge('000001.SH', '5m', 1000)
    df_d = fetch_longbridge('000001.SH', '1d', 120)
    
    # 合成
    df_3m = synthesize_kline(df_1m, 3)
    df_15m = synthesize_kline(df_5m, 3)
    df_30m = synthesize_kline(df_5m, 6)
    df_60m = synthesize_kline(df_5m, 12)
    df_bid = synthesize_kline(df_d, 2)
    
    print(f"\n✅ 数据获取完成:")
    for name, df in [('1F',df_1m),('3F',df_3m),('5F',df_5m),('15F',df_15m),('30F',df_30m),('60F',df_60m),('日线',df_d),('双日',df_bid)]:
        print(f"  {name}: {len(df)}根 {'✅' if len(df) >= 55 else '❌'}")
    
    # 55线
    print(f"\n【55线思维 - 核心】")
    for name, df in [('30F', df_30m), ('60F', df_60m), ('日线', df_d), ('双日', df_bid)]:
        if len(df) >= 55:
            r = analyze_55(df, name)
            print(f"  {name}: 价{r['price']:.2f} vs MA55={r['ma55']:.2f} | {r['structure']}")
    
    # MACD稳定性
    print(f"\n【MACD稳定性分析】")
    for name, df in [('30F', df_30m), ('60F', df_60m), ('日线', df_d), ('双日', df_bid)]:
        if len(df) >= 30:
            r = analyze_macd_stability(df, name)
            print(f"  {name}: {r['state']} | DIF={r['dif']}, DEA={r['dea']}, MACD={r['macd']}")
    
    # 联合区
    print(f"\n【联合支撑/压制区】")
    d55 = ma(df_d, 55).iloc[-1]
    b55 = ma(df_bid, 55).iloc[-1] if len(df_bid) >= 55 else None
    db = boll(df_d)
    bb = boll(df_bid)
    
    if b55:
        diff = abs(d55 - b55)
        strength = '极强' if diff < 5 else ('强' if diff < 20 else '中等')
        print(f"  🛡️ {strength}联合支撑: 日线55={d55:.2f} vs 双日55={b55:.2f} (差{diff:.2f})")
    
    if len(df_bid) >= 20:
        diffm = abs(db['middle'].iloc[-1] - bb['middle'].iloc[-1])
        strength = '极强' if diffm < 5 else ('强' if diffm < 20 else '中等')
        print(f"  ⛰️ {strength}联合压制: 日线中轨={db['middle'].iloc[-1]:.2f} vs 双日中轨={bb['middle'].iloc[-1]:.2f} (差{diffm:.2f})")
    
    # 主涨段判定
    print(f"\n【主涨段判定 (v4.0)】")
    p = df_d['Close'].iloc[-1]
    print(f"  当前价: {p:.2f}")
    print(f"  30F: {'主涨段' if p > ma(df_30m,55).iloc[-1] and macd(df_30m)['macd'].iloc[-1] > 0 else '非主涨段'}")
    print(f"  60F: {'强' if macd(df_60m)['macd'].iloc[-1] > 0 else '弱'}")
    
    # 传导链
    print(f"\n【级别传导链】")
    m30 = macd(df_30m)['macd'].iloc[-1]
    m60 = macd(df_60m)['macd'].iloc[-1]
    md = macd(df_d)['macd'].iloc[-1]
    if m30 > 0 and m60 > 0 and md < 0:
        print(f"  30F/60F主涨段 → 传导至日线 | 日线X段等待确认")
    elif m30 > 0 and m60 > 0 and md > 0:
        print(f"  ✅ 全级别共振主涨")
    elif m30 < 0 and m60 < 0 and md < 0:
        print(f"  ❌ 全级别共振主跌")
    else:
        print(f"  震荡/转换中")
    
    # 假突破/骗炮
    print(f"\n【假突破识别】")
    price = df_d['Close'].iloc[-1]
    d55v = ma(df_d, 55).iloc[-1]
    md_d = macd(df_d)['macd'].iloc[-1]
    if price > d55v and md_d < 0:
        print(f"  ⚠️ 站上日线55线({d55v:.2f})但MACD={md_d:.2f}<0 → 假突破/骗炮风险")
    elif price > d55v and md_d > 0:
        print(f"  ✅ 真突破: 站上55线 + MACD>0")
    else:
        print(f"  价格{d55v:.2f} vs 55线{price:.2f}")
    
    # 二买/二卖
    print(f"\n【二买/二卖判断】")
    # 简化：看是否创新低/新高
    last5 = df_d['Close'].iloc[-5:]
    if len(last5) >= 3:
        if last5.iloc[-1] > last5.iloc[-2] > last5.iloc[-3]:
            print(f"  日线: 连续3日上涨，关注是否形成二买")
        elif last5.iloc[-1] < last5.iloc[-2] < last5.iloc[-3]:
            print(f"  日线: 连续3日下跌，关注是否形成二卖")
        else:
            print(f"  日线: 震荡，等待二买/二卖结构")
    
    # 时间窗口
    print(f"\n【时间窗口】")
    md_dif = macd(df_d)['dif'].iloc[-1]
    md_dea = macd(df_d)['dea'].iloc[-1]
    if md_dif < md_dea:
        print(f"  ⛔ 日线MACD死叉中，时间窗口未开启，等待底背离+突破中轨")
    elif md_dif > md_dea:
        print(f"  ✅ 日线MACD金叉，时间窗口开启")
    else:
        print(f"  等待方向")
    
    # 策略
    print(f"\n【明日策略】")
    print(f"  当前收盘: {p:.2f}")
    print(f"  30F MA55: {ma(df_30m,55).iloc[-1]:.2f}")
    print(f"  日线 MA55: {d55v:.2f}")
    print(f"  日线 MACD: {md_d:.2f}")
    
    # 持仓者
    print(f"\n  📌 持仓者:")
    if m30 > 0:
        print(f"    • 30F主涨段，持仓观察")
        if md_d < 0:
            print(f"    • 日线MACD仍为负，设止损: {d55v:.2f}（日线55线）")
    else:
        print(f"    • 30F非主涨段，减仓")
    
    # 空仓者
    print(f"\n  📌 空仓者:")
    if md_d < 0:
        print(f"    • 日线X段，非确认性买点，观望或等回踩")
        print(f"    • 回踩买点: {ma(df_30m,55).iloc[-1]:.2f}附近（30F55线）")
    else:
        print(f"    • 突破日线确认后追涨")
    
    print(f"\n📅 日期: {df_d['Date'].iloc[-1].date()}")
    print("="*60)

if __name__ == "__main__":
    main()
