#!/usr/bin/env python3
"""
VQM策略回测优化系统 v8.0 (极速版)
- 每日调仓+止损
- 简化计算逻辑
"""

import os
import pandas as pd
import numpy as np
from datetime import datetime
import sqlite3
import json
import random
import warnings
warnings.filterwarnings('ignore')

DB_PATH = '/root/.openclaw/workspace/data/historical/historical.db'

print("🚀 VQM策略回测优化系统 v8.0")
print("="*60)

# 加载数据
print("📊 加载数据...")
conn = sqlite3.connect(DB_PATH)

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
        LIMIT 30
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
df['alpha'] = df.groupby('ts_code')['close'].pct_change(10)
df['beta'] = df.groupby('ts_code')['close'].pct_change(1).rolling(10).std().reset_index(level=0, drop=True)
df['quality'] = df.groupby('ts_code')['close'].pct_change(20)

# 创建索引
date_data = {d: df[df['trade_date'] == d].set_index('ts_code')['close'].to_dict() for d in trading_dates}
date_factors = {d: df[df['trade_date'] == d].set_index('ts_code') for d in trading_dates}

print("✅ 准备完成")
print("="*60)


def select_stocks(date_idx: int, params: dict) -> list:
    """选股"""
    if date_idx < 20:
        return []
    
    date = trading_dates[date_idx]
    factors = date_factors.get(date)
    if factors is None or factors.empty:
        return random.sample(stock_list, min(4, len(stock_list)))
    
    factors = factors.dropna(subset=['alpha', 'beta', 'quality'])
    if factors.empty:
        return random.sample(stock_list, min(4, len(stock_list)))
    
    # 评分
    factors['score'] = (
        factors['alpha'].rank(pct=True) * params['alpha_w'] +
        (1 - factors['beta'].rank(pct=True)) * params['beta_w'] +
        factors['quality'].rank(pct=True) * params['quality_w']
    )
    
    return factors.nlargest(params['n_stocks'], 'score').index.tolist()


def run_backtest(params: dict) -> dict:
    """极速回测"""
    cash = 1000000.0
    holdings = {}  # {stock: (shares, cost)}
    values = []
    trades = 0
    
    n_stocks = params['n_stocks']
    stop_loss = params['stop_loss']
    position_pct = params['position_pct']
    
    for di, date in enumerate(trading_dates):
        prices = date_data.get(date, {})
        
        # 首次建仓
        if not holdings:
            selected = select_stocks(di, params)
            if selected:
                available = cash * position_pct
                per = available / len(selected)
                for s in selected:
                    if s in prices and prices[s] > 0:
                        shares = int(per / prices[s] / 100) * 100
                        if shares > 0:
                            cost = shares * prices[s]
                            cash -= cost
                            holdings[s] = (shares, cost)
                            trades += 1
            continue
        
        # 止损检查
        to_sell = []
        for s, (shares, cost) in holdings.items():
            if s in prices and prices[s] > 0:
                ret = (shares * prices[s] - cost) / cost
                if ret <= -stop_loss:
                    to_sell.append(s)
        
        for s in to_sell:
            cash += holdings[s][0] * prices.get(s, 0)
            trades += 1
            del holdings[s]
        
        # 调仓
        if di % 5 == 0:  # 每5天调仓一次
            current = set(holdings.keys())
            selected = set(select_stocks(di, params))
            
            # 卖出不在候选的
            for s in list(holdings.keys()):
                if s not in selected and s in prices:
                    cash += holdings[s][0] * prices[s]
                    trades += 1
                    del holdings[s]
            
            # 买入候选
            if len(holdings) < n_stocks:
                need = n_stocks - len(holdings)
                candidates = [s for s in selected if s not in holdings]
                for s in candidates[:need]:
                    if s in prices and prices[s] > 0 and cash > 0:
                        per = cash / (need + 1)
                        shares = int(per / prices[s] / 100) * 100
                        if shares > 0:
                            cost = shares * prices[s]
                            cash -= cost
                            holdings[s] = (shares, cost)
                            trades += 1
        
        # 计算净值
        v = cash
        for s, (shares, _) in holdings.items():
            if s in prices:
                v += shares * prices[s]
        values.append(v)
    
    # 指标
    pv = np.array(values)
    if len(pv) < 2:
        return {'success': False, 'total_return': -1, 'max_drawdown': 1}
    
    rets = np.diff(pv) / pv[:-1]
    total_ret = (pv[-1] - 1000000) / 1000000
    years = len(pv) / 252
    annual = (1 + total_ret) ** (1/max(years, 0.1)) - 1
    
    cummax = np.maximum.accumulate(pv)
    max_dd = abs(np.min((pv - cummax) / cummax))
    
    std = np.std(rets)
    sharpe = (annual - 0.03) / (std * np.sqrt(252)) if std > 0 else 0
    
    return {
        'success': max_dd <= 0.075,
        'total_return': total_ret,
        'annual_return': annual,
        'max_drawdown': max_dd,
        'sharpe': sharpe,
        'trades': trades,
        'final_value': pv[-1]
    }


# 优化
print(f"\n🚀 50次参数优化...")
print("="*60)

results = []
best = None
best_ret = -float('inf')

for i in range(50):
    params = {
        'alpha_w': random.uniform(0.3, 0.6),
        'beta_w': random.uniform(0.2, 0.4),
        'quality_w': random.uniform(0.1, 0.3),
        'n_stocks': random.randint(3, 5),
        'stop_loss': 0.075,
        'position_pct': random.uniform(0.4, 0.7),
    }
    total = params['alpha_w'] + params['beta_w'] + params['quality_w']
    params['alpha_w'] /= total
    params['beta_w'] /= total
    params['quality_w'] /= total
    
    result = run_backtest(params)
    results.append({'iteration': i+1, 'params': params, 'result': result})
    
    status = "✅" if result['success'] else "❌"
    print(f"{status} {i+1:02d}/50 | 收益:{result['total_return']*100:+6.1f}% | 回撤:{result['max_drawdown']*100:5.1f}% | 夏普:{result['sharpe']:5.2f}")
    
    if result['total_return'] > best_ret:
        best_ret = result['total_return']
        best = {'iteration': i+1, 'params': params, **result}

print("="*60)
print(f"✅ 完成! 最佳:{best_ret*100:.1f}% 回撤:{best['max_drawdown']*100:.1f}% 成功:{best['success']}")

# 保存
output = {
    'timestamp': datetime.now().isoformat(),
    'best': {
        'iteration': best['iteration'],
        'params': {k: float(v) for k, v in best['params'].items()},
        'total_return': float(best['total_return']),
        'max_drawdown': float(best['max_drawdown']),
        'success': bool(best['success'])
    },
    'summary': {
        'total': 50,
        'success_count': sum(1 for r in results if r['result']['success']),
        'best_return': float(best_ret)
    }
}

with open('/root/.openclaw/workspace/quant/backtest_results.json', 'w') as f:
    json.dump(output, f, indent=2)

print(f"\n📊 报告:")
print(f"   最佳迭代: #{best['iteration']}")
print(f"   收益: {best['total_return']*100:+.1f}%")
print(f"   回撤: {best['max_drawdown']*100:.1f}%")
print(f"   成功: {'是' if best['success'] else '否'}")
print(f"   持仓: {best['params']['n_stocks']}只")
print(f"   仓位: {best['params']['position_pct']*100:.0f}%")
