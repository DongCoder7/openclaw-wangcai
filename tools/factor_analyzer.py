#!/usr/bin/env python3
"""
豆奶多因子模型 - 单因子检验
IC分析、IR分析、分层回测
"""
import sqlite3
import pandas as pd
import numpy as np
from typing import Dict, List, Tuple
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
import sys

sys.path.insert(0, '/root/.openclaw/workspace/tools')
from factor_library import FactorLibrary, DataLoader

DB_PATH = '/root/.openclaw/workspace/data/historical/historical.db'


class FactorAnalyzer:
    """单因子检验器"""
    
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self.library = FactorLibrary()
        self.loader = DataLoader(db_path)
    
    def ic_analysis(self, factor_name: str, start_date: str, end_date: str, 
                   forward_period: int = 20) -> Dict:
        """
        IC分析 (Information Coefficient)
        
        计算因子值与未来收益的相关性
        
        Args:
            factor_name: 因子名称
            start_date: 开始日期
            end_date: 结束日期
            forward_period: 前瞻期（默认20日）
        
        Returns:
            IC统计结果
        """
        print(f"\n{'='*60}")
        print(f"IC分析: {factor_name}")
        print(f"期间: {start_date} - {end_date}")
        print(f"前瞻期: {forward_period}日")
        print(f"{'='*60}")
        
        # 获取历史数据
        conn = sqlite3.connect(self.db_path)
        
        query = f"""
        SELECT ts_code, trade_date, close, ret_20, ret_60
        FROM stock_factors
        WHERE trade_date BETWEEN '{start_date}' AND '{end_date}'
        ORDER BY trade_date
        """
        
        df = pd.read_sql(query, conn)
        conn.close()
        
        if df.empty:
            print("❌ 无数据")
            return {}
        
        # 计算前瞻收益
        df['forward_ret'] = df.groupby('ts_code')['close'].pct_change(forward_period).shift(-forward_period)
        
        # 按日期分组计算IC
        ic_series = []
        dates = []
        
        for date, group in df.groupby('trade_date'):
            if len(group) < 10:
                continue
            
            # 获取因子值
            try:
                factor_value = self.library.calc_factor(factor_name, group)
            except:
                continue
            
            # 计算Rank IC (Spearman)
            valid = factor_value.notna() & group['forward_ret'].notna()
            if valid.sum() < 10:
                continue
            
            ic = factor_value[valid].corr(group['forward_ret'][valid], method='spearman')
            
            if not np.isnan(ic):
                ic_series.append(ic)
                dates.append(date)
        
        if not ic_series:
            print("❌ 无法计算IC")
            return {}
        
        ic_series = pd.Series(ic_series, index=dates)
        
        # 统计
        result = {
            'factor': factor_name,
            'period': f"{start_date}-{end_date}",
            'forward_period': forward_period,
            'ic_mean': ic_series.mean(),
            'ic_std': ic_series.std(),
            'ir': ic_series.mean() / ic_series.std() if ic_series.std() > 0 else 0,
            'ic_positive_ratio': (ic_series > 0).mean(),
            'ic_series': ic_series
        }
        
        # 打印结果
        print(f"\n📊 IC统计结果:")
        print(f"  IC均值: {result['ic_mean']:.4f}")
        print(f"  IC标准差: {result['ic_std']:.4f}")
        print(f"  IR比率: {result['ir']:.4f}")
        print(f"  IC>0占比: {result['ic_positive_ratio']*100:.1f}%")
        
        # 评价
        if abs(result['ic_mean']) > 0.03 and abs(result['ir']) > 0.3:
            print(f"  ✅ 因子有效")
        else:
            print(f"  ⚠️ 因子效果一般")
        
        return result
    
    def quantile_backtest(self, factor_name: str, start_date: str, end_date: str,
                         n_quantiles: int = 5, forward_period: int = 20) -> Dict:
        """
        分层回测
        
        将股票按因子值分为n组，观察各组收益差异
        
        Args:
            factor_name: 因子名称
            start_date: 开始日期
            end_date: 结束日期
            n_quantiles: 分层数（默认5层）
            forward_period: 前瞻期
        
        Returns:
            分层回测结果
        """
        print(f"\n{'='*60}")
        print(f"分层回测: {factor_name}")
        print(f"分层数: {n_quantiles}层")
        print(f"{'='*60}")
        
        # 获取数据
        conn = sqlite3.connect(self.db_path)
        
        query = f"""
        SELECT ts_code, trade_date, close, ret_{forward_period} as forward_ret
        FROM stock_factors
        WHERE trade_date BETWEEN '{start_date}' AND '{end_date}'
        AND ret_{forward_period} IS NOT NULL
        ORDER BY trade_date
        """
        
        df = pd.read_sql(query, conn)
        conn.close()
        
        if df.empty:
            print("❌ 无数据")
            return {}
        
        # 计算因子值并分层
        quantile_returns = {i: [] for i in range(1, n_quantiles+1)}
        
        for date, group in df.groupby('trade_date'):
            if len(group) < n_quantiles * 10:
                continue
            
            try:
                factor_value = self.library.calc_factor(factor_name, group)
            except:
                continue
            
            # 分层
            valid = factor_value.notna() & group['forward_ret'].notna()
            if valid.sum() < n_quantiles * 5:
                continue
            
            group_valid = group[valid].copy()
            group_valid['factor'] = factor_value[valid]
            group_valid['quantile'] = pd.qcut(group_valid['factor'], n_quantiles, labels=False) + 1
            
            # 计算每层收益
            for q in range(1, n_quantiles+1):
                q_ret = group_valid[group_valid['quantile'] == q]['forward_ret'].mean()
                if not np.isnan(q_ret):
                    quantile_returns[q].append(q_ret)
        
        # 统计
        result = {}
        for q in range(1, n_quantiles+1):
            if quantile_returns[q]:
                result[f'Q{q}'] = {
                    'mean_return': np.mean(quantile_returns[q]),
                    'std': np.std(quantile_returns[q]),
                    'sharpe': np.mean(quantile_returns[q]) / np.std(quantile_returns[q]) if np.std(quantile_returns[q]) > 0 else 0
                }
        
        # 打印结果
        print(f"\n📊 分层收益统计:")
        for q in range(1, n_quantiles+1):
            if f'Q{q}' in result:
                r = result[f'Q{q}']
                print(f"  Q{q} (最低因子值): 收益={r['mean_return']*100:+.2f}%, 夏普={r['sharpe']:.2f}")
        
        # 多空收益
        if f'Q{n_quantiles}' in result and 'Q1' in result:
            long_short = result[f'Q{n_quantiles}']['mean_return'] - result['Q1']['mean_return']
            print(f"\n  多空收益 (Q{n_quantiles}-Q1): {long_short*100:+.2f}%")
            
            if abs(long_short) > 0.01:
                print(f"  ✅ 分层效果明显")
            else:
                print(f"  ⚠️ 分层效果一般")
        
        return result
    
    def analyze_all_factors(self, start_date: str, end_date: str) -> pd.DataFrame:
        """
        分析所有因子
        
        Returns:
            DataFrame with IC/IR for all factors
        """
        print(f"\n{'='*70}")
        print(f"全因子分析: {start_date} - {end_date}")
        print(f"{'='*70}")
        
        results = []
        
        for factor in self.library.get_all_factors():
            try:
                ic_result = self.ic_analysis(factor.name, start_date, end_date)
                if ic_result:
                    results.append({
                        'factor': factor.name,
                        'category': factor.category,
                        'ic_mean': ic_result['ic_mean'],
                        'ic_std': ic_result['ic_std'],
                        'ir': ic_result['ir'],
                        'ic_positive_ratio': ic_result['ic_positive_ratio']
                    })
            except Exception as e:
                print(f"  分析 {factor.name} 失败: {e}")
        
        df = pd.DataFrame(results)
        
        # 按IR排序
        df = df.sort_values('ir', key=abs, ascending=False)
        
        print(f"\n{'='*70}")
        print("因子IC/IR排名 (按IR绝对值):")
        print(f"{'='*70}")
        print(df.to_string(index=False))
        
        # 推荐有效因子
        effective = df[(df['ic_mean'].abs() > 0.02) & (df['ir'].abs() > 0.2)]
        print(f"\n✅ 有效因子 ({len(effective)}个):")
        print(effective[['factor', 'category', 'ir']].to_string(index=False))
        
        return df


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='单因子检验')
    parser.add_argument('--factor', type=str, help='指定因子名称')
    parser.add_argument('--start', type=str, default='20240101', help='开始日期')
    parser.add_argument('--end', type=str, default='20241231', help='结束日期')
    parser.add_argument('--all', action='store_true', help='分析所有因子')
    
    args = parser.parse_args()
    
    analyzer = FactorAnalyzer()
    
    if args.all:
        # 分析所有因子
        analyzer.analyze_all_factors(args.start, args.end)
    elif args.factor:
        # 分析单个因子
        analyzer.ic_analysis(args.factor, args.start, args.end)
        analyzer.quantile_backtest(args.factor, args.start, args.end)
    else:
        # 显示可用因子
        print("可用因子列表:")
        library = FactorLibrary()
        for category in ['value', 'quality', 'momentum', 'volatility', 'liquidity', 'sentiment']:
            factors = library.get_factors_by_category(category)
            print(f"\n{category.upper()}:")
            for f in factors:
                print(f"  - {f.name}: {f.description}")
        
        print("\n使用方法:")
        print("  python3 factor_analyzer.py --factor momentum_20 --start 20240101 --end 20241231")
        print("  python3 factor_analyzer.py --all --start 20240101 --end 20241231")


if __name__ == '__main__':
    main()
