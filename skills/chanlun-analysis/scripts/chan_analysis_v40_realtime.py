#!/root/.openclaw/workspace/venv/bin/python3
"""
缠论分析 v4.0 - 实时数据版
修复：增加实时数据拉取，不再依赖本地过期CSV
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import os
import sys

# 添加长桥SDK路径
sys.path.insert(0, '/root/.openclaw/workspace/venv/lib/python3.12/site-packages')

def fetch_data(file_path):
    """从本地CSV读取（备用）"""
    df = pd.read_csv(file_path)
    df['Date'] = pd.to_datetime(df['Date'])
    return df

def fetch_from_longbridge(symbol='SH.000001', period='1d', count=120):
    """
    从长桥API获取实时K线数据
    period: 1m, 5m, 30m, 60m, 1d
    """
    try:
        from longport.openapi import Config, QuoteContext, Period, AdjustType, Market
        
        # 加载环境变量（去掉引号，避免Config读取到带引号的Token）
        env_path = '/root/.openclaw/workspace/.longbridge.env'
        if os.path.exists(env_path):
            with open(env_path) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, val = line.split('=', 1)
                        val = val.strip().strip('"').strip("'")
                        os.environ[key] = val
        
        config = Config.from_env()
        ctx = QuoteContext(config)
        
        # 映射周期
        period_map = {
            '1m': Period.Min_1,
            '5m': Period.Min_5,
            '30m': Period.Min_30,
            '60m': Period.Min_60,
            '1d': Period.Day
        }
        
        p = period_map.get(period, Period.Day)
        
        # 获取K线
        resp = ctx.candlesticks(symbol, p, count, AdjustType.NoAdjust)
        
        data = []
        for candle in resp:
            data.append({
                'Date': pd.to_datetime(candle.timestamp),
                'Open': candle.open,
                'High': candle.high,
                'Low': candle.low,
                'Close': candle.close,
                'Volume': candle.volume
            })
        
        df = pd.DataFrame(data)
        df = df.sort_values('Date').reset_index(drop=True)
        return df
        
    except Exception as e:
        print(f"长桥API获取失败: {e}")
        return None

def fetch_from_efinance(symbol='000001', freq='1m', period=120):
    """
    从efinance获取A股实时数据（备用）
    """
    try:
        import efinance as ef
        
        # efinance获取K线
        freq_map = {'1m': '1', '5m': '5', '30m': '30', '60m': '60', '1d': '101'}
        ef_freq = freq_map.get(freq, '101')
        
        df = ef.stock.get_quote_history(symbol, klt=ef_freq)
        
        if df is not None and len(df) > 0:
            df = df.rename(columns={
                '日期': 'Date',
                '开盘': 'Open',
                '最高': 'High',
                '最低': 'Low',
                '收盘': 'Close',
                '成交量': 'Volume'
            })
            df['Date'] = pd.to_datetime(df['Date'])
            df = df[['Date', 'Open', 'High', 'Low', 'Close', 'Volume']]
            df = df.sort_values('Date').reset_index(drop=True)
            return df
        return None
        
    except Exception as e:
        print(f"efinance获取失败: {e}")
        return None

def synthesize_kline(df_source, n, name=""):
    """K线合成：n根合1根"""
    df = df_source.copy()
    df['Group'] = df.index // n
    df_target = df.groupby('Group').agg({
        'Date': 'last', 'Open': 'first', 'High': 'max',
        'Low': 'min', 'Close': 'last', 'Volume': 'sum'
    }).reset_index(drop=True)
    return df_target

def check_data_integrity(df, level_name='未知'):
    """数据完整性检查"""
    n = len(df)
    return {
        'level': level_name,
        'total_rows': n,
        'ma55_ok': n >= 55,
        'boll_ok': n >= 20,
        'usable': n >= 55
    }

def calculate_ma(df, window):
    """计算MA"""
    return df['Close'].rolling(window=window).mean()

def calculate_bollinger(df, window=20, num_std=2):
    """计算布林带"""
    ma = df['Close'].rolling(window=window).mean()
    std = df['Close'].rolling(window=window).std()
    return {
        'upper': ma + (std * num_std),
        'middle': ma,
        'lower': ma - (std * num_std)
    }

def calculate_macd(df, fast=12, slow=26, signal=9):
    """计算MACD"""
    ema_fast = df['Close'].ewm(span=fast, adjust=False).mean()
    ema_slow = df['Close'].ewm(span=slow, adjust=False).mean()
    dif = ema_fast - ema_slow
    dea = dif.ewm(span=signal, adjust=False).mean()
    macd = (dif - dea) * 2
    return {'dif': dif, 'dea': dea, 'macd': macd}

def analyze_macd_stability(df, level_name='30F'):
    """
    MACD稳定性分析 (v4.0)
    返回6种状态之一
    """
    macd_data = calculate_macd(df)
    dif = macd_data['dif'].iloc[-1]
    dea = macd_data['dea'].iloc[-1]
    macd = macd_data['macd'].iloc[-1]
    
    # 6种状态判定
    if dif >= 0 and dea <= 0 and macd > 0:
        state = '极强'
        action = '不做空'
    elif dif > dea > 0 and macd > 0:
        state = '强'
        action = '做多胜率高'
    elif 0 > dif > dea and macd > 0:
        state = '中性偏强'
        action = '观察'
    elif dif <= 0 and dea >= 0 and macd < 0:
        state = '极弱'
        action = '不做多'
    elif dif < dea < 0 and macd < 0:
        state = '弱'
        action = '做空胜率高'
    elif 0 < dif < dea and macd < 0:
        state = '中性偏弱'
        action = '观察'
    else:
        state = '中性'
        action = '观望'
    
    # 金叉死叉形态
    prev_dif = macd_data['dif'].iloc[-2]
    prev_dea = macd_data['dea'].iloc[-2]
    
    cross_type = '无'
    if prev_dif <= prev_dea and dif > dea:
        # 金叉
        if abs(dif) < 0.5 and abs(dea) < 0.5:
            cross_type = '零轴金叉'
        elif dif > 0 and dea > 0:
            cross_type = '水上金叉'
        else:
            cross_type = '水下金叉'
    elif prev_dif >= prev_dea and dif < dea:
        # 死叉
        if abs(dif) < 0.5 and abs(dea) < 0.5:
            cross_type = '零轴死叉'
        elif dif < 0 and dea < 0:
            cross_type = '水下死叉'
        else:
            cross_type = '水上死叉'
    
    return {
        'state': state,
        'action': action,
        'dif': round(dif, 2),
        'dea': round(dea, 2),
        'macd': round(macd, 2),
        'cross_type': cross_type
    }

def analyze_55line(df, level_name='30F'):
    """55线思维分析"""
    ma55 = calculate_ma(df, 55)
    macd_data = calculate_macd(df)
    
    price = df['Close'].iloc[-1]
    ma55_val = ma55.iloc[-1]
    macd = macd_data['macd'].iloc[-1]
    
    if price > ma55_val and macd > 0:
        structure = '主涨段'
    elif price < ma55_val and macd < 0:
        structure = '主跌段'
    elif price > ma55_val and macd < 0:
        structure = '55线上方X段'
    elif price < ma55_val and macd > 0:
        structure = '55线下方X段'
    else:
        structure = '中性'
    
    return {
        'price': price,
        'ma55': ma55_val,
        'macd': macd,
        'structure': structure
    }

def analyze_unified_zone(df_daily, df_biday):
    """联合支撑/压制区分析"""
    if df_biday is None or len(df_biday) < 55:
        return {'unified_zones': []}
    
    daily_ma55 = calculate_ma(df_daily, 55).iloc[-1]
    biday_ma55 = calculate_ma(df_biday, 55).iloc[-1]
    
    daily_boll = calculate_bollinger(df_daily)
    biday_boll = calculate_bollinger(df_biday)
    
    zones = []
    
    # 联合支撑：日线55线 + 双日55线
    diff_55 = abs(daily_ma55 - biday_ma55)
    if diff_55 < 50:
        strength = '极强联合' if diff_55 < 5 else ('强联合' if diff_55 < 20 else '中等联合')
        zones.append({
            'type': '联合支撑区',
            'strength': strength,
            'description': f'日线55线({daily_ma55:.2f})与双日55线({biday_ma55:.2f})差值{diff_55:.2f}点({strength})'
        })
    
    # 联合压制：日线中轨 + 双日中轨
    diff_mid = abs(daily_boll['middle'].iloc[-1] - biday_boll['middle'].iloc[-1])
    if diff_mid < 50:
        strength = '极强联合' if diff_mid < 5 else ('强联合' if diff_mid < 20 else '中等联合')
        zones.append({
            'type': '联合区',
            'strength': strength,
            'description': f'日线中轨({daily_boll["middle"].iloc[-1]:.2f})与双日中轨({biday_boll["middle"].iloc[-1]:.2f})差值{diff_mid:.2f}点({strength})'
        })
    
    return {'unified_zones': zones}

def main():
    print("="*60)
    print("缠论分析系统 v4.0 - 实时数据版")
    print("="*60)
    
    # 尝试获取实时数据
    print("\n📡 正在获取实时数据...")
    
    # 尝试长桥API
    df_daily = fetch_from_longbridge('SH.000001', '1d', 120)
    df_5m = fetch_from_longbridge('SH.000001', '5m', 1000)
    df_1m = fetch_from_longbridge('SH.000001', '1m', 1000)
    
    # 如果长桥失败，尝试efinance
    if df_daily is None:
        print("长桥日线失败，尝试efinance...")
        df_daily = fetch_from_efinance('000001', '1d', 120)
    
    if df_5m is None:
        print("长桥5分钟失败，尝试efinance...")
        df_5m = fetch_from_efinance('000001', '5m', 1000)
    
    # 如果都失败，用本地数据
    if df_daily is None:
        print("⚠️ 实时数据获取失败，使用本地数据（可能过期）")
        df_daily = fetch_data("/mnt/kimi/output/sh_1day_latest.csv")
    
    if df_5m is None:
        df_5m = fetch_data("/mnt/kimi/output/sh_5min_latest.csv")
    
    if df_1m is None:
        df_1m = fetch_data("/mnt/kimi/output/sh_1min_latest.csv")
    
    # 合成各级别
    df_3m = synthesize_kline(df_1m, 3, '3F') if df_1m is not None else None
    df_15m = synthesize_kline(df_5m, 3, '15F') if df_5m is not None else None
    df_30m = synthesize_kline(df_5m, 6, '30F') if df_5m is not None else None
    df_60m = synthesize_kline(df_5m, 12, '60F') if df_5m is not None else None
    df_biday = synthesize_kline(df_daily, 2, '双日') if df_daily is not None else None
    
    # 数据完整性检查
    print("\n【数据完整性】")
    levels = {
        '1F': df_1m, '3F': df_3m, '5F': df_5m, '15F': df_15m,
        '30F': df_30m, '60F': df_60m, '日线': df_daily, '双日': df_biday
    }
    
    for name, df in levels.items():
        if df is not None:
            integrity = check_data_integrity(df, name)
            status = "✅" if integrity['usable'] else "❌"
            print(f"  {status} {name}: {integrity['total_rows']}根")
        else:
            print(f"  ❌ {name}: 无数据")
    
    # MACD稳定性分析
    print("\n【MACD稳定性分析】")
    for name, df in [('30F', df_30m), ('日线', df_daily), ('双日', df_biday)]:
        if df is not None and len(df) >= 30:
            macd = analyze_macd_stability(df, name)
            print(f"  {name}: {macd['state']} | DIF={macd['dif']}, DEA={macd['dea']}, MACD={macd['macd']}")
            if macd['cross_type'] != '无':
                print(f"    → {macd['cross_type']}（{macd['action']}）")
    
    # 55线思维
    print("\n【55线思维】")
    for name, df in [('30F', df_30m), ('日线', df_daily), ('双日', df_biday)]:
        if df is not None and len(df) >= 55:
            line = analyze_55line(df, name)
            print(f"  {name}: 价{line['price']:.2f} vs MA55={line['ma55']:.2f} | {line['structure']}")
    
    # 联合支撑/压制区
    print("\n【联合支撑/压制区】")
    if df_daily is not None and df_biday is not None:
        uz = analyze_unified_zone(df_daily, df_biday)
        for z in uz.get('unified_zones', []):
            icon = '🛡️' if '支撑' in z['type'] else '⛰️'
            print(f"  {icon} {z['strength']}: {z['description']}")
    
    # 当前价格
    if df_daily is not None:
        current_price = df_daily['Close'].iloc[-1]
        print(f"\n📊 当前收盘: {current_price}")
    
    print("\n" + "="*60)

if __name__ == "__main__":
    main()
