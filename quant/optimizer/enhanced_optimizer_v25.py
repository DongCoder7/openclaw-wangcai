#!/usr/bin/env python3
"""
增强版优化器 v25 - 使用全部因子并自动分析因子重要性
"""
import sqlite3, pandas as pd
import numpy as np
from datetime import datetime
import json
import os

DB = '/root/.openclaw/workspace/data/historical/historical.db'
OUT = '/root/.openclaw/workspace/quant/optimizer'

# 所有可用因子配置
ALL_FACTORS = {
    # 动量因子
    'momentum': ['ret_20', 'ret_60', 'ret_120', 'mom_accel', 'profit_mom', 'rel_strength'],
    # 波动率因子
    'volatility': ['vol_20', 'vol_ratio', 'vol_120', 'downside_vol', 'max_drawdown_120'],
    # 趋势因子
    'trend': ['price_pos_20', 'price_pos_60', 'price_pos_high', 'ma_20', 'ma_60'],
    # 资金因子
    'flow': ['money_flow', 'vol_ratio_amt'],
    # 质量因子 (防御)
    'quality': ['sharpe_like', 'low_vol_score'],
    # 估值因子
    'valuation': ['pe_ttm', 'pb'],
    # 财务因子
    'financial': ['roe', 'revenue_growth', 'netprofit_growth', 'debt_ratio', 'dividend_yield']
}

def get_all_factors():
    """获取所有因子名称的扁平列表"""
    factors = []
    for cat, facs in ALL_FACTORS.items():
        factors.extend(facs)
    return factors

def load_data():
    """加载所有因子数据"""
    conn = sqlite3.connect(DB)
    
    # 基础查询 - 主因子表
    base_query = '''
        SELECT e.ts_code, e.trade_date, e.close, e.volume, e.amount,
               f.ret_20, f.ret_60, f.ret_120, f.vol_20, f.vol_ratio, 
               f.ma_20, f.ma_60, f.money_flow, f.rel_strength, f.mom_accel,
               f.price_pos_20, f.price_pos_60, f.price_pos_high, f.profit_mom,
               f.vol_ratio_amt
        FROM stock_efinance e
        LEFT JOIN stock_factors f ON e.ts_code = f.ts_code AND e.trade_date = f.trade_date
        WHERE e.trade_date BETWEEN '20180101' AND '20211231'
    '''
    
    df = pd.read_sql(base_query, conn)
    
    # 加载防御因子
    def_query = '''
        SELECT ts_code, trade_date, vol_120, max_drawdown_120, 
               downside_vol, sharpe_like, low_vol_score
        FROM stock_defensive_factors
        WHERE trade_date BETWEEN '20180101' AND '20211231'
    '''
    df_def = pd.read_sql(def_query, conn)
    
    # 加载财务因子
    fin_query = '''
        SELECT ts_code, report_date as trade_date, pe_ttm, pb, roe,
               revenue_growth, netprofit_growth, debt_ratio, dividend_yield
        FROM stock_fina
    '''
    df_fin = pd.read_sql(fin_query, conn)
    
    conn.close()
    
    # 合并数据
    df = df.merge(df_def, on=['ts_code', 'trade_date'], how='left')
    df = df.merge(df_fin, on=['ts_code', 'trade_date'], how='left')
    
    # 过滤有效数据
    df = df[df['ret_20'].notna()]
    
    return df

def calculate_factor_score(df, factor_weights):
    """根据因子权重计算综合得分"""
    df = df.copy()
    df['score'] = 0
    
    for factor, weight in factor_weights.items():
        if factor in df.columns and df[factor].notna().any():
            # 正向因子：值越大越好
            if factor in ['ret_20', 'ret_60', 'ret_120', 'mom_accel', 'profit_mom', 
                         'money_flow', 'rel_strength', 'sharpe_like', 'roe', 
                         'revenue_growth', 'netprofit_growth', 'dividend_yield']:
                df['score'] += df[factor].rank(pct=True, na_option='keep') * weight
            # 负向因子：值越小越好
            elif factor in ['vol_20', 'vol_ratio', 'vol_120', 'downside_vol', 
                           'max_drawdown_120', 'pe_ttm', 'pb', 'debt_ratio']:
                df['score'] += (1 - df[factor].rank(pct=True, na_option='keep')) * weight
            # 中性因子：中间位置可能更好
            else:
                df['score'] += df[factor].rank(pct=True, na_option='keep') * weight
    
    return df

def backtest(df, params, idx_dict):
    """回测函数"""
    p, s, n, rebal = params['p'], params['s'], params['n'], params['rebal']
    res = []
    
    for y in ['2018', '2019', '2020', '2021']:
        yd = df[(df['trade_date'] >= f'{y}0101') & (df['trade_date'] <= f'{y}1231')]
        dates = sorted(yd['trade_date'].unique())
        if len(dates) < 20:
            continue
        
        init = 1000000.0
        cash = init
        holdings = {}
        
        for rd in dates[::rebal]:
            rd_d = yd[yd['trade_date'] == rd]
            
            # 计算当前持仓价值
            hv = sum(holdings[c]['s'] * float(rd_d[rd_d['ts_code'] == c]['close'].iloc[0])
                    for c in holdings if not rd_d[rd_d['ts_code'] == c].empty)
            tot = cash + hv
            
            # 择时：趋势向下时清仓
            if idx_dict.get(rd, 1) == 0:
                for c in list(holdings.keys()):
                    cd = rd_d[rd_d['ts_code'] == c]
                    if not cd.empty:
                        cash += holdings[c]['s'] * float(cd['close'].iloc[0])
                holdings = {}
                continue
            
            # 选股
            cand = rd_d[rd_d['score'].notna()].nlargest(n, 'score')
            if cand.empty:
                continue
            
            tgt = tot * p / len(cand)
            
            # 卖出不在候选中的股票
            for c in list(holdings.keys()):
                if c not in cand['ts_code'].values:
                    cd = rd_d[rd_d['ts_code'] == c]
                    if not cd.empty:
                        cash += holdings[c]['s'] * float(cd['close'].iloc[0])
                        del holdings[c]
            
            # 买入新股票
            for _, r in cand.iterrows():
                if r['ts_code'] not in holdings:
                    sh = int(tgt / r['close'])
                    if sh > 0:
                        holdings[r['ts_code']] = {'s': sh, 'p': r['close']}
                        cash -= sh * r['close']
            
            # 止损止盈
            for c in list(holdings.keys()):
                cd = rd_d[rd_d['ts_code'] == c]
                if not cd.empty:
                    ret = (float(cd['close'].iloc[0]) - holdings[c]['p']) / holdings[c]['p']
                    if ret < -s:  # 止损
                        cash += holdings[c]['s'] * float(cd['close'].iloc[0])
                        del holdings[c]
                    elif ret > 0.15:  # 止盈
                        cash += holdings[c]['s'] * float(cd['close'].iloc[0])
                        del holdings[c]
        
        # 年终结算
        rd = dates[-1]
        rd_d = yd[yd['trade_date'] == rd]
        fv = cash + sum(holdings[c]['s'] * float(rd_d[rd_d['ts_code'] == c]['close'].iloc[0])
                       for c in holdings if not rd_d[rd_d['ts_code'] == c].empty)
        res.append({'year': y, 'return': (fv - init) / init})
    
    return res

def analyze_factor_importance(df, idx_dict):
    """分析各因子的重要性"""
    print("\n" + "="*60)
    print("🔍 因子重要性分析")
    print("="*60)
    
    factor_scores = {}
    base_params = {'p': 0.7, 's': 0.08, 'n': 5, 'rebal': 10}
    
    # 单独测试每个因子的效果
    for category, factors in ALL_FACTORS.items():
        print(f"\n📂 {category} 类别:")
        for factor in factors:
            if factor not in df.columns:
                continue
            
            # 使用该因子单独评分
            weights = {factor: 1.0}
            df_test = calculate_factor_score(df, weights)
            results = backtest(df_test, base_params, idx_dict)
            
            if results:
                avg_return = np.mean([r['return'] for r in results]) * 100
                factor_scores[factor] = avg_return
                print(f"  {factor:25s}: {avg_return:+.2f}%")
    
    # 排序并返回重要性
    sorted_factors = sorted(factor_scores.items(), key=lambda x: x[1], reverse=True)
    print("\n📊 因子重要性排名 (Top 10):")
    for i, (factor, score) in enumerate(sorted_factors[:10], 1):
        print(f"  {i:2d}. {factor:25s}: {score:+.2f}%")
    
    return sorted_factors

def optimize_weights(df, idx_dict, top_factors):
    """优化因子权重"""
    print("\n" + "="*60)
    print("⚖️  因子权重优化")
    print("="*60)
    
    best_score = -999
    best_weights = {}
    
    # 使用Top因子进行权重优化
    test_factors = [f[0] for f in top_factors[:8]]
    
    # 简单的网格搜索
    for w1 in [0.1, 0.15, 0.2]:
        for w2 in [0.1, 0.15, 0.2]:
            for w3 in [0.1, 0.15]:
                weights = {test_factors[0]: w1, test_factors[1]: w2, test_factors[2]: w3}
                for i, f in enumerate(test_factors[3:], 3):
                    weights[f] = 0.1
                
                df_test = calculate_factor_score(df, weights)
                results = backtest(df_test, {'p': 0.7, 's': 0.08, 'n': 5, 'rebal': 10}, idx_dict)
                
                if results:
                    avg = np.mean([r['return'] for r in results])
                    if avg > best_score:
                        best_score = avg
                        best_weights = weights.copy()
    
    print(f"\n🏆 最优权重组合 (预期收益: {best_score*100:+.2f}%):")
    for factor, weight in sorted(best_weights.items(), key=lambda x: x[1], reverse=True):
        print(f"  {factor:25s}: {weight:.2f}")
    
    return best_weights

def main():
    print("="*70)
    print("🚀 增强版优化器 v25 - 全因子分析与优化")
    print("="*70)
    
    # 加载数据
    print("\n📥 加载数据...")
    df = load_data()
    print(f"   加载 {len(df):,} 条记录，{df['ts_code'].nunique()} 只股票")
    
    # 计算市场指数择时
    idx = df.groupby('trade_date')['close'].median().reset_index()
    idx['ma20'] = idx['close'].rolling(20).mean()
    idx['trend'] = (idx['close'] > idx['ma20']).astype(int)
    idx_dict = dict(zip(idx['trade_date'], idx['trend']))
    
    # 因子重要性分析
    top_factors = analyze_factor_importance(df, idx_dict)
    
    # 优化权重
    best_weights = optimize_weights(df, idx_dict, top_factors)
    
    # 使用最优权重进行完整回测
    print("\n" + "="*60)
    print("📈 完整回测 (使用最优因子组合)")
    print("="*60)
    
    df_scored = calculate_factor_score(df, best_weights)
    
    # 参数优化
    best_result = None
    best_avg = -999
    best_params = None
    
    for p in [0.5, 0.7, 1.0]:
        for s in [0.05, 0.08, 0.10]:
            for n in [3, 5, 8]:
                for rebal in [10, 15]:
                    params = {'p': p, 's': s, 'n': n, 'rebal': rebal}
                    r = backtest(df_scored, params, idx_dict)
                    if not r:
                        continue
                    avg = np.mean([x['return'] for x in r])
                    loss = sum(1 for x in r if x['return'] < 0)
                    score = avg - loss * 0.1
                    if score > best_avg:
                        best_avg = score
                        best_result = r
                        best_params = params
    
    if best_result:
        yearly = [f"{d['year']}: {d['return']*100:+.1f}%" for d in best_result]
        avg = np.mean([d['return'] for d in best_result]) * 100
        
        print(f"\n🏆 最优参数: 仓位{best_params['p']*100:.0f}% 止损{best_params['s']*100:.0f}% 持仓{best_params['n']}只 调仓{best_params['rebal']}天")
        print("📈 年度收益: " + " | ".join(yearly))
        print(f"📊 平均收益: {avg:+.1f}%")
        
        # 保存结果
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # 保存参数
        result = {
            'params': best_params,
            'factor_weights': best_weights,
            'top_factors': [{'factor': f, 'score': s} for f, s in top_factors[:10]],
            'yearly_returns': best_result,
            'avg_return': avg,
            'timestamp': ts
        }
        
        with open(f'{OUT}/v25_result_{ts}.json', 'w') as f:
            json.dump(result, f, indent=2)
        
        # 保存报告
        report = f"""📊 **v25增强优化器报告** ({ts})

## 最优参数
- 仓位: {best_params['p']*100:.0f}%
- 止损: {best_params['s']*100:.0f}%
- 持仓: {best_params['n']}只
- 调仓频率: {best_params['rebal']}天

## 因子权重配置
"""
        for factor, weight in sorted(best_weights.items(), key=lambda x: x[1], reverse=True):
            report += f"- {factor}: {weight:.2f}\n"
        
        report += f"\n## 因子重要性排名 (Top 10)\n"
        for i, (factor, score) in enumerate(top_factors[:10], 1):
            report += f"{i}. {factor}: {score:+.2f}%\n"
        
        report += f"\n## 回测结果\n"
        report += "📈 " + " | ".join(yearly) + f"\n📊 平均收益: {avg:+.1f}%\n"
        
        with open(f'{OUT}/v25_report_{ts}.txt', 'w') as f:
            f.write(report)
        
        # 更新最新报告
        with open(f'{OUT}/latest_report.txt', 'w') as f:
            f.write(report)
        
        print("\n✅ 增强优化完成！")
        print(f"   结果保存: v25_result_{ts}.json")
        print(f"   报告保存: v25_report_{ts}.txt")
    else:
        print("❌ 无有效结果")

if __name__ == '__main__':
    main()
