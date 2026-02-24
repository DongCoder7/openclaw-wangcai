#!/usr/bin/env python3
"""
VQM策略回测优化系统 v5.0 (极速版)
- 减少股票数量
- 优化查询
"""

import os
import sys
import pandas as pd
import numpy as np
from datetime import datetime
import sqlite3
import json
import random
import warnings
warnings.filterwarnings('ignore')

DB_PATH = '/root/.openclaw/workspace/data/historical/historical.db'

print("🚀 VQM策略回测优化系统 v5.0")
print("="*60)

# 加载数据
print("📊 加载数据...")
conn = sqlite3.connect(DB_PATH)

# 只加载50只活跃股票
query = '''
    SELECT ts_code, trade_date, close, volume
    FROM daily_price
    WHERE trade_date BETWEEN '20180101' AND '20210104'
      AND ts_code IN (
        SELECT ts_code FROM daily_price 
        WHERE trade_date BETWEEN '20180101' AND '20210104'
        GROUP BY ts_code 
        HAVING COUNT(*) > 700
        ORDER BY SUM(volume) DESC
        LIMIT 50
      )
    ORDER BY ts_code, trade_date
'''

df = pd.read_sql(query, conn)
conn.close()

print(f"   数据量: {len(df):,} 行")
stock_list = df['ts_code'].unique().tolist()
print(f"   股票数: {len(stock_list)}")

trading_dates = sorted(df['trade_date'].unique().tolist())
print(f"   交易日: {len(trading_dates)}")

# 预计算因子
print("🔧 预计算因子...")
df = df.sort_values(['ts_code', 'trade_date'])
df['return_20d'] = df.groupby('ts_code')['close'].pct_change(20)
df['volatility_20d'] = df.groupby('ts_code')['close'].pct_change(1).rolling(20).std().reset_index(level=0, drop=True)
df['volume_ma20'] = df.groupby('ts_code')['volume'].rolling(20).mean().reset_index(level=0, drop=True)
df['volume_ratio'] = df['volume'] / df['volume_ma20']

# 创建快速查询索引
df_dict = df.set_index(['ts_code', 'trade_date']).to_dict('index')
date_data = {d: df[df['trade_date'] == d].copy() for d in trading_dates}

print("✅ 数据准备完成")
print("="*60)


def get_rebalance_dates():
    """获取每月第一个交易日"""
    dates = []
    for i in range(36):
        year, month = 2018 + i // 12, i % 12 + 1
        target = f"{year}{month:02d}"
        for d in trading_dates:
            if d.startswith(target):
                dates.append(d)
                break
    return dates


def select_stocks(date: str, params: dict) -> list:
    """选股"""
    data = date_data.get(date)
    if data is None or data.empty:
        return random.sample(stock_list, min(8, len(stock_list)))
    
    data = data.dropna(subset=['return_20d', 'volatility_20d'])
    if data.empty:
        return random.sample(stock_list, min(8, len(stock_list)))
    
    # 计算得分
    data['score'] = (
        data['return_20d'].rank(pct=True) * params['alpha'] +
        (1 - data['volatility_20d'].rank(pct=True)) * params['beta'] +
        (1 - abs(data['volume_ratio'] - 1).rank(pct=True)) * params['vol'] +
        (1 - data['volatility_20d'].rank(pct=True)) * params['low_vol']
    )
    
    return data.nlargest(8, 'score')['ts_code'].tolist()


def get_price(stock: str, date: str) -> float:
    """获取价格"""
    key = (stock, date)
    if key in df_dict:
        return df_dict[key].get('close', 0)
    return 0


def run_backtest(params: dict) -> dict:
    """运行回测"""
    rebalance_dates = set(get_rebalance_dates())
    
    cash = 1000000.0
    holdings = {}
    portfolio_values = []
    trades = 0
    
    for date in trading_dates:
        # 调仓
        if date in rebalance_dates:
            # 卖出
            for stock in list(holdings.keys()):
                price = get_price(stock, date)
                if price > 0:
                    cash += holdings[stock] * price
                    trades += 1
            holdings = {}
            
            # 选股买入
            selected = select_stocks(date, params)
            if selected and cash > 0:
                per_stock = cash / len(selected)
                for stock in selected:
                    price = get_price(stock, date)
                    if price > 0:
                        shares = int(per_stock / price / 100) * 100
                        if shares > 0:
                            cash -= shares * price
                            holdings[stock] = shares
                            trades += 1
        
        # 计算组合价值
        value = cash
        for stock, shares in holdings.items():
            price = get_price(stock, date)
            value += shares * price
        portfolio_values.append(value)
    
    # 计算指标
    pv = np.array(portfolio_values)
    returns = np.diff(pv) / pv[:-1]
    
    total_return = (pv[-1] - 1000000) / 1000000
    years = len(pv) / 252
    annual_return = (1 + total_return) ** (1/years) - 1 if years > 0 else 0
    
    cummax = np.maximum.accumulate(pv)
    max_drawdown = abs(np.min((pv - cummax) / cummax))
    
    sharpe = (annual_return - 0.03) / (np.std(returns) * np.sqrt(252)) if np.std(returns) > 0 else 0
    
    return {
        'success': max_drawdown <= 0.075,
        'total_return': total_return,
        'annual_return': annual_return,
        'max_drawdown': max_drawdown,
        'sharpe': sharpe,
        'trades': trades,
        'final_value': pv[-1]
    }


# 运行优化
print(f"\n🚀 开始50次参数优化...")
print("="*60)

results = []
best = None
best_return = -float('inf')

for i in range(50):
    # 随机参数
    params = {
        'alpha': random.uniform(0.1, 0.8),
        'beta': random.uniform(0.1, 0.6),
        'vol': random.uniform(0.0, 0.4),
        'low_vol': random.uniform(0.0, 0.3),
    }
    total = sum(params.values())
    params = {k: v/total for k, v in params.items()}
    
    # 运行回测
    result = run_backtest(params)
    
    results.append({'iteration': i+1, 'params': params, 'result': result})
    
    status = "✅" if result['success'] else "❌"
    print(f"{status} {i+1:02d}/50 | 收益:{result['total_return']*100:+6.1f}% | "
          f"年化:{result['annual_return']*100:+6.1f}% | 回撤:{result['max_drawdown']*100:5.1f}% | "
          f"夏普:{result['sharpe']:5.2f}")
    
    if result['total_return'] > best_return:
        best_return = result['total_return']
        best = {'iteration': i+1, 'params': params, **result}

print("="*60)

# 保存结果
output = {
    'timestamp': datetime.now().isoformat(),
    'best': best,
    'all_results': [{'iteration': r['iteration'], 'params': r['params'], 
                     'total_return': r['result']['total_return'],
                     'max_drawdown': r['result']['max_drawdown']} for r in results]
}

with open('/root/.openclaw/workspace/quant/backtest_results.json', 'w') as f:
    json.dump(output, f, indent=2, default=lambda x: float(x) if isinstance(x, (np.floating, np.integer)) else str(x))

# 打印最佳报告
print(f"""
📊 最佳回测报告 #{best['iteration']}
{'='*50}

🎯 参数配置:
   • 动量因子(α): {best['params']['alpha']*100:.1f}%
   • 波动率因子(β): {best['params']['beta']*100:.1f}%
   • 成交量因子: {best['params']['vol']*100:.1f}%
   • 低波动偏好: {best['params']['low_vol']*100:.1f}%

📈 收益指标:
   • 总收益率: {best['total_return']*100:+.2f}%
   • 年化收益率: {best['annual_return']*100:+.2f}%
   • 最终净值: ¥{best['final_value']:,.0f}

⚠️ 风险指标:
   • 最大回撤: {best['max_drawdown']*100:.2f}%
   • 夏普比率: {best['sharpe']:.2f}

✅ 状态: {'成功 (回撤<7.5%)' if best['success'] else '失败'}
{'='*50}
""")

print(f"\n💾 结果已保存到: /root/.openclaw/workspace/quant/backtest_results.json")
