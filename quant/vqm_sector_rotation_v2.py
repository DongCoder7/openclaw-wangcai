#!/usr/bin/env python3
"""
VQM策略 - 行业轮动版 (回撤限制15%)
- 按行业板块轮动
- 动态调整行业配置
- 目标: 15%回撤内追求更高收益
- 修改: 无满足条件时输出最接近结果
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
print('🚀 VQM行业轮动策略 - 15%回撤限制')
print('='*60)

# 加载全量股票数据
conn = sqlite3.connect(DB_PATH)
query = '''
    SELECT ts_code, trade_date, close, volume, change_pct
    FROM daily_price
    WHERE trade_date BETWEEN '20180101' AND '20210104'
    ORDER BY ts_code, trade_date
'''
df = pd.read_sql(query, conn)
conn.close()

print(f'数据加载: {df["ts_code"].nunique()}只股票, {df["trade_date"].nunique()}个交易日')

# 简单行业分类
def get_industry(ts_code):
    code = ts_code.split('.')[0]
    prefix = code[:3] if code[:2] in ['60', '00', '30', '68'] else code[:2]
    
    # 根据实际A股代码规律分类
    code_num = int(code[:6]) if code[:6].isdigit() else 0
    
    if code_num in range(600000, 600100) or '银行' in ts_code:
        return '银行'
    elif code_num in range(600100, 600200) or '地产' in ts_code:
        return '地产'
    elif code_num in range(600500, 600700) or '酒' in ts_code or '食' in ts_code:
        return '消费'
    elif code_num >= 300000 or '科技' in ts_code or '电子' in ts_code:
        return '科技'
    elif code_num in range(600300, 600400) or '钢铁' in ts_code or '煤炭' in ts_code:
        return '周期'
    else:
        return '综合'

# 为每只股票打标签
df['industry'] = df['ts_code'].apply(get_industry)

# 计算动量
df = df.sort_values(['ts_code', 'trade_date'])
df['momentum'] = df.groupby('ts_code')['close'].pct_change(20)
df['volatility'] = df.groupby('ts_code')['close'].pct_change(1).rolling(20).std().reset_index(level=0, drop=True)

# 计算行业动量
industry_df = df.groupby(['trade_date', 'industry'])['close'].mean().reset_index()
industry_df['ind_momentum'] = industry_df.groupby('industry')['close'].pct_change(20)

print(f'行业分布: {df.groupby("industry")["ts_code"].nunique().to_dict()}')

# 创建索引
trading_dates = sorted(df['trade_date'].unique().tolist())
date_data = {d: df[df['trade_date'] == d].copy() for d in trading_dates}

def get_top_industries(date, n=3):
    """获取当日行业排名"""
    ind = industry_df[industry_df['trade_date'] == date]
    if ind.empty: return []
    ind = ind.dropna(subset=['ind_momentum'])
    return ind.sort_values('ind_momentum', ascending=False)['industry'].tolist()[:n]

def select_stocks(date_idx, params):
    """选股"""
    if date_idx < 20: return []
    
    date = trading_dates[date_idx]
    day = date_data.get(date)
    if day is None: return []
    
    # 获取强势行业
    top_inds = get_top_industries(date, params['num_ind'])
    if not top_inds: return []
    
    selected = []
    for ind in top_inds:
        ind_stocks = day[day['industry'] == ind].copy()
        ind_stocks = ind_stocks.dropna(subset=['momentum', 'volatility'])
        if ind_stocks.empty: continue
        
        # 评分
        ind_stocks['score'] = (
            ind_stocks['momentum'].rank(pct=True) * 0.7 -
            ind_stocks['volatility'].rank(pct=True) * 0.3
        )
        
        top = ind_stocks.nlargest(2, 'score')['ts_code'].tolist()
        selected.extend(top)
    
    return selected[:params['num_stocks']]

def run_backtest(params):
    """回测"""
    cash = 1000000.0
    holdings = {}
    values = []
    trades = []
    
    for di, date in enumerate(trading_dates):
        day = date_data.get(date)
        if day is None: continue
        prices = day.set_index('ts_code')['close'].to_dict()
        
        # 建仓
        if not holdings and di > 20:
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
            continue
        
        # 止损
        for s in list(holdings.keys()):
            if s in prices and prices[s] > 0:
                v = holdings[s]['sh'] * prices[s]
                if (v - holdings[s]['cost']) / holdings[s]['cost'] <= -params['sl']:
                    cash += v
                    trades.append({'date': date, 'a': 'SELL', 's': s, 'r': 'stop', 'ind': holdings[s]['ind']})
                    del holdings[s]
        
        # 轮动调仓
        if di % 20 == 0 and holdings:
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
        return {'success': False, 'ret': -1, 'dd': 1, 'trades': []}
    
    pv = np.array(values)
    ret = (pv[-1] - 1000000) / 1000000
    cummax = np.maximum.accumulate(pv)
    dd = abs(np.min((pv - cummax) / cummax))
    
    return {'success': dd <= 0.15, 'ret': ret, 'dd': dd, 'trades': trades, 'values': values, 'pv': pv}

# 优化 - 记录所有结果
print('\n🔬 开始优化...')
all_results = []  # 记录所有结果
best_success = {'ret': -1, 'dd': 1, 'params': None}
best_overall = {'ret': -1, 'dd': 1, 'params': None, 'trades': [], 'success': False}

for r in range(1, 21):
    for _ in range(50):
        params = {
            'num_ind': random.randint(2, 4),
            'num_stocks': random.randint(6, 10),
            'pos': random.uniform(0.7, 0.95),
            'sl': random.uniform(0.08, 0.15),
        }
        
        result = run_backtest(params)
        
        # 记录所有结果
        all_results.append({
            'ret': result['ret'],
            'dd': result['dd'],
            'success': result['success'],
            'params': params
        })
        
        # 更新最佳成功结果
        if result['success'] and result['ret'] > best_success['ret']:
            best_success.update(result)
            best_success['params'] = params
            print(f'🎉 第{r}轮新最佳(成功): +{result["ret"]*100:.1f}% 回撤{result["dd"]*100:.1f}%')
        
        # 更新全局最佳(不管是否成功)
        if result['ret'] > best_overall['ret']:
            best_overall.update(result)
            best_overall['params'] = params
    
    if r % 5 == 0:
        bs = f'+{best_success["ret"]*100:.1f}%' if best_success['ret'] > -1 else '无'
        bo = f'+{best_overall["ret"]*100:.1f}%' if best_overall['ret'] > -1 else '无'
        print(f'  进度{r}/20 | 最佳成功:{bs} | 全局最佳:{bo}')

# 输出结果
print('\n' + '='*60)
print('✅ 优化完成!')
print('='*60)

# 如果有成功结果
if best_success['ret'] > -1:
    print(f'\n🏆 最佳成功结果 (回撤≤15%):')
    print(f'   收益: +{best_success["ret"]*100:.2f}%')
    print(f'   回撤: {best_success["dd"]*100:.1f}%')
    print(f'   参数: 行业{best_success["params"]["num_ind"]}个, 持股{best_success["params"]["num_stocks"]}只')

# 输出全局最佳(即使回撤超标)
print(f'\n📊 全局最佳结果 (回撤可能超标):')
print(f'   收益: +{best_overall["ret"]*100:.2f}%')
print(f'   回撤: {best_overall["dd"]*100:.1f}% {"✅" if best_overall["dd"] <= 0.15 else "❌超标"}')
print(f'   参数: {best_overall["params"]}')

# 统计
success_count = sum(1 for x in all_results if x['success'])
print(f'\n📈 统计: {success_count}/{len(all_results)} 组参数满足回撤≤15%')

# 找出最接近15%回撤的高收益结果
close_results = [x for x in all_results if 0.14 <= x['dd'] <= 0.20 and x['ret'] > 0]
if close_results:
    close_best = max(close_results, key=lambda x: x['ret'])
    print(f'\n🎯 最接近15%回撤的高收益结果:')
    print(f'   收益: +{close_best["ret"]*100:.2f}%')
    print(f'   回撤: {close_best["dd"]*100:.1f}%')

# 行业分布
if best_overall.get('trades'):
    buys = [t for t in best_overall['trades'] if t['a'] == 'BUY']
    ind_count = {}
    for t in buys:
        ind = t.get('ind', '未知')
        ind_count[ind] = ind_count.get(ind, 0) + 1
    
    print(f'\n📊 行业交易分布:')
    for ind, cnt in sorted(ind_count.items(), key=lambda x: x[1], reverse=True)[:5]:
        print(f'   {ind}: {cnt}次')

# 保存结果
output = {
    'timestamp': datetime.now().isoformat(),
    'strategy': 'VQM_Sector_Rotation_15pct',
    'drawdown_limit': 0.15,
    'best_success': {
        'return': float(best_success['ret']) if best_success['ret'] > -1 else None,
        'drawdown': float(best_success['dd']) if best_success['ret'] > -1 else None,
        'params': best_success.get('params')
    },
    'best_overall': {
        'return': float(best_overall['ret']),
        'drawdown': float(best_overall['dd']),
        'success': best_overall['dd'] <= 0.15,
        'params': best_overall.get('params')
    },
    'statistics': {
        'total': len(all_results),
        'success_count': success_count,
        'success_rate': success_count / len(all_results) if all_results else 0
    }
}

with open('/root/.openclaw/workspace/quant/sector_rotation_results.json', 'w') as f:
    json.dump(output, f, indent=2)

print('\n💾 结果已保存到 sector_rotation_results.json')
