#!/usr/bin/env python3
"""
WFO真实数据库回测引擎 - 使用真实数据
"""
import os
import sys
import sqlite3
import pandas as pd
import numpy as np
from datetime import datetime
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass

DB_PATH = '/root/.openclaw/workspace/data/historical/historical.db'


@dataclass
class StockScore:
    """股票评分结果"""
    ts_code: str
    score: float
    factors: Dict[str, float]


class RealBacktestEngine:
    """真实数据库回测引擎"""
    
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        
    def __del__(self):
        if hasattr(self, 'conn'):
            self.conn.close()
    
    def get_trading_dates(self, start_date: str, end_date: str) -> List[str]:
        """获取交易日列表"""
        query = '''
            SELECT DISTINCT trade_date 
            FROM daily_price 
            WHERE trade_date BETWEEN ? AND ?
            ORDER BY trade_date
        '''
        df = pd.read_sql(query, self.conn, params=[start_date, end_date])
        return df['trade_date'].tolist()
    
    def get_rebalance_dates(self, start_date: str, end_date: str, 
                           rebalance_days: int = 10) -> List[str]:
        """获取调仓日期列表"""
        all_dates = self.get_trading_dates(start_date, end_date)
        if not all_dates:
            return []
        
        # 每隔rebalance_days天调仓一次
        rebalance_dates = []
        for i in range(0, len(all_dates), rebalance_days):
            rebalance_dates.append(all_dates[i])
        
        return rebalance_dates
    
    def get_stock_list(self, trade_date: str, min_price: float = 5.0) -> List[str]:
        """获取某交易日的股票列表"""
        query = f'''
            SELECT DISTINCT dp.ts_code
            FROM daily_price dp
            JOIN stock_basic sb ON dp.ts_code = sb.ts_code
            WHERE dp.trade_date = ?
            AND dp.close >= ?
            AND dp.volume > 0
            AND sb.股票名称 NOT LIKE '%ST%'
            AND sb.股票名称 NOT LIKE '%退%'
        '''
        df = pd.read_sql(query, self.conn, params=[trade_date, min_price])
        return df['ts_code'].tolist()
    
    def get_factor_data(self, ts_code: str, trade_date: str) -> Dict[str, float]:
        """获取股票在某日的因子数据"""
        factors = {}
        
        # 技术因子 + 防御因子 + 财务因子
        query = f'''
            SELECT 
                sf.ret_5, sf.ret_10, sf.ret_20, sf.ret_60, sf.ret_120,
                sf.vol_20, sf.vol_ratio, 
                sf.price_pos_20, sf.price_pos_60, sf.price_pos_high,
                sf.ma_20, sf.ma_60, sf.rel_strength, sf.mom_accel,
                sdf.vol_120, sdf.max_drawdown_120, sdf.sharpe_like, 
                sdf.downside_vol, sdf.low_vol_score,
                f.pe_ttm, f.pb, f.roe, f.revenue_growth, f.netprofit_growth
            FROM daily_price dp
            LEFT JOIN stock_factors sf ON dp.ts_code = sf.ts_code AND dp.trade_date = sf.trade_date
            LEFT JOIN stock_defensive_factors sdf ON dp.ts_code = sdf.ts_code AND dp.trade_date = sdf.trade_date
            LEFT JOIN (
                SELECT ts_code, pe_ttm, pb, roe, revenue_growth, netprofit_growth,
                       ROW_NUMBER() OVER (PARTITION BY ts_code ORDER BY report_date DESC) as rn
                FROM stock_fina
                WHERE report_date <= ?
            ) f ON dp.ts_code = f.ts_code AND f.rn = 1
            WHERE dp.ts_code = ? AND dp.trade_date = ?
        '''
        
        try:
            df = pd.read_sql(query, self.conn, params=[trade_date, ts_code, trade_date])
            if not df.empty:
                row = df.iloc[0]
                for col in df.columns:
                    val = row[col]
                    if pd.notna(val):
                        factors[col] = float(val)
        except Exception as e:
            pass
        
        return factors
    
    def calculate_score(self, factors: Dict[str, float]) -> float:
        """计算综合评分"""
        if not factors:
            return -999
        
        # 处理缺失值
        valid_factors = {k: v for k, v in factors.items() 
                        if v is not None and not np.isnan(v)}
        
        if len(valid_factors) < 3:
            return -999
        
        score = 0
        weights = 0
        
        for factor, value in valid_factors.items():
            # 动量因子：收益率越高越好
            if factor.startswith('ret_'):
                weight = 1.0
                contrib = value * 50
            # 波动率因子：越低越好
            elif factor.startswith('vol_') and factor != 'vol_ratio':
                weight = 0.8
                contrib = -abs(value) * 10
            # 价格位置因子
            elif factor.startswith('price_pos_'):
                weight = 0.5
                contrib = -abs(value - 0.5) * 20
            # 夏普类因子
            elif factor == 'sharpe_like' or factor == 'low_vol_score':
                weight = 1.5
                contrib = value * 15
            # 财务因子
            elif factor == 'roe':
                weight = 1.2
                contrib = value * 5
            elif factor == 'pe_ttm':
                weight = 0.8
                if value > 0:
                    contrib = max(0, 30 - value) * 2
                else:
                    contrib = 0
            elif factor == 'pb':
                weight = 0.6
                if value > 0:
                    contrib = max(0, 8 - value) * 5
                else:
                    contrib = 0
            elif factor in ['revenue_growth', 'netprofit_growth']:
                weight = 1.0
                contrib = value * 3
            else:
                weight = 0.3
                contrib = value
            
            score += weight * contrib
            weights += weight
        
        return score / weights if weights > 0 else -999
    
    def select_stocks(self, trade_date: str, max_holding: int = 5) -> List[StockScore]:
        """选股"""
        stock_list = self.get_stock_list(trade_date)
        
        scores = []
        for ts_code in stock_list[:500]:  # 限制数量加速
            factors = self.get_factor_data(ts_code, trade_date)
            score = self.calculate_score(factors)
            
            if score > -50:
                scores.append(StockScore(
                    ts_code=ts_code,
                    score=score,
                    factors=factors
                ))
        
        scores.sort(key=lambda x: x.score, reverse=True)
        return scores[:max_holding]
    
    def get_price(self, ts_code: str, trade_date: str) -> Optional[float]:
        """获取收盘价"""
        query = 'SELECT close FROM daily_price WHERE ts_code = ? AND trade_date = ?'
        df = pd.read_sql(query, self.conn, params=[ts_code, trade_date])
        return float(df['close'].iloc[0]) if not df.empty else None
    
    def run_backtest(self, start_date: str, end_date: str,
                    position_pct: float = 0.7,
                    stop_loss: float = 0.08,
                    max_holding: int = 5,
                    rebalance_days: int = 10,
                    initial_capital: float = 1000000) -> Dict:
        """执行真实回测"""
        print(f"   回测区间: {start_date} ~ {end_date}")
        
        rebalance_dates = self.get_rebalance_dates(start_date, end_date, rebalance_days)
        print(f"   调仓次数: {len(rebalance_dates)}次")
        
        if len(rebalance_dates) < 2:
            return self._empty_result()
        
        capital = initial_capital
        positions = {}
        equity_curve = []
        
        for i, rebalance_date in enumerate(rebalance_dates):
            # 止损检查
            if positions:
                for ts_code, pos in list(positions.items()):
                    current_price = self.get_price(ts_code, rebalance_date)
                    if current_price:
                        loss_pct = (current_price - pos['cost']) / pos['cost']
                        if loss_pct < -stop_loss:
                            capital += pos['shares'] * current_price
                            del positions[ts_code]
            
            # 选股
            selected = self.select_stocks(rebalance_date, max_holding=max_holding)
            
            # 清仓
            for ts_code, pos in positions.items():
                sell_price = self.get_price(ts_code, rebalance_date)
                if sell_price:
                    capital += pos['shares'] * sell_price
            
            positions = {}
            
            # 建仓
            if selected and capital > 0:
                position_value = capital * position_pct / len(selected)
                for stock in selected:
                    buy_price = self.get_price(stock.ts_code, rebalance_date)
                    if buy_price and buy_price > 0:
                        shares = int(position_value / buy_price / 100) * 100
                        if shares > 0:
                            cost = shares * buy_price
                            capital -= cost
                            positions[stock.ts_code] = {
                                'shares': shares,
                                'cost': buy_price
                            }
            
            # 计算净值
            total_value = capital
            for ts_code, pos in positions.items():
                price = self.get_price(ts_code, rebalance_date)
                if price:
                    total_value += pos['shares'] * price
            
            equity_curve.append({
                'date': rebalance_date,
                'equity': total_value,
                'holdings': len(positions)
            })
            
            if (i + 1) % 5 == 0:
                ret_pct = (total_value - initial_capital) / initial_capital * 100
                print(f"   [{i+1}/{len(rebalance_dates)}] {rebalance_date}: "
                      f"净值¥{total_value:,.0f} ({ret_pct:+.1f}%)")
        
        return self._calculate_stats(equity_curve, initial_capital)
    
    def _calculate_stats(self, equity_curve: List[Dict], initial_capital: float) -> Dict:
        """计算统计指标"""
        if not equity_curve:
            return self._empty_result()
        
        equity_values = [e['equity'] for e in equity_curve]
        final_equity = equity_values[-1]
        total_return = (final_equity - initial_capital) / initial_capital
        
        # 最大回撤
        max_drawdown = 0
        peak = equity_values[0]
        for eq in equity_values:
            if eq > peak:
                peak = eq
            dd = (eq - peak) / peak
            if dd < max_drawdown:
                max_drawdown = dd
        
        # 日收益率
        daily_returns = []
        for i in range(1, len(equity_values)):
            dr = (equity_values[i] - equity_values[i-1]) / equity_values[i-1]
            daily_returns.append(dr)
        
        # 年化收益
        days = len(equity_curve)
        years = days / 252 if days > 0 else 1
        annual_return = (1 + total_return) ** (1/years) - 1 if years > 0 else 0
        
        # 夏普比率
        if daily_returns:
            avg_ret = np.mean(daily_returns)
            std_ret = np.std(daily_returns)
            sharpe = (avg_ret * 252 - 0.03) / (std_ret * np.sqrt(252)) if std_ret > 0 else 0
        else:
            sharpe = 0
        
        # 卡玛比率
        calmar = annual_return / abs(max_drawdown) if max_drawdown != 0 else 0
        
        return {
            'annual_return': annual_return,
            'max_drawdown': max_drawdown,
            'sharpe_ratio': sharpe,
            'calmar_ratio': calmar,
            'win_rate': 0,
            'total_trades': len([e for e in equity_curve if e['holdings'] > 0]),
            'profit_factor': 0,
            'volatility': np.std(daily_returns) * np.sqrt(252) if daily_returns else 0,
            'equity_curve': equity_curve,
            'trades': []
        }
    
    def _empty_result(self) -> Dict:
        return {
            'annual_return': 0, 'max_drawdown': 0, 'sharpe_ratio': 0,
            'calmar_ratio': 0, 'win_rate': 0, 'total_trades': 0,
            'profit_factor': 0, 'volatility': 0, 'equity_curve': [], 'trades': []
        }


def test_real_backtest():
    """测试真实回测"""
    print("="*70)
    print("🧪 真实数据库回测测试")
    print("="*70)
    
    engine = RealBacktestEngine()
    
    # 测试最近3个月
    print("\n📈 回测 2025Q4:")
    result = engine.run_backtest(
        start_date='20251001',
        end_date='20251231',
        position_pct=0.7,
        stop_loss=0.08,
        max_holding=5,
        rebalance_days=10
    )
    
    print(f"\n📊 回测结果:")
    print(f"   年化收益: {result['annual_return']*100:+.2f}%")
    print(f"   最大回撤: {result['max_drawdown']*100:.2f}%")
    print(f"   夏普比率: {result['sharpe_ratio']:.2f}")
    print(f"   卡玛比率: {result['calmar_ratio']:.2f}")


if __name__ == '__main__':
    test_real_backtest()
