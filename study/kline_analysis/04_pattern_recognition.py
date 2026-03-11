# K线形态识别脚本

"""
K线技术分析 - 形态识别工具
用于自动识别常见K线形态
"""

import pandas as pd
import numpy as np


def is_doji(open_price, close_price, high, low, threshold=0.01):
    """
    识别十字星形态
    
    参数:
        open_price: 开盘价
        close_price: 收盘价
        high: 最高价
        low: 最低价
        threshold: 实体占价格范围的阈值
    
    返回:
        bool: 是否为十字星
    """
    body = abs(close_price - open_price)
    range_price = high - low
    
    if range_price == 0:
        return False
    
    return body / range_price < threshold


def is_hammer(open_price, close_price, high, low):
    """
    识别锤子线形态
    
    条件:
        1. 小实体(在价格范围上部)
        2. 长下影线(>=2倍实体)
        3. 上影线很短或没有
    
    返回:
        bool: 是否为锤子线
        str: 'bullish'(看涨) 或 'bearish'(看跌)
    """
    body = abs(close_price - open_price)
    upper_shadow = high - max(open_price, close_price)
    lower_shadow = min(open_price, close_price) - low
    range_price = high - low
    
    if body == 0 or range_price == 0:
        return False, None
    
    # 小实体(实体<范围30%)
    small_body = body / range_price < 0.3
    
    # 长下影线(>=2倍实体)
    long_lower = lower_shadow >= 2 * body
    
    # 短上影线(<实体)
    short_upper = upper_shadow < body
    
    if small_body and long_lower and short_upper:
        # 判断颜色
        if close_price > open_price:
            return True, 'bullish'
        else:
            return True, 'bearish'
    
    return False, None


def is_shooting_star(open_price, close_price, high, low):
    """
    识别流星线形态
    
    条件:
        1. 小实体(在价格范围下部)
        2. 长上影线(>=2倍实体)
        3. 下影线很短或没有
    """
    body = abs(close_price - open_price)
    upper_shadow = high - max(open_price, close_price)
    lower_shadow = min(open_price, close_price) - low
    range_price = high - low
    
    if body == 0 or range_price == 0:
        return False, None
    
    # 小实体
    small_body = body / range_price < 0.3
    
    # 长上影线
    long_upper = upper_shadow >= 2 * body
    
    # 短下影线
    short_lower = lower_shadow < body
    
    if small_body and long_upper and short_lower:
        if close_price < open_price:
            return True, 'bearish'
        else:
            return True, 'bullish'
    
    return False, None


def is_engulfing(df, idx):
    """
    识别吞没形态
    
    参数:
        df: DataFrame包含open, high, low, close
        idx: 当前索引(必须是第二根K线)
    
    返回:
        bool: 是否形成吞没
        str: 'bullish'(看涨吞没) 或 'bearish'(看跌吞没)
    """
    if idx < 1:
        return False, None
    
    prev_open = df['open'].iloc[idx-1]
    prev_close = df['close'].iloc[idx-1]
    curr_open = df['open'].iloc[idx]
    curr_close = df['close'].iloc[idx]
    
    # 看涨吞没
    if curr_close > curr_open:  # 当前阳线
        if prev_close < prev_open:  # 前一根阴线
            if curr_open < prev_close and curr_close > prev_open:
                return True, 'bullish'
    
    # 看跌吞没
    if curr_close < curr_open:  # 当前阴线
        if prev_close > prev_open:  # 前一根阳线
            if curr_open > prev_close and curr_close < prev_open:
                return True, 'bearish'
    
    return False, None


def is_morning_star(df, idx):
    """
    识别早晨之星形态(三根K线)
    
    条件:
        1. 第一根: 大阴线
        2. 第二根: 小实体(星线)
        3. 第三根: 大阳线，收盘深入第一根实体
    """
    if idx < 2:
        return False
    
    # 第一根: 大阴线
    first_body = df['open'].iloc[idx-2] - df['close'].iloc[idx-2]
    first_range = df['high'].iloc[idx-2] - df['low'].iloc[idx-2]
    
    if first_body / first_range < 0.5:  # 不够大
        return False
    
    if df['close'].iloc[idx-2] >= df['open'].iloc[idx-2]:  # 不是阴线
        return False
    
    # 第二根: 小实体(星线)
    second_body = abs(df['close'].iloc[idx-1] - df['open'].iloc[idx-1])
    second_range = df['high'].iloc[idx-1] - df['low'].iloc[idx-1]
    
    if second_body / second_range > 0.3:  # 不够小
        return False
    
    # 第三根: 大阳线
    if df['close'].iloc[idx] <= df['open'].iloc[idx]:  # 不是阳线
        return False
    
    third_body = df['close'].iloc[idx] - df['open'].iloc[idx]
    if third_body / first_body < 0.5:  # 不够大
        return False
    
    # 第三根收盘深入第一根实体
    if df['close'].iloc[idx] > (df['open'].iloc[idx-2] + df['close'].iloc[idx-2]) / 2:
        return True
    
    return False


def is_evening_star(df, idx):
    """
    识别黄昏之星形态(三根K线)
    
    条件:
        1. 第一根: 大阳线
        2. 第二根: 小实体(星线)
        3. 第三根: 大阴线，收盘深入第一根实体
    """
    if idx < 2:
        return False
    
    # 第一根: 大阳线
    first_body = df['close'].iloc[idx-2] - df['open'].iloc[idx-2]
    first_range = df['high'].iloc[idx-2] - df['low'].iloc[idx-2]
    
    if first_body / first_range < 0.5:
        return False
    
    if df['close'].iloc[idx-2] <= df['open'].iloc[idx-2]:
        return False
    
    # 第二根: 小实体
    second_body = abs(df['close'].iloc[idx-1] - df['open'].iloc[idx-1])
    second_range = df['high'].iloc[idx-1] - df['low'].iloc[idx-1]
    
    if second_body / second_range > 0.3:
        return False
    
    # 第三根: 大阴线
    if df['close'].iloc[idx] >= df['open'].iloc[idx]:
        return False
    
    third_body = df['open'].iloc[idx] - df['close'].iloc[idx]
    if third_body / first_body < 0.5:
        return False
    
    # 第三根收盘深入第一根实体
    if df['close'].iloc[idx] < (df['open'].iloc[idx-2] + df['close'].iloc[idx-2]) / 2:
        return True
    
    return False


def analyze_candlestick(df):
    """
    分析整个DataFrame的K线形态
    
    参数:
        df: DataFrame包含open, high, low, close列
    
    返回:
        DataFrame: 增加形态识别列
    """
    df = df.copy()
    
    # 初始化形态列
    df['pattern'] = ''
    df['pattern_type'] = ''
    
    for i in range(len(df)):
        open_p = df['open'].iloc[i]
        close_p = df['close'].iloc[i]
        high_p = df['high'].iloc[i]
        low_p = df['low'].iloc[i]
        
        # 检查单根K线形态
        if is_doji(open_p, close_p, high_p, low_p):
            df.loc[df.index[i], 'pattern'] = 'doji'
            df.loc[df.index[i], 'pattern_type'] = 'indecision'
        
        is_hammer_result, hammer_type = is_hammer(open_p, close_p, high_p, low_p)
        if is_hammer_result:
            df.loc[df.index[i], 'pattern'] = f'hammer_{hammer_type}'
            df.loc[df.index[i], 'pattern_type'] = 'reversal'
        
        is_star_result, star_type = is_shooting_star(open_p, close_p, high_p, low_p)
        if is_star_result:
            df.loc[df.index[i], 'pattern'] = f'shooting_star_{star_type}'
            df.loc[df.index[i], 'pattern_type'] = 'reversal'
        
        # 检查组合形态
        if i >= 1:
            is_engulf, engulf_type = is_engulfing(df, i)
            if is_engulf:
                df.loc[df.index[i], 'pattern'] = f'engulfing_{engulf_type}'
                df.loc[df.index[i], 'pattern_type'] = 'reversal'
        
        if i >= 2:
            if is_morning_star(df, i):
                df.loc[df.index[i], 'pattern'] = 'morning_star'
                df.loc[df.index[i], 'pattern_type'] = 'reversal'
            elif is_evening_star(df, i):
                df.loc[df.index[i], 'pattern'] = 'evening_star'
                df.loc[df.index[i], 'pattern_type'] = 'reversal'
    
    return df


def get_pattern_summary(df):
    """
    获取形态统计摘要
    
    返回:
        dict: 各形态出现次数统计
    """
    patterns = df[df['pattern'] != '']['pattern'].value_counts().to_dict()
    return patterns


# 示例使用
if __name__ == '__main__':
    # 创建示例数据
    data = {
        'open': [100, 102, 101, 98, 95],
        'high': [103, 104, 103, 100, 97],
        'low': [99, 101, 95, 94, 92],
        'close': [102, 101, 98, 95, 96]
    }
    df = pd.DataFrame(data)
    
    # 分析形态
    result = analyze_candlestick(df)
    print("K线形态分析结果:")
    print(result[['open', 'high', 'low', 'close', 'pattern', 'pattern_type']])
    
    # 统计摘要
    summary = get_pattern_summary(result)
    print("\n形态统计:")
    for pattern, count in summary.items():
        print(f"  {pattern}: {count}次")
