#!/usr/bin/env python3
"""
WFO (Walk-Forward Optimization) 回测系统
滚动窗口优化策略参数，防止过拟合

策略框架:
1. 多因子打分模型
2. 训练期优化因子权重
3. 验证期测试表现
4. 滚动窗口持续优化
"""
import os
import sys
import sqlite3
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from scipy.optimize import minimize
import json
import warnings
warnings.filterwarnings('ignore')

WORKSPACE = '/root/.openclaw/workspace'
DB_PATH = f'{WORKSPACE}/data/historical/historical.db'
REPORTS_PATH = f'{WORKSPACE}/skills/quant-data-system/reports'

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

def load_data(start_date, end_date):
    """加载数据"""
    conn = sqlite3.connect(DB_PATH)
    
    # 加载技术因子
    df_tech = pd.read_sql(f"""
        SELECT ts_code, trade_date, ret_20, ret_60, ret_120,
               vol_20, vol_ratio, price_pos_20, price_pos_60, price_pos_high,
               money_flow, rel_strength, mom_accel, profit_mom
        FROM stock_factors
        WHERE trade_date BETWEEN '{start_date}' AND '{end_date}'
    """, conn)
    
    # 加载防御因子
    df_def = pd.read_sql(f"""
        SELECT ts_code, trade_date, vol_120, max_drawdown_120, 
               downside_vol, sharpe_like, low_vol_score
        FROM stock_defensive_factors
        WHERE trade_date BETWEEN '{start_date}' AND '{end_date}'
    """, conn)
    
    # 加载日线数据
    df_price = pd.read_sql(f"""
        SELECT ts_code, trade_date, close, pct_chg
        FROM daily_price
        WHERE trade_date BETWEEN '{start_date}' AND '{end_date}'
    """, conn)
    
    conn.close()
    
    # 合并数据
    df = df_tech.merge(df_def, on=['ts_code', 'trade_date'], how='outer')
    df = df.merge(df_price, on=['ts_code', 'trade_date'], how='inner')
    
    return df

def calculate_portfolio_return(df, weights, lookback=20):
    """计算组合收益"""
    # 计算综合打分
    factors = ['ret_20', 'ret_60', 'vol_20', 'price_pos_20', 
               'sharpe_like', 'rel_strength', 'mom_accel']
    
    # 填充缺失值
    for f in factors:
        df[f] = df[f].fillna(0)
    
    # 计算因子打分
    df['score'] = 0
    for i, f in enumerate(factors):
        if i < len(weights):
            df['score'] += df[f] * weights[i]
    
    # 选股 (前10%)
    df = df.sort_values(['trade_date', 'score'], ascending=[True, False])
    df['rank'] = df.groupby('trade_date')['score'].rank(ascending=False, pct=True)
    selected = df[df['rank'] <= 0.1].copy()
    
    # 计算组合收益 (等权)
    returns = selected.groupby('trade_date')['pct_chg'].mean()
    
    return returns

def calculate_sharpe(returns, risk_free_rate=0.03):
    """计算夏普比率"""
    excess_returns = returns - risk_free_rate / 252
    if returns.std() == 0:
        return 0
    return excess_returns.mean() / returns.std() * np.sqrt(252)

def calculate_max_drawdown(returns):
    """计算最大回撤"""
    cumulative = (1 + returns / 100).cumprod()
    peak = cumulative.expanding().max()
    drawdown = (cumulative - peak) / peak
    return drawdown.min()

def objective(weights, df_train):
    """优化目标函数"""
    returns = calculate_portfolio_return(df_train, weights)
    
    if len(returns) == 0 or returns.std() == 0:
        return 1e6
    
    sharpe = calculate_sharpe(returns)
    max_dd = calculate_max_drawdown(returns)
    
    # 目标: 最大化夏普，限制回撤
    penalty = 0
    if max_dd < -0.3:  # 回撤超过30%
        penalty = abs(max_dd + 0.3) * 10
    
    return -(sharpe - penalty)

def optimize_weights(df_train):
    """优化因子权重"""
    n_factors = 7
    initial_weights = np.ones(n_factors) / n_factors
    
    # 约束: 权重和为1，每个权重在0-1之间
    constraints = {'type': 'eq', 'fun': lambda x: np.sum(x) - 1}
    bounds = [(0, 1) for _ in range(n_factors)]
    
    result = minimize(
        objective,
        initial_weights,
        args=(df_train,),
        method='SLSQP',
        bounds=bounds,
        constraints=constraints,
        options={'maxiter': 100}
    )
    
    return result.x

def run_wfo_window(train_start, train_end, test_start, test_end):
    """运行单个WFO窗口"""
    log(f"训练期: {train_start} - {train_end}")
    log(f"验证期: {test_start} - {test_end}")
    
    # 加载训练数据
    df_train = load_data(train_start, train_end)
    
    # 优化权重
    weights = optimize_weights(df_train)
    log(f"优化权重: {[f'{w:.3f}' for w in weights]}")
    
    # 加载验证数据
    df_test = load_data(test_start, test_end)
    
    # 计算验证期收益
    returns = calculate_portfolio_return(df_test, weights)
    
    if len(returns) == 0:
        return None
    
    # 计算指标
    total_return = (1 + returns / 100).prod() - 1
    annual_return = (1 + total_return) ** (252 / len(returns)) - 1
    sharpe = calculate_sharpe(returns)
    max_dd = calculate_max_drawdown(returns)
    volatility = returns.std() * np.sqrt(252)
    
    result = {
        'train_period': f"{train_start}-{train_end}",
        'test_period': f"{test_start}-{test_end}",
        'weights': weights.tolist(),
        'total_return': total_return,
        'annual_return': annual_return,
        'sharpe_ratio': sharpe,
        'max_drawdown': max_dd,
        'volatility': volatility,
        'trade_days': len(returns)
    }
    
    log(f"验证结果: 年化{annual_return*100:.2f}%, 夏普{sharpe:.2f}, 回撤{max_dd*100:.2f}%")
    
    return result

def run_wfo_backtest():
    """运行完整WFO回测"""
    log("="*60)
    log("🚀 WFO (Walk-Forward Optimization) 回测")
    log("="*60)
    
    # WFO窗口设置
    windows = [
        # (训练开始, 训练结束, 验证开始, 验证结束)
        ('20180101', '20201231', '20210101', '20211231'),
        ('20190101', '20211231', '20220101', '20221231'),
        ('20200101', '20221231', '20230101', '20231231'),
        ('20210101', '20231231', '20240101', '20241231'),
    ]
    
    results = []
    
    for i, (train_start, train_end, test_start, test_end) in enumerate(windows, 1):
        log(f"\n{'='*60}")
        log(f"窗口 {i}/{len(windows)}")
        log(f"{'='*60}")
        
        result = run_wfo_window(train_start, train_end, test_start, test_end)
        if result:
            results.append(result)
    
    # 汇总结果
    log(f"\n{'='*60}")
    log("📊 WFO回测汇总")
    log(f"{'='*60}")
    
    avg_return = np.mean([r['annual_return'] for r in results])
    avg_sharpe = np.mean([r['sharpe_ratio'] for r in results])
    avg_drawdown = np.mean([r['max_drawdown'] for r in results])
    
    log(f"平均年化收益: {avg_return*100:.2f}%")
    log(f"平均夏普比率: {avg_sharpe:.2f}")
    log(f"平均最大回撤: {avg_drawdown*100:.2f}%")
    
    # 保存结果
    os.makedirs(REPORTS_PATH, exist_ok=True)
    report_file = f"{REPORTS_PATH}/wfo_backtest_{datetime.now().strftime('%Y%m%d')}.json"
    
    with open(report_file, 'w') as f:
        json.dump({
            'generated_at': datetime.now().isoformat(),
            'summary': {
                'avg_annual_return': avg_return,
                'avg_sharpe': avg_sharpe,
                'avg_max_drawdown': avg_drawdown,
                'windows_count': len(results)
            },
            'windows': results
        }, f, indent=2)
    
    log(f"\n报告已保存: {report_file}")
    
    return results

def main():
    run_wfo_backtest()

if __name__ == '__main__':
    main()
