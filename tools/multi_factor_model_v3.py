#!/usr/bin/env python3
"""
豆奶多因子模型 v3.0 - 多策略配置
支持进攻型/防御型/平衡型策略
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


class MultiFactorModelV3:
    """多因子评分模型 v3.0 - 多策略配置"""
    
    # ========== 策略配置 ==========
    
    # 1. 进攻型策略 (牛市) - 动量为主
    OFFENSIVE_FACTORS = {
        # 动量因子 (50%)
        'ret_20': {'weight': 0.20, 'direction': 1},
        'ret_60': {'weight': 0.15, 'direction': 1},
        'momentum_accel': {'weight': 0.10, 'direction': 1},
        'relative_strength': {'weight': 0.05, 'direction': 1},
        
        # 情绪因子 (20%)
        'money_flow_20': {'weight': 0.15, 'direction': 1},
        'profit_mom': {'weight': 0.05, 'direction': 1},
        
        # 价值因子 (15%)
        'pe_ttm': {'weight': 0.10, 'direction': -1},
        'pb_ttm': {'weight': 0.05, 'direction': -1},
        
        # 波动因子 (15%)
        'volatility_20': {'weight': 0.10, 'direction': -1},
        'vol_ratio': {'weight': 0.05, 'direction': -1},
    }
    
    # 2. 防御型策略 (熊市) - 低波动+质量
    DEFENSIVE_FACTORS = {
        # 防御因子 (40%) - 低波动
        'low_vol_score': {'weight': 0.15, 'direction': 1},
        'volatility_20': {'weight': 0.10, 'direction': -1},
        'downside_vol': {'weight': 0.10, 'direction': -1},
        'max_drawdown_120': {'weight': 0.05, 'direction': 1},  # 回撤小的好
        
        # 价值因子 (30%) - 便宜的好
        'pe_ttm': {'weight': 0.15, 'direction': -1},
        'pb_ttm': {'weight': 0.10, 'direction': -1},
        'market_cap': {'weight': 0.05, 'direction': -1},
        
        # 质量因子 (20%) - 盈利稳定的
        'profit_mom': {'weight': 0.15, 'direction': 1},
        'sharpe_like': {'weight': 0.05, 'direction': 1},
        
        # 动量因子 (10%) - 温和动量
        'ret_60': {'weight': 0.05, 'direction': 1},
        'rel_strength': {'weight': 0.05, 'direction': 1},
    }
    
    # 3. 平衡型策略 (震荡市)
    BALANCED_FACTORS = {
        # 价值因子 (25%)
        'pe_ttm': {'weight': 0.15, 'direction': -1},
        'pb_ttm': {'weight': 0.10, 'direction': -1},
        
        # 动量因子 (25%)
        'ret_20': {'weight': 0.10, 'direction': 1},
        'ret_60': {'weight': 0.10, 'direction': 1},
        'relative_strength': {'weight': 0.05, 'direction': 1},
        
        # 防御因子 (25%)
        'low_vol_score': {'weight': 0.10, 'direction': 1},
        'volatility_20': {'weight': 0.10, 'direction': -1},
        'downside_vol': {'weight': 0.05, 'direction': -1},
        
        # 质量因子 (15%)
        'profit_mom': {'weight': 0.10, 'direction': 1},
        'sharpe_like': {'weight': 0.05, 'direction': 1},
        
        # 情绪因子 (10%)
        'money_flow_20': {'weight': 0.10, 'direction': 1},
    }
    
    # 4. 原v2.0策略 (保留兼容)
    V2_FACTORS = {
        'pe_ttm': {'weight': 0.15, 'direction': -1},
        'pb_ttm': {'weight': 0.10, 'direction': -1},
        'market_cap': {'weight': 0.10, 'direction': -1},
        'ret_20': {'weight': 0.12, 'direction': 1},
        'ret_60': {'weight': 0.10, 'direction': 1},
        'momentum_accel': {'weight': 0.08, 'direction': 1},
        'relative_strength': {'weight': 0.05, 'direction': 1},
        'profit_mom': {'weight': 0.10, 'direction': 1},
        'volatility_20': {'weight': 0.05, 'direction': -1},
        'vol_ratio': {'weight': 0.05, 'direction': -1},
        'money_flow_20': {'weight': 0.10, 'direction': 1},
    }
    
    STRATEGIES = {
        'offensive': OFFENSIVE_FACTORS,
        'defensive': DEFENSIVE_FACTORS,
        'balanced': BALANCED_FACTORS,
        'v2': V2_FACTORS,
    }
    
    def __init__(self, strategy: str = 'balanced', db_path: str = DB_PATH):
        """
        初始化
        
        Args:
            strategy: 策略类型 ('offensive', 'defensive', 'balanced', 'v2')
            db_path: 数据库路径
        """
        self.db_path = db_path
        self.strategy_name = strategy
        self.factor_weights = self.STRATEGIES.get(strategy, self.BALANCED_FACTORS)
        self.conn = sqlite3.connect(db_path)
    
    def get_data_with_all_factors(self, trade_date: str = None) -> pd.DataFrame:
        """获取包含所有因子的数据"""
        if not trade_date:
            cursor = self.conn.cursor()
            cursor.execute("SELECT MAX(trade_date) FROM stock_factors")
            trade_date = cursor.fetchone()[0]
        
        # Query all available factors
        query = f"""
        SELECT 
            f.ts_code,
            f.trade_date,
            f.ret_20, f.ret_60, f.ret_120,
            f.vol_20, f.vol_ratio,
            f.price_pos_20, f.price_pos_60,
            f.money_flow, f.rel_strength, f.mom_accel, f.profit_mom,
            v.pe as pe_ttm, v.pb as pb_ttm, v.market_cap, v.turnover_rate,
            d.vol_120, d.max_drawdown_120, d.downside_vol, d.low_vol_score, d.sharpe_like
        FROM stock_factors f
        LEFT JOIN stock_valuation v ON f.ts_code = v.ts_code AND f.trade_date = v.trade_date
        LEFT JOIN stock_defensive_factors d ON f.ts_code = d.ts_code AND f.trade_date = d.trade_date
        WHERE f.trade_date = '{trade_date}'
        """
        
        df = pd.read_sql(query, self.conn)
        return df
    
    def calc_factor_score(self, df: pd.DataFrame, factor_name: str, 
                         direction: int) -> pd.Series:
        """计算单因子得分"""
        # Get factor value
        if factor_name in df.columns:
            factor_value = df[factor_name]
        else:
            return pd.Series(np.nan, index=df.index)
        
        # 去除异常值
        q_low = factor_value.quantile(0.01)
        q_high = factor_value.quantile(0.99)
        factor_value = factor_value.clip(q_low, q_high)
        
        # 排名标准化 (0-1)
        score = factor_value.rank(pct=True)
        
        # 根据方向调整
        if direction == -1:
            score = 1 - score
        
        return score
    
    def calc_composite_score(self, df: pd.DataFrame) -> pd.DataFrame:
        """计算综合评分"""
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
        
        result['composite_score'] = composite
        
        # 计算因子暴露
        for factor_name in self.factor_weights.keys():
            if factor_name in factor_scores:
                result[f'factor_{factor_name}'] = factor_scores[factor_name]
        
        return result
    
    def select_stocks(self, trade_date: str = None, top_n: int = 50) -> pd.DataFrame:
        """选股"""
        print(f"\n{'='*60}")
        print(f"多因子选股 v3.0 - 策略: {self.strategy_name}")
        print(f"{'='*60}")
        
        # 加载数据
        df = self.get_data_with_all_factors(trade_date)
        
        if df.empty:
            print("❌ 无数据")
            return pd.DataFrame()
        
        print(f"原始股票数: {len(df)}")
        
        # 统计各因子覆盖率
        print(f"\n因子覆盖情况:")
        for factor in self.factor_weights.keys():
            if factor in df.columns:
                coverage = df[factor].notna().sum()
                print(f"  {factor}: {coverage}/{len(df)} ({coverage/len(df)*100:.1f}%)")
        
        # 过滤基本数据
        df = df.dropna(subset=['ret_20'])
        
        # 过滤PE/PB异常值
        if 'pe_ttm' in df.columns:
            df = df[(df['pe_ttm'].isna()) | ((df['pe_ttm'] > 0) & (df['pe_ttm'] < 500))]
        if 'pb_ttm' in df.columns:
            df = df[(df['pb_ttm'].isna()) | ((df['pb_ttm'] > 0) & (df['pb_ttm'] < 100))]
        
        print(f"\n过滤后: {len(df)} 只")
        
        # 计算综合评分
        df = self.calc_composite_score(df)
        
        # 排序
        df = df.sort_values('composite_score', ascending=False)
        
        # 选出Top N
        selected = df.head(top_n).copy()
        
        # 打印结果
        print(f"\n✅ 选出 {len(selected)} 只股票")
        print(f"\nTop 10:")
        for i, (idx, row) in enumerate(selected.head(10).iterrows(), 1):
            pe_str = f"PE={row['pe_ttm']:.1f}" if pd.notna(row.get('pe_ttm')) else "PE=N/A"
            pb_str = f"PB={row['pb_ttm']:.1f}" if pd.notna(row.get('pb_ttm')) else "PB=N/A"
            print(f"  {i:2d}. {row['ts_code']}: 评分={row['composite_score']:.3f}, {pe_str}, {pb_str}")
        
        return selected
    
    def close(self):
        """关闭连接"""
        self.conn.close()


def test_all_strategies():
    """测试所有策略"""
    print("="*70)
    print("测试所有策略")
    print("="*70)
    
    strategies = ['offensive', 'defensive', 'balanced', 'v2']
    
    for strategy in strategies:
        print(f"\n{'='*70}")
        model = MultiFactorModelV3(strategy=strategy)
        selected = model.select_stocks(top_n=30)
        
        if not selected.empty:
            print(f"\n策略 {strategy}:")
            print(f"  平均PE: {selected['pe_ttm'].mean():.2f}")
            print(f"  平均PB: {selected['pb_ttm'].mean():.2f}")
            print(f"  平均20日收益: {selected['ret_20'].mean()*100:.2f}%")
            print(f"  平均低波动得分: {selected.get('low_vol_score', pd.Series()).mean():.3f}")
        
        model.close()


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='多因子选股 v3.0')
    parser.add_argument('--strategy', type=str, default='balanced',
                       choices=['offensive', 'defensive', 'balanced', 'v2'],
                       help='策略类型')
    parser.add_argument('--date', type=str, help='指定日期 (YYYYMMDD)')
    parser.add_argument('--top', type=int, default=50, help='选出前N只')
    parser.add_argument('--test-all', action='store_true', help='测试所有策略')
    
    args = parser.parse_args()
    
    if args.test_all:
        test_all_strategies()
    else:
        model = MultiFactorModelV3(strategy=args.strategy)
        selected = model.select_stocks(trade_date=args.date, top_n=args.top)
        
        # Save results
        output_file = f'/root/.openclaw/workspace/data/selected_{args.strategy}_{datetime.now().strftime("%Y%m%d")}.csv'
        selected.to_csv(output_file, index=False)
        print(f"\n结果已保存: {output_file}")
        
        model.close()


if __name__ == '__main__':
    main()
