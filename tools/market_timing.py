#!/usr/bin/env python3
"""
市场择时模块
判断当前市场环境，调整仓位
"""
import sqlite3
import pandas as pd
import numpy as np
from datetime import datetime
from typing import Dict, Optional

DB_PATH = '/root/.openclaw/workspace/data/historical/historical.db'


class MarketTiming:
    """市场择时器"""
    
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
    
    def get_market_index_data(self, days: int = 60) -> Optional[pd.DataFrame]:
        """
        获取大盘指数数据（使用全市场平均）
        """
        conn = sqlite3.connect(self.db_path)
        
        # 获取最近N天的全市场平均收益
        query = f"""
        SELECT 
            trade_date,
            AVG(ret_20) as avg_ret_20,
            AVG(ret_60) as avg_ret_60,
            AVG(vol_20) as avg_vol_20,
            COUNT(*) as stock_count
        FROM stock_factors
        WHERE trade_date >= date('now', '-{days} days')
        GROUP BY trade_date
        ORDER BY trade_date
        """
        
        df = pd.read_sql(query, conn)
        conn.close()
        
        if df.empty:
            return None
        
        df['trade_date'] = pd.to_datetime(df['trade_date'])
        return df
    
    def calculate_market_score(self, date: str = None) -> Dict:
        """
        计算市场环境评分
        
        Returns:
            {
                'market_state': 'bull'|'bear'|'neutral',
                'position_pct': 0.0~1.0,
                'market_score': -1.0~1.0,
                'signals': {}
            }
        """
        df = self.get_market_index_data(days=60)
        
        if df is None or len(df) < 20:
            return {
                'market_state': 'neutral',
                'position_pct': 0.5,
                'market_score': 0,
                'signals': {'error': 'Insufficient data'}
            }
        
        latest = df.iloc[-1]
        
        # 计算多个信号
        signals = {}
        
        # 1. 短期趋势 (20日收益)
        short_term_ret = latest['avg_ret_20']
        signals['short_term'] = 1 if short_term_ret > 0.05 else (-1 if short_term_ret < -0.05 else 0)
        
        # 2. 中期趋势 (60日收益)
        medium_term_ret = latest['avg_ret_60']
        signals['medium_term'] = 1 if medium_term_ret > 0.10 else (-1 if medium_term_ret < -0.10 else 0)
        
        # 3. 趋势动量 (20日 vs 60日)
        if len(df) >= 60:
            ret_20 = df['avg_ret_20'].iloc[-20:].mean()
            ret_60 = df['avg_ret_60'].iloc[-1]
            momentum = ret_20 - ret_60 / 3
            signals['momentum'] = 1 if momentum > 0.02 else (-1 if momentum < -0.02 else 0)
        else:
            signals['momentum'] = 0
        
        # 4. 市场波动率
        recent_vol = df['avg_vol_20'].iloc[-10:].mean()
        vol_score = -1 if recent_vol > 0.05 else (1 if recent_vol < 0.03 else 0)
        signals['volatility'] = vol_score
        
        # 5. 市场广度 (上涨股票比例)
        # 简化：使用最近1日收益判断
        latest_ret = latest['avg_ret_20']
        breadth = 1 if latest_ret > 0 else (-1 if latest_ret < 0 else 0)
        signals['breadth'] = breadth
        
        # 综合评分
        weights = {
            'short_term': 0.25,
            'medium_term': 0.25,
            'momentum': 0.20,
            'volatility': 0.15,
            'breadth': 0.15
        }
        
        market_score = sum(signals[k] * weights[k] for k in weights.keys())
        
        # 判断市场状态
        if market_score > 0.3:
            market_state = 'bull'
            position_pct = 1.0
        elif market_score < -0.3:
            market_state = 'bear'
            position_pct = 0.0  # 空仓
        else:
            market_state = 'neutral'
            position_pct = 0.5
        
        # 波动率调整
        if recent_vol > 0.06:  # 高波动市场降低仓位
            position_pct *= 0.7
        
        return {
            'market_state': market_state,
            'position_pct': position_pct,
            'market_score': market_score,
            'signals': signals,
            'short_term_ret': short_term_ret,
            'medium_term_ret': medium_term_ret,
            'recent_vol': recent_vol,
            'date': latest['trade_date'].strftime('%Y-%m-%d') if hasattr(latest['trade_date'], 'strftime') else str(latest['trade_date'])
        }
    
    def get_position_adjustment(self, base_position: float = 0.95) -> float:
        """
        获取仓位调整系数
        
        Args:
            base_position: 基础仓位 (默认95%)
        
        Returns:
            调整后仓位 (0.0 ~ 1.0)
        """
        timing = self.calculate_market_score()
        return timing['position_pct'] * base_position
    
    def should_trade(self) -> bool:
        """判断是否允许交易"""
        timing = self.calculate_market_score()
        return timing['market_state'] != 'bear'


def main():
    """测试"""
    print("="*60)
    print("市场择时测试")
    print("="*60)
    
    timing = MarketTiming()
    result = timing.calculate_market_score()
    
    print(f"\n市场环境分析:")
    print(f"  日期: {result['date']}")
    print(f"  市场状态: {result['market_state']}")
    print(f"  市场评分: {result['market_score']:.2f}")
    print(f"  建议仓位: {result['position_pct']*100:.0f}%")
    
    print(f"\n细分信号:")
    for signal, value in result['signals'].items():
        desc = {1: '看多', -1: '看空', 0: '中性'}.get(value, '未知')
        print(f"  {signal}: {desc} ({value})")
    
    print(f"\n市场数据:")
    print(f"  20日收益: {result['short_term_ret']*100:.2f}%")
    print(f"  60日收益: {result['medium_term_ret']*100:.2f}%")
    print(f"  近期波动: {result['recent_vol']*100:.2f}%")


if __name__ == '__main__':
    main()
