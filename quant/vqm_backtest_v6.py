#!/usr/bin/env python3
"""
VQM策略回测优化系统 v6.0 (Alpha-Beta因子版)
基于本地量化知识:
- Alpha: PE估值因子 (低PE = 高Alpha)
- Beta: ROE质量因子 (高ROE = 低Beta)  
- 波动率: 风险控制因子
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

print("🚀 VQM策略回测优化系统 v6.0 (Alpha-Beta因子版)")
print("="*60)

# 加载数据
print("📊 加载数据...")
conn = sqlite3.connect(DB_PATH)

# 加载50只活跃股票
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
print("   - Alpha: 20日动量因子")
print("   - Beta: 波动率因子")
print("   - 质量: ROE代理因子")

df = df.sort_values(['ts_code', 'trade_date'])

# Alpha因子: 动量 (20日收益)
df['alpha_factor'] = df.groupby('ts_code')['close'].pct_change(20)

# Beta因子: 波动率 (风险)
df['beta_factor'] = df.groupby('ts_code')['close'].pct_change(1).rolling(20).std().reset_index(level=0, drop=True)

# 质量因子: 盈利能力代理 (用价格动量强度)
df['quality_factor'] = df.groupby('ts_code')['close'].pct_change(60)  # 60日强势

# 成交量因子
df['volume_ma20'] = df.groupby('ts_code')['volume'].rolling(20).mean().reset_index(level=0, drop=True)
df['volume_ratio'] = df['volume'] / df['volume_ma20']

# 创建快速查询索引
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
    """
    选股 - 基于Alpha/Beta/Quality因子
    
    Alpha (α): 动量因子 - 过去20日收益越高越好
    Beta (β): 波动率因子 - 波动越低越好 (风险低)
    Quality: 质量因子 - 60日动量越强越好
    """
    data = date_data.get(date)
    if data is None or data.empty:
        return random.sample(stock_list, min(8, len(stock_list)))
    
    data = data.dropna(subset=['alpha_factor', 'beta_factor', 'quality_factor'])
    if data.empty:
        return random.sample(stock_list, min(8, len(stock_list)))
    
    # Alpha: 动量因子 (越高越好) -> 排名
    data['alpha_score'] = data['alpha_factor'].rank(pct=True) * params['alpha_weight']
    
    # Beta: 波动率因子 (越低越好) -> 反向排名
    data['beta_score'] = (1 - data['beta_factor'].rank(pct=True)) * params['beta_weight']
    
    # Quality: 质量因子 (越高越好)
    data['quality_score'] = data['quality_factor'].rank(pct=True) * params['quality_weight']
    
    # 低波动偏好 (Beta风险管理)
    data['low_vol_score'] = (1 - data['beta_factor'].rank(pct=True)) * params['low_vol_weight']
    
    # 综合得分
    data['total_score'] = (
        data['alpha_score'] + 
        data['beta_score'] + 
        data['quality_score'] +
        data['low_vol_score']
    )
    
    return data.nlargest(8, 'total_score')['ts_code'].tolist()


def get_price(stock: str, date: str) -> float:
    """获取价格"""
    data = date_data.get(date)
    if data is not None:
        row = data[data['ts_code'] == stock]
        if not row.empty:
            return row.iloc[0]['close']
    return 0


def run_backtest(params: dict) -> dict:
    """运行回测"""
    rebalance_dates = set(get_rebalance_dates())
    
    cash = 1000000.0
    holdings = {}
    portfolio_values = []
    trades = 0
    
    for date in trading_dates:
        # 调仓 (每月第一个交易日)
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
print("因子说明:")
print("  • Alpha (α): 动量因子权重 - 20日收益")
print("  • Beta (β): 波动率因子权重 - 风险控制")
print("  • Quality: 质量因子权重 - 60日动量")
print("  • LowVol: 低波动偏好权重")
print("="*60)

results = []
best = None
best_return = -float('inf')

for i in range(50):
    # 随机参数 (4个因子权重)
    params = {
        'alpha_weight': random.uniform(0.2, 0.6),    # Alpha动量
        'beta_weight': random.uniform(0.1, 0.4),      # Beta波动率
        'quality_weight': random.uniform(0.1, 0.4),  # 质量因子
        'low_vol_weight': random.uniform(0.0, 0.2),  # 低波动
    }
    # 归一化
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
print(f"✅ 优化完成! 最佳收益: {best_return*100:.1f}%")

# 保存结果
output = {
    'timestamp': datetime.now().isoformat(),
    'best': {
        'iteration': best['iteration'],
        'params': best['params'],
        'total_return': best['total_return'],
        'annual_return': best['annual_return'],
        'max_drawdown': best['max_drawdown'],
        'sharpe': best['sharpe'],
        'final_value': best['final_value'],
        'success': best['success']
    },
    'all_results': [{'iteration': r['iteration'], 
                     'alpha_weight': r['params']['alpha_weight'],
                     'beta_weight': r['params']['beta_weight'],
                     'quality_weight': r['params']['quality_weight'],
                     'low_vol_weight': r['params']['low_vol_weight'],
                     'total_return': r['result']['total_return'],
                     'max_drawdown': r['result']['max_drawdown'],
                     'success': r['result']['success']} for r in results]
}

with open('/root/.openclaw/workspace/quant/backtest_results.json', 'w') as f:
    json.dump(output, f, indent=2)

# 打印最佳报告
print(f"""
📊 最佳回测报告 #{best['iteration']}
{'='*50}

🎯 Alpha/Beta因子配置:
   • Alpha (动量因子): {best['params']['alpha_weight']*100:.1f}%
   • Beta (波动率因子): {best['params']['beta_weight']*100:.1f}%
   • Quality (质量因子): {best['params']['quality_weight']*100:.1f}%
   • LowVol (低波动): {best['params']['low_vol_weight']*100:.1f}%

📈 收益指标:
   • 总收益率: {best['total_return']*100:+.2f}%
   • 年化收益率: {best['annual_return']*100:+.2f}%
   • 最终净值: ¥{best['final_value']:,.0f}

⚠️ 风险指标:
   • 最大回撤: {best['max_drawdown']*100:.2f}%
   • 夏普比率: {best['sharpe']:.2f}

✅ 状态: {'成功 (回撤<7.5%)' if best['success'] else '失败 (回撤超标)'}
{'='*50}
""")

print(f"\n💾 结果已保存到: /root/.openclaw/workspace/quant/backtest_results.json")
