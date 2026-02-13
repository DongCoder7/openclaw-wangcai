import pandas as pd
import numpy as np

# 使用之前获取的日K数据
data = [
    ['2026-02-02', 14.66, 14.45, 14.87, 14.43, 1.33],
    ['2026-02-03', 14.61, 14.95, 15.00, 14.46, 1.71],
    ['2026-02-04', 14.92, 15.05, 15.05, 14.80, 1.23],
    ['2026-02-05', 14.90, 14.75, 15.03, 14.73, 0.94],
    ['2026-02-06', 14.55, 14.72, 14.93, 14.44, 0.93],
    ['2026-02-09', 14.90, 14.98, 15.00, 14.78, 1.50],
    ['2026-02-10', 15.13, 15.30, 15.40, 15.12, 2.10],
    ['2026-02-11', 15.29, 15.10, 15.34, 15.08, 1.14],
    ['2026-02-12', 15.10, 15.32, 15.36, 15.04, 1.29],
    ['2026-02-13', 15.20, 15.48, 15.56, 15.15, 1.00]
]

df = pd.DataFrame(data, columns=['日期', '开盘', '收盘', '最高', '最低', '成交额'])
df['收盘'] = df['收盘'].astype(float)

# 计算均线
df['MA5'] = df['收盘'].rolling(window=5).mean()
df['MA10'] = df['收盘'].rolling(window=10).mean()

# 最新数据
latest = df.iloc[-1]

print('=== 领益智造(002600) 技术分析 ===')
print(f'最新收盘价: {latest[\"收盘\"]:.2f}')
print()
print('=== 均线系统 ===')
print(f'MA5:  {latest[\"MA5\"]:.2f}')
print(f'MA10: {latest[\"MA10\"]:.2f}')
is_above_ma5 = latest["收盘"] > latest["MA5"]
print(f'股价位于MA5之上: {\"是\" if is_above_ma5 else \"否\"}')
print()

# 计算MACD
exp1 = df['收盘'].ewm(span=12, adjust=False).mean()
exp2 = df['收盘'].ewm(span=26, adjust=False).mean()
df['DIF'] = exp1 - exp2
df['DEA'] = df['DIF'].ewm(span=9, adjust=False).mean()
df['MACD'] = 2 * (df['DIF'] - df['DEA'])

latest_macd = df.iloc[-1]
prev_macd = df.iloc[-2]

print('=== MACD指标 ===')
print(f'DIF: {latest_macd[\"DIF\"]:.3f}')
print(f'DEA: {latest_macd[\"DEA\"]:.3f}')
print(f'MACD柱状: {latest_macd[\"MACD\"]:.3f}')
if latest_macd['DIF'] > latest_macd['DEA'] and prev_macd['DIF'] <= prev_macd['DEA']:
    signal = '金叉（买入信号）'
elif latest_macd['DIF'] < latest_macd['DEA'] and prev_macd['DIF'] >= prev_macd['DEA']:
    signal = '死叉（卖出信号）'
else:
    signal = '维持现状'
print(f'信号: {signal}')
print()

# 近期走势
print('=== 近期走势统计 ===')
print(f'近5日涨跌幅: {((latest[\"收盘\"] / df.iloc[-5][\"收盘\"]) - 1) * 100:.2f}%')
print(f'近10日涨跌幅: {((latest[\"收盘\"] / df.iloc[0][\"收盘\"]) - 1) * 100:.2f}%')

# 60日范围估算
high_10 = df['最高'].max()
low_10 = df['最低'].min()
print(f'近期高点: {high_10:.2f}')
print(f'近期低点: {low_10:.2f}')
current_pos = (latest["收盘"] - low_10) / (high_10 - low_10) * 100
print(f'当前位置: {current_pos:.1f}%')

# 量价分析
print()
print('=== 量价分析 ===')
avg_volume = df['成交额'].tail(5).mean()
latest_volume = latest['成交额']
print(f'近5日平均成交额: {avg_volume:.2f}亿元')
print(f'今日成交额: {latest_volume:.2f}亿元')
if latest_volume > avg_volume * 1.1:
    vol_status = '放量'
elif latest_volume < avg_volume * 0.9:
    vol_status = '缩量'
else:
    vol_status = '平量'
print(f'量能: {vol_status}')
