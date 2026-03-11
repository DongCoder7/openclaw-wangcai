#!/root/.openclaw/workspace/venv/bin/python3
"""
WFO滚动窗口优化分析 - 完整实现
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import pickle
import json
import warnings
warnings.filterwarnings('ignore')

# 加载数据
with open('/root/.openclaw/workspace/study/wfo_stock_data.pkl', 'rb') as f:
    stock_data = pickle.load(f)

# WFO参数
TRAIN_DAYS = 60
VALID_DAYS = 20
STEP_DAYS = 20

# 技术指标计算
def calculate_indicators(df):
    df = df.copy()
    df['return'] = df['close'].pct_change()
    df['ma5'] = df['close'].rolling(5).mean()
    df['ma10'] = df['close'].rolling(10).mean()
    df['ma20'] = df['close'].rolling(20).mean()
    
    exp1 = df['close'].ewm(span=12, adjust=False).mean()
    exp2 = df['close'].ewm(span=26, adjust=False).mean()
    df['macd'] = exp1 - exp2
    df['macd_signal'] = df['macd'].ewm(span=9, adjust=False).mean()
    df['macd_hist'] = df['macd'] - df['macd_signal']
    
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df['rsi'] = 100 - (100 / (1 + rs))
    
    df['volatility'] = df['return'].rolling(20).std() * np.sqrt(252)
    df['volume_ma5'] = df['volume'].rolling(5).mean()
    df['volume_ratio'] = df['volume'] / df['volume_ma5']
    df['price_position'] = (df['close'] - df['close'].rolling(20).min()) / \
                           (df['close'].rolling(20).max() - df['close'].rolling(20).min())
    
    return df

# 为每只股票计算指标
for symbol, info in stock_data.items():
    info['data'] = calculate_indicators(info['data'])

# WFO滚动窗口分析
def wfo_rolling_analysis(df, symbol, name):
    """
    WFO滚动窗口分析
    返回各窗口的分析结果
    """
    results = []
    n = len(df)
    
    # 计算可以分成多少个窗口
    num_windows = (n - TRAIN_DAYS - VALID_DAYS) // STEP_DAYS + 1
    
    for i in range(num_windows):
        start_idx = i * STEP_DAYS
        train_end = start_idx + TRAIN_DAYS
        valid_end = train_end + VALID_DAYS
        
        if valid_end > n:
            break
        
        # 训练数据
        train_data = df.iloc[start_idx:train_end].copy()
        # 验证数据
        valid_data = df.iloc[train_end:valid_end].copy()
        
        # 计算训练期特征
        train_returns = train_data['return'].dropna()
        train_features = {
            'window': i + 1,
            'train_start': train_data['date'].iloc[0],
            'train_end': train_data['date'].iloc[-1],
            'valid_start': valid_data['date'].iloc[0],
            'valid_end': valid_data['date'].iloc[-1],
            'train_return_mean': train_returns.mean(),
            'train_return_std': train_returns.std(),
            'train_volatility': train_data['volatility'].iloc[-1],
            'train_rsi': train_data['rsi'].iloc[-1],
            'train_macd': train_data['macd'].iloc[-1],
            'train_price_position': train_data['price_position'].iloc[-1],
            'train_trend': 1 if train_data['close'].iloc[-1] > train_data['close'].iloc[0] else -1,
        }
        
        # 计算验证期实际表现
        valid_return = (valid_data['close'].iloc[-1] / valid_data['close'].iloc[0]) - 1
        valid_max_drawdown = ((valid_data['close'] / valid_data['close'].cummax()) - 1).min()
        
        train_features['valid_return'] = valid_return
        train_features['valid_max_dd'] = valid_max_drawdown
        train_features['valid_sharpe'] = valid_return / (valid_data['return'].std() * np.sqrt(VALID_DAYS)) if valid_data['return'].std() > 0 else 0
        
        # 信号准确性评估
        predicted_direction = train_features['train_trend']
        actual_direction = 1 if valid_return > 0 else -1
        train_features['prediction_correct'] = 1 if predicted_direction == actual_direction else 0
        
        results.append(train_features)
    
    return pd.DataFrame(results)

# 运行WFO分析
print("\n" + "="*70)
print("WFO滚动窗口分析结果")
print("="*70 + "\n")

all_results = {}

for symbol, info in stock_data.items():
    name = info['name']
    df = info['data']
    
    print(f"\n📈 {name} ({symbol})")
    print("-" * 70)
    
    # 运行WFO
    wfo_results = wfo_rolling_analysis(df, symbol, name)
    all_results[symbol] = wfo_results
    
    # 显示结果摘要
    if len(wfo_results) > 0:
        print(f"  窗口数量: {len(wfo_results)}")
        print(f"  方向预测准确率: {wfo_results['prediction_correct'].mean():.1%}")
        print(f"  平均验证期收益: {wfo_results['valid_return'].mean():.2%}")
        print(f"  平均最大回撤: {wfo_results['valid_max_dd'].mean():.2%}")
        print(f"  最新训练期趋势: {'上涨📈' if wfo_results['train_trend'].iloc[-1] > 0 else '下跌📉'}")
        print(f"  最新RSI: {wfo_results['train_rsi'].iloc[-1]:.1f}")
        print(f"  最新MACD: {wfo_results['train_macd'].iloc[-1]:.4f}")

# 保存结果
with open('/root/.openclaw/workspace/study/wfo_results.pkl', 'wb') as f:
    pickle.dump(all_results, f)

print("\n" + "="*70)
print("WFO分析完成，结果已保存")
print("="*70)
