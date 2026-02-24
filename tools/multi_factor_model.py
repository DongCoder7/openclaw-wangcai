#!/usr/bin/env python3
"""
豆奶多因子模型 v2.0 - 多因子评分模型
整合技术因子 + 估值因子 (PE/PB/市值)
"""
import sqlite3
import pandas as pd
import numpy as np
from typing import Dict, List, Optional
from datetime import datetime
import sys

sys.path.insert(0, '/root/.openclaw/workspace/tools')
from factor_library import FactorLibrary, DataLoader

DB_PATH = '/root/.openclaw/workspace/data/historical/historical.db'


class MultiFactorModel:
    """多因子评分模型 v2.0"""
    
    # 完整版因子配置 (使用腾讯API估值数据)
    DEFAULT_FACTORS_FULL = {
        # 价值因子 (35%)
        'pe_ttm': {'weight': 0.15, 'direction': -1},        # PE负向
        'pb_ttm': {'weight': 0.10, 'direction': -1},        # PB负向
        'market_cap': {'weight': 0.10, 'direction': -1},    # 市值负向 (小市值)
        
        # 动量因子 (35%)
        'ret_20': {'weight': 0.12, 'direction': 1},         # 20日收益
        'ret_60': {'weight': 0.10, 'direction': 1},         # 60日收益
        'momentum_accel': {'weight': 0.08, 'direction': 1}, # 动量加速
        'relative_strength': {'weight': 0.05, 'direction': 1}, # 相对强度
        
        # 质量因子 (10%)
        'profit_mom': {'weight': 0.10, 'direction': 1},     # 收益动量
        
        # 波动因子 (10%)
        'volatility_20': {'weight': 0.05, 'direction': -1}, # 波动率负向
        'vol_ratio': {'weight': 0.05, 'direction': -1},     # 量比负向
        
        # 情绪因子 (10%)
        'money_flow_20': {'weight': 0.10, 'direction': 1},  # 资金流向
    }
    
    # 轻量版 (仅技术因子)
    DEFAULT_FACTORS_LITE = {
        'ret_20': {'weight': 0.25, 'direction': 1},
        'ret_60': {'weight': 0.20, 'direction': 1},
        'momentum_accel': {'weight': 0.15, 'direction': 1},
        'relative_strength': {'weight': 0.10, 'direction': 1},
        'price_pos_20': {'weight': 0.10, 'direction': 1},
        'volatility_20': {'weight': 0.10, 'direction': -1},
        'vol_ratio': {'weight': 0.05, 'direction': -1},
        'money_flow_20': {'weight': 0.05, 'direction': 1},
    }
    
    def __init__(self, factor_weights: Dict = None, db_path: str = DB_PATH, use_full: bool = True):
        """
        初始化
        
        Args:
            factor_weights: 自定义因子权重
            db_path: 数据库路径
            use_full: 是否使用完整版（含估值因子）
        """
        self.db_path = db_path
        self.library = FactorLibrary()
        self.loader = DataLoader(db_path)
        self.factor_weights = factor_weights or (self.DEFAULT_FACTORS_FULL if use_full else self.DEFAULT_FACTORS_LITE)
        self.use_full = use_full
    
    def calc_factor_score(self, df: pd.DataFrame, factor_name: str, 
                         direction: int, method: str = 'rank') -> pd.Series:
        """
        计算单因子得分 (标准化)
        
        Args:
            df: 数据
            factor_name: 因子名称
            direction: 方向 (1=正向, -1=负向)
            method: 标准化方法 ('rank' or 'zscore')
        
        Returns:
            标准化后的因子得分
        """
        try:
            factor_value = self.library.calc_factor(factor_name, df)
        except Exception as e:
            # 对于数据库直接有的字段（如pe, pb），直接使用
            if factor_name in df.columns:
                factor_value = df[factor_name]
            elif factor_name == 'pe_ttm' and 'pe' in df.columns:
                factor_value = df['pe']
            elif factor_name == 'pb_ttm' and 'pb' in df.columns:
                factor_value = df['pb']
            else:
                print(f"计算因子 {factor_name} 失败: {e}")
                return pd.Series(np.nan, index=df.index)
        
        # 去除异常值
        q_low = factor_value.quantile(0.01)
        q_high = factor_value.quantile(0.99)
        factor_value = factor_value.clip(q_low, q_high)
        
        if method == 'rank':
            # 排名标准化 (0-1)
            score = factor_value.rank(pct=True)
        elif method == 'zscore':
            # Z-score标准化
            mean = factor_value.mean()
            std = factor_value.std()
            if std > 0:
                score = (factor_value - mean) / std
            else:
                score = pd.Series(0, index=df.index)
        else:
            raise ValueError(f"未知标准化方法: {method}")
        
        # 根据方向调整
        if direction == -1:
            score = 1 - score
        
        return score
    
    def calc_composite_score(self, df: pd.DataFrame, 
                            neutralize: bool = True) -> pd.DataFrame:
        """
        计算综合评分
        
        Args:
            df: 原始数据
            neutralize: 是否进行市值中性化
        
        Returns:
            带综合评分的DataFrame
        """
        result = df.copy()
        
        # 计算每个因子的得分
        factor_scores = {}
        
        for factor_name, config in self.factor_weights.items():
            weight = config['weight']
            direction = config['direction']
            
            score = self.calc_factor_score(result, factor_name, direction)
            factor_scores[factor_name] = score * weight
        
        # 计算加权综合得分
        composite = pd.Series(0, index=result.index)
        for factor_name, score in factor_scores.items():
            composite += score.fillna(0)
        
        # 市值中性化
        if neutralize:
            # 使用market_cap作为市值代理
            if 'market_cap' in result.columns and result['market_cap'].notna().sum() > 0:
                # 按市值分为5组
                result['cap_group'] = pd.qcut(result['market_cap'].rank(method='first'), 5, labels=False, duplicates='drop')
                
                # 每组内标准化
                neutralized = pd.Series(np.nan, index=result.index)
                for group in range(5):
                    mask = result['cap_group'] == group
                    if mask.sum() > 0:
                        group_score = composite[mask]
                        if group_score.std() > 0:
                            neutralized[mask] = (group_score - group_score.mean()) / group_score.std()
                        else:
                            neutralized[mask] = 0
                
                result['composite_score'] = neutralized.fillna(composite)
            else:
                # 无法中性化，直接使用原始分数
                result['composite_score'] = composite
        else:
            result['composite_score'] = composite
        
        # 计算因子暴露
        for factor_name in self.factor_weights.keys():
            if factor_name in factor_scores:
                result[f'factor_{factor_name}'] = factor_scores[factor_name]
        
        return result
    
    def select_stocks(self, trade_date: str = None, top_n: int = 50,
                     min_score: float = None) -> pd.DataFrame:
        """
        选股
        
        Args:
            trade_date: 交易日期，默认最新
            top_n: 选出前N只
            min_score: 最低综合评分
        
        Returns:
            选股结果DataFrame
        """
        print(f"\n{'='*60}")
        print(f"多因子选股 v2.0")
        print(f"{'='*60}")
        
        # 加载数据（包含估值）
        df = self.loader.get_stock_data_with_valuation(trade_date)
        
        if df.empty:
            print("❌ 无数据")
            return pd.DataFrame()
        
        print(f"原始股票数: {len(df)}")
        print(f"有PE数据: {df['pe'].notna().sum()}")
        print(f"有PB数据: {df['pb'].notna().sum()}")
        
        # 过滤：只保留有基本数据的
        df = df.dropna(subset=['ret_20'])
        
        # 如果有估值数据，过滤掉异常值
        if self.use_full:
            # 过滤PE/PB为负或异常高的
            if 'pe' in df.columns:
                df = df[(df['pe'].isna()) | ((df['pe'] > 0) & (df['pe'] < 500))]
            if 'pb' in df.columns:
                df = df[(df['pb'].isna()) | ((df['pb'] > 0) & (df['pb'] < 100))]
        
        print(f"过滤后股票数: {len(df)}")
        
        # 计算综合评分
        df = self.calc_composite_score(df, neutralize=True)
        
        # 排序
        df = df.sort_values('composite_score', ascending=False)
        
        # 筛选
        if min_score:
            df = df[df['composite_score'] >= min_score]
        
        selected = df.head(top_n).copy()
        
        # 打印结果
        print(f"\n✅ 选出 {len(selected)} 只股票")
        print(f"\nTop 10:")
        display_cols = ['ts_code', 'composite_score', 'pe', 'pb', 'ret_20', 'market_cap']
        available_cols = [c for c in display_cols if c in selected.columns]
        for i, (idx, row) in enumerate(selected.head(10).iterrows(), 1):
            pe_str = f"PE={row['pe']:.1f}" if pd.notna(row.get('pe')) else "PE=N/A"
            pb_str = f"PB={row['pb']:.1f}" if pd.notna(row.get('pb')) else "PB=N/A"
            ret_str = f"Ret20={row['ret_20']*100:.1f}%"
            print(f"  {i:2d}. {row['ts_code']}: 评分={row['composite_score']:.3f}, {pe_str}, {pb_str}, {ret_str}")
        
        return selected
    
    def get_factor_exposure(self, portfolio: pd.DataFrame) -> Dict:
        """
        计算组合因子暴露
        
        Args:
            portfolio: 组合DataFrame
        
        Returns:
            因子暴露统计
        """
        exposure = {}
        
        for factor_name in self.factor_weights.keys():
            col = f'factor_{factor_name}'
            if col in portfolio.columns:
                exposure[factor_name] = {
                    'mean': portfolio[col].mean(),
                    'std': portfolio[col].std(),
                    'min': portfolio[col].min(),
                    'max': portfolio[col].max()
                }
        
        return exposure
    
    def generate_report(self, selected: pd.DataFrame) -> str:
        """生成选股报告"""
        lines = [
            "="*60,
            "豆奶多因子模型 v2.0 - 选股报告",
            "="*60,
            f"日期: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            f"模型版本: {'完整版 (含估值)' if self.use_full else '轻量版'}",
            f"选中股票数: {len(selected)}",
            "",
            "因子配置:",
        ]
        
        for factor, config in self.factor_weights.items():
            lines.append(f"  {factor}: 权重={config['weight']:.0%}, 方向={'正向' if config['direction']==1 else '负向'}")
        
        lines.extend([
            "",
            "Top 20 选股结果:",
            "-"*60,
        ])
        
        for i, (idx, row) in enumerate(selected.head(20).iterrows(), 1):
            lines.append(f"  {i:2d}. {row['ts_code']}  评分={row['composite_score']:.3f}")
        
        lines.extend([
            "-"*60,
            "组合特征:",
        ])
        
        if 'pe' in selected.columns:
            lines.append(f"  平均PE: {selected['pe'].mean():.2f}")
        if 'pb' in selected.columns:
            lines.append(f"  平均PB: {selected['pb'].mean():.2f}")
        if 'market_cap' in selected.columns:
            lines.append(f"  平均市值: {selected['market_cap'].mean()/1e8:.2f}亿")
        
        lines.append("="*60)
        
        return '\n'.join(lines)


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='多因子选股 v2.0')
    parser.add_argument('--date', type=str, help='指定日期 (YYYYMMDD)')
    parser.add_argument('--top', type=int, default=50, help='选出前N只')
    parser.add_argument('--report', action='store_true', help='生成详细报告')
    parser.add_argument('--lite', action='store_true', help='使用轻量版')
    
    args = parser.parse_args()
    
    # 初始化模型
    model = MultiFactorModel(use_full=not args.lite)
    
    # 选股
    selected = model.select_stocks(trade_date=args.date, top_n=args.top)
    
    if args.report:
        report = model.generate_report(selected)
        print(report)
        
        # 保存结果
        output_file = f'/root/.openclaw/workspace/data/selected_stocks_{datetime.now().strftime("%Y%m%d")}.csv'
        selected.to_csv(output_file, index=False)
        print(f"\n结果已保存: {output_file}")


if __name__ == '__main__':
    main()
