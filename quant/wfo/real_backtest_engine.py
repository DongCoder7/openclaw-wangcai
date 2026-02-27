#!/usr/bin/env python3
"""
WFO真实数据库回测引擎
基于historical.db执行真实回测
"""
import os
import sys
import sqlite3
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass

sys.path.insert(0, '/root/.openclaw/workspace/quant/wfo')

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
        """获取某交易日的股票列表（过滤ST、低价股）"""
        query = '''
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
    
    def get_factor_data(self, ts_code: str, trade_date: str, 
                       selected_factors: List[str]) -> Dict[str, float]:
        """获取股票在某日的因子数据"""
        factors = {}
        
        # 1. 技术因子
        tech_factors = [f for f in selected_factors 
                       if f in ['ret_20', 'ret_60', 'ret_120', 'vol_20', 'vol_ratio',
                               'price_pos_20', 'price_pos_60', 'price_pos_high',
                               'ma_20', 'ma_60', 'rel_strength', 'mom_accel']]
        if tech_factors:
            cols = ', '.join(tech_factors)
            query = f'''
                SELECT {cols}
                FROM stock_factors
                WHERE ts_code = ? AND trade_date = ?
            '''
            df = pd.read_sql(query, self.conn, params=[ts_code, trade_date])
            if not df.empty:
                for col in tech_factors:
                    factors[col] = df[col].iloc[0]
        
        # 2. 防御因子
        def_factors = [f for f in selected_factors 
                      if f in ['vol_120', 'max_drawdown_120', 'sharpe_like', 
                              'downside_vol', 'low_vol_score']]
        if def_factors:
            cols = ', '.join(def_factors)
            query = f'''
                SELECT {cols}
                FROM stock_defensive_factors
                WHERE ts_code = ? AND trade_date = ?
            '''
            df = pd.read_sql(query, self.conn, params=[ts_code, trade_date])
            if not df.empty:
                for col in def_factors:
                    factors[col] = df[col].iloc[0]
        
        # 3. 财务因子
        fina_factors = [f for f in selected_factors 
                       if f in ['pe_ttm', 'pb', 'roe', 'revenue_growth', 
                               'netprofit_growth', 'debt_ratio', 'dividend_yield']]
        if fina_factors:
            cols = ', '.join(fina_factors)
            # 财务数据用最近的报告期
            query = f'''
                SELECT {cols}
                FROM stock_fina
                WHERE ts_code = ? AND report_date <= ?
                ORDER BY report_date DESC
                LIMIT 1
            '''
            df = pd.read_sql(query, self.conn, params=[ts_code, trade_date])
            if not df.empty:
                for col in fina_factors:
                    factors[col] = df[col].iloc[0]
        
        return factors
    
    def calculate_score(self, factors: Dict[str, float], 
                       method: str = 'equal') -> float:
        """计算综合评分"""
        if not factors:
            return -999
        
        # 处理缺失值
        valid_factors = {k: v for k, v in factors.items() 
                        if v is not None and not np.isnan(v)}
        
        if len(valid_factors) < 3:  # 至少需要3个有效因子
            return -999
        
        score = 0
        weights = 0
        
        # 根据因子类型计算贡献
        for factor, value in valid_factors.items():
            if factor.startswith('ret_'):  # 收益率因子，越高越好
                weight = 1.0
                contrib = value * 100 if value else 0  # 转为百分比
            elif factor.startswith('vol_'):  # 波动率因子，越低越好
                weight = 1.0
                contrib = -value * 100 if value else 0
            elif factor.startswith('price_pos_'):  # 价格位置，适中最好
                weight = 1.0
                contrib = -abs(value - 0.5) * 100 if value else 0
            elif factor == 'sharpe_like':  # 夏普类指标，越高越好
                weight = 1.5
                contrib = value * 10 if value else 0
            elif factor in ['roe', 'revenue_growth', 'netprofit_growth']:  # 增长类，越高越好
                weight = 1.2
                contrib = value * 10 if value else 0
            elif factor == 'pe_ttm':  # PE，越低越好（但>0）
                weight = 1.0
                if value and value > 0:
                    contrib = max(0, 30 - value)  # PE 30以上得分递减
                else:
                    contrib = 0
            elif factor == 'pb':  # PB，越低越好
                weight = 0.8
                if value and value > 0:
                    contrib = max(0, 5 - value) * 2
                else:
                    contrib = 0
            else:
                weight = 0.5
                contrib = value if value else 0
            
            score += weight * contrib
            weights += weight
        
        return score / weights if weights > 0 else -999
    
    def select_stocks(self, trade_date: str, 
                     selected_factors: List[str],
                     max_holding: int = 5,
                     min_score: float = -10) -> List[StockScore]:
        """选股：基于因子评分选择top N"""
        stock_list = self.get_stock_list(trade_date)
        
        scores = []
        for ts_code in stock_list:
            factors = self.get_factor_data(ts_code, trade_date, selected_factors)
            score = self.calculate_score(factors)
            
            if score > min_score:
                scores.append(StockScore(
                    ts_code=ts_code,
                    score=score,
                    factors=factors
                ))
        
        # 按评分排序
        scores.sort(key=lambda x: x.score, reverse=True)
        
        return scores[:max_holding]
    
    def get_price(self, ts_code: str, trade_date: str) -> Optional[float]:
        """获取某股票某日的收盘价"""
        query = '''
            SELECT close
            FROM daily_price
            WHERE ts_code = ? AND trade_date = ?
        '''
        df = pd.read_sql(query, self.conn, params=[ts_code, trade_date])
        return df['close'].iloc[0] if not df.empty else None
    
    def get_next_trading_date(self, trade_date: str) -> Optional[str]:
        """获取下一个交易日"""
        query = '''
            SELECT trade_date
            FROM daily_price
            WHERE trade_date > ?
            ORDER BY trade_date
            LIMIT 1
        '''
        df = pd.read_sql(query, self.conn, params=[trade_date])
        return df['trade_date'].iloc[0] if not df.empty else None
    
    def run_backtest(self, start_date: str, end_date: str,
                    position_pct: float = 0.7,
                    stop_loss: float = 0.08,
                    max_holding: int = 5,
                    rebalance_days: int = 10,
                    selected_factors: List[str] = None,
                    initial_capital: float = 1000000) -> Dict:
        """
        执行真实回测
        
        Returns:
            {
                'annual_return': float,
                'max_drawdown': float,
                'sharpe_ratio': float,
                'calmar_ratio': float,
                'win_rate': float,
                'total_trades': int,
                'equity_curve': List[Dict],
                'trades': List[Dict]
            }
        """
        if selected_factors is None:
            selected_factors = ['ret_20', 'vol_20', 'sharpe_like', 'roe', 'pe_ttm']
        
        print(f"   回测区间: {start_date} ~ {end_date}")
        print(f"   初始资金: ¥{initial_capital:,.0f}")
        print(f"   调仓周期: {rebalance_days}天")
        print(f"   最大持仓: {max_holding}只")
        print(f"   仓位比例: {position_pct*100:.0f}%")
        print(f"   止损线: {stop_loss*100:.0f}%")
        
        # 获取调仓日期
        rebalance_dates = self.get_rebalance_dates(start_date, end_date, rebalance_days)
        print(f"   调仓次数: {len(rebalance_dates)}次")
        
        if len(rebalance_dates) < 2:
            print("   ⚠️ 调仓日期不足，无法回测")
            return self._empty_result()
        
        # 初始化
        capital = initial_capital
        positions = {}  # {ts_code: {'shares': int, 'cost': float, 'buy_date': str}}
        equity_curve = []
        trades = []
        
        # 遍历每个调仓日
        for i, rebalance_date in enumerate(rebalance_dates):
            # 1. 检查止损
            if positions:
                for ts_code, pos in list(positions.items()):
                    current_price = self.get_price(ts_code, rebalance_date)
                    if current_price:
                        loss_pct = (current_price - pos['cost']) / pos['cost']
                        if loss_pct < -stop_loss:
                            # 止损卖出
                            sell_value = pos['shares'] * current_price
                            capital += sell_value
                            trades.append({
                                'date': rebalance_date,
                                'ts_code': ts_code,
                                'action': 'STOP_LOSS',
                                'shares': pos['shares'],
                                'price': current_price,
                                'pnl_pct': loss_pct * 100
                            })
                            del positions[ts_code]
            
            # 2. 选股
            selected = self.select_stocks(
                rebalance_date, 
                selected_factors,
                max_holding=max_holding
            )
            
            if not selected:
                print(f"   [{i+1}/{len(rebalance_dates)}] {rebalance_date}: 未选出股票")
                continue
            
            # 3. 清仓旧持仓
            for ts_code, pos in positions.items():
                sell_price = self.get_price(ts_code, rebalance_date)
                if sell_price:
                    sell_value = pos['shares'] * sell_price
                    capital += sell_value
                    pnl_pct = (sell_price - pos['cost']) / pos['cost'] * 100
                    trades.append({
                        'date': rebalance_date,
                        'ts_code': ts_code,
                        'action': 'SELL',
                        'shares': pos['shares'],
                        'price': sell_price,
                        'pnl_pct': pnl_pct
                    })
            
            positions = {}
            
            # 4. 建立新持仓
            position_value = capital * position_pct / len(selected)
            
            for stock in selected:
                buy_price = self.get_price(stock.ts_code, rebalance_date)
                if buy_price and buy_price > 0:
                    shares = int(position_value / buy_price / 100) * 100  # 100股整数倍
                    if shares > 0:
                        cost = shares * buy_price
                        capital -= cost
                        positions[stock.ts_code] = {
                            'shares': shares,
                            'cost': buy_price,
                            'buy_date': rebalance_date
                        }
                        trades.append({
                            'date': rebalance_date,
                            'ts_code': stock.ts_code,
                            'action': 'BUY',
                            'shares': shares,
                            'price': buy_price,
                            'score': stock.score
                        })
            
            # 5. 计算当日净值
            total_value = capital
            for ts_code, pos in positions.items():
                price = self.get_price(ts_code, rebalance_date)
                if price:
                    total_value += pos['shares'] * price
            
            equity_curve.append({
                'date': rebalance_date,
                'equity': total_value,
                'cash': capital,
                'holdings': len(positions)
            })
            
            if (i + 1) % 10 == 0 or i == len(rebalance_dates) - 1:
                ret_pct = (total_value - initial_capital) / initial_capital * 100
                print(f"   [{i+1}/{len(rebalance_dates)}] {rebalance_date}: "
                      f"净值¥{total_value:,.0f} ({ret_pct:+.1f}%) 持仓{len(positions)}只")
        
        # 计算回测统计
        return self._calculate_stats(equity_curve, trades, initial_capital)
    
    def _calculate_stats(self, equity_curve: List[Dict], 
                        trades: List[Dict],
                        initial_capital: float) -> Dict:
        """计算回测统计指标"""
        if not equity_curve:
            return self._empty_result()
        
        # 权益序列
        equity_values = [e['equity'] for e in equity_curve]
        dates = [e['date'] for e in equity_curve]
        
        # 总收益
        final_equity = equity_values[-1]
        total_return = (final_equity - initial_capital) / initial_capital
        
        # 计算日收益率
        daily_returns = []
        for i in range(1, len(equity_values)):
            daily_ret = (equity_values[i] - equity_values[i-1]) / equity_values[i-1]
            daily_returns.append(daily_ret)
        
        # 年化收益
        days = len(equity_curve)
        years = days / 252 if days > 0 else 1
        annual_return = (1 + total_return) ** (1/years) - 1 if years > 0 else 0
        
        # 最大回撤
        max_drawdown = 0
        peak = equity_values[0]
        for eq in equity_values:
            if eq > peak:
                peak = eq
            dd = (eq - peak) / peak
            if dd < max_drawdown:
                max_drawdown = dd
        
        # 夏普比率 (假设无风险利率3%)
        if daily_returns:
            avg_daily_ret = np.mean(daily_returns)
            std_daily_ret = np.std(daily_returns)
            if std_daily_ret > 0:
                sharpe = (avg_daily_ret * 252 - 0.03) / (std_daily_ret * np.sqrt(252))
            else:
                sharpe = 0
        else:
            sharpe = 0
        
        # 卡玛比率
        calmar = annual_return / abs(max_drawdown) if max_drawdown != 0 else 0
        
        # 胜率
        sell_trades = [t for t in trades if t['action'] in ['SELL', 'STOP_LOSS']]
        win_trades = [t for t in sell_trades if t.get('pnl_pct', 0) > 0]
        win_rate = len(win_trades) / len(sell_trades) if sell_trades else 0
        
        return {
            'annual_return': annual_return,
            'max_drawdown': max_drawdown,
            'sharpe_ratio': sharpe,
            'calmar_ratio': calmar,
            'win_rate': win_rate,
            'total_trades': len([t for t in trades if t['action'] == 'BUY']),
            'profit_factor': 0,  # 简化版暂不计算
            'volatility': np.std(daily_returns) * np.sqrt(252) if daily_returns else 0,
            'equity_curve': equity_curve,
            'trades': trades
        }
    
    def _empty_result(self) -> Dict:
        """空结果"""
        return {
            'annual_return': 0,
            'max_drawdown': 0,
            'sharpe_ratio': 0,
            'calmar_ratio': 0,
            'win_rate': 0,
            'total_trades': 0,
            'profit_factor': 0,
            'volatility': 0,
            'equity_curve': [],
            'trades': []
        }


if __name__ == '__main__':
    # 测试
    print("="*70)
    print("🧪 真实数据库回测引擎测试")
    print("="*70)
    
    engine = RealBacktestEngine()
    
    # 获取数据范围
    query = "SELECT MIN(trade_date), MAX(trade_date) FROM daily_price"
    df = pd.read_sql(query, engine.conn)
    print(f"\n📊 数据范围: {df.iloc[0,0]} ~ {df.iloc[0,1]}")
    
    # 测试选股
    print("\n📋 测试选股 (20250225):")
    stocks = engine.select_stocks('20250225', ['ret_20', 'vol_20', 'sharpe_like'], max_holding=10)
    for s in stocks[:5]:
        print(f"   {s.ts_code}: 评分={s.score:.2f}")
    
    # 测试回测 (最近3个月)
    print("\n📈 测试回测 (2024Q4):")
    result = engine.run_backtest(
        start_date='20241001',
        end_date='20241231',
        position_pct=0.7,
        stop_loss=0.08,
        max_holding=5,
        rebalance_days=10,
        selected_factors=['ret_20', 'vol_20', 'sharpe_like', 'roe', 'pe_ttm']
    )
    
    print(f"\n📊 回测结果:")
    print(f"   年化收益: {result['annual_return']*100:+.2f}%")
    print(f"   最大回撤: {result['max_drawdown']*100:.2f}%")
    print(f"   夏普比率: {result['sharpe_ratio']:.2f}")
    print(f"   交易次数: {result['total_trades']}次")
    
    print("\n✅ 测试完成")
