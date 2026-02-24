#!/usr/bin/env python3
"""
豆奶多因子模型 - 完整因子库
包含6大类30+因子的定义和计算
"""
import sqlite3
import pandas as pd
import numpy as np
from typing import Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime, timedelta

DB_PATH = '/root/.openclaw/workspace/data/historical/historical.db'

@dataclass
class Factor:
    """因子定义"""
    name: str
    category: str
    description: str
    direction: int  # 1=正向(越大越好), -1=负向(越小越好)
    calc_func: callable

class FactorLibrary:
    """因子库 - 管理所有因子定义和计算"""
    
    def __init__(self):
        self.factors = {}
        self._define_factors()
    
    def _define_factors(self):
        """定义所有因子"""
        
        # ==================== 1. 价值因子 ====================
        self.factors['pe_ttm'] = Factor(
            name='pe_ttm',
            category='value',
            description='市盈率TTM',
            direction=-1,
            calc_func=self._calc_pe_ttm
        )
        
        self.factors['pe_percentile'] = Factor(
            name='pe_percentile',
            category='value',
            description='PE历史分位数(5年)',
            direction=-1,
            calc_func=self._calc_pe_percentile
        )
        
        self.factors['pb_ttm'] = Factor(
            name='pb_ttm',
            category='value',
            description='市净率TTM',
            direction=-1,
            calc_func=self._calc_pb_ttm
        )
        
        self.factors['pb_percentile'] = Factor(
            name='pb_percentile',
            category='value',
            description='PB历史分位数(5年)',
            direction=-1,
            calc_func=self._calc_pb_percentile
        )
        
        self.factors['ps_ttm'] = Factor(
            name='ps_ttm',
            category='value',
            description='市销率TTM',
            direction=-1,
            calc_func=self._calc_ps_ttm
        )
        
        self.factors['dividend_yield'] = Factor(
            name='dividend_yield',
            category='value',
            description='股息率',
            direction=1,
            calc_func=self._calc_dividend_yield
        )
        
        # ==================== 2. 质量因子 ====================
        self.factors['roe_ttm'] = Factor(
            name='roe_ttm',
            category='quality',
            description='净资产收益率TTM',
            direction=1,
            calc_func=self._calc_roe_ttm
        )
        
        self.factors['roe_stability'] = Factor(
            name='roe_stability',
            category='quality',
            description='ROE稳定性(8季度标准差倒数)',
            direction=1,
            calc_func=self._calc_roe_stability
        )
        
        self.factors['roa'] = Factor(
            name='roa',
            category='quality',
            description='总资产收益率',
            direction=1,
            calc_func=self._calc_roa
        )
        
        self.factors['gross_margin'] = Factor(
            name='gross_margin',
            category='quality',
            description='毛利率',
            direction=1,
            calc_func=self._calc_gross_margin
        )
        
        self.factors['revenue_growth'] = Factor(
            name='revenue_growth',
            category='quality',
            description='营收增长率(同比)',
            direction=1,
            calc_func=self._calc_revenue_growth
        )
        
        self.factors['profit_growth'] = Factor(
            name='profit_growth',
            category='quality',
            description='净利润增长率(同比)',
            direction=1,
            calc_func=self._calc_profit_growth
        )
        
        self.factors['debt_ratio'] = Factor(
            name='debt_ratio',
            category='quality',
            description='资产负债率',
            direction=-1,
            calc_func=self._calc_debt_ratio
        )
        
        # ==================== 3. 动量因子 ====================
        self.factors['ret_20'] = Factor(
            name='ret_20',
            category='momentum',
            description='20日收益率',
            direction=1,
            calc_func=self._calc_ret_20
        )
        
        self.factors['ret_60'] = Factor(
            name='ret_60',
            category='momentum',
            description='60日收益率',
            direction=1,
            calc_func=self._calc_ret_60
        )
        
        self.factors['ret_120'] = Factor(
            name='ret_120',
            category='momentum',
            description='120日收益率',
            direction=1,
            calc_func=self._calc_ret_120
        )
        
        self.factors['momentum_12_1'] = Factor(
            name='momentum_12_1',
            category='momentum',
            description='12个月-1个月动量(剔除最近1月)',
            direction=1,
            calc_func=self._calc_momentum_12_1
        )
        
        self.factors['momentum_accel'] = Factor(
            name='momentum_accel',
            category='momentum',
            description='动量加速度(20日-60日动量差)',
            direction=1,
            calc_func=self._calc_momentum_accel
        )
        
        self.factors['price_pos_20'] = Factor(
            name='price_pos_20',
            category='momentum',
            description='20日价格位置(0-1)',
            direction=1,
            calc_func=self._calc_price_pos_20
        )
        
        self.factors['price_pos_60'] = Factor(
            name='price_pos_60',
            category='momentum',
            description='60日价格位置(0-1)',
            direction=1,
            calc_func=self._calc_price_pos_60
        )
        
        self.factors['relative_strength'] = Factor(
            name='relative_strength',
            category='momentum',
            description='相对强度(股价/20日均线-1)',
            direction=1,
            calc_func=self._calc_relative_strength
        )
        
        # ==================== 4. 波动因子 ====================
        self.factors['volatility_20'] = Factor(
            name='volatility_20',
            category='volatility',
            description='20日波动率(年化)',
            direction=-1,
            calc_func=self._calc_volatility_20
        )
        
        self.factors['volatility_60'] = Factor(
            name='volatility_60',
            category='volatility',
            description='60日波动率(年化)',
            direction=-1,
            calc_func=self._calc_volatility_60
        )
        
        self.factors['max_drawdown_60'] = Factor(
            name='max_drawdown_60',
            category='volatility',
            description='60日最大回撤',
            direction=-1,
            calc_func=self._calc_max_drawdown_60
        )
        
        self.factors['downside_vol'] = Factor(
            name='downside_vol',
            category='volatility',
            description='下行波动率',
            direction=-1,
            calc_func=self._calc_downside_vol
        )
        
        self.factors['beta'] = Factor(
            name='beta',
            category='volatility',
            description='市场Beta(60日)',
            direction=-1,
            calc_func=self._calc_beta
        )
        
        # ==================== 5. 流动性因子 ====================
        self.factors['turnover_20'] = Factor(
            name='turnover_20',
            category='liquidity',
            description='20日平均换手率',
            direction=-1,
            calc_func=self._calc_turnover_20
        )
        
        self.factors['market_cap'] = Factor(
            name='market_cap',
            category='liquidity',
            description='总市值(对数)',
            direction=-1,
            calc_func=self._calc_market_cap
        )
        
        self.factors['amt_20'] = Factor(
            name='amt_20',
            description='20日平均成交额(对数)',
            category='liquidity',
            direction=-1,
            calc_func=self._calc_amt_20
        )
        
        self.factors['amihud'] = Factor(
            name='amihud',
            category='liquidity',
            description='Amihud非流动性指标',
            direction=-1,
            calc_func=self._calc_amihud
        )
        
        # ==================== 6. 情绪因子 ====================
        self.factors['money_flow_20'] = Factor(
            name='money_flow_20',
            category='sentiment',
            description='20日资金流向',
            direction=1,
            calc_func=self._calc_money_flow_20
        )
        
        self.factors['net_inflow_ratio'] = Factor(
            name='net_inflow_ratio',
            category='sentiment',
            description='净流入比率',
            direction=1,
            calc_func=self._calc_net_inflow_ratio
        )

        # ==================== 7. 原始数据因子 (直接使用) ====================
        self.factors['vol_ratio'] = Factor(
            name='vol_ratio',
            category='liquidity',
            description='量比',
            direction=-1,
            calc_func=self._calc_vol_ratio
        )

        self.factors['profit_mom'] = Factor(
            name='profit_mom',
            category='quality',
            description='收益动量',
            direction=1,
            calc_func=self._calc_profit_mom_direct
        )
    
    # ==================== 因子计算函数 ====================
    
    def _calc_pe_ttm(self, df: pd.DataFrame) -> pd.Series:
        """PE_TTM"""
        return df.get('pe', pd.Series(index=df.index, dtype=float))
    
    def _calc_pe_percentile(self, df: pd.DataFrame) -> pd.Series:
        """PE历史分位数"""
        # 简化实现，实际应该用历史数据计算
        pe = df.get('pe', pd.Series(index=df.index, dtype=float))
        return pe.rank(pct=True)
    
    def _calc_pb_ttm(self, df: pd.DataFrame) -> pd.Series:
        """PB_TTM"""
        return df.get('pb', pd.Series(index=df.index, dtype=float))
    
    def _calc_pb_percentile(self, df: pd.DataFrame) -> pd.Series:
        """PB历史分位数"""
        pb = df.get('pb', pd.Series(index=df.index, dtype=float))
        return pb.rank(pct=True)
    
    def _calc_ps_ttm(self, df: pd.DataFrame) -> pd.Series:
        """PS_TTM"""
        return df.get('ps', pd.Series(index=df.index, dtype=float))
    
    def _calc_dividend_yield(self, df: pd.DataFrame) -> pd.Series:
        """股息率"""
        return df.get('dv_ratio', pd.Series(index=df.index, dtype=float)) / 100
    
    def _calc_roe_ttm(self, df: pd.DataFrame) -> pd.Series:
        """ROE_TTM"""
        return df.get('roe', pd.Series(index=df.index, dtype=float))
    
    def _calc_roe_stability(self, df: pd.DataFrame) -> pd.Series:
        """ROE稳定性 - 简化实现"""
        return pd.Series(0.5, index=df.index)  # 占位
    
    def _calc_roa(self, df: pd.DataFrame) -> pd.Series:
        """ROA"""
        # 简化: ROE * (1 - debt_ratio)
        roe = df.get('roe', pd.Series(index=df.index, dtype=float))
        debt = df.get('debt_ratio', pd.Series(index=df.index, dtype=float))
        return roe * (1 - debt.fillna(0))
    
    def _calc_gross_margin(self, df: pd.DataFrame) -> pd.Series:
        """毛利率 - 简化实现"""
        return pd.Series(0.2, index=df.index)  # 占位
    
    def _calc_revenue_growth(self, df: pd.DataFrame) -> pd.Series:
        """营收增长率"""
        return df.get('revenue_growth', pd.Series(index=df.index, dtype=float))
    
    def _calc_profit_growth(self, df: pd.DataFrame) -> pd.Series:
        """净利润增长率"""
        return df.get('netprofit_growth', pd.Series(index=df.index, dtype=float))
    
    def _calc_debt_ratio(self, df: pd.DataFrame) -> pd.Series:
        """资产负债率"""
        return df.get('debt_ratio', pd.Series(index=df.index, dtype=float))
    
    def _calc_ret_20(self, df: pd.DataFrame) -> pd.Series:
        """20日收益率"""
        return df.get('ret_20', pd.Series(index=df.index, dtype=float))
    
    def _calc_ret_60(self, df: pd.DataFrame) -> pd.Series:
        """60日收益率"""
        return df.get('ret_60', pd.Series(index=df.index, dtype=float))
    
    def _calc_ret_120(self, df: pd.DataFrame) -> pd.Series:
        """120日收益率"""
        return df.get('ret_120', pd.Series(index=df.index, dtype=float))
    
    def _calc_momentum_12_1(self, df: pd.DataFrame) -> pd.Series:
        """12月-1月动量"""
        # 简化: 用120日收益近似
        return df.get('ret_120', pd.Series(index=df.index, dtype=float))
    
    def _calc_momentum_accel(self, df: pd.DataFrame) -> pd.Series:
        """动量加速度"""
        ret_20 = df.get('ret_20', pd.Series(index=df.index, dtype=float))
        ret_60 = df.get('ret_60', pd.Series(index=df.index, dtype=float))
        return ret_20 - ret_60 / 3
    
    def _calc_price_pos_20(self, df: pd.DataFrame) -> pd.Series:
        """20日价格位置"""
        return df.get('price_pos_20', pd.Series(index=df.index, dtype=float))
    
    def _calc_price_pos_60(self, df: pd.DataFrame) -> pd.Series:
        """60日价格位置"""
        return df.get('price_pos_60', pd.Series(index=df.index, dtype=float))
    
    def _calc_relative_strength(self, df: pd.DataFrame) -> pd.Series:
        """相对强度"""
        return df.get('rel_strength', pd.Series(index=df.index, dtype=float))
    
    def _calc_volatility_20(self, df: pd.DataFrame) -> pd.Series:
        """20日波动率"""
        return df.get('vol_20', pd.Series(index=df.index, dtype=float))
    
    def _calc_volatility_60(self, df: pd.DataFrame) -> pd.Series:
        """60日波动率 - 简化"""
        return df.get('vol_20', pd.Series(index=df.index, dtype=float)) * np.sqrt(3)
    
    def _calc_max_drawdown_60(self, df: pd.DataFrame) -> pd.Series:
        """60日最大回撤 - 简化"""
        return df.get('price_pos_high', pd.Series(index=df.index, dtype=float)).abs()
    
    def _calc_downside_vol(self, df: pd.DataFrame) -> pd.Series:
        """下行波动率 - 简化"""
        return df.get('vol_20', pd.Series(index=df.index, dtype=float))
    
    def _calc_beta(self, df: pd.DataFrame) -> pd.Series:
        """Beta - 简化"""
        return pd.Series(1.0, index=df.index)
    
    def _calc_turnover_20(self, df: pd.DataFrame) -> pd.Series:
        """20日换手率"""
        return df.get('turnover_rate', pd.Series(index=df.index, dtype=float))
    
    def _calc_market_cap(self, df: pd.DataFrame) -> pd.Series:
        """总市值对数"""
        mv = df.get('total_mv', pd.Series(index=df.index, dtype=float))
        return np.log(mv.replace(0, np.nan))
    
    def _calc_amt_20(self, df: pd.DataFrame) -> pd.Series:
        """20日成交额对数"""
        amt = df.get('amount', pd.Series(index=df.index, dtype=float))
        return np.log(amt.replace(0, np.nan))
    
    def _calc_amihud(self, df: pd.DataFrame) -> pd.Series:
        """Amihud非流动性"""
        return pd.Series(0.001, index=df.index)  # 占位
    
    def _calc_money_flow_20(self, df: pd.DataFrame) -> pd.Series:
        """20日资金流向"""
        return df.get('money_flow', pd.Series(index=df.index, dtype=float))
    
    def _calc_net_inflow_ratio(self, df: pd.DataFrame) -> pd.Series:
        """净流入比率 - 简化"""
        return pd.Series(0.0, index=df.index)  # 占位

    def _calc_vol_ratio(self, df: pd.DataFrame) -> pd.Series:
        """量比 - 直接使用原始数据"""
        return df.get('vol_ratio', pd.Series(index=df.index, dtype=float))

    def _calc_profit_mom_direct(self, df: pd.DataFrame) -> pd.Series:
        """收益动量 - 直接使用原始数据"""
        return df.get('profit_mom', pd.Series(index=df.index, dtype=float))
    
    # ==================== 公共方法 ====================
    
    def get_factor(self, name: str) -> Optional[Factor]:
        """获取因子定义"""
        return self.factors.get(name)
    
    def get_factors_by_category(self, category: str) -> List[Factor]:
        """按类别获取因子"""
        return [f for f in self.factors.values() if f.category == category]
    
    def get_all_factors(self) -> List[Factor]:
        """获取所有因子"""
        return list(self.factors.values())
    
    def calc_factor(self, name: str, df: pd.DataFrame) -> pd.Series:
        """计算单个因子"""
        factor = self.factors.get(name)
        if not factor:
            raise ValueError(f"未知因子: {name}")
        return factor.calc_func(df)
    
    def calc_all_factors(self, df: pd.DataFrame) -> pd.DataFrame:
        """计算所有因子"""
        result = df.copy()
        for name, factor in self.factors.items():
            try:
                result[name] = factor.calc_func(df)
            except Exception as e:
                print(f"计算因子 {name} 失败: {e}")
                result[name] = np.nan
        return result


# ==================== 数据获取类 ====================

class DataLoader:
    """数据加载器"""
    
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
    
    def get_stock_data_with_valuation(self, trade_date: str = None) -> pd.DataFrame:
        """
        获取指定日期的全市场股票数据（包含估值）
        
        Args:
            trade_date: 交易日期 (YYYYMMDD), 默认为最新日期
        
        Returns:
            DataFrame with factors + valuation
        """
        conn = sqlite3.connect(self.db_path)
        
        if not trade_date:
            # 获取最新日期
            cursor = conn.cursor()
            cursor.execute("SELECT MAX(trade_date) FROM stock_factors")
            trade_date = cursor.fetchone()[0]
        
        # 从多个表获取数据（包含估值表）
        query = f"""
        SELECT 
            f.ts_code,
            f.trade_date,
            f.ret_20,
            f.ret_60,
            f.ret_120,
            f.vol_20,
            f.vol_ratio,
            f.ma_20,
            f.ma_60,
            f.price_pos_20,
            f.price_pos_60,
            f.price_pos_high,
            f.vol_ratio_amt,
            f.money_flow,
            f.rel_strength,
            f.mom_accel,
            f.profit_mom,
            v.pe,
            v.pb,
            v.market_cap,
            v.turnover_rate as turnover_val
        FROM stock_factors f
        LEFT JOIN stock_valuation v 
            ON f.ts_code = v.ts_code 
            AND f.trade_date = v.trade_date
        WHERE f.trade_date = '{trade_date}'
        """
        
        df = pd.read_sql(query, conn)
        conn.close()
        
        return df
    
    def get_historical_data(self, ts_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        """获取单只股票历史数据"""
        conn = sqlite3.connect(self.db_path)
        
        query = f"""
        SELECT * FROM stock_factors
        WHERE ts_code = '{ts_code}'
        AND trade_date BETWEEN '{start_date}' AND '{end_date}'
        ORDER BY trade_date
        """
        
        df = pd.read_sql(query, conn)
        conn.close()
        
        return df


if __name__ == '__main__':
    # 测试
    print("="*60)
    print("豆奶多因子模型 - 因子库测试")
    print("="*60)
    
    # 初始化
    library = FactorLibrary()
    loader = DataLoader()
    
    # 打印因子列表
    print(f"\n共定义 {len(library.get_all_factors())} 个因子:")
    for category in ['value', 'quality', 'momentum', 'volatility', 'liquidity', 'sentiment']:
        factors = library.get_factors_by_category(category)
        print(f"\n{category.upper()} ({len(factors)}个):")
        for f in factors:
            print(f"  - {f.name}: {f.description}")
    
    # 加载数据
    print("\n" + "="*60)
    print("加载最新数据...")
    df = loader.get_stock_data()
    print(f"获取到 {len(df)} 只股票数据")
    
    # 计算所有因子
    print("\n计算所有因子...")
    df_with_factors = library.calc_all_factors(df)
    
    # 显示结果
    factor_cols = [f.name for f in library.get_all_factors()]
    print(f"\n因子样例 (前3只股票):")
    print(df_with_factors[['ts_code'] + factor_cols[:5]].head(3))
    
    print("\n✅ 因子库测试完成")
