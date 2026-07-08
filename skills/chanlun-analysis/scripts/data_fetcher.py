#!/root/.openclaw/workspace/venv/bin/python3
"""
多数据源统一获取模块

优先级：tdxrs > 长桥 > tushare pro > efinance

使用方法：
    from data_fetcher import fetch_data
    df = fetch_data('000001.SH', '5m', 1000)
"""

import pandas as pd
from datetime import datetime, timedelta


def _parse_symbol(symbol):
    """解析 symbol 为各数据源格式
    symbol 格式: '000001.SH' 或 '000001.SZ' 等
    返回: (code, market_name, tdx_market, tushare_code, efinance_code)
    """
    if '.' in symbol:
        code, market = symbol.split('.')
        market = market.upper()
    else:
        code = symbol
        market = 'SH'
    tushare_code = f"{code}.{market}"
    efinance_code = code
    if market in ('SH', 'SSE'):
        tdx_market = 1  # MARKET_SH
        market_name = 'SH'
    elif market in ('SZ', 'SZE'):
        tdx_market = 0  # MARKET_SZ
        market_name = 'SZ'
    elif market in ('BJ', 'BSE'):
        tdx_market = 2  # MARKET_BJ
        market_name = 'BJ'
    else:
        tdx_market = 1
        market_name = 'SH'
    return code, market_name, tdx_market, tushare_code, efinance_code


def _tdxrs_period_map(period):
    """tdxrs 周期映射"""
    from tdxrs.constants import KLINE_1MIN, KLINE_5MIN, KLINE_15MIN, KLINE_30MIN, KLINE_1HOUR, KLINE_DAILY
    mapping = {
        '1m': KLINE_1MIN, '5m': KLINE_5MIN, '15m': KLINE_15MIN,
        '30m': KLINE_30MIN, '60m': KLINE_1HOUR, '1d': KLINE_DAILY
    }
    return mapping.get(period)


def fetch_tdxrs(symbol, period, count):
    """从 tdxrs (通达信) 获取K线"""
    import tdxrs
    from tdxrs.constants import FQ_NONE
    code, _, market, _, _ = _parse_symbol(symbol)
    tdx_period = _tdxrs_period_map(period)
    if tdx_period is None:
        return None
    client = tdxrs.TdxHqClient()
    try:
        client.connect_to_any()
        all_data = []
        remaining = count
        start = 0
        while remaining > 0:
            batch = min(remaining, 800)
            df = client.get_security_bars_dataframe(tdx_period, market, code, start=start, count=batch, fq=FQ_NONE)
            if df is None or df.empty:
                break
            all_data.append(df)
            if len(df) < batch:
                break
            start += batch
            remaining -= batch
        if not all_data:
            return None
        df = pd.concat(all_data, ignore_index=True)
        df = df.rename(columns={
            'datetime': 'Date',
            'open': 'Open',
            'high': 'High',
            'low': 'Low',
            'close': 'Close',
            'vol': 'Volume'
        })
        df['Date'] = pd.to_datetime(df['Date'])
        df = df.sort_values('Date').reset_index(drop=True)
        return df
    except Exception as e:
        print(f"    [tdxrs] 获取失败: {e}")
        return None
    finally:
        try:
            client.disconnect()
        except:
            pass


def fetch_tushare(symbol, period, count):
    """从 tushare pro 获取K线"""
    import tushare as ts
    code, _, _, ts_code, _ = _parse_symbol(symbol)
    try:
        ts.set_token('cd2c935050381b52c9849eb054d1b198c21b0f29be2f025f9a9ece30')
        pro = ts.pro_api()
        end_date = datetime.now().strftime('%Y%m%d')
        if period == '1d':
            start_date = (datetime.now() - timedelta(days=count*2)).strftime('%Y%m%d')
            df = pro.index_daily(ts_code=ts_code, start_date=start_date, end_date=end_date)
        else:
            freq_map = {'1m': '1min', '5m': '5min', '15m': '15min', '30m': '30min', '60m': '60min', '120m': '120min'}
            freq = freq_map.get(period, '5min')
            start_date = (datetime.now() - timedelta(days=count//2 + 5)).strftime('%Y%m%d')
            df = ts.pro_bar(ts_code=ts_code, asset='I', freq=freq, start_date=start_date, end_date=end_date)
        if df is None or df.empty:
            return None
        if 'trade_date' in df.columns:
            df['Date'] = pd.to_datetime(df['trade_date'])
        elif 'trade_time' in df.columns:
            df['Date'] = pd.to_datetime(df['trade_time'])
        else:
            df['Date'] = pd.to_datetime(df.iloc[:, 1])
        df = df.rename(columns={
            'open': 'Open', 'high': 'High', 'low': 'Low',
            'close': 'Close', 'vol': 'Volume'
        })
        df = df.sort_values('Date').reset_index(drop=True)
        cols = ['Date', 'Open', 'High', 'Low', 'Close', 'Volume']
        cols = [c for c in cols if c in df.columns]
        df = df[cols].copy()
        return df
    except Exception as e:
        print(f"    [tushare] 获取失败: {e}")
        return None


def fetch_efinance(symbol, period, count):
    """从 efinance (东方财富) 获取K线"""
    import efinance as ef
    code, _, _, _, ef_code = _parse_symbol(symbol)
    try:
        klt_map = {'1m': 1, '5m': 5, '15m': 15, '30m': 30, '60m': 60, '120m': 120, '1d': 101}
        klt = klt_map.get(period, 5)
        df = ef.stock.get_quote_history(ef_code, klt=klt, fqt=0)
        if df is None or df.empty:
            return None
        col_map = {
            '日期': 'Date', '开盘': 'Open', '最高': 'High',
            '最低': 'Low', '收盘': 'Close', '成交量': 'Volume'
        }
        for old, new in col_map.items():
            if old in df.columns:
                df[new] = df[old]
        df['Date'] = pd.to_datetime(df['Date'])
        df = df.sort_values('Date').reset_index(drop=True)
        cols = ['Date', 'Open', 'High', 'Low', 'Close', 'Volume']
        cols = [c for c in cols if c in df.columns]
        df = df[cols].copy()
        return df
    except Exception as e:
        print(f"    [efinance] 获取失败: {e}")
        return None


def fetch_longbridge(symbol, period, count):
    """从长桥获取K线"""
    from longport.openapi import Config, QuoteContext, Period, AdjustType
    config = Config.from_env()
    ctx = QuoteContext(config)
    
    period_map = {
        '1m': Period.Min_1, '2m': Period.Min_2, '3m': Period.Min_3,
        '5m': Period.Min_5, '10m': Period.Min_10, '15m': Period.Min_15,
        '20m': Period.Min_20, '30m': Period.Min_30, '45m': Period.Min_45,
        '60m': Period.Min_60, '120m': Period.Min_120, '180m': Period.Min_180,
        '240m': Period.Min_240, '1d': Period.Day
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


def fetch_data(symbol, period, count, min_rows=None):
    """统一数据获取接口，按优先级尝试多个数据源
    
    优先级: tdxrs > 长桥 > tushare pro > efinance
    
    Args:
        symbol: 如 '000001.SH'
        period: 如 '5m', '15m', '1d'
        count: 期望获取的K线数量
        min_rows: 最小有效行数（默认 count 的 50%）
    """
    if min_rows is None:
        min_rows = max(int(count * 0.5), 10)
    
    sources = [
        ('tdxrs', fetch_tdxrs),
        ('长桥', fetch_longbridge),
        ('tushare', fetch_tushare),
        ('efinance', fetch_efinance),
    ]
    
    for name, fn in sources:
        try:
            df = fn(symbol, period, count)
            if df is not None and len(df) >= min_rows:
                print(f"    ✅ [{name}] {period} 获取成功: {len(df)} 条")
                return df
            elif df is not None:
                print(f"    ⚠️ [{name}] {period} 数据不足: {len(df)}/{min_rows} 条，尝试下一个数据源")
            else:
                print(f"    ⚠️ [{name}] {period} 返回空，尝试下一个数据源")
        except Exception as e:
            print(f"    ❌ [{name}] {period} 异常: {e}")
    
    print(f"    🔴 所有数据源均失败: {symbol} {period}")
    return pd.DataFrame(columns=['Date', 'Open', 'High', 'Low', 'Close', 'Volume'])
