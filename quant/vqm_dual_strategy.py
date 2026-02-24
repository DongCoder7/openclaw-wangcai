#!/usr/bin/env python3
"""
VQM策略 - 双策略配置版 (选项3)
- 保守策略70% + 科技增强30%
- 组合优化，分散风险
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

print('='*60)
print('🚀 VQM双策略配置版 - 组合测试')
print('配置: 保守70% + 科技增强30%')
print('='*60)

# 加载数据
conn = sqlite3.connect(DB_PATH)
query = '''
    SELECT ts_code, trade_date, close, volume, change_pct
    FROM daily_price
    WHERE trade_date BETWEEN '20180101' AND '20210104'
    ORDER BY ts_code, trade_date
'''
df = pd.read_sql(query, conn)
conn.close()

# 股票池分类
stock_stats = df.groupby('ts_code').agg({
    'volume': 'sum',
    'trade_date': 'count',
    'change_pct': 'std'
}).reset_index()
stock_stats['annual_vol'] = stock_stats['change_pct'] * np.sqrt(252)
stock_stats = stock_stats[stock_stats['trade_date'] > 700]

# 分类: 保守股(低波动) vs 科技股(高波动)
conservative_stocks = stock_stats.nsmallest(30, 'annual_vol')['ts_code'].tolist()
tech_stocks = stock_stats.nlargest(25, 'annual_vol')['ts_code'].tolist()

print(f'保守股池: {len(conservative_stocks)}只 (低波动)')
print(f'科技股池: {len(tech_stocks)}只 (高波动)')

# 计算因子
df = df.sort_values(['ts_code', 'trade_date'])
df['alpha'] = df.groupby('ts_code')['close'].pct_change(10)
df['beta'] = df.groupby('ts_code')['close'].pct_change(1).rolling(10).std().reset_index(level=0, drop=True)
df['quality'] = df.groupby('ts_code')['close'].pct_change(20)
df['tech_momentum'] = df.groupby('ts_code')['close'].pct_change(5)

date_data = {d: df[df['trade_date'] == d].set_index('ts_code') for d in sorted(df['trade_date'].unique())}
trading_dates = sorted(df['trade_date'].unique().tolist())

def select_stocks_conservative(date_idx, n=4):
    """保守策略选股 - 低波动优先"""
    if date_idx < 20: return []
    date = trading_dates[date_idx]
    factors = date_data.get(date)
    if factors is None: return []
    factors = factors[factors.index.isin(conservative_stocks)]
    factors = factors.dropna(subset=['alpha', 'beta', 'quality'])
    if factors.empty: return []
    
    factors['score'] = (
        factors['alpha'].rank(pct=True) * 0.5 +
        (1 - factors['beta'].rank(pct=True)) * 0.35 +  # 高Beta惩罚
        factors['quality'].rank(pct=True) * 0.15
    )
    return factors.nlargest(n, 'score').index.tolist()

def select_stocks_tech(date_idx, n=3):
    """科技策略选股 - 高动量优先"""
    if date_idx < 20: return []
    date = trading_dates[date_idx]
    factors = date_data.get(date)
    if factors is None: return []
    factors = factors[factors.index.isin(tech_stocks)]
    factors = factors.dropna(subset=['alpha', 'tech_momentum'])
    if factors.empty: return []
    
    factors['score'] = (
        factors['tech_momentum'].rank(pct=True) * 0.4 +  # 短动量
        factors['alpha'].rank(pct=True) * 0.4 +
        (1 - factors['beta'].rank(pct=True)) * 0.2     # 低Beta惩罚降低
    )
    return factors.nlargest(n, 'score').index.tolist()

def run_dual_strategy(conservative_weight=0.7, tech_weight=0.3):
    """运行双策略配置"""
    total_capital = 1000000.0
    
    # 分配资金
    cons_capital = total_capital * conservative_weight
    tech_capital = total_capital * tech_weight
    
    # 保守策略账户
    cons_cash, cons_holdings, cons_values = cons_capital, {}, []
    # 科技策略账户  
    tech_cash, tech_holdings, tech_values = tech_capital, {}, []
    
    trades = []
    
    for di, date in enumerate(trading_dates):
        prices_data = date_data.get(date)
        if prices_data is None: continue
        prices = prices_data['close'].to_dict()
        
        # ===== 保守策略 (70%) =====
        if not cons_holdings and di > 20:
            selected = select_stocks_conservative(di, n=4)
            if selected:
                per = cons_cash * 0.7 / len(selected)  # 70%仓位
                for s in selected:
                    if s in prices and prices[s] > 0:
                        shares = int(per / prices[s] / 100) * 100
                        if shares > 0:
                            cost = shares * prices[s]
                            cons_cash -= cost
                            cons_holdings[s] = {'shares': shares, 'cost': cost}
                            trades.append({'date': date, 'strategy': 'conservative', 'action': 'BUY', 'stock': s, 'value': cost})
        
        # 保守止损 (3%)
        for s in list(cons_holdings.keys()):
            if s in prices and prices[s] > 0:
                v = cons_holdings[s]['shares'] * prices[s]
                if (v - cons_holdings[s]['cost']) / cons_holdings[s]['cost'] <= -0.03:
                    cons_cash += v
                    trades.append({'date': date, 'strategy': 'conservative', 'action': 'SELL', 'stock': s, 'reason': 'stop_loss'})
                    del cons_holdings[s]
        
        # ===== 科技策略 (30%) =====
        if not tech_holdings and di > 20:
            selected = select_stocks_tech(di, n=3)
            if selected:
                per = tech_cash * 0.8 / len(selected)  # 80%仓位(更激进)
                for s in selected:
                    if s in prices and prices[s] > 0:
                        shares = int(per / prices[s] / 100) * 100
                        if shares > 0:
                            cost = shares * prices[s]
                            tech_cash -= cost
                            tech_holdings[s] = {'shares': shares, 'cost': cost}
                            trades.append({'date': date, 'strategy': 'tech', 'action': 'BUY', 'stock': s, 'value': cost})
        
        # 科技止损 (5% - 更宽松)
        for s in list(tech_holdings.keys()):
            if s in prices and prices[s] > 0:
                v = tech_holdings[s]['shares'] * prices[s]
                if (v - tech_holdings[s]['cost']) / tech_holdings[s]['cost'] <= -0.05:
                    tech_cash += v
                    trades.append({'date': date, 'strategy': 'tech', 'action': 'SELL', 'stock': s, 'reason': 'stop_loss'})
                    del tech_holdings[s]
        
        # 计算总净值
        cons_value = cons_cash + sum(cons_holdings[s]['shares'] * prices.get(s, 0) for s in cons_holdings)
        tech_value = tech_cash + sum(tech_holdings[s]['shares'] * prices.get(s, 0) for s in tech_holdings)
        total_value = cons_value + tech_value
        
        cons_values.append(cons_value)
        tech_values.append(tech_value)
    
    if len(cons_values) < 2:
        return {'success': False, 'return': -1, 'dd': 1}
    
    # 计算组合指标
    total_values = np.array(cons_values) + np.array(tech_values)
    total_ret = (total_values[-1] - 1000000) / 1000000
    cummax = np.maximum.accumulate(total_values)
    max_dd = abs(np.min((total_values - cummax) / cummax))
    
    # 分别计算
    cons_ret = (cons_values[-1] - cons_capital) / cons_capital if cons_capital > 0 else 0
    tech_ret = (tech_values[-1] - tech_capital) / tech_capital if tech_capital > 0 else 0
    
    return {
        'success': max_dd <= 0.075,
        'return': total_ret,
        'dd': max_dd,
        'conservative_return': cons_ret,
        'tech_return': tech_ret,
        'conservative_values': cons_values,
        'tech_values': tech_values,
        'total_values': total_values.tolist(),
        'trades': trades
    }

# 测试不同配置比例
print('\\n📊 测试不同配置比例...')
configs = [
    {'cons': 0.7, 'tech': 0.3, 'name': '标准配置 (70:30)'},
    {'cons': 0.6, 'tech': 0.4, 'name': '均衡配置 (60:40)'},
    {'cons': 0.8, 'tech': 0.2, 'name': '保守配置 (80:20)'},
]

results = []
for cfg in configs:
    print(f"\\n测试: {cfg['name']}")
    result = run_dual_strategy(cfg['cons'], cfg['tech'])
    if result['success']:
        print(f"  ✅ 总收益: +{result['return']*100:.1f}% 回撤:{result['dd']*100:.1f}%")
        print(f"     保守部分: +{result['conservative_return']*100:.1f}%")
        print(f"     科技部分: +{result['tech_return']*100:.1f}%")
        results.append({
            'config': cfg['name'],
            'weights': f"{cfg['cons']*100:.0f}:{cfg['tech']*100:.0f}",
            'total_return': result['return'],
            'drawdown': result['dd'],
            'cons_return': result['conservative_return'],
            'tech_return': result['tech_return']
        })
    else:
        print(f"  ❌ 回撤超标: {result['dd']*100:.1f}%")

# 找出最佳配置
if results:
    best = max(results, key=lambda x: x['total_return'])
    
    print('\\n' + '='*60)
    print('🏆 最佳双策略配置')
    print('='*60)
    print(f"配置: {best['config']}")
    print(f"总收益: +{best['total_return']*100:.2f}%")
    print(f"最大回撤: {best['drawdown']*100:.1f}%")
    print(f"保守部分收益: +{best['cons_return']*100:.1f}%")
    print(f"科技部分收益: +{best['tech_return']*100:.1f}%")
    
    # 保存结果
    output = {
        'strategy': 'VQM_Dual_Strategy',
        'timestamp': datetime.now().isoformat(),
        'best_config': best,
        'all_results': results,
        'comparison': {
            'pure_conservative': {'return': 0.102, 'dd': 0.066},
            'dual_strategy': {'return': best['total_return'], 'dd': best['drawdown']}
        }
    }
    
    with open('/root/.openclaw/workspace/quant/best_strategy_dual.json', 'w') as f:
        json.dump(output, f, indent=2)
    
    print('\\n💾 结果已保存到 best_strategy_dual.json')

print('\\n' + '='*60)
print('📊 三种策略对比')
print('='*60)
print('策略类型          | 收益   | 回撤  | 特点')
print('-'*60)
print('纯保守版         | +10.2% | 6.6%  | 低波动，银行消费')
print('科技增强版       | 待测   | 待测  | 高波动，科技股')
print('双策略配置       | 待测   | 待测  | 组合分散风险')
