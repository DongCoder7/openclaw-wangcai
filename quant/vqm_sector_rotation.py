#!/usr/bin/env python3
"""
VQM策略 - 行业轮动版 (回撤限制15%)
- 按行业板块轮动
- 动态调整行业配置
- 目标: 15%回撤内追求更高收益
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

# 简单行业分类 (基于股票代码前缀)
def get_industry(ts_code):
    """基于代码前缀判断行业"""
    code = ts_code.split('.')[0]
    prefix = code[:2]
    
    # 银行
    if prefix in ['60', '00'] and int(code) in range(600000, 600100):
        return '银行'
    # 医药
    elif prefix in ['60', '00', '30'] and ('医' in ts_code or '药' in ts_code):
        return '医药'
    # 科技
    elif prefix in ['00', '30', '68']:
        return '科技'
    # 消费
    elif prefix in ['60', '00'] and int(code) in range(600500, 600700):
        return '消费'
    # 能源
    elif prefix in ['60', '00'] and int(code) in range(600000, 600100):
        return '能源'
    else:
        return '其他'

# 为每只股票打标签
df['industry'] = df['ts_code'].apply(get_industry)

# 计算行业和个股动量
df = df.sort_values(['ts_code', 'trade_date'])
df['stock_momentum'] = df.groupby('ts_code')['close'].pct_change(20)  # 20日个股动量
df['stock_volatility'] = df.groupby('ts_code')['close'].pct_change(1).rolling(20).std().reset_index(level=0, drop=True)

# 计算行业指数动量
industry_momentum = df.groupby(['trade_date', 'industry'])['close'].mean().reset_index()
industry_momentum['ind_momentum'] = industry_momentum.groupby('industry')['close'].pct_change(20)

print(f'数据加载完成: {df["ts_code"].nunique()}只股票, {df["trade_date"].nunique()}个交易日')
print(f'行业分布: {df.groupby("industry")["ts_code"].nunique().to_dict()}')

# 创建查询索引
date_data = {d: df[df['trade_date'] == d].copy() for d in sorted(df['trade_date'].unique())}
trading_dates = sorted(df['trade_date'].unique().tolist())

def get_industry_momentum(date):
    """获取当日行业动量排名"""
    ind_data = industry_momentum[industry_momentum['trade_date'] == date]
    if ind_data.empty: return []
    ind_data = ind_data.dropna(subset=['ind_momentum'])
    return ind_data.sort_values('ind_momentum', ascending=False)['industry'].tolist()

def select_stocks_by_industry(date_idx, params):
    """基于行业轮动的选股"""
    if date_idx < 20: return []
    
    date = trading_dates[date_idx]
    day_data = date_data.get(date)
    if day_data is None: return []
    
    # 获取行业排名
    ind_rank = get_industry_momentum(date)
    if not ind_rank: return []
    
    # 选择前N个行业
    top_industries = ind_rank[:params['num_industries']]
    
    selected = []
    for industry in top_industries:
        # 从该行业选最强个股
        ind_stocks = day_data[day_data['industry'] == industry].copy()
        ind_stocks = ind_stocks.dropna(subset=['stock_momentum', 'stock_volatility'])
        if ind_stocks.empty: continue
        
        # 个股评分: 动量 - 波动率惩罚
        ind_stocks['score'] = (
            ind_stocks['stock_momentum'].rank(pct=True) * 0.7 -
            ind_stocks['stock_volatility'].rank(pct=True) * 0.3
        )
        
        # 每个行业选前2只
        top_stocks = ind_stocks.nlargest(2, 'score')['ts_code'].tolist()
        selected.extend(top_stocks)
    
    return selected[:params['num_stocks']]

def run_sector_rotation(params):
    """运进行业轮动策略"""
    cash = 1000000.0
    holdings = {}
    values = []
    trades = []
    
    for di, date in enumerate(trading_dates):
        day_data = date_data.get(date)
        if day_data is None: continue
        prices = day_data.set_index('ts_code')['close'].to_dict()
        
        # 建仓
        if not holdings and di > 20:
            selected = select_stocks_by_industry(di, params)
            if selected:
                # 等权重配置
                per_stock = cash * params['position'] / len(selected)
                for s in selected:
                    if s in prices and prices[s] > 0:
                        shares = int(per_stock / prices[s] / 100) * 100
                        if shares > 0:
                            cost = shares * prices[s]
                            cash -= cost
                            holdings[s] = {'shares': shares, 'cost': cost, 'industry': day_data[day_data['ts_code']==s]['industry'].values[0]}
                            trades.append({'date': date, 'action': 'BUY', 'stock': s, 'industry': holdings[s]['industry'], 'value': cost})
            continue
        
        # 止损 (更宽松)
        for s in list(holdings.keys()):
            if s in prices and prices[s] > 0:
                v = holdings[s]['shares'] * prices[s]
                if (v - holdings[s]['cost']) / holdings[s]['cost'] <= -params['stop_loss']:
                    cash += v
                    trades.append({'date': date, 'action': 'SELL', 'stock': s, 'reason': 'stop_loss', 'industry': holdings[s]['industry']})
                    del holdings[s]
        
        # 行业轮动调仓 (每月)
        if di % 20 == 0 and holdings:  # 约每月调仓
            new_selected = set(select_stocks_by_industry(di, params))
            
            # 卖出不在新选中的
            for s in list(holdings.keys()):
                if s not in new_selected and s in prices:
                    cash += holdings[s]['shares'] * prices[s]
                    trades.append({'date': date, 'action': 'SELL', 'stock': s, 'reason': 'rotation', 'industry': holdings[s]['industry']})
                    del holdings[s]
            
            # 买入新选中的
            need = params['num_stocks'] - len(holdings)
            if need > 0:
                for s in [x for x in new_selected if x not in holdings][:need]:
                    if s in prices and prices[s] > 0 and cash > 0:
                        per = cash * params['position'] / (need + 1)
                        shares = int(per / prices[s] / 100) * 100
                        if shares > 0:
                            cost = shares * prices[s]
                            cash -= cost
                            ind = day_data[day_data['ts_code']==s]['industry'].values[0] if not day_data[day_data['ts_code']==s].empty else '未知'
                            holdings[s] = {'shares': shares, 'cost': cost, 'industry': ind}
                            trades.append({'date': date, 'action': 'BUY', 'stock': s, 'industry': ind, 'value': cost})
        
        # 计算净值
        v = cash + sum(holdings[s]['shares'] * prices.get(s, 0) for s in holdings)
        values.append(v)
    
    if len(values) < 2:
        return {'success': False, 'return': -1, 'dd': 1, 'trades': []}
    
    pv = np.array(values)
    total_ret = (pv[-1] - 1000000) / 1000000
    cummax = np.maximum.accumulate(pv)
    max_dd = abs(np.min((pv - cummax) / cummax))
    
    return {
        'success': max_dd <= 0.15,  # 15%回撤限制
        'return': total_ret,
        'dd': max_dd,
        'trades': trades,
        'values': values
    }

# 优化
print('\\n🔬 开始行业轮动优化...')
best = {'return': 0, 'dd': 1, 'params': None, 'trades': []}

for round_num in range(1, 21):
    best_round = None
    best_ret = -float('inf')
    
    for _ in range(50):
        params = {
            'num_industries': random.randint(2, 4),  # 同时持有2-4个行业
            'num_stocks': random.randint(6, 10),      # 总持股6-10只
            'position': random.uniform(0.7, 0.9),     # 仓位70-90%
            'stop_loss': random.uniform(0.08, 0.15),  # 止损8-15%
        }
        
        result = run_sector_rotation(params)
        if result['success'] and result['return'] > best_ret:
            best_ret = result['return']
            best_round = result
            best_round['params'] = params
    
    if best_round and best_round['return'] > best['return']:
        best.update(best_round)
        print(f'🎉 第{round_num}轮新最佳: +{best_round["return"]*100:.1f}% 回撤{best_round["dd"]*100:.1f}%')
    
    if round_num % 5 == 0:
        print(f'  进度: {round_num}/20, 当前最佳: +{best["return"]*100:.1f}%')

print('\\n' + '='*60)
print('✅ 行业轮动策略优化完成!')
print(f'🏆 最佳: +{best["return"]*100:.2f}% 回撤{best["dd"]*100:.1f}%')

if best['trades']:
    # 统计行业分布
    buy_trades = [t for t in best['trades'] if t['action'] == 'BUY']
    ind_dist = {}
    for t in buy_trades:
        ind = t.get('industry', '未知')
        ind_dist[ind] = ind_dist.get(ind, 0) + t.get('value', 0)
    
    print('\\n📊 行业配置分布:')
    total_val = sum(ind_dist.values())
    for ind, val in sorted(ind_dist.items(), key=lambda x: x[1], reverse=True):
        print(f'  {ind}: {val/total_val*100:.1f}%')

# 保存
output = {
    'strategy': 'VQM_Sector_Rotation',
    'timestamp': datetime.now().isoformat(),
    'drawdown_limit': '15%',
    'best': {
        'return': float(best['return']),
        'drawdown': float(best['dd']),
        'params': best['params'],
    }
}

with open('/root/.openclaw/workspace/quant/best_strategy_sector.json', 'w') as f:
    json.dump(output, f, indent=2)

print('\\n💾 结果已保存到 best_strategy_sector.json')
