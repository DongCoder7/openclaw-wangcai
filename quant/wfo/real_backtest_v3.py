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
        query = '''
            SELECT DISTINCT trade_date 
            FROM daily_price 
            WHERE trade_date BETWEEN ? AND ?
            ORDER BY trade_date
        '''
        df = pd.read_sql(query, self.conn, params=[start_date, end_date])
        return df['trade_date'].tolist()
    
    def get_rebalance_dates(self, start_date: str, end_date: str, rebalance_days: int = 10) -> List[str]:
        all_dates = self.get_trading_dates(start_date, end_date)
        if not all_dates:
            return []
        return [all_dates[i] for i in range(0, len(all_dates), rebalance_days)]
    
    def get_price(self, ts_code: str, trade_date: str) -> Optional[float]:
        query = 'SELECT close FROM daily_price WHERE ts_code = ? AND trade_date = ?'
        df = pd.read_sql(query, self.conn, params=[ts_code, trade_date])
        return float(df['close'].iloc[0]) if not df.empty else None
    
    def select_stocks(self, trade_date: str, max_holding: int = 5) -> List[StockScore]:
        """直接从SQL查询选股"""
        query = f'''
            SELECT 
                dp.ts_code,
                dp.close,
                COALESCE(sf.ret_20, 0) as ret_20,
                COALESCE(sf.vol_20, 0.5) as vol_20,
                COALESCE(sdf.sharpe_like, 0) as sharpe_like,
                COALESCE(sf.price_pos_20, 0.5) as price_pos_20,
                COALESCE(f.roe, 0) as roe,
                COALESCE(f.pe_ttm, 20) as pe_ttm
            FROM daily_price dp
            LEFT JOIN stock_factors sf ON dp.ts_code = sf.ts_code AND dp.trade_date = sf.trade_date
            LEFT JOIN stock_defensive_factors sdf ON dp.ts_code = sdf.ts_code AND dp.trade_date = sdf.trade_date
            LEFT JOIN (
                SELECT ts_code, pe_ttm, roe,
                       ROW_NUMBER() OVER (PARTITION BY ts_code ORDER BY report_date DESC) as rn
                FROM stock_fina
                WHERE report_date <= ?
            ) f ON dp.ts_code = f.ts_code AND f.rn = 1
            WHERE dp.trade_date = ?
            AND dp.close >= 10
            AND dp.volume > 0
            ORDER BY (sf.ret_20 * 50 - sf.vol_20 * 10 + sdf.sharpe_like * 15 - ABS(sf.price_pos_20 - 0.5) * 20) DESC
            LIMIT ?
        '''
        
        df = pd.read_sql(query, self.conn, params=[trade_date, trade_date, max_holding * 3])
        
        scores = []
        for _, row in df.iterrows():
            # 简单评分公式
            score = (row['ret_20'] * 50 - row['vol_20'] * 10 + 
                    row['sharpe_like'] * 15 - abs(row['price_pos_20'] - 0.5) * 20)
            
            if row['roe'] > 5 and row['pe_ttm'] > 0 and row['pe_ttm'] < 50:
                score += 10  # 优质财务加分
            
            scores.append(StockScore(
                ts_code=row['ts_code'],
                score=score,
                factors={'ret_20': row['ret_20'], 'vol_20': row['vol_20']}
            ))
        
        return scores[:max_holding]
    
    def run_backtest(self, start_date: str, end_date: str,
                    position_pct: float = 0.7,
                    stop_loss: float = 0.08,
                    max_holding: int = 5,
                    rebalance_days: int = 10,
                    initial_capital: float = 1000000) -> Dict:
        
        print(f"   区间: {start_date} ~ {end_date}")
        
        rebalance_dates = self.get_rebalance_dates(start_date, end_date, rebalance_days)
        print(f"   调仓: {len(rebalance_dates)}次")
        
        if len(rebalance_dates) < 2:
            return self._empty_result()
        
        capital = initial_capital
        positions = {}
        equity_curve = []
        
        for i, rebalance_date in enumerate(rebalance_dates):
            # 止损
            if positions:
                for ts_code in list(positions.keys()):
                    price = self.get_price(ts_code, rebalance_date)
                    if price:
                        pos = positions[ts_code]
                        loss_pct = (price - pos['cost']) / pos['cost']
                        if loss_pct < -stop_loss:
                            capital += pos['shares'] * price
                            del positions[ts_code]
            
            # 选股
            selected = self.select_stocks(rebalance_date, max_holding)
            
            # 清仓旧持仓
            for ts_code in list(positions.keys()):
                price = self.get_price(ts_code, rebalance_date)
                if price:
                    capital += positions[ts_code]['shares'] * price
            positions = {}
            
            # 建新仓
            if selected and capital > 0:
                position_value = capital * position_pct / len(selected)
                for stock in selected:
                    price = self.get_price(stock.ts_code, rebalance_date)
                    if price and price > 0:
                        shares = int(position_value / price / 100) * 100
                        if shares > 0:
                            cost = shares * price
                            capital -= cost
                            positions[stock.ts_code] = {'shares': shares, 'cost': price}
            
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
            
            if (i + 1) % 3 == 0 or i == len(rebalance_dates) - 1:
                ret = (total_value - initial_capital) / initial_capital * 100
                print(f"   [{i+1}/{len(rebalance_dates)}] {rebalance_date}: "
                      f"¥{total_value:,.0f} ({ret:+.1f}%) 持仓{len(positions)}")
        
        return self._calculate_stats(equity_curve, initial_capital)
    
    def _calculate_stats(self, equity_curve: List[Dict], initial_capital: float) -> Dict:
        if not equity_curve:
            return self._empty_result()
        
        values = [e['equity'] for e in equity_curve]
        final = values[-1]
        total_ret = (final - initial_capital) / initial_capital
        
        # 最大回撤
        max_dd = 0
        peak = values[0]
        for v in values:
            if v > peak: peak = v
            dd = (v - peak) / peak
            if dd < max_dd: max_dd = dd
        
        # 日收益
        daily_ret = []
        for i in range(1, len(values)):
            daily_ret.append((values[i] - values[i-1]) / values[i-1])
        
        years = len(equity_curve) / 252
        annual_ret = (1 + total_ret) ** (1/years) - 1 if years > 0 else 0
        
        # 夏普
        if daily_ret:
            sharpe = (np.mean(daily_ret) * 252 - 0.03) / (np.std(daily_ret) * np.sqrt(252)) if np.std(daily_ret) > 0 else 0
        else:
            sharpe = 0
        
        calmar = annual_ret / abs(max_dd) if max_dd != 0 else 0
        
        return {
            'annual_return': annual_ret,
            'max_drawdown': max_dd,
            'sharpe_ratio': sharpe,
            'calmar_ratio': calmar,
            'win_rate': 0,
            'total_trades': len([e for e in equity_curve if e['holdings'] > 0]),
            'profit_factor': 0,
            'volatility': np.std(daily_ret) * np.sqrt(252) if daily_ret else 0,
            'equity_curve': equity_curve,
            'trades': []
        }
    
    def _empty_result(self) -> Dict:
        return {
            'annual_return': 0, 'max_drawdown': 0, 'sharpe_ratio': 0,
            'calmar_ratio': 0, 'win_rate': 0, 'total_trades': 0,
            'profit_factor': 0, 'volatility': 0, 'equity_curve': [], 'trades': []
        }


if __name__ == '__main__':
    print("="*60)
    print("🧪 真实数据库WFO回测")
    print("="*60)
    
    engine = RealBacktestEngine()
    
    # 测试2024年
    print("\n📈 2024全年回测:")
    result = engine.run_backtest(
        start_date='20240101',
        end_date='20241231',
        position_pct=0.7,
        stop_loss=0.08,
        max_holding=5,
        rebalance_days=10
    )
    
    print(f"\n📊 结果:")
    print(f"   年化: {result['annual_return']*100:+.2f}%")
    print(f"   回撤: {result['max_drawdown']*100:.2f}%")
    print(f"   夏普: {result['sharpe_ratio']:.2f}")
