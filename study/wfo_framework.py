#!/root/.openclaw/workspace/venv/bin/python3
"""
WFO滚动窗口优化分析 - 7只股票短期走势预测
Walk-Forward Optimization (WFO) 框架

设计思路:
1. 训练期: 60天滚动窗口
2. 验证期: 20天 (约1个月)
3. 步长: 20天 (滚动推进)
4. 预测: 基于优化参数预测未来走势
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import pickle
import json
import warnings
warnings.filterwarnings('ignore')

print("="*70)
print("WFO滚动窗口优化分析框架")
print("="*70)
print(f"分析时间: {datetime.now()}")
print(f"分析方法: Walk-Forward Optimization (WFO)")
print(f"训练窗口: 60天")
print(f"验证窗口: 20天")
print(f"预测目标: 短期走势方向 + 强度")
print("="*70)

# 加载数据
with open('/root/.openclaw/workspace/study/wfo_stock_data.pkl', 'rb') as f:
    stock_data = pickle.load(f)

print(f"\n📊 已加载 {len(stock_data)} 只股票数据\n")

# WFO参数设置
TRAIN_DAYS = 60    # 训练期天数
VALID_DAYS = 20    # 验证期天数
STEP_DAYS = 20     # 滚动步长

print("WFO参数配置:")
print(f"  • 训练期: {TRAIN_DAYS} 天")
print(f"  • 验证期: {VALID_DAYS} 天")
print(f"  • 滚动步长: {STEP_DAYS} 天")
print()

# 技术指标计算函数
def calculate_indicators(df):
    """计算技术指标"""
    df = df.copy()
    
    # 收益率
    df['return'] = df['close'].pct_change()
    
    # 移动平均线
    df['ma5'] = df['close'].rolling(5).mean()
    df['ma10'] = df['close'].rolling(10).mean()
    df['ma20'] = df['close'].rolling(20).mean()
    
    # MACD
    exp1 = df['close'].ewm(span=12, adjust=False).mean()
    exp2 = df['close'].ewm(span=26, adjust=False).mean()
    df['macd'] = exp1 - exp2
    df['macd_signal'] = df['macd'].ewm(span=9, adjust=False).mean()
    df['macd_hist'] = df['macd'] - df['macd_signal']
    
    # RSI
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df['rsi'] = 100 - (100 / (1 + rs))
    
    # 波动率
    df['volatility'] = df['return'].rolling(20).std() * np.sqrt(252)
    
    # 成交量指标
    df['volume_ma5'] = df['volume'].rolling(5).mean()
    df['volume_ratio'] = df['volume'] / df['volume_ma5']
    
    # 价格位置 (过去20日区间)
    df['price_position'] = (df['close'] - df['close'].rolling(20).min()) / \
                           (df['close'].rolling(20).max() - df['close'].rolling(20).min())
    
    return df

# 为每只股票计算指标
for symbol, info in stock_data.items():
    info['data'] = calculate_indicators(info['data'])
    print(f"✅ {info['name']} ({symbol}): 技术指标计算完成")

print("\n" + "="*70)
print("开始WFO滚动分析")
print("="*70)
