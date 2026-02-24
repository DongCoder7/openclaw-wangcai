#!/usr/bin/env python3
"""
VQM策略回测优化系统 v7.0 (每日调仓+止损版)
- 每日调仓
- 7.5%止损机制
- 自由建仓（可不满仓）
- 最大回撤 <= 7.5%
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

print("🚀 VQM策略回测优化系统 v7.0 (每日调仓+止损版)")
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

# Alpha: 动量因子
df['alpha_factor'] = df.groupby('ts_code')['close'].pct_change(20)

# Beta: 波动率因子
df['beta_factor'] = df.groupby('ts_code')['close'].pct_change(1).rolling(20).std().reset_index(level=0, drop=True)

# 质量因子
df['quality_factor'] = df.groupby('ts_code')['close'].pct_change(60)

# 成交量
df['volume_ma20'] = df.groupby('ts_code')['volume'].rolling(20).mean().reset_index(level=0, drop=True)
df['volume_ratio'] = df['volume'] / df['volume_ma20']

# 快速查询
date_data = {d: df[df['trade_date'] == d].copy() for d in trading_dates}

print("✅ 数据准备完成")
print("="*60)


def select_stocks(date: str, params: dict, pool: list) -> list:
    """选股"""
    data = date_data.get(date)
    if data is None or data.empty:
        return random.sample(pool, min(5, len(pool)))
    
    data = data[data['ts_code'].isin(pool)].copy()
    data = data.dropna(subset=['alpha_factor', 'beta_factor', 'quality_factor'])
    if data.empty:
        return random.sample(pool, min(5, len(pool)))
    
    # 评分
    data['alpha_score'] = data['alpha_factor'].rank(pct=True) * params['alpha_weight']
    data['beta_score'] = (1 - data['beta_factor'].rank(pct=True)) * params['beta_weight']
    data['quality_score'] = data['quality_factor'].rank(pct=True) * params['quality_weight']
    data['low_vol_score'] = (1 - data['beta_factor'].rank(pct=True)) * params['low_vol_weight']
    
    data['total_score'] = (
        data['alpha_score'] + 
        data['beta_score'] + 
        data['quality_score'] +
        data['low_vol_score']
    )
    
    num = params.get('num_stocks', 5)
    return data.nlargest(num, 'total_score')['ts_code'].tolist()


def get_price(stock: str, date: str) -> float:
    """获取价格"""
    data = date_data.get(date)
    if data is not None:
        row = data[data['ts_code'] == stock]
        if not row.empty:
            return row.iloc[0]['close']
    return 0


def run_backtest(params: dict) -> dict:
    """运行回测 - 每日调仓+止损"""
    
    initial_capital = 1000000.0
    cash = initial_capital
    holdings = {}  # {stock: {'shares': x, 'cost': y}}
    portfolio_values = []
    trades = 0
    
    # 止损参数
    stop_loss = params.get('stop_loss', 0.075)  # -7.5%止损
    
    # 建仓参数
    initial_allocation = params.get('initial_allocation', 0.8)  # 初始仓位80%
    max_position = params.get('max_position', 0.15)  # 单只股票最大15%
    
    # 调仓参数
    rebalance_threshold = params.get('rebalance_threshold', 0.05)  # 5%偏离调仓
    
    num_stocks = params.get('num_stocks', 5)  # 持仓数量
    
    first_trade = False
    
    for date in trading_dates:
        # 首次建仓
        if not first_trade and len(trading_dates) > 20:
            # 选择表现最好的股票建仓
            selected = select_stocks(date, params, stock_list)
            if selected and cash > 0:
                # 使用部分资金建仓
                available_cash = cash * initial_allocation
                per_stock = available_cash / len(selected)
                
                for stock in selected:
                    price = get_price(stock, date)
                    if price > 0:
                        shares = int(per_stock / price / 100) * 100
                        if shares > 0:
                            cost = shares * price
                            cash -= cost
                            holdings[stock] = {'shares': shares, 'cost': cost}
                            trades += 1
                first_trade = True
        
        # 每日检查止损
        holdings_to_sell = []
        for stock, pos in holdings.items():
            current_price = get_price(stock, date)
            if current_price > 0:
                pos_value = pos['shares'] * current_price
                cost = pos['cost']
                return_pct = (pos_value - cost) / cost
                
                # 止损检查
                if return_pct <= -stop_loss:
                    holdings_to_sell.append(stock)
        
        # 卖出止损股票
        for stock in holdings_to_sell:
            price = get_price(stock, date)
            if price > 0:
                cash += holdings[stock]['shares'] * price
                trades += 1
                del holdings[stock]
        
        # 每日调仓检查
        if first_trade and holdings:
            # 检查是否需要调仓
            need_rebalance = False
            
            # 检查持仓偏离
            total_value = cash + sum(h['shares'] * get_price(s, date) for s, h in holdings.items() if get_price(s, date) > 0)
            
            for stock in list(holdings.keys()):
                current_price = get_price(stock, date)
                if current_price > 0:
                    pos_value = holdings[stock]['shares'] * current_price
                    weight = pos_value / total_value if total_value > 0 else 0
                    
                    if abs(weight - max_position) > rebalance_threshold:
                        need_rebalance = True
                        break
            
            # 选股检查 - 是否有更好的股票
            current_stocks = list(holdings.keys())
            all_candidates = select_stocks(date, params, stock_list)
            
            # 找出需要卖出的（不在候选中且表现不好）
            for stock in current_stocks:
                if stock not in all_candidates[:num_stocks]:
                    current_price = get_price(stock, date)
                    if current_price > 0:
                        pos_value = holdings[stock]['shares'] * current_price
                        return_pct = (pos_value - holdings[stock]['cost']) / holdings[stock]['cost']
                        # 卖出表现差的
                        if return_pct < 0:
                            cash += pos_value
                            trades += 1
                            del holdings[stock]
            
            # 买入候选股票（如果仓位不满）
            if len(holdings) < num_stocks:
                candidates = [s for s in all_candidates if s not in holdings]
                available_cash = cash
                
                for stock in candidates[:num_stocks - len(holdings)]:
                    if available_cash <= 0:
                        break
                    price = get_price(stock, date)
                    if price > 0:
                        shares = int((available_cash * max_position) / price / 100) * 100
                        if shares > 0:
                            cost = shares * price
                            cash -= cost
                            holdings[stock] = {'shares': shares, 'cost': cost}
                            trades += 1
                            available_cash -= cost
        
        # 计算组合价值
        value = cash
        for stock, pos in holdings.items():
            price = get_price(stock, date)
            if price > 0:
                value += pos['shares'] * price
        
        portfolio_values.append(value)
    
    # 计算指标
    pv = np.array(portfolio_values)
    returns = np.diff(pv) / pv[:-1]
    returns = returns[~np.isnan(returns)]
    
    total_return = (pv[-1] - initial_capital) / initial_capital
    years = len(pv) / 252
    annual_return = (1 + total_return) ** (1/years) - 1 if years > 0 else 0
    
    # 最大回撤
    cummax = np.maximum.accumulate(pv)
    drawdowns = (pv - cummax) / cummax
    max_drawdown = abs(np.min(drawdowns))
    
    # 夏普
    std_ret = np.std(returns)
    sharpe = (annual_return - 0.03) / (std_ret * np.sqrt(252)) if std_ret > 0 else 0
    
    success = max_drawdown <= 0.075
    
    return {
        'success': success,
        'total_return': total_return,
        'annual_return': annual_return,
        'max_drawdown': max_drawdown,
        'sharpe': sharpe,
        'trades': trades,
        'final_value': pv[-1],
        'params': params
    }


# 运行优化
print(f"\n🚀 开始50次参数优化 (每日调仓+止损)...")
print("="*60)

results = []
best = None
best_return = -float('inf')

for i in range(50):
    # 随机参数
    params = {
        'alpha_weight': random.uniform(0.2, 0.5),
        'beta_weight': random.uniform(0.15, 0.35),
        'quality_weight': random.uniform(0.15, 0.35),
        'low_vol_weight': random.uniform(0.05, 0.2),
        'num_stocks': random.randint(3, 6),
        'stop_loss': 0.075,  # 固定7.5%止损
        'initial_allocation': random.uniform(0.5, 0.8),
        'max_position': random.uniform(0.1, 0.2),
        'rebalance_threshold': random.uniform(0.03, 0.08),
    }
    # 归一化权重
    total = params['alpha_weight'] + params['beta_weight'] + params['quality_weight'] + params['low_vol_weight']
    params['alpha_weight'] /= total
    params['beta_weight'] /= total
    params['quality_weight'] /= total
    params['low_vol_weight'] /= total
    
    # 运行回测
    result = run_backtest(params)
    
    results.append({'iteration': i+1, 'params': params, 'result': result})
    
    status = "✅" if result['success'] else "❌"
    print(f"{status} {i+1:02d}/50 | 收益:{result['total_return']*100:+6.1f}% | "
          f"年化:{result['annual_return']*100:+6.1f}% | 回撤:{result['max_drawdown']*100:5.1f}% | "
          f"夏普:{result['sharpe']:5.2f} | 持仓:{params['num_stocks']}只")
    
    if result['total_return'] > best_return:
        best_return = result['total_return']
        best = {'iteration': i+1, 'params': params, **result}

print("="*60)
print(f"✅ 优化完成!")
print(f"   最佳收益: {best_return*100:.1f}%")
print(f"   回撤: {best['max_drawdown']*100:.1f}%")
print(f"   成功(回撤<7.5%): {'是' if best['success'] else '否'}")

# 保存结果
output = {
    'timestamp': datetime.now().isoformat(),
    'best': {
        'iteration': best['iteration'],
        'params': {k: float(v) if isinstance(v, (np.floating, np.integer)) else v for k, v in best['params'].items()},
        'total_return': float(best['total_return']),
        'annual_return': float(best['annual_return']),
        'max_drawdown': float(best['max_drawdown']),
        'sharpe': float(best['sharpe']),
        'final_value': float(best['final_value']),
        'success': bool(best['success'])
    },
    'summary': {
        'total_iterations': 50,
        'success_count': sum(1 for r in results if r['result']['success']),
        'best_return': float(best_return),
        'best_drawdown': float(best['max_drawdown'])
    }
}

with open('/root/.openclaw/workspace/quant/backtest_results.json', 'w') as f:
    json.dump(output, f, indent=2)

# 打印报告
print(f"""
📊 最佳回测报告 #{best['iteration']}
{'='*50}

🎯 参数配置:
   • 持仓数量: {best['params']['num_stocks']}只
   • 初始仓位: {best['params']['initial_allocation']*100:.0f}%
   • 单股最大仓位: {best['params']['max_position']*100:.0f}%
   • 止损线: {best['params']['stop_loss']*100:.1f}%
   • Alpha因子: {best['params']['alpha_weight']*100:.1f}%
   • Beta因子: {best['params']['beta_weight']*100:.1f}%
   • 质量因子: {best['params']['quality_weight']*100:.1f}%
   • 低波因子: {best['params']['low_vol_weight']*100:.1f}%

📈 收益指标:
   • 总收益率: {best['total_return']*100:+.2f}%
   • 年化收益率: {best['annual_return']*100:+.2f}%
   • 最终净值: ¥{best['final_value']:,.0f}

⚠️ 风险指标:
   • 最大回撤: {best['max_drawdown']*100:.2f}%
   • 夏普比率: {best['sharpe']:.2f}

📊 交易统计:
   • 总交易次数: {best['trades']}次

{'✅ 成功 (回撤<7.5%)' if best['success'] else '❌ 失败 (回撤超标)'}
{'='*50}
""")

print(f"\n💾 结果已保存到: /root/.openclaw/workspace/quant/backtest_results.json")
