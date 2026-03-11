#!/root/.openclaw/workspace/venv/bin/python3
"""
技术指标信号生成脚本
用于计算MACD、生成交易信号
"""

import pandas as pd
import numpy as np


def calculate_macd(df, fast=12, slow=26, signal=9):
    """
    计算MACD指标
    
    参数:
        df: DataFrame包含'close'列
        fast: 快速EMA周期 (默认12)
        slow: 慢速EMA周期 (默认26)
        signal: 信号线周期 (默认9)
    
    返回:
        DataFrame: 增加macd, signal, histogram列
    """
    df = df.copy()
    
    # 计算EMA
    ema_fast = df['close'].ewm(span=fast, adjust=False).mean()
    ema_slow = df['close'].ewm(span=slow, adjust=False).mean()
    
    # MACD线
    df['macd'] = ema_fast - ema_slow
    
    # 信号线
    df['signal'] = df['macd'].ewm(span=signal, adjust=False).mean()
    
    # MACD柱状图
    df['histogram'] = df['macd'] - df['signal']
    
    return df


def calculate_rsi(df, period=14):
    """
    计算RSI指标
    
    参数:
        df: DataFrame包含'close'列
        period: RSI周期 (默认14)
    
    返回:
        DataFrame: 增加rsi列
    """
    df = df.copy()
    
    # 计算价格变化
    delta = df['close'].diff()
    
    # 分离涨跌
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)
    
    # 计算平均涨跌
    avg_gain = gain.ewm(span=period, adjust=False).mean()
    avg_loss = loss.ewm(span=period, adjust=False).mean()
    
    # 计算RS和RSI
    rs = avg_gain / avg_loss
    df['rsi'] = 100 - (100 / (1 + rs))
    
    return df


def calculate_bollinger(df, period=20, std_dev=2):
    """
    计算布林带指标
    
    参数:
        df: DataFrame包含'close'列
        period: 移动平均周期 (默认20)
        std_dev: 标准差倍数 (默认2)
    
    返回:
        DataFrame: 增加bb_middle, bb_upper, bb_lower列
    """
    df = df.copy()
    
    # 中轨 (移动平均线)
    df['bb_middle'] = df['close'].rolling(window=period).mean()
    
    # 标准差
    rolling_std = df['close'].rolling(window=period).std()
    
    # 上轨和下轨
    df['bb_upper'] = df['bb_middle'] + (rolling_std * std_dev)
    df['bb_lower'] = df['bb_middle'] - (rolling_std * std_dev)
    
    # 带宽 (%B)
    df['bb_width'] = (df['bb_upper'] - df['bb_lower']) / df['bb_middle']
    df['bb_percent'] = (df['close'] - df['bb_lower']) / (df['bb_upper'] - df['bb_lower'])
    
    return df


def generate_macd_signals(df):
    """
    基于MACD生成交易信号
    
    信号类型:
        - BUY: 金叉买入
        - SELL: 死叉卖出
        - STRONG_BUY: 零轴上方金叉
        - STRONG_SELL: 零轴下方死叉
        - DIVERGENCE_BULL: 底背离
        - DIVERGENCE_BEAR: 顶背离
    
    返回:
        DataFrame: 增加signal列
    """
    df = df.copy()
    df['trade_signal'] = ''
    df['signal_strength'] = 0
    
    for i in range(1, len(df)):
        # 金叉检测
        if df['macd'].iloc[i] > df['signal'].iloc[i] and \
           df['macd'].iloc[i-1] <= df['signal'].iloc[i-1]:
            
            if df['macd'].iloc[i] > 0:
                df.loc[df.index[i], 'trade_signal'] = 'STRONG_BUY'
                df.loc[df.index[i], 'signal_strength'] = 3
            else:
                df.loc[df.index[i], 'trade_signal'] = 'BUY'
                df.loc[df.index[i], 'signal_strength'] = 2
        
        # 死叉检测
        elif df['macd'].iloc[i] < df['signal'].iloc[i] and \
             df['macd'].iloc[i-1] >= df['signal'].iloc[i-1]:
            
            if df['macd'].iloc[i] < 0:
                df.loc[df.index[i], 'trade_signal'] = 'STRONG_SELL'
                df.loc[df.index[i], 'signal_strength'] = -3
            else:
                df.loc[df.index[i], 'trade_signal'] = 'SELL'
                df.loc[df.index[i], 'signal_strength'] = -2
    
    return df


def detect_macd_divergence(df, lookback=5):
    """
    检测MACD背离
    
    参数:
        df: DataFrame包含close, macd列
        lookback: 回溯周期
    
    返回:
        DataFrame: 增加divergence列
    """
    df = df.copy()
    df['divergence'] = ''
    
    for i in range(lookback, len(df)):
        # 获取回溯期间的价格和MACD
        price_window = df['close'].iloc[i-lookback:i+1]
        macd_window = df['macd'].iloc[i-lookback:i+1]
        
        # 顶背离: 价格新高，MACD未新高
        if price_window.iloc[-1] == price_window.max() and \
           macd_window.iloc[-1] < macd_window.max():
            df.loc[df.index[i], 'divergence'] = 'BEARISH'
        
        # 底背离: 价格新低，MACD未新低
        elif price_window.iloc[-1] == price_window.min() and \
             macd_window.iloc[-1] > macd_window.min():
            df.loc[df.index[i], 'divergence'] = 'BULLISH'
    
    return df


def analyze_volume(df):
    """
    成交量分析
    
    返回:
        DataFrame: 增加成交量相关指标
    """
    df = df.copy()
    
    # 成交量均线
    df['volume_ma5'] = df['volume'].rolling(window=5).mean()
    df['volume_ma20'] = df['volume'].rolling(window=20).mean()
    
    # 量比
    df['volume_ratio'] = df['volume'] / df['volume_ma5']
    
    # 放量/缩量标记
    df['volume_status'] = 'normal'
    df.loc[df['volume_ratio'] > 2, 'volume_status'] = 'extreme_high'
    df.loc[(df['volume_ratio'] > 1.5) & (df['volume_ratio'] <= 2), 'volume_status'] = 'high'
    df.loc[(df['volume_ratio'] < 0.8) & (df['volume_ratio'] >= 0.5), 'volume_status'] = 'low'
    df.loc[df['volume_ratio'] < 0.5, 'volume_status'] = 'extreme_low'
    
    # 量价配合
    df['price_change'] = df['close'].pct_change()
    df['volume_price_align'] = False
    
    # 量价齐升
    df.loc[(df['price_change'] > 0) & (df['volume_ratio'] > 1.2), 'volume_price_align'] = True
    # 量价齐跌
    df.loc[(df['price_change'] < 0) & (df['volume_ratio'] > 1.2), 'volume_price_align'] = True
    
    return df


def comprehensive_analysis(df):
    """
    综合分析: MACD + RSI + 布林带 + 成交量
    
    参数:
        df: DataFrame包含open, high, low, close, volume列
    
    返回:
        DataFrame: 包含所有指标和信号
    """
    # 计算各项指标
    df = calculate_macd(df)
    df = calculate_rsi(df)
    df = calculate_bollinger(df)
    df = analyze_volume(df)
    
    # 生成MACD信号
    df = generate_macd_signals(df)
    df = detect_macd_divergence(df)
    
    # 综合评分
    df['composite_score'] = 0
    
    for i in range(len(df)):
        score = 0
        
        # MACD信号 (权重3)
        if 'BUY' in df['trade_signal'].iloc[i]:
            score += df['signal_strength'].iloc[i] * 3
        elif 'SELL' in df['trade_signal'].iloc[i]:
            score += df['signal_strength'].iloc[i] * 3
        
        # RSI (权重2)
        if df['rsi'].iloc[i] < 30:
            score += 2  # 超卖，看涨
        elif df['rsi'].iloc[i] > 70:
            score -= 2  # 超买，看跌
        
        # 布林带 (权重2)
        if df['bb_percent'].iloc[i] < 0.1:
            score += 2  # 接近下轨，看涨
        elif df['bb_percent'].iloc[i] > 0.9:
            score -= 2  # 接近上轨，看跌
        
        # 成交量 (权重1)
        if df['volume_price_align'].iloc[i]:
            if df['price_change'].iloc[i] > 0:
                score += 1  # 量价齐升
            else:
                score -= 1  # 量价齐跌
        
        # 背离 (权重2)
        if df['divergence'].iloc[i] == 'BULLISH':
            score += 4
        elif df['divergence'].iloc[i] == 'BEARISH':
            score -= 4
        
        df.loc[df.index[i], 'composite_score'] = score
    
    # 综合建议
    df['recommendation'] = 'HOLD'
    df.loc[df['composite_score'] >= 8, 'recommendation'] = 'STRONG_BUY'
    df.loc[(df['composite_score'] >= 4) & (df['composite_score'] < 8), 'recommendation'] = 'BUY'
    df.loc[(df['composite_score'] <= -4) & (df['composite_score'] > -8), 'recommendation'] = 'SELL'
    df.loc[df['composite_score'] <= -8, 'recommendation'] = 'STRONG_SELL'
    
    return df


def get_latest_signal(df):
    """
    获取最新信号摘要
    
    返回:
        dict: 最新信号信息
    """
    latest = df.iloc[-1]
    
    return {
        'date': df.index[-1],
        'price': latest['close'],
        'macd': latest['macd'],
        'signal': latest['signal'],
        'histogram': latest['histogram'],
        'rsi': latest['rsi'],
        'bb_position': latest['bb_percent'],
        'volume_ratio': latest['volume_ratio'],
        'trade_signal': latest['trade_signal'],
        'divergence': latest['divergence'],
        'composite_score': latest['composite_score'],
        'recommendation': latest['recommendation']
    }


# 示例使用
if __name__ == '__main__':
    # 创建示例数据
    np.random.seed(42)
    n = 100
    
    data = {
        'open': 100 + np.random.randn(n).cumsum(),
        'high': 100 + np.random.randn(n).cumsum() + abs(np.random.randn(n)),
        'low': 100 + np.random.randn(n).cumsum() - abs(np.random.randn(n)),
        'close': 100 + np.random.randn(n).cumsum(),
        'volume': np.random.randint(1000000, 5000000, n)
    }
    
    # 确保数据合理性
    for i in range(n):
        data['high'][i] = max(data['open'][i], data['close'][i], data['high'][i])
        data['low'][i] = min(data['open'][i], data['close'][i], data['low'][i])
    
    df = pd.DataFrame(data)
    df.index = pd.date_range('2024-01-01', periods=n, freq='D')
    
    # 综合分析
    result = comprehensive_analysis(df)
    
    # 显示最新信号
    latest = get_latest_signal(result)
    print("=" * 50)
    print("最新技术分析信号")
    print("=" * 50)
    for key, value in latest.items():
        print(f"{key}: {value}")
    
    # 显示最近5天的建议
    print("\n" + "=" * 50)
    print("最近5天交易建议")
    print("=" * 50)
    print(result[['close', 'macd', 'rsi', 'recommendation']].tail())
