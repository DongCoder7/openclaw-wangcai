#!/usr/bin/env python3
"""
VQM策略 - 高级择时轮动版 (v3.0)
- 全量816只股票池
- 市场择时: 大盘趋势向下时空仓
- 科技+保守行业轮动
- 严格7.5%回撤控制
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
print('🚀 VQM高级择时轮动策略 v3.0')
print('全量816只股票 | 择时空仓 | 科技轮动 | 回撤<7.5%')
print('='*60)

# 加载全量数据
conn = sqlite3.connect(DB_PATH)
query = '''
    SELECT ts_code, trade_date, close, volume, change_pct
    FROM daily_price
    WHERE trade_date BETWEEN '20180101' AND '20210104'
    ORDER BY ts_code, trade_date
'''
df = pd.read_sql(query, conn)
conn.close()

print(f'✅ 数据加载: {df["ts_code"].nunique()}只股票, {df["trade_date"].nunique()}个交易日')

# 行业分类 (基于代码规律)
def classify_industry(ts_code):
    code = ts_code.split('.')[0]
    try:
        num = int(code)
        # 科创板 + 创业板部分 = 科技
        if num >= 688000 or (300000 <= num <= 301000):
            return '科技'
        # 主板电子通信
        elif num in range(600000, 600100):
            return '金融'
        elif num in range(600100, 600200):
            return '地产'
        elif num in range(600300, 600400):
            return '工业'
        elif num in range(600500, 600700):
            return '消费'
        elif num in range(600700, 600900):
            return '能源'
        else:
            return '综合'
    except:
        return '综合'

df['industry'] = df['ts_code'].apply(classify_industry)

# 计算技术指标
df = df.sort_values(['ts_code', 'trade_date'])
df['momentum_10'] = df.groupby('ts_code')['close'].pct_change(10)
df['momentum_20'] = df.groupby('ts_code')['close'].pct_change(20)
df['volatility'] = df.groupby('ts_code')['close'].pct_change(1).rolling(10).std().reset_index(level=0, drop=True)

# 计算市场指数 (所有股票平均)
market = df.groupby('trade_date').agg({
    'close': 'mean',
    'volume': 'sum'
}).reset_index()
market['market_ma20'] = market['close'].rolling(20).mean()
market['market_trend'] = (market['close'] > market['market_ma20']).astype(int)

print(f'行业分布: {df.groupby("industry")["ts_code"].nunique().to_dict()}')

# 创建索引
trading_dates = sorted(df['trade_date'].unique().tolist())
date_data = {d: df[df['trade_date'] == d].copy() for d in trading_dates}
market_data = market.set_index('trade_date').to_dict('index')

# 行业轮动信号计算
industry_data = df.groupby(['trade_date', 'industry'])['close'].mean().reset_index()
industry_data['ind_momentum'] = industry_data.groupby('industry')['close'].pct_change(20)
industry_dict = {}
for date in trading_dates:
    ind = industry_data[industry_data['trade_date'] == date]
    if not ind.empty:
        ind = ind.dropna(subset=['ind_momentum'])
        industry_dict[date] = ind.sort_values('ind_momentum', ascending=False)

def get_market_signal(date):
    """市场择时信号: 1=多头, 0=空头(空仓)"""
    m = market_data.get(date)
    if m is None: return 1
    return m.get('market_trend', 1)

def get_top_industries(date, n=3):
    """获取强势行业"""
    ind = industry_dict.get(date)
    if ind is None or ind.empty: return []
    return ind['industry'].tolist()[:n]

def select_stocks(date_idx, params):
    """选股逻辑"""
    if date_idx < 30: return []
    
    date = trading_dates[date_idx]
    
    # 市场择时: 趋势向下时空仓
    if get_market_signal(date) == 0:
        return []
    
    day = date_data.get(date)
    if day is None: return []
    
    # 获取强势行业
    top_inds = get_top_industries(date, params['num_ind'])
    if not top_inds: return []
    
    selected = []
    for ind in top_inds:
        ind_stocks = day[day['industry'] == ind].copy()
        ind_stocks = ind_stocks.dropna(subset=['momentum_10', 'volatility'])
        if ind_stocks.empty: continue
        
        # 科技股降低权重
        tech_penalty = 0.8 if ind == '科技' else 1.0
        
        ind_stocks['score'] = (
            ind_stocks['momentum_10'].rank(pct=True) * 0.6 +
            ind_stocks['momentum_20'].rank(pct=True) * 0.2 -
            ind_stocks['volatility'].rank(pct=True) * 0.2
        ) * tech_penalty
        
        top = ind_stocks.nlargest(2, 'score')['ts_code'].tolist()
        selected.extend(top)
    
    return selected[:params['num_stocks']]

def run_backtest(params):
    """回测"""
    cash = 1000000.0
    holdings = {}
    values = []
    trades = []
    empty_periods = 0
    
    for di, date in enumerate(trading_dates):
        day = date_data.get(date)
        if day is None: continue
        prices = day.set_index('ts_code')['close'].to_dict()
        
        # 检查市场信号
        market_signal = get_market_signal(date)
        
        # 市场信号为0时清仓
        if market_signal == 0 and holdings:
            for s in list(holdings.keys()):
                if s in prices:
                    cash += holdings[s]['sh'] * prices[s]
                    trades.append({'date': date, 'a': 'SELL', 's': s, 'r': 'market_down', 'ind': holdings[s]['ind']})
                    del holdings[s]
            empty_periods += 1
        
        # 建仓
        if not holdings and market_signal == 1 and di > 30:
            sel = select_stocks(di, params)
            if sel:
                per = cash * params['pos'] / len(sel)
                for s in sel:
                    if s in prices and prices[s] > 0:
                        sh = int(per / prices[s] / 100) * 100
                        if sh > 0:
                            cost = sh * prices[s]
                            cash -= cost
                            ind = day[day['ts_code']==s]['industry'].values[0] if not day[day['ts_code']==s].empty else '未知'
                            holdings[s] = {'sh': sh, 'cost': cost, 'ind': ind}
                            trades.append({'date': date, 'a': 'BUY', 's': s, 'ind': ind, 'v': cost})
        
        # 止损
        for s in list(holdings.keys()):
            if s in prices and prices[s] > 0:
                v = holdings[s]['sh'] * prices[s]
                sl = params['sl'] * (1.5 if holdings[s]['ind'] == '科技' else 1.0)  # 科技股更宽松止损
                if (v - holdings[s]['cost']) / holdings[s]['cost'] <= -sl:
                    cash += v
                    trades.append({'date': date, 'a': 'SELL', 's': s, 'r': 'stop', 'ind': holdings[s]['ind']})
                    del holdings[s]
        
        # 调仓
        if di % 20 == 0 and holdings and market_signal == 1:
            new_sel = set(select_stocks(di, params))
            
            for s in list(holdings.keys()):
                if s not in new_sel and s in prices:
                    cash += holdings[s]['sh'] * prices[s]
                    trades.append({'date': date, 'a': 'SELL', 's': s, 'r': 'rotate', 'ind': holdings[s]['ind']})
                    del holdings[s]
            
            need = params['num_stocks'] - len(holdings)
            if need > 0:
                for s in [x for x in new_sel if x not in holdings][:need]:
                    if s in prices and prices[s] > 0 and cash > 0:
                        per = cash * params['pos'] / (need + 1)
                        sh = int(per / prices[s] / 100) * 100
                        if sh > 0:
                            cost = sh * prices[s]
                            cash -= cost
                            ind = day[day['ts_code']==s]['industry'].values[0] if not day[day['ts_code']==s].empty else '未知'
                            holdings[s] = {'sh': sh, 'cost': cost, 'ind': ind}
                            trades.append({'date': date, 'a': 'BUY', 's': s, 'ind': ind, 'v': cost})
        
        v = cash + sum(holdings[s]['sh'] * prices.get(s, 0) for s in holdings)
        values.append(v)
    
    if len(values) < 2:
        return {'success': False, 'ret': -1, 'dd': 1, 'trades': [], 'empty': 0}
    
    pv = np.array(values)
    ret = (pv[-1] - 1000000) / 1000000
    cummax = np.maximum.accumulate(pv)
    dd = abs(np.min((pv - cummax) / cummax))
    
    return {
        'success': dd <= 0.075,
        'ret': ret,
        'dd': dd,
        'trades': trades,
        'empty': empty_periods,
        'pv': pv
    }

# 优化
print('\n🔬 开始高级优化 (20轮 × 50次 = 1000次迭代)...')
all_results = []
best_success = {'ret': -1, 'dd': 1, 'params': None}
best_overall = {'ret': -1, 'dd': 1, 'params': None, 'trades': []}

for r in range(1, 21):
    for _ in range(50):
        params = {
            'num_ind': random.randint(2, 4),
            'num_stocks': random.randint(4, 8),
            'pos': random.uniform(0.4, 0.7),
            'sl': random.uniform(0.025, 0.05),
        }
        
        result = run_backtest(params)
        
        all_results.append({
            'ret': result['ret'],
            'dd': result['dd'],
            'success': result['success'],
            'params': params
        })
        
        if result['success'] and result['ret'] > best_success['ret']:
            best_success.update(result)
            best_success['params'] = params
            print(f'🎉 第{r}轮新最佳: +{result["ret"]*100:.1f}% 回撤{result["dd"]*100:.1f}% 空仓{result["empty"]}次')
        
        if result['ret'] > best_overall['ret']:
            best_overall.update(result)
            best_overall['params'] = params
    
    if r % 5 == 0:
        bs = f'+{best_success["ret"]*100:.1f}%' if best_success['ret'] > -1 else '无'
        bo = f'+{best_overall["ret"]*100:.1f}%' if best_overall['ret'] > -1 else '无'
        print(f'  进度{r}/20 | 最佳成功:{bs} | 全局最佳:{bo}')

# 输出结果
print('\n' + '='*60)
print('✅ 高级择时轮动策略优化完成!')
print('='*60)

if best_success['ret'] > -1:
    print(f'\n🏆 最佳成功结果 (回撤≤7.5%):')
    print(f'   收益: +{best_success["ret"]*100:.2f}%')
    print(f'   回撤: {best_success["dd"]*100:.2f}%')
    print(f'   空仓次数: {best_success["empty"]}次')
    print(f'   参数: {best_success["params"]}')

print(f'\n📊 全局最佳结果:')
print(f'   收益: +{best_overall["ret"]*100:.2f}%')
print(f'   回撤: {best_overall["dd"]*100:.2f}% {"✅" if best_overall["dd"] <= 0.075 else "❌超标"}')
print(f'   参数: {best_overall["params"]}')

success_count = sum(1 for x in all_results if x['success'])
print(f'\n📈 统计: {success_count}/{len(all_results)} 组参数满足回撤≤7.5%')

# 行业分布
if best_overall.get('trades'):
    buys = [t for t in best_overall['trades'] if t['a'] == 'BUY']
    tech_count = sum(1 for t in buys if t.get('ind') == '科技')
    print(f'\n📊 科技股占比: {tech_count}/{len(buys)} = {tech_count/len(buys)*100:.1f}%' if buys else '无交易')

# 保存结果
output = {
    'strategy': 'VQM_Advanced_Timing_v3',
    'timestamp': datetime.now().isoformat(),
    'drawdown_limit': 0.075,
    'best_success': {
        'return': float(best_success['ret']) if best_success['ret'] > -1 else None,
        'drawdown': float(best_success['dd']) if best_success['ret'] > -1 else None,
        'params': best_success.get('params'),
        'empty_periods': best_success.get('empty', 0)
    },
    'best_overall': {
        'return': float(best_overall['ret']),
        'drawdown': float(best_overall['dd']),
        'success': best_overall['dd'] <= 0.075,
        'params': best_overall.get('params')
    },
    'statistics': {
        'total': len(all_results),
        'success_count': success_count,
        'success_rate': success_count / len(all_results) if all_results else 0
    }
}

with open('/root/.openclaw/workspace/quant/v3_advanced_timing.json', 'w') as f:
    json.dump(output, f, indent=2)

print('\n💾 结果已保存到 v3_advanced_timing.json')
print('='*60)
