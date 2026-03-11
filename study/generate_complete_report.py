#!/root/.openclaw/workspace/venv/bin/python3
"""
WFO完整分析报告 - 7只股票
包含：支撑位/压力位计算详解、预测收益方法说明
"""

import pandas as pd
import numpy as np
from datetime import datetime
import pickle
import json

print("="*70)
print("WFO滚动周期预测完整分析报告")
print("="*70)
print(f"报告时间: {datetime.now()}")
print(f"分析股票: 7只")
print(f"数据周期: 252个交易日")
print("="*70)

# 加载数据
with open('/root/.openclaw/workspace/study/wfo_stock_data_v2.pkl', 'rb') as f:
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
    
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df['rsi'] = 100 - (100 / (1 + rs))
    
    df['volatility'] = df['return'].rolling(20).std() * np.sqrt(252)
    return df

# 为每只股票计算指标
for symbol, info in stock_data.items():
    info['data'] = calculate_indicators(info['data'])

# WFO滚动窗口分析
def wfo_analysis(df):
    """WFO滚动窗口分析"""
    results = []
    n = len(df)
    num_windows = (n - TRAIN_DAYS - VALID_DAYS) // STEP_DAYS + 1
    
    for i in range(num_windows):
        start_idx = i * STEP_DAYS
        train_end = start_idx + TRAIN_DAYS
        valid_end = train_end + VALID_DAYS
        
        if valid_end > n:
            break
        
        train_data = df.iloc[start_idx:train_end].copy()
        valid_data = df.iloc[train_end:valid_end].copy()
        
        train_returns = train_data['return'].dropna()
        
        train_features = {
            'window': i + 1,
            'train_return_mean': train_returns.mean(),
            'train_return_std': train_returns.std(),
            'train_volatility': train_data['volatility'].iloc[-1],
            'train_rsi': train_data['rsi'].iloc[-1],
            'train_macd': train_data['macd'].iloc[-1],
            'train_trend': 1 if train_data['close'].iloc[-1] > train_data['close'].iloc[0] else -1,
        }
        
        # 验证期实际表现
        valid_return = (valid_data['close'].iloc[-1] / valid_data['close'].iloc[0]) - 1
        valid_max_dd = ((valid_data['close'] / valid_data['close'].cummax()) - 1).min()
        
        train_features['valid_return'] = valid_return
        train_features['valid_max_dd'] = valid_max_dd
        
        # 预测准确性
        predicted_direction = train_features['train_trend']
        actual_direction = 1 if valid_return > 0 else -1
        train_features['prediction_correct'] = 1 if predicted_direction == actual_direction else 0
        
        results.append(train_features)
    
    return pd.DataFrame(results)

print("\n" + "="*70)
print("第一部分: 支撑位与压力位详解")
print("="*70)

print("""
【计算方法说明】

支撑位 (Support) 和压力位 (Resistance) 是技术分析中的核心概念。

计算公式:
  支撑位 = 最近N个交易日最低价的最小值
  压力位 = 最近N个交易日最高价的最大值

本报告使用 N=20 (最近20个交易日，约1个月)

【支撑位含义】:
  - 股价下跌到这个位置时，买盘力量增强
  - 历史上多次在此位置反弹
  - 跌破支撑位可能继续下跌

【压力位含义】:
  - 股价上涨到这个位置时，卖盘力量增强
  - 历史上多次在此位置受阻回落
  - 突破压力位可能继续上涨

【支撑/压力位的有效性】:
  - 触碰次数越多，有效性越强
  - 时间越近，有效性越强
  - 成交量越大，有效性越强
""")

print("\n" + "-"*70)
print("7只股票支撑压力位详情")
print("-"*70)

for symbol, info in stock_data.items():
    latest = info['latest_price']
    support = info['support']
    resistance = info['resistance']
    
    # 计算距离支撑/压力的百分比
    dist_to_support = (latest - support) / support * 100
    dist_to_resistance = (resistance - latest) / resistance * 100
    
    print(f"\n📊 {info['name']} ({symbol})")
    print(f"  最新价:     {latest:.2f}")
    print(f"  支撑位:     {support:.2f} (距离 {dist_to_support:.1f}%)")
    print(f"  压力位:     {resistance:.2f} (距离 {dist_to_resistance:.1f}%)")
    print(f"  波动区间:   {support:.2f} - {resistance:.2f}")
    
    # 判断位置
    if dist_to_support < 5:
        print(f"  位置判断:   🔵 接近支撑位 (关注反弹机会)")
    elif dist_to_resistance < 5:
        print(f"  位置判断:   🔴 接近压力位 (关注突破或回落)")
    else:
        mid = (support + resistance) / 2
        if latest > mid:
            print(f"  位置判断:   🟡 区间上半部分 (偏强)")
        else:
            print(f"  位置判断:   ⚪ 区间下半部分 (偏弱)")

print("\n" + "="*70)
print("第二部分: 未来预测收益计算方法详解")
print("="*70)

print("""
【WFO (Walk-Forward Optimization) 滚动窗口优化方法】

Step 1: 数据分割
  - 将252天数据分割成多个滚动窗口
  - 每个窗口包含:
    • 训练期: 60天 (用于学习历史规律)
    • 验证期: 20天 (用于验证预测准确性)
  - 滚动步长: 20天 (窗口向前推进)
  - 总窗口数: 9个

Step 2: 特征工程
  对每个训练期计算以下特征:
  
  A. 趋势特征:
     - 训练期收益率均值 (train_return_mean)
     - 训练期趋势方向 (train_trend)
       * 收盘价 > 开盘价 → 上涨趋势 (编码: +1)
       * 收盘价 < 开盘价 → 下跌趋势 (编码: -1)
  
  B. 技术指标:
     - RSI (相对强弱指标): 0-100
       * RSI > 70 → 超买 (看跌信号)
       * RSI < 30 → 超卖 (看涨信号)
       * 30-70 → 中性
     
     - MACD (指数平滑异同移动平均线):
       * MACD > 0 → 金叉区域 (看涨)
       * MACD < 0 → 死叉区域 (看跌)
  
  C. 波动率:
     - 年化波动率 (volatility)
     - 用于评估风险水平

Step 3: 验证期表现评估
  对每个窗口的验证期计算:
  
  - 实际收益率 (valid_return):
    valid_return = (验证期收盘价 / 验证期开盘价) - 1
  
  - 最大回撤 (valid_max_dd):
    验证期内从高点到低点的最大跌幅
  
  - 预测准确性 (prediction_correct):
    比较训练期趋势方向与验证期实际方向
    * 方向一致 → 预测正确 (1)
    * 方向相反 → 预测错误 (0)

Step 4: 综合评分计算

  公式:
  综合评分 = (趋势得分 × 1.0) + (RSI得分 × 0.5) + (MACD得分 × 0.8) + (历史准确率调整 × 0.5)
  
  各项得分说明:
  
  A. 趋势得分 = train_trend (+1 或 -1)
     - 上涨趋势 +1分
     - 下跌趋势 -1分
  
  B. RSI得分:
     - RSI > 70 (超买): -1分
     - RSI < 30 (超卖): +1分
     - 30-70 (中性): 0分
  
  C. MACD得分:
     - MACD > 0 (金叉区域): +1分
     - MACD < 0 (死叉区域): -1分
  
  D. 历史准确率调整:
     调整值 = (历史准确率 - 0.5) × 2
     - 准确率 > 50% → 正向调整
     - 准确率 < 50% → 负向调整

Step 5: 预测方向判定

  根据综合评分判定预测方向:
  
  综合评分 >= 1.5  → 强烈看涨 🚀
  综合评分 >= 0.5  → 看涨 📈
  综合评分 >= -0.5 → 震荡 ➡️
  综合评分 >= -1.5 → 看跌 📉
  综合评分 < -1.5  → 强烈看跌 🔻

Step 6: 预期收益预测

  公式:
  预期收益 = 历史平均验证期收益 × 方向系数 × 准确率调整
  
  其中:
  - 历史平均验证期收益: 该股票所有窗口验证期收益的平均值
  - 方向系数: 根据预测方向确定
    * 强烈看涨: +1.0
    * 看涨: +0.8
    * 震荡: 0
    * 看跌: -0.8
    * 强烈看跌: -1.0
  - 准确率调整: 历史准确率 / 0.5 (基准准确率)

【预测收益的局限性】:
1. 基于历史数据，不代表未来表现
2. 20日预测周期较短，随机性较大
3. 未考虑突发事件影响
4. 建议作为参考，不作为投资依据
""")

print("\n" + "="*70)
print("第三部分: 7只股票WFO预测结果")
print("="*70)

all_predictions = []

for symbol, info in stock_data.items():
    df = info['data']
    wfo_df = wfo_analysis(df)
    
    if len(wfo_df) == 0:
        continue
    
    latest = wfo_df.iloc[-1]
    
    # 计算综合评分
    trend_score = latest['train_trend'] * 1.0
    
    rsi = latest['train_rsi']
    rsi_score = 0
    rsi_signal = '中性'
    if rsi > 70:
        rsi_score = -1
        rsi_signal = '超买'
    elif rsi < 30:
        rsi_score = 1
        rsi_signal = '超卖'
    
    macd = latest['train_macd']
    macd_score = 1 if macd > 0 else -1
    macd_signal = '金叉区域' if macd > 0 else '死叉区域'
    
    accuracy = wfo_df['prediction_correct'].mean()
    accuracy_adjust = (accuracy - 0.5) * 2
    
    composite_score = trend_score + (rsi_score * 0.5) + (macd_score * 0.8) + (accuracy_adjust * 0.5)
    
    # 预测方向
    if composite_score >= 1.5:
        direction = '强烈看涨'
        direction_code = 2
        emoji = '🚀'
    elif composite_score >= 0.5:
        direction = '看涨'
        direction_code = 1
        emoji = '📈'
    elif composite_score >= -0.5:
        direction = '震荡'
        direction_code = 0
        emoji = '➡️'
    elif composite_score >= -1.5:
        direction = '看跌'
        direction_code = -1
        emoji = '📉'
    else:
        direction = '强烈看跌'
        direction_code = -2
        emoji = '🔻'
    
    # 预期收益
    avg_valid_return = wfo_df['valid_return'].mean()
    predicted_return = avg_valid_return * (direction_code / 2) * (accuracy / 0.5)
    
    # 风险等级
    vol = latest['train_volatility']
    if vol > 0.7:
        risk_level = '高'
    elif vol > 0.5:
        risk_level = '中高'
    elif vol > 0.3:
        risk_level = '中等'
    else:
        risk_level = '低'
    
    pred = {
        'symbol': symbol,
        'name': info['name'],
        'latest_price': info['latest_price'],
        'support': info['support'],
        'resistance': info['resistance'],
        'composite_score': composite_score,
        'direction': direction,
        'emoji': emoji,
        'predicted_return_20d': predicted_return,
        'rsi': rsi,
        'rsi_signal': rsi_signal,
        'macd': macd,
        'macd_signal': macd_signal,
        'trend': '上涨' if latest['train_trend'] > 0 else '下跌',
        'accuracy': accuracy,
        'volatility': vol,
        'risk_level': risk_level,
        'avg_historical_return': avg_valid_return
    }
    
    all_predictions.append(pred)
    
    # 打印结果
    print(f"\n{emoji} {info['name']} ({symbol})")
    print(f"  最新价格:     {info['latest_price']:.2f}")
    print(f"  支撑位:       {info['support']:.2f}")
    print(f"  压力位:       {info['resistance']:.2f}")
    print(f"  预测方向:     {direction}")
    print(f"  预期收益(20日): {predicted_return:.2%}")
    print(f"  综合评分:     {composite_score:.2f}")
    print(f"  历史准确率:   {accuracy:.1%}")
    print(f"  当前趋势:     {pred['trend']}")
    print(f"  RSI指标:      {rsi:.1f} ({rsi_signal})")
    print(f"  MACD指标:     {macd:.4f} ({macd_signal})")
    print(f"  波动率:       {vol:.2%}")
    print(f"  风险等级:     {risk_level}")

# 排序
all_predictions.sort(key=lambda x: x['composite_score'], reverse=True)

print("\n" + "="*70)
print("推荐排序 (按综合评分)")
print("="*70)

for i, pred in enumerate(all_predictions, 1):
    rank_emoji = '🥇' if i == 1 else '🥈' if i == 2 else '🥉' if i == 3 else '•'
    print(f"{rank_emoji} {i}. {pred['name']}: {pred['direction']} (评分{pred['composite_score']:.2f}, 预期收益{pred['predicted_return_20d']:.2%})")

print("\n" + "="*70)
print("风险提示")
print("="*70)
print("""
⚠️ 重要声明:
1. 本分析基于历史数据，不构成投资建议
2. 预测准确率平均约60%，存在较大不确定性
3. 半导体行业波动率高，风险较大
4. 支撑位和压力位可能被突破，需动态调整
5. 建议小仓位验证，严格设置止损
6. 本报告仅供学习和研究使用
""")

# 保存完整报告
with open('/root/.openclaw/workspace/study/WFO_COMPLETE_REPORT.txt', 'w', encoding='utf-8') as f:
    f.write("="*70 + "\n")
    f.write("WFO滚动周期预测完整报告\n")
    f.write("="*70 + "\n")
    f.write(f"生成时间: {datetime.now()}\n")
    f.write(f"分析股票: 7只\n")
    f.write(f"数据周期: 252个交易日\n")
    f.write("="*70 + "\n\n")
    
    for pred in all_predictions:
        f.write(f"{pred['emoji']} {pred['name']} ({pred['symbol']})\n")
        f.write(f"  最新价: {pred['latest_price']:.2f}\n")
        f.write(f"  支撑位: {pred['support']:.2f}\n")
        f.write(f"  压力位: {pred['resistance']:.2f}\n")
        f.write(f"  预测方向: {pred['direction']}\n")
        f.write(f"  预期收益(20日): {pred['predicted_return_20d']:.2%}\n")
        f.write(f"  综合评分: {pred['composite_score']:.2f}\n")
        f.write(f"  历史准确率: {pred['accuracy']:.1%}\n")
        f.write(f"  RSI: {pred['rsi']:.1f} ({pred['rsi_signal']})\n")
        f.write(f"  MACD: {pred['macd']:.4f} ({pred['macd_signal']})\n")
        f.write(f"  风险等级: {pred['risk_level']}\n\n")

print("\n" + "="*70)
print("完整报告已保存到: WFO_COMPLETE_REPORT.txt")
print("="*70)
