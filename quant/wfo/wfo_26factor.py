#!/usr/bin/env python3
"""
WFO完整26因子回测系统
整合: 技术因子 + 防御因子 + 财务因子 + 择时信号
"""
import os
import sys
import sqlite3
import pandas as pd
import numpy as np
from datetime import datetime
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass

sys.path.insert(0, '/root/.openclaw/workspace/quant/wfo')

DB_PATH = '/root/.openclaw/workspace/data/historical/historical.db'
WFO_DIR = '/root/.openclaw/workspace/quant/wfo'


@dataclass
class FactorWeights:
    """26因子权重配置"""
    # 技术因子 (10个)
    ret_20: float = 1.0
    ret_60: float = 0.8
    ret_120: float = 0.5
    vol_20: float = -0.8  # 负权重: 波动率越低越好
    price_pos_20: float = 0.6
    price_pos_60: float = 0.4
    price_pos_high: float = 0.5
    rel_strength: float = 0.7
    mom_accel: float = 0.6
    profit_mom: float = 0.5

    # 防御因子 (5个)
    sharpe_like: float = 1.5  # 最重要
    low_vol_score: float = 1.2
    max_drawdown_120: float = -1.0  # 回撤越小越好
    downside_vol: float = -0.8
    vol_120: float = -0.6

    # 财务因子 (6个)
    roe: float = 1.0
    netprofit_growth: float = 0.8
    revenue_growth: float = 0.6
    pe_ttm: float = -0.5  # PE越低越好
    pb: float = -0.4
    debt_ratio: float = -0.3  # 负债率越低越好

    # 择时因子 (5个)
    market_trend: float = 1.0  # 市场趋势
    sector_rotation: float = 0.8  # 板块轮动
    volume_trend: float = 0.6  # 量能趋势
    volatility_regime: float = -0.7  # 波动率环境
    sentiment: float = 0.5  # 情绪指标


@dataclass
class StrategyParams:
    """策略参数"""
    position_pct: float = 0.7
    stop_loss: float = 0.08
    max_holding: int = 5
    rebalance_days: int = 10
    factor_weights: FactorWeights = None

    def __post_init__(self):
        if self.factor_weights is None:
            self.factor_weights = FactorWeights()

    def to_dict(self) -> Dict:
        """转为字典用于优化"""
        base = {
            'position_pct': self.position_pct,
            'stop_loss': self.stop_loss,
            'max_holding': self.max_holding,
            'rebalance_days': self.rebalance_days
        }
        # 添加所有因子权重
        for attr in dir(self.factor_weights):
            if not attr.startswith('_'):
                base[f'fw_{attr}'] = getattr(self.factor_weights, attr)
        return base


class FullFactorEngine:
    """完整26因子回测引擎"""

    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row

        # 因子列表
        self.tech_factors = [
            'ret_20', 'ret_60', 'ret_120', 'vol_20', 'price_pos_20',
            'price_pos_60', 'price_pos_high', 'rel_strength', 'mom_accel', 'profit_mom'
        ]
        self.def_factors = [
            'sharpe_like', 'low_vol_score', 'max_drawdown_120', 'downside_vol', 'vol_120'
        ]
        self.fina_factors = [
            'roe', 'netprofit_growth', 'revenue_growth', 'pe_ttm', 'pb', 'debt_ratio'
        ]

    def __del__(self):
        if hasattr(self, 'conn'):
            self.conn.close()

    def get_all_factors(self, ts_code: str, trade_date: str) -> Dict[str, float]:
        """获取股票完整26因子数据"""
        factors = {}

        # 1. 技术因子
        tech_cols = ', '.join(self.tech_factors)
        row = self.conn.execute(f'''
            SELECT {tech_cols} FROM stock_factors
            WHERE ts_code = ? AND trade_date = ?
        ''', [ts_code, trade_date]).fetchone()

        if row:
            for i, col in enumerate(self.tech_factors):
                if row[i] is not None:
                    factors[col] = float(row[i])

        # 2. 防御因子
        def_cols = ', '.join(self.def_factors)
        row = self.conn.execute(f'''
            SELECT {def_cols} FROM stock_defensive_factors
            WHERE ts_code = ? AND trade_date = ?
        ''', [ts_code, trade_date]).fetchone()

        if row:
            for i, col in enumerate(self.def_factors):
                if row[i] is not None:
                    factors[col] = float(row[i])

        # 3. 财务因子 (使用最新报告期)
        fina_cols = ', '.join(self.fina_factors)
        row = self.conn.execute(f'''
            SELECT {fina_cols} FROM stock_fina
            WHERE ts_code = ? AND report_date <= ?
            ORDER BY report_date DESC LIMIT 1
        ''', [ts_code, trade_date]).fetchone()

        if row:
            for i, col in enumerate(self.fina_factors):
                if row[i] is not None:
                    factors[col] = float(row[i])

        return factors

    def calculate_26factor_score(self, factors: Dict[str, float],
                                  weights: FactorWeights,
                                  timing_factors: Dict[str, float] = None) -> float:
        """计算26因子综合评分"""
        if len(factors) < 10:  # 至少需要10个有效因子
            return -999

        score = 0
        total_weight = 0

        # 技术因子评分
        for factor in self.tech_factors:
            if factor in factors:
                weight = getattr(weights, factor, 0)
                value = factors[factor]
                # 标准化处理
                if factor.startswith('ret_'):
                    normalized = value * 100  # 收益率转为百分比
                elif factor.startswith('vol_'):
                    normalized = -value * 50  # 波动率反转
                elif factor.startswith('price_pos_'):
                    normalized = -(abs(value - 0.5) * 100)  # 偏离0.5越远越差
                else:
                    normalized = value

                score += weight * normalized
                total_weight += abs(weight)

        # 防御因子评分
        for factor in self.def_factors:
            if factor in factors:
                weight = getattr(weights, factor, 0)
                value = factors[factor]

                if factor == 'sharpe_like':
                    normalized = value * 20  # 夏普比率放大
                elif factor == 'max_drawdown_120':
                    normalized = value * 100  # 回撤转为正分（越小越好）
                elif 'vol' in factor or 'downside' in factor:
                    normalized = -value * 50  # 波动率反转
                else:
                    normalized = value * 10

                score += weight * normalized
                total_weight += abs(weight)

        # 财务因子评分
        for factor in self.fina_factors:
            if factor in factors:
                weight = getattr(weights, factor, 0)
                value = factors[factor]

                if factor == 'roe':
                    normalized = value * 5  # ROE放大
                elif 'growth' in factor:
                    normalized = value * 3  # 增长率
                elif factor in ['pe_ttm', 'pb']:
                    normalized = -value * 2 if value > 0 else 0  # 估值反转
                elif factor == 'debt_ratio':
                    normalized = -value * 2  # 负债率反转
                else:
                    normalized = value

                score += weight * normalized
                total_weight += abs(weight)

        # 择时因子
        if timing_factors:
            for factor, value in timing_factors.items():
                weight = getattr(weights, factor, 0)
                score += weight * value
                total_weight += abs(weight)

        return score / total_weight if total_weight > 0 else -999

    def _calculate_timing_factors(self, trade_date: str) -> Dict[str, float]:
        """计算择时因子"""
        timing = {}

        # 市场趋势: 用沪深300的20日收益
        market_ret = self.conn.execute('''
            SELECT AVG(ret_20) FROM stock_factors
            WHERE trade_date = ? AND ts_code IN ('000300.SH', '000001.SH')
        ''', [trade_date]).fetchone()[0]

        timing['market_trend'] = market_ret * 100 if market_ret else 0

        # 波动率环境
        market_vol = self.conn.execute('''
            SELECT AVG(vol_20) FROM stock_factors
            WHERE trade_date = ?
        ''', [trade_date]).fetchone()[0]

        timing['volatility_regime'] = -market_vol * 100 if market_vol else 0

        # 量能趋势
        vol_trend = self.conn.execute('''
            SELECT AVG(vol_ratio) FROM stock_factors
            WHERE trade_date = ?
        ''', [trade_date]).fetchone()[0]

        timing['volume_trend'] = (vol_trend - 1) * 100 if vol_trend else 0

        # 情绪和板块轮动简化计算
        timing['sentiment'] = 0
        timing['sector_rotation'] = 0

        return timing

    def select_stocks_with_defense(self, trade_date: str, max_holding: int = 5,
                                    params: StrategyParams = None) -> List[Dict]:
        """选股: 进攻+防御平衡"""
        if params is None:
            params = StrategyParams()
        
        # 计算择时因子
        timing_factors = self._calculate_timing_factors(trade_date)
        
        # 获取所有有因子数据的股票
        stocks = []
        
        # 先获取技术因子有数据的股票
        tech_stocks = self.conn.execute('''
            SELECT DISTINCT ts_code FROM stock_factors 
            WHERE trade_date = ? AND ret_20 IS NOT NULL
            LIMIT 300
        ''', [trade_date]).fetchall()
        
        for (ts_code,) in tech_stocks:
            # 获取价格
            price_row = self.conn.execute('''
                SELECT close FROM daily_price 
                WHERE ts_code = ? AND trade_date = ?
            ''', [ts_code, trade_date]).fetchone()
            
            if not price_row or price_row[0] < 10:
                continue
            
            # 获取完整因子
            factors = self.get_all_factors(ts_code, trade_date)
            
            if len(factors) >= 8:  # 至少8个有效因子
                score = self.calculate_26factor_score(factors, params.factor_weights, timing_factors)
                
                # 防御筛选: 最大回撤和夏普必须达标
                defense_ok = True
                if 'max_drawdown_120' in factors and factors['max_drawdown_120'] < -0.30:
                    defense_ok = False
                if 'sharpe_like' in factors and factors['sharpe_like'] < 0:
                    defense_ok = False
                
                if defense_ok and score > -50:
                    stocks.append({
                        'ts_code': ts_code,
                        'price': price_row[0],
                        'score': score,
                        'factors': factors
                    })
        
        # 按评分排序
        stocks.sort(key=lambda x: x['score'], reverse=True)
        return stocks[:max_holding]

    def run_wfo_backtest(self, train_start: str, train_end: str,
                         test_start: str, test_end: str,
                         params: StrategyParams = None) -> Dict:
        """运行单个WFO周期回测"""
        if params is None:
            params = StrategyParams()

        print(f"\n{'='*60}")
        print(f"WFO周期: 训练[{train_start}-{train_end}] -> 测试[{test_start}-{test_end}]")
        print(f"{'='*60}")

        # 获取交易日
        dates = [r[0] for r in self.conn.execute('''
            SELECT trade_date FROM daily_price
            WHERE trade_date BETWEEN ? AND ?
            GROUP BY trade_date ORDER BY trade_date
        ''', [test_start, test_end]).fetchall()]

        rebalance_dates = dates[::params.rebalance_days]
        print(f"测试期调仓: {len(rebalance_dates)}次")

        # 回测
        capital = 1000000
        positions = {}  # {ts_code: shares_value}
        equity_curve = []

        for i, rd in enumerate(rebalance_dates):
            # 1. 止损检查
            for ts_code in list(positions.keys()):
                price_row = self.conn.execute('''
                    SELECT close FROM daily_price
                    WHERE ts_code = ? AND trade_date = ?
                ''', [ts_code, rd]).fetchone()

                if price_row:
                    current_price = price_row[0]
                    buy_price = positions[ts_code]['price']
                    loss_pct = (current_price - buy_price) / buy_price

                    if loss_pct < -params.stop_loss:
                        capital += positions[ts_code]['shares'] * current_price
                        del positions[ts_code]

            # 2. 清仓旧持仓
            for ts_code in list(positions.keys()):
                price_row = self.conn.execute('''
                    SELECT close FROM daily_price
                    WHERE ts_code = ? AND trade_date = ?
                ''', [ts_code, rd]).fetchone()

                if price_row:
                    capital += positions[ts_code]['shares'] * price_row[0]

            positions = {}

            # 3. 选股建仓
            selected = self.select_stocks_with_defense(rd, params.max_holding, params)

            if selected and capital > 0:
                position_value = capital * params.position_pct / len(selected)

                for stock in selected:
                    price = stock['price']
                    if price > 0:
                        shares = int(position_value / price / 100) * 100
                        if shares > 0:
                            cost = shares * price
                            capital -= cost
                            positions[stock['ts_code']] = {
                                'shares': shares,
                                'price': price,
                                'score': stock['score']
                            }

            # 4. 计算净值
            total_value = capital
            for ts_code, pos in positions.items():
                price_row = self.conn.execute('''
                    SELECT close FROM daily_price
                    WHERE ts_code = ? AND trade_date = ?
                ''', [ts_code, rd]).fetchone()

                if price_row:
                    total_value += pos['shares'] * price_row[0]

            equity_curve.append({
                'date': rd,
                'equity': total_value,
                'holdings': len(positions)
            })

            if (i + 1) % 3 == 0 or i == len(rebalance_dates) - 1:
                ret_pct = (total_value - 1000000) / 1000000 * 100
                print(f"   [{i+1}/{len(rebalance_dates)}] {rd}: "
                      f"¥{total_value:,.0f} ({ret_pct:+.1f}%) 持仓{len(positions)}")

        # 计算统计
        return self._calculate_stats(equity_curve)

    def _calculate_stats(self, equity_curve: List[Dict]) -> Dict:
        """计算回测统计"""
        if not equity_curve:
            return {'annual_return': 0, 'max_drawdown': 0, 'sharpe_ratio': 0}

        values = [e['equity'] for e in equity_curve]
        final = values[-1]
        total_ret = (final - 1000000) / 1000000

        # 最大回撤
        max_dd = 0
        peak = values[0]
        for v in values:
            if v > peak:
                peak = v
            dd = (v - peak) / peak
            if dd < max_dd:
                max_dd = dd

        # 年化收益
        days = len(equity_curve)
        years = days / 252
        annual_ret = (1 + total_ret) ** (1/years) - 1 if years > 0 else 0

        # 夏普
        daily_ret = []
        for i in range(1, len(values)):
            daily_ret.append((values[i] - values[i-1]) / values[i-1])

        if daily_ret:
            sharpe = (np.mean(daily_ret) * 252 - 0.03) / (np.std(daily_ret) * np.sqrt(252)) if np.std(daily_ret) > 0 else 0
        else:
            sharpe = 0

        return {
            'annual_return': annual_ret,
            'max_drawdown': max_dd,
            'sharpe_ratio': sharpe,
            'total_return': total_ret,
            'equity_curve': equity_curve
        }


if __name__ == '__main__':
    print("="*70)
    print("🚀 完整26因子WFO回测系统")
    print("="*70)

    engine = FullFactorEngine()

    # 测试单个周期
    params = StrategyParams(
        position_pct=0.7,
        stop_loss=0.08,
        max_holding=5,
        rebalance_days=10
    )

    result = engine.run_wfo_backtest(
        train_start='20240101',
        train_end='20251231',
        test_start='20251201',
        test_end='20260213',
        params=params
    )

    print(f"\n📊 回测结果:")
    print(f"   年化收益: {result['annual_return']*100:+.2f}%")
    print(f"   最大回撤: {result['max_drawdown']*100:.2f}%")
    print(f"   夏普比率: {result['sharpe_ratio']:.2f}")
    print(f"   总收益: {result['total_return']*100:+.2f}%")

    print("\n✅ 26因子WFO回测完成")
