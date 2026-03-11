#!/root/.openclaw/workspace/venv/bin/python3
"""
WFO预测生成与优化分析
基于滚动窗口结果预测未来走势
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import pickle
import json

# 加载WFO结果
with open('/root/.openclaw/workspace/study/wfo_results.pkl', 'rb') as f:
    wfo_results = pickle.load(f)

with open('/root/.openclaw/workspace/study/wfo_stock_data.pkl', 'rb') as f:
    stock_data = pickle.load(f)

print("="*70)
print("WFO预测生成与优化分析")
print("="*70)
print(f"预测时间: {datetime.now()}")
print(f"预测周期: 未来20个交易日")
print("="*70)

# 预测函数
def generate_prediction(symbol, wfo_df, stock_info):
    """
    基于WFO结果生成预测
    """
    latest = wfo_df.iloc[-1]
    
    # 趋势强度计算
    trend_strength = abs(latest['train_return_mean']) / latest['train_return_std'] if latest['train_return_std'] > 0 else 0
    
    # RSI信号
    rsi = latest['train_rsi']
    if rsi > 70:
        rsi_signal = '超买'
        rsi_score = -1
    elif rsi < 30:
        rsi_signal = '超卖'
        rsi_score = 1
    else:
        rsi_signal = '中性'
        rsi_score = 0
    
    # MACD信号
    macd = latest['train_macd']
    macd_signal = '金叉区域' if macd > 0 else '死叉区域'
    macd_score = 1 if macd > 0 else -1
    
    # 历史准确率加权
    accuracy = wfo_df['prediction_correct'].mean()
    
    # 综合评分 (-3到+3)
    composite_score = (
        latest['train_trend'] * 1.0 +  # 趋势权重
        rsi_score * 0.5 +              # RSI权重
        macd_score * 0.8 +             # MACD权重
        (accuracy - 0.5) * 2           # 历史准确率权重
    )
    
    # 预测方向
    if composite_score >= 1.5:
        direction = '强烈看涨'
        direction_code = 2
    elif composite_score >= 0.5:
        direction = '看涨'
        direction_code = 1
    elif composite_score >= -0.5:
        direction = '震荡'
        direction_code = 0
    elif composite_score >= -1.5:
        direction = '看跌'
        direction_code = -1
    else:
        direction = '强烈看跌'
        direction_code = -2
    
    # 预期收益 (基于历史验证期平均收益)
    avg_return = wfo_df['valid_return'].mean()
    predicted_return = avg_return * direction_code / 2
    
    # 风险水平
    avg_volatility = latest['train_volatility']
    if avg_volatility > 0.7:
        risk_level = '高'
    elif avg_volatility > 0.5:
        risk_level = '中高'
    elif avg_volatility > 0.3:
        risk_level = '中等'
    else:
        risk_level = '低'
    
    return {
        'symbol': symbol,
        'name': stock_info['name'],
        'latest_price': stock_info['latest_price'],
        'composite_score': composite_score,
        'predicted_direction': direction,
        'direction_code': direction_code,
        'predicted_return_20d': predicted_return,
        'rsi': rsi,
        'rsi_signal': rsi_signal,
        'macd': macd,
        'macd_signal': macd_signal,
        'trend': '上涨' if latest['train_trend'] > 0 else '下跌',
        'historical_accuracy': accuracy,
        'volatility': avg_volatility,
        'risk_level': risk_level,
        'max_drawdown_hist': wfo_df['valid_max_dd'].mean()
    }

# 为每只股票生成预测
predictions = []

print("\n📊 未来20日走势预测\n")
print("-"*70)

for symbol, wfo_df in wfo_results.items():
    pred = generate_prediction(symbol, wfo_df, stock_data[symbol])
    predictions.append(pred)
    
    # 显示预测结果
    emoji = {'强烈看涨': '🚀', '看涨': '📈', '震荡': '➡️', '看跌': '📉', '强烈看跌': '🔻'}
    
    print(f"\n{pred['name']} ({symbol})")
    print(f"  当前价格: {pred['latest_price']:.2f}")
    print(f"  预测方向: {emoji.get(pred['predicted_direction'], '➡️')} {pred['predicted_direction']}")
    print(f"  预期收益: {pred['predicted_return_20d']:.2%} (20日)")
    print(f"  综合评分: {pred['composite_score']:.2f}")
    print(f"  历史准确率: {pred['historical_accuracy']:.1%}")
    print(f"  RSI指标: {pred['rsi']:.1f} ({pred['rsi_signal']})")
    print(f"  MACD指标: {pred['macd']:.4f} ({pred['macd_signal']})")
    print(f"  风险等级: {pred['risk_level']}")

# 转换为DataFrame便于分析
pred_df = pd.DataFrame(predictions)

print("\n" + "="*70)
print("预测结果汇总")
print("="*70)

# 统计
print(f"\n预测分布:")
direction_counts = pred_df['predicted_direction'].value_counts()
for direction, count in direction_counts.items():
    print(f"  {direction}: {count}只")

print(f"\n平均预期收益: {pred_df['predicted_return_20d'].mean():.2%}")
print(f"平均历史准确率: {pred_df['historical_accuracy'].mean():.1%}")
print(f"平均波动率: {pred_df['volatility'].mean():.2%}")

# 排序推荐
print("\n" + "="*70)
print("股票推荐排序 (按综合评分)")
print("="*70)

pred_df_sorted = pred_df.sort_values('composite_score', ascending=False)

for i, row in pred_df_sorted.iterrows():
    rank = pred_df_sorted.index.get_loc(i) + 1
    emoji = '🥇' if rank == 1 else '🥈' if rank == 2 else '🥉' if rank == 3 else '•'
    print(f"{emoji} {rank}. {row['name']}: {row['predicted_direction']} (评分: {row['composite_score']:.2f})")

# 保存预测结果
with open('/root/.openclaw/workspace/study/wfo_predictions.json', 'w', encoding='utf-8') as f:
    json.dump(predictions, f, ensure_ascii=False, indent=2, default=str)

print("\n" + "="*70)
print("预测结果已保存到 wfo_predictions.json")
print("="*70)
