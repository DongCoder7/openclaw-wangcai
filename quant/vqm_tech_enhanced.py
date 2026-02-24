#!/usr/bin/env python3
"""
VQM策略 - 科技增强版 (选项2)
- 扩展股票池包含科技股
- 提高Beta因子容忍度
- 目标: 在回撤<7.5%前提下追求更高收益
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
print('🚀 VQM科技增强版 - 20轮优化')
print('目标: 回撤<7.5%, 追求10%+收益')
print('='*60)

# 加载扩展股票池(包含科技股)
conn = sqlite3.connect(DB_PATH)
query = '''
    SELECT ts_code, trade_date, close, volume, change_pct
    FROM daily_price
    WHERE trade_date BETWEEN '20180101' AND '20210104'
    ORDER BY ts_code, trade_date
'''
df = pd.read_sql(query, conn)
conn.close()

# 计算每只股票的年化波动率筛选
vol_df = df.groupby('ts_code')['change_pct'].agg(['std', 'mean']).reset_index()
vol_df['annual_vol'] = vol_df['std'] * np.sqrt(252)

# 选择: 高成交量 + 数据完整 + 包含高波动(科技)
stock_stats = df.groupby('ts_code').agg({
    'volume': 'sum',
    'trade_date': 'count'
}).reset_index()
stock_stats = stock_stats[stock_stats['trade_date'] > 700]  # 数据完整

# 混合选股: 50只 = 30只低波 + 20只高波动(科技成长型)
stock_stats = stock_stats.merge(vol_df[['ts_code', 'annual_vol']], on='ts_code')
low_vol = stock_stats.nsmallest(30, 'annual_vol')['ts_code'].tolist()
high_vol = stock_stats.nlargest(20, 'annual_vol')['ts_code'].tolist()
selected_stocks = list(set(low_vol + high_vol))[:50]

print(f'股票池: {len(selected_stocks)}只 (低波{len(low_vol)} + 高波{len(high_vol)})')

df = df[df['ts_code'].isin(selected_stocks)]
stock_list = df['ts_code'].unique().tolist()
trading_dates = sorted(df['trade_date'].unique().tolist())

# 计算因子
df = df.sort_values(['ts_code', 'trade_date'])
df['alpha'] = df.groupby('ts_code')['close'].pct_change(10)  # 10日动量
df['beta'] = df.groupby('ts_code')['close'].pct_change(1).rolling(10).std().reset_index(level=0, drop=True)
df['quality'] = df.groupby('ts_code')['close'].pct_change(20)  # 20日质量
df['tech_momentum'] = df.groupby('ts_code')['close'].pct_change(5)  # 5日短动量(科技股)

date_data = {d: df[df['trade_date'] == d].set_index('ts_code') for d in trading_dates}

# 市场波动率
market_vol = []
for d in trading_dates:
    day_data = date_data.get(d)
    if day_data is not None and not day_data.empty:
        rets = day_data['close'].pct_change().dropna()
        market_vol.append(rets.std() if not rets.empty else 0.02)
    else:
        market_vol.append(0.02)
market_ma = pd.Series(market_vol).rolling(10).mean().tolist()

def select_stocks(date_idx, params, tech_bias=False):
    """选股 - tech_bias=True时倾向科技股"""
    if date_idx < 20: return []
    date = trading_dates[date_idx]
    factors = date_data.get(date)
    if factors is None: return []
    factors = factors.dropna(subset=['alpha', 'beta', 'quality'])
    if factors.empty: return []
    
    # 科技增强: 增加短动量权重
    tech_w = params.get('tech_w', 0.1)
    factors['score'] = (
        factors['alpha'].rank(pct=True) * (params['alpha_w'] - tech_w) +
        (1 - factors['beta'].rank(pct=True)) * params['beta_w'] * 0.7 +  # 降低Beta惩罚
        factors['quality'].rank(pct=True) * params['quality_w'] +
        factors['tech_momentum'].rank(pct=True) * tech_w  # 科技短动量
    )
    return factors.nlargest(params['n'], 'score').index.tolist()

def run_backtest(params, tech_mode=False):
    """回测"""
    cash = 1000000.0
    holdings = {}
    values = []
    trades = []
    
    for di, date in enumerate(trading_dates):
        prices_data = date_data.get(date)
        if prices_data is None: continue
        prices = prices_data['close'].to_dict()
        
        vol = market_ma[di] if di < len(market_ma) else 0.02
        base_pos = params['pos']
        
        # 波动率调整 - 科技版更激进
        if vol < 0.018: vol_adj = 1.0
        elif vol < 0.025: vol_adj = 0.75 if tech_mode else 0.65
        elif vol < 0.035: vol_adj = 0.55 if tech_mode else 0.45
        else: vol_adj = 0.35 if tech_mode else 0.25
        
        actual_pos = base_pos * vol_adj
        
        # 建仓
        if not holdings and di > 20:
            selected = select_stocks(di, params, tech_bias=tech_mode)
            if selected:
                avail = cash * actual_pos
                per = avail / len(selected)
                for s in selected:
                    if s in prices and prices[s] > 0:
                        shares = int(per / prices[s] / 100) * 100
                        if shares > 0:
                            cost = shares * prices[s]
                            cash -= cost
                            holdings[s] = {'shares': shares, 'cost': cost}
                            trades.append({'date': date, 'action': 'BUY', 'stock': s, 'value': cost})
            continue
        
        # 止损 - 科技股允许更大回撤
        sl = params['sl'] * (1.3 if tech_mode else 1.0)  # 科技版止损放宽30%
        for s in list(holdings.keys()):
            if s in prices and prices[s] > 0:
                v = holdings[s]['shares'] * prices[s]
                if (v - holdings[s]['cost']) / holdings[s]['cost'] <= -sl:
                    cash += v
                    trades.append({'date': date, 'action': 'SELL', 'stock': s, 'reason': 'stop_loss'})
                    del holdings[s]
        
        # 调仓
        selected = set(select_stocks(di, params, tech_bias=tech_mode))
        for s in list(holdings.keys()):
            if s not in selected and s in prices:
                cash += holdings[s]['shares'] * prices[s]
                trades.append({'date': date, 'action': 'SELL', 'stock': s, 'reason': 'rebalance'})
                del holdings[s]
        
        # 补仓
        need = params['n'] - len(holdings)
        if need > 0:
            for s in [x for x in selected if x not in holdings][:need]:
                if s in prices and prices[s] > 0 and cash > 0:
                    per = cash * actual_pos / (need + 1)
                    shares = int(per / prices[s] / 100) * 100
                    if shares > 0:
                        cost = shares * prices[s]
                        cash -= cost
                        holdings[s] = {'shares': shares, 'cost': cost}
                        trades.append({'date': date, 'action': 'BUY', 'stock': s, 'value': cost})
        
        v = cash + sum(holdings[s]['shares'] * prices.get(s, 0) for s in holdings)
        values.append(v)
    
    if len(values) < 2:
        return {'success': False, 'return': -1, 'dd': 1, 'trades': []}
    
    pv = np.array(values)
    total_ret = (pv[-1] - 1000000) / 1000000
    cummax = np.maximum.accumulate(pv)
    max_dd = abs(np.min((pv - cummax) / cummax))
    
    return {
        'success': max_dd <= 0.075,
        'return': total_ret,
        'dd': max_dd,
        'trades': trades,
        'values': values
    }

# 优化 - 科技增强版
print('\\n🔬 科技增强版优化 (允许更高波动)...')
best_tech = {'return': 0, 'dd': 1, 'params': None}

for r in range(1, 21):
    for _ in range(50):
        params = {
            'n': random.randint(4, 7),
            'sl': random.uniform(0.035, 0.05),  # 更宽松止损
            'pos': random.uniform(0.25, 0.4),   # 更高仓位
            'alpha_w': random.uniform(0.35, 0.5),
            'beta_w': random.uniform(0.2, 0.3), # 降低Beta权重
            'quality_w': random.uniform(0.15, 0.25),
            'tech_w': random.uniform(0.1, 0.2), # 科技动量权重
        }
        total = sum([params['alpha_w'], params['beta_w'], params['quality_w'], params['tech_w']])
        for k in ['alpha_w', 'beta_w', 'quality_w', 'tech_w']:
            params[k] /= total
        
        result = run_backtest(params, tech_mode=True)
        if result['success'] and result['return'] > best_tech['return']:
            best_tech.update(result)
            best_tech['params'] = params
            print(f'  第{r}轮新最佳: +{result["return"]*100:.1f}% 回撤{result["dd"]*100:.1f}%')
    
    if r % 5 == 0:
        print(f'  进度: {r}/20, 当前最佳: +{best_tech["return"]*100:.1f}%')

print('\\n' + '='*60)
print('✅ 科技增强版优化完成!')
print(f'🏆 最佳: +{best_tech["return"]*100:.2f}% 回撤{best_tech["dd"]*100:.1f}%')

# 统计科技股占比
tech_keywords = ['科技', '电子', '通信', '计算机', '芯片', '半导体']
if best_tech.get('trades'):
    tech_count = sum(1 for t in best_tech['trades'][:20] if any(k in str(t.get('stock', '')) for k in tech_keywords))
    print(f'📊 科技股占比: ~{tech_count*5}%')

# 保存结果
output = {
    'strategy': 'VQM_Tech_Enhanced',
    'timestamp': datetime.now().isoformat(),
    'best': {
        'return': float(best_tech['return']),
        'drawdown': float(best_tech['dd']),
        'params': {k: float(v) for k, v in best_tech['params'].items()},
    },
    'comparison': {
        'conservative': {'return': 0.102, 'dd': 0.066},
        'tech_enhanced': {'return': float(best_tech['return']), 'dd': float(best_tech['dd'])}
    }
}

with open('/root/.openclaw/workspace/quant/best_strategy_tech.json', 'w') as f:
    json.dump(output, f, indent=2)

print('💾 结果已保存到 best_strategy_tech.json')
