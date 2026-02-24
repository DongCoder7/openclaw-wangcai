#!/usr/bin/env python3
"""
行业分类与中性化模块
使用市值分组作为行业代理（简化实现）
"""
import sqlite3
import pandas as pd
import numpy as np
from typing import Dict, List
from datetime import datetime

DB_PATH = '/root/.openclaw/workspace/data/historical/historical.db'


class IndustryNeutralizer:
    """行业中性化器"""
    
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
    
    def assign_size_groups(self, df: pd.DataFrame, n_groups: int = 5) -> pd.DataFrame:
        """
        按市值分组（作为行业代理）
        
        Args:
            df: 包含市值数据的DataFrame
            n_groups: 分组数
        
        Returns:
            添加了size_group列的DataFrame
        """
        if 'market_cap' not in df.columns or df['market_cap'].isna().all():
            # 没有市值数据，使用价格作为代理
            if 'ma_20' in df.columns:
                df['size_proxy'] = df['ma_20']
            else:
                df['size_group'] = 2  # 默认中等
                return df
        else:
            df['size_proxy'] = df['market_cap']
        
        # 分组
        try:
            df['size_group'] = pd.qcut(
                df['size_proxy'].rank(method='first'), 
                n_groups, 
                labels=range(n_groups),
                duplicates='drop'
            )
        except:
            # 如果分组失败，使用简单分箱
            df['size_group'] = pd.cut(df['size_proxy'], bins=n_groups, labels=range(n_groups))
        
        return df
    
    def neutralize_by_group(self, df: pd.DataFrame, factor_col: str = 'composite_score') -> pd.DataFrame:
        """
        在每组内进行标准化
        
        Args:
            df: 包含size_group和factor_col的DataFrame
            factor_col: 需要中性化的因子列
        
        Returns:
            添加了中性化后分数的DataFrame
        """
        if 'size_group' not in df.columns:
            print("Warning: size_group not found, skipping neutralization")
            df[f'{factor_col}_neutral'] = df[factor_col]
            return df
        
        # 在每组内标准化
        neutralized = pd.Series(np.nan, index=df.index)
        
        for group in df['size_group'].unique():
            if pd.isna(group):
                continue
            
            mask = df['size_group'] == group
            if mask.sum() < 5:  # 组内样本太少
                neutralized[mask] = df.loc[mask, factor_col]
                continue
            
            group_values = df.loc[mask, factor_col]
            
            if group_values.std() > 0:
                # Z-score标准化
                neutralized[mask] = (group_values - group_values.mean()) / group_values.std()
            else:
                neutralized[mask] = 0
        
        df[f'{factor_col}_neutral'] = neutralized
        
        # 将NaN填充为原始值
        df[f'{factor_col}_neutral'] = df[f'{factor_col}_neutral'].fillna(df[factor_col])
        
        return df
    
    def apply_constraints(self, df: pd.DataFrame, 
                         max_per_group: int = 5,
                         total_positions: int = 20) -> pd.DataFrame:
        """
        应用行业/市值约束
        
        Args:
            df: 已评分的DataFrame
            max_per_group: 每组最大持仓数
            total_positions: 总持仓数
        
        Returns:
            满足约束的选股结果
        """
        if 'size_group' not in df.columns:
            # 没有分组信息，直接返回Top N
            return df.head(total_positions)
        
        selected = []
        group_counts = {}
        
        # 按评分排序
        df_sorted = df.sort_values('composite_score', ascending=False)
        
        for _, row in df_sorted.iterrows():
            group = row.get('size_group', 0)
            
            # 检查组限制
            if group not in group_counts:
                group_counts[group] = 0
            
            if group_counts[group] < max_per_group and len(selected) < total_positions:
                selected.append(row)
                group_counts[group] += 1
        
        return pd.DataFrame(selected)
    
    def get_group_exposure(self, portfolio: pd.DataFrame) -> Dict:
        """
        计算组合的分组暴露
        
        Returns:
            各组持仓分布
        """
        if 'size_group' not in portfolio.columns:
            return {}
        
        exposure = portfolio.groupby('size_group').size().to_dict()
        total = len(portfolio)
        
        return {
            group: {'count': count, 'pct': count/total}
            for group, count in exposure.items()
        }


def main():
    """测试"""
    print("="*60)
    print("行业中性化测试")
    print("="*60)
    
    # 模拟数据
    import numpy as np
    np.random.seed(42)
    
    df = pd.DataFrame({
        'ts_code': [f'{i:06d}.SZ' for i in range(100)],
        'market_cap': np.random.lognormal(10, 2, 100),
        'composite_score': np.random.randn(100)
    })
    
    neutralizer = IndustryNeutralizer()
    
    # 分组
    df = neutralizer.assign_size_groups(df)
    print(f"\n市值分组分布:")
    print(df['size_group'].value_counts().sort_index())
    
    # 中性化
    df = neutralizer.neutralize_by_group(df)
    print(f"\n中性化前后相关性: {df['composite_score'].corr(df['composite_score_neutral']):.3f}")
    
    # 应用约束
    selected = neutralizer.apply_constraints(df, max_per_group=5, total_positions=20)
    print(f"\n选中 {len(selected)} 只股票")
    
    # 检查暴露
    exposure = neutralizer.get_group_exposure(selected)
    print(f"\n分组暴露:")
    for group, info in sorted(exposure.items()):
        print(f"  组{group}: {info['count']}只 ({info['pct']*100:.0f}%)")


if __name__ == '__main__':
    main()
