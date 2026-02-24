#!/usr/bin/env python3
"""
VQM策略回测优化系统 v3.0 (极速版)
- 每月第一个交易日建仓
- 最多8只股票
- 初始资金100万
- 3年投资期
- 最大回撤 <= 7.5%
- 50次参数优化
"""

import os
import sys
import pandas as pd
import numpy as np
from datetime import datetime
from typing import Dict, List, Tuple
import sqlite3
import json
import random
import warnings
warnings.filterwarnings('ignore')

DB_PATH = '/root/.openclaw/workspace/data/historical/historical.db'

print("🚀 VQM策略回测优化系统 v3.0")
print("="*60)

# 加载所有数据到内存
print("📊 加载数据到内存...")
conn = sqlite3.connect(DB_PATH)

# 加载日线数据
query = '''
    SELECT ts_code, trade_date, close, volume
    FROM daily_price
    WHERE trade_date BETWEEN '20180101' AND '20210104'
    ORDER BY ts_code, trade_date
'''
df = pd.read_sql(query, conn, parse_dates=['trade_date'])
conn.close()

print(f"   数据量: {len(df):,} 行")

# 股票列表
stock_list = df['ts_code'].unique().tolist()
print(f"   股票数: {len(stock_list)}")

# 交易日
trading_dates = sorted(df['trade_date'].unique().tolist())
print(f"   交易日: {len(trading_dates)}")

# 计算因子 (向量化)
print("🔧 计算因子...")
df = df.sort_values(['ts_code', 'trade_date'])

# 收益率
df['return_1d'] = df.groupby('ts_code')['close'].pct_change(1)
df['return_20d'] = df.groupby('ts_code')['close'].pct_change(20)

# 波动率
df['volatility_20d'] = df.groupby('ts_code')['return_1d'].rolling(20).std().reset_index(level=0, drop=True)

# 成交量
df['volume_ma20'] = df.groupby('ts_code')['volume'].rolling(20).mean().reset_index(level=0, drop=True)
df['volume_ratio'] = df['volume'] / df['volume_ma20']

print("✅ 数据准备完成")
print("="*60)


def get_first_trading_day_of_month(year: int, month: int) -> str:
    """获取某月第一个交易日"""
    target = f"{year}{month:02d}"
    for date in trading_dates:
        if isinstance(date, str):
            d = date.replace('-', '')
        else:
            d = date.strftime('%Y%m%d')
        if d.startswith(target):
            return d
    return None


def get_monthly_rebalance_dates(start_year: int, num_months: int) -> List[str]:
    """获取每月调仓日期"""
    dates = []
    for i in range(num_months):
        total_months = (start_year - 2018) * 12 + i
        year = 2018 + total_months // 12
        month = total_months % 12 + 1
        first_day = get_first_trading_day_of_month(year, month)
        if first_day:
            dates.append(first_day)
    return dates


def select_stocks(trade_date: str, pool: List[str], num: int, params: Dict) -> List[str]:
    """选股"""
    if isinstance(trade_date, str):
        date_str = trade_date.replace('-', '')
    else:
        date_str = trade_date.strftime('%Y%m%d')
    
    # 获取当日数据
    date_data = df[(df['trade_date'].dt.strftime('%Y%m%d') == date_str) & 
                   (df['ts_code'].isin(pool))].copy()
    
    if date_data.empty:
        return random.sample(pool, min(num, len(pool)))
    
    # 有效数据
    date_data = date_data.dropna(subset=['return_20d', 'volatility_20d'])
    if date_data.empty:
        return random.sample(pool, min(num, len(pool)))
    
    # 评分
    alpha_w = params.get('alpha_weight', 0.4)
    beta_w = params.get('beta_weight', 0.3)
    vol_w = params.get('volume_weight', 0.2)
    low_vol = params.get('low_volatility', 0.1)
    
    date_data['mom_s'] = date_data['return_20d'].rank(pct=True) * alpha_w
    date_data['vol_s'] = (1 - date_data['volatility_20d'].rank(pct=True)) * beta_w
    date_data['vr_s'] = (1 - abs(date_data['volume_ratio'] - 1).rank(pct=True)) * vol_w
    date_data['lv_s'] = (1 - date_data['volatility_20d'].rank(pct=True)) * low_vol
    
    date_data['score'] = date_data['mom_s'] + date_data['vol_s'] + date_data['vr_s'] + date_data['lv_s']
    
    return date_data.nlargest(num, 'ts_code')['ts_code'].tolist()


def run_backtest(params: Dict, start_date: str, end_date: str, 
                num_stocks: int = 8, max_dd: float = 0.075) -> Dict:
    """运行回测"""
    
    rebalance_dates = get_monthly_rebalance_dates(2018, 36)
    rebalance_dates = [d for d in rebalance_dates if d >= start_date and d <= end_date]
    
    if not rebalance_dates:
        return {'success': False, 'error': 'No dates'}
    
    cash = 1000000.0
    holdings = {}
    portfolio_values = []
    trade_log = []
    
    date_to_idx = {d: i for i, d in enumerate(trading_dates)}
    start_idx = date_to_idx.get(start_date, 0)
    end_idx = date_to_idx.get(end_date, len(trading_dates) - 1)
    
    current_rebalance_idx = 0
    
    for idx in range(start_idx, min(end_idx + 1, len(trading_dates))):
        date = trading_dates[idx]
        if isinstance(date, str):
            date_str = date
        else:
            date_str = date.strftime('%Y%m%d')
        
        # 调仓
        if current_rebalance_idx < len(rebalance_dates):
            rebalance_date = rebalance_dates[current_rebalance_idx]
            
            if date_str >= rebalance_date:
                # 卖出
                for stock in list(holdings.keys()):
                    price_data = df[(df['ts_code'] == stock) & 
                                   (df['trade_date'].dt.strftime('%Y%m%d') == date_str)]
                    if not price_data.empty:
                        price = price_data.iloc[0]['close']
                        cash += holdings[stock] * price
                        trade_log.append({'date': date_str, 'action': 'sell', 'stock': stock, 'price': price})
                
                holdings = {}
                
                # 选股买入
                selected = select_stocks(date_str, stock_list, num_stocks, params)
                
                if selected and cash > 0:
                    per_stock = cash / len(selected)
                    
                    for stock in selected:
                        price_data = df[(df['ts_code'] == stock) & 
                                       (df['trade_date'].dt.strftime('%Y%m%d') == date_str)]
                        if not price_data.empty:
                            price = price_data.iloc[0]['close']
                            if price > 0:
                                shares = int(per_stock / price / 100) * 100
                                if shares > 0:
                                    cash -= shares * price
                                    holdings[stock] = shares
                                    trade_log.append({'date': date_str, 'action': 'buy', 'stock': stock, 'shares': shares, 'price': price})
                
                current_rebalance_idx += 1
        
        # 组合价值
        portfolio_value = cash
        for stock, shares in holdings.items():
            price_data = df[(df['ts_code'] == stock) & 
                           (df['trade_date'].dt.strftime('%Y%m%d') == date_str)]
            if not price_data.empty:
                portfolio_value += shares * price_data.iloc[0]['close']
        
        portfolio_values.append({'date': date_str, 'value': portfolio_value})
    
    # 计算指标
    if not portfolio_values:
        return {'success': False, 'error': 'No values'}
    
    pdf = pd.DataFrame(portfolio_values)
    pdf['return'] = pdf['value'].pct_change()
    
    total_return = (pdf.iloc[-1]['value'] - 1000000) / 1000000
    
    num_days = len(pdf)
    years = num_days / 252
    annual_return = (1 + total_return) ** (1 / years) - 1 if years > 0 else 0
    
    pdf['cummax'] = pdf['value'].cummax()
    pdf['drawdown'] = (pdf['value'] - pdf['cummax']) / pdf['cummax']
    max_drawdown = abs(pdf['drawdown'].min())
    
    if pdf['return'].std() > 0:
        sharpe = (annual_return - 0.03) / pdf['return'].std() * np.sqrt(252)
    else:
        sharpe = 0
    
    success = max_drawdown <= max_dd
    
    return {
        'success': success,
        'total_return': total_return,
        'annual_return': annual_return,
        'max_drawdown': max_drawdown,
        'sharpe': sharpe,
        'num_trades': len(trade_log),
        'final_value': pdf.iloc[-1]['value'],
        'trade_log': trade_log[-20:],
        'params': params
    }


# 运行优化
print(f"\n🚀 开始50次参数优化...")
print("="*60)

results = []
best_result = None
best_return = -float('inf')

for i in range(50):
    params = {
        'alpha_weight': random.uniform(0.1, 0.8),
        'beta_weight': random.uniform(0.1, 0.6),
        'volume_weight': random.uniform(0.0, 0.4),
        'low_volatility': random.uniform(0.0, 0.3),
    }
    
    # 归一化
    total_w = params['alpha_weight'] + params['beta_weight'] + params['volume_weight'] + params['low_volatility']
    params['alpha_weight'] /= total_w
    params['beta_weight'] /= total_w
    params['volume_weight'] /= total_w
    params['low_volatility'] /= total_w
    
    result = run_backtest(params, '20180102', '20210102', 8, 0.075)
    
    results.append({
        'iteration': i + 1,
        'params': params,
        'result': result
    })
    
    status = "✅" if result['success'] else "❌"
    print(f"{status} {i+1:02d}/50 | 收益:{result.get('total_return',0)*100:+6.1f}% | "
          f"年化:{result.get('annual_return',0)*100:+6.1f}% | 回撤:{result.get('max_drawdown',0)*100:5.1f}% | "
          f"夏普:{result.get('sharpe',0):5.2f}")
    
    if result.get('total_return', -float('inf')) > best_return:
        best_return = result.get('total_return', -float('inf'))
        best_result = result
        best_result['iteration'] = i + 1
        best_result['params'] = params

print("="*60)
print(f"✅ 优化完成! 最佳收益: {best_return*100:.1f}%")

# 保存结果
output = {
    'timestamp': datetime.now().isoformat(),
    'best_result': {
        'iteration': best_result.get('iteration'),
        'params': best_result.get('params'),
        'metrics': {
            'total_return': best_result.get('total_return'),
            'annual_return': best_result.get('annual_return'),
            'max_drawdown': best_result.get('max_drawdown'),
            'sharpe': best_result.get('sharpe'),
            'final_value': best_result.get('final_value'),
        }
    },
    'all_results': [
        {
            'iteration': r['iteration'],
            'params': r['params'],
            'total_return': r['result'].get('total_return'),
            'max_drawdown': r['result'].get('max_drawdown'),
            'success': r['result'].get('success')
        }
        for r in results
    ]
}

with open('/root/.openclaw/workspace/quant/backtest_optimization_results.json', 'w') as f:
    json.dump(output, f, indent=2, default=str)

# 打印最佳报告
print(f"""
📊 最佳回测报告 #{best_result.get('iteration')}
{'='*50}

🎯 参数配置:
   • 动量因子(α): {best_result.get('params',{}).get('alpha_weight',0)*100:.1f}%
   • 波动率因子(β): {best_result.get('params',{}).get('beta_weight',0)*100:.1f}%
   • 成交量因子: {best_result.get('params',{}).get('volume_weight',0)*100:.1f}%
   • 低波动偏好: {best_result.get('params',{}).get('low_volatility',0)*100:.1f}%

📈 收益指标:
   • 总收益率: {best_result.get('total_return',0)*100:+.2f}%
   • 年化收益率: {best_result.get('annual_return',0)*100:+.2f}%
   • 最终净值: ¥{best_result.get('final_value',0):,.0f}

⚠️ 风险指标:
   • 最大回撤: {best_result.get('max_drawdown',0)*100:.2f}%
   • 夏普比率: {best_result.get('sharpe',0):.2f}

✅ 状态: {'成功 (回撤<7.5%)' if best_result.get('success') else '失败'}
{'='*50}
""")

print(f"\n💾 结果已保存到: /root/.openclaw/workspace/quant/backtest_optimization_results.json")
