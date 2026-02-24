#!/usr/bin/env python3
"""
动态风控模块
整合市场择时、仓位管理、止损止盈
"""
import sqlite3
import pandas as pd
import numpy as np
from typing import Dict, List, Optional
from datetime import datetime
import sys

sys.path.insert(0, '/root/.openclaw/workspace/tools')
from market_timing import MarketTiming
from industry_neutralizer import IndustryNeutralizer
from multi_factor_model_v3 import MultiFactorModelV3

DB_PATH = '/root/.openclaw/workspace/data/historical/historical.db'


class DynamicRiskManager:
    """动态风控管理器"""
    
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self.timing = MarketTiming(db_path)
        self.neutralizer = IndustryNeutralizer(db_path)
    
    def calculate_dynamic_position(self, date: str = None) -> Dict:
        """
        计算动态仓位
        
        Returns:
            {
                'base_position': 基础仓位,
                'timing_adjustment': 择时调整,
                'vol_adjustment': 波动率调整,
                'final_position': 最终仓位,
                'max_positions': 最大持仓数,
                'stop_loss': 止损线,
                'stop_profit': 止盈线
            }
        """
        # 基础仓位
        base_position = 0.95
        
        # 市场择时调整
        timing = self.timing.calculate_market_score(date)
        timing_adj = timing['position_pct']
        
        # 波动率调整
        recent_vol = timing.get('recent_vol', 0.04)
        if recent_vol > 0.05:
            vol_adj = 0.8
        elif recent_vol > 0.04:
            vol_adj = 0.9
        else:
            vol_adj = 1.0
        
        # 计算最终仓位
        final_position = base_position * timing_adj * vol_adj
        final_position = max(0.0, min(1.0, final_position))  # 限制在0-1之间
        
        # 根据市场状态调整参数
        market_state = timing['market_state']
        if market_state == 'bull':
            max_positions = 20
            stop_loss = -0.08
            stop_profit = 0.15
        elif market_state == 'bear':
            max_positions = 10  # 熊市减少持仓
            stop_loss = -0.05   # 更严格的止损
            stop_profit = 0.08
        else:  # neutral
            max_positions = 15
            stop_loss = -0.06
            stop_profit = 0.12
        
        return {
            'date': timing.get('date'),
            'market_state': market_state,
            'market_score': timing['market_score'],
            'base_position': base_position,
            'timing_adjustment': timing_adj,
            'vol_adjustment': vol_adj,
            'final_position': final_position,
            'max_positions': max_positions,
            'stop_loss': stop_loss,
            'stop_profit': stop_profit,
            'recent_vol': recent_vol
        }
    
    def check_risk_limits(self, portfolio: Dict, prices: Dict[str, float], 
                         date: str) -> List[Dict]:
        """
        检查风控限制
        
        Args:
            portfolio: 当前持仓 {code: {'shares': int, 'cost': float}}
            prices: 当前价格
            date: 日期
        
        Returns:
            需要卖出的列表
        """
        to_sell = []
        
        # 获取动态风控参数
        risk_params = self.calculate_dynamic_position(date)
        stop_loss = risk_params['stop_loss']
        stop_profit = risk_params['stop_profit']
        
        for code, pos in portfolio.items():
            if code not in prices:
                continue
            
            current_price = prices[code]
            cost = pos['cost']
            ret = (current_price - cost) / cost
            
            # 止损检查
            if ret <= stop_loss:
                to_sell.append({
                    'code': code,
                    'reason': 'stop_loss',
                    'return': ret,
                    'shares': pos['shares']
                })
            # 止盈检查
            elif ret >= stop_profit:
                to_sell.append({
                    'code': code,
                    'reason': 'take_profit',
                    'return': ret,
                    'shares': pos['shares']
                })
        
        return to_sell
    
    def get_optimal_strategy(self, date: str = None) -> str:
        """
        根据市场环境选择最优策略
        
        Returns:
            策略名称 ('offensive', 'defensive', 'balanced')
        """
        timing = self.timing.calculate_market_score(date)
        market_state = timing['market_state']
        
        if market_state == 'bull':
            return 'offensive'
        elif market_state == 'bear':
            return 'defensive'
        else:
            return 'balanced'


class EnhancedBacktestEngine:
    """增强版回测引擎 - 整合择时、风控、中性化"""
    
    def __init__(self, db_path: str = DB_PATH, strategy: str = 'adaptive'):
        self.db_path = db_path
        self.strategy = strategy  # 'adaptive' = 根据市场自动选择
        self.risk_manager = DynamicRiskManager(db_path)
        
        # 回测状态
        self.cash = 1000000.0
        self.initial_capital = 1000000.0
        self.positions = {}
        self.portfolio_value = []
        self.trades = []
        self.risk_logs = []
    
    def run_backtest(self, start_date: str, end_date: str) -> Dict:
        """运行增强回测"""
        print(f"\n{'='*70}")
        print(f"增强回测: {start_date} - {end_date}")
        print(f"策略: {self.strategy}")
        print(f"{'='*70}")
        
        # 获取交易日历
        conn = sqlite3.connect(self.db_path)
        query = f"""
        SELECT DISTINCT trade_date FROM stock_factors
        WHERE trade_date BETWEEN '{start_date}' AND '{end_date}'
        ORDER BY trade_date
        """
        trade_dates = pd.read_sql(query, conn)['trade_date'].tolist()
        conn.close()
        
        if len(trade_dates) < 20:
            print("❌ 交易日数量不足")
            return {}
        
        print(f"交易日数: {len(trade_dates)}")
        
        # 初始化
        self.cash = self.initial_capital
        self.positions = {}
        self.portfolio_value = []
        self.trades = []
        self.risk_logs = []
        
        last_rebalance_idx = -20
        
        for i, date in enumerate(trade_dates):
            # 获取价格
            prices = self._get_prices(date)
            if not prices:
                continue
            
            # 计算市值
            market_value = sum(
                self.positions[code]['shares'] * prices.get(code, 0)
                for code in self.positions
            )
            total_value = self.cash + market_value
            
            # 记录
            self.portfolio_value.append({
                'date': date,
                'cash': self.cash,
                'market_value': market_value,
                'total_value': total_value,
                'positions': len(self.positions)
            })
            
            # 获取风控参数
            risk_params = self.risk_manager.calculate_dynamic_position(date)
            
            # 风控检查
            sells = self.risk_manager.check_risk_limits(self.positions, prices, date)
            for sell in sells:
                self._sell_stock(sell['code'], sell['shares'], prices[sell['code']], 
                               date, sell['reason'])
            
            # 定期调仓
            if i - last_rebalance_idx >= 20:
                print(f"\n[{date}] 调仓")
                print(f"  市场状态: {risk_params['market_state']}, "
                      f"建议仓位: {risk_params['final_position']*100:.0f}%")
                
                if risk_params['market_state'] != 'bear':
                    self._rebalance(date, prices, risk_params)
                else:
                    print(f"  熊市环境，清仓观望")
                    self._clear_all_positions(prices, date)
                
                last_rebalance_idx = i
        
        return self._calculate_performance()
    
    def _get_prices(self, date: str) -> Dict[str, float]:
        """获取价格"""
        conn = sqlite3.connect(self.db_path)
        query = f"SELECT ts_code, ma_20 as close FROM stock_factors WHERE trade_date = '{date}'"
        df = pd.read_sql(query, conn)
        conn.close()
        return dict(zip(df['ts_code'], df['close']))
    
    def _sell_stock(self, code: str, shares: int, price: float, date: str, reason: str):
        """卖出股票"""
        if code not in self.positions:
            return
        
        pos = self.positions[code]
        shares = min(shares, pos['shares'])
        
        proceeds = shares * price
        self.cash += proceeds
        pos['shares'] -= shares
        
        if pos['shares'] == 0:
            del self.positions[code]
        
        self.trades.append({
            'date': date, 'code': code, 'action': 'sell',
            'shares': shares, 'price': price, 'reason': reason
        })
    
    def _clear_all_positions(self, prices: Dict[str, float], date: str):
        """清仓"""
        for code in list(self.positions.keys()):
            if code in prices:
                self._sell_stock(code, self.positions[code]['shares'], 
                               prices[code], date, 'bear_market')
    
    def _rebalance(self, date: str, prices: Dict[str, float], risk_params: Dict):
        """调仓"""
        # 选择策略
        if self.strategy == 'adaptive':
            strategy = risk_params['market_state']
            if strategy == 'bear':
                strategy = 'defensive'
            elif strategy == 'bull':
                strategy = 'offensive'
            else:
                strategy = 'balanced'
        else:
            strategy = self.strategy
        
        # 选股
        model = MultiFactorModelV3(strategy=strategy, db_path=self.db_path)
        
        try:
            df = model.get_data_with_all_factors(date)
            if df.empty:
                print(f"  无数据")
                return
            
            df = df.dropna(subset=['ret_20'])
            df = df[(df['pe_ttm'].isna()) | ((df['pe_ttm'] > 0) & (df['pe_ttm'] < 500))]
            df = df[(df['pb_ttm'].isna()) | ((df['pb_ttm'] > 0) & (df['pb_ttm'] < 100))]
            
            if len(df) < risk_params['max_positions']:
                print(f"  数据不足: {len(df)} 只")
                return
            
            # 行业中性化
            neutralizer = IndustryNeutralizer(self.db_path)
            df = neutralizer.assign_size_groups(df)
            df = model.calc_composite_score(df)
            df = neutralizer.neutralize_by_group(df)
            
            # 使用中性化后的分数
            if 'composite_score_neutral' in df.columns:
                df['composite_score'] = df['composite_score_neutral']
            
            # 应用约束
            selected = neutralizer.apply_constraints(
                df, 
                max_per_group=5, 
                total_positions=risk_params['max_positions']
            )
            
            if selected.empty:
                print(f"  未选出股票")
                return
            
            selected_codes = selected['ts_code'].tolist()
            print(f"  选中 {len(selected_codes)} 只")
            
        except Exception as e:
            print(f"  选股失败: {e}")
            return
        finally:
            model.close()
        
        # 清仓不在组合中的
        for code in list(self.positions.keys()):
            if code not in selected_codes and code in prices:
                self._sell_stock(code, self.positions[code]['shares'], 
                               prices[code], date, 'rebalance')
        
        # 买入新股票
        target_value = (self.cash + sum(
            self.positions[code]['shares'] * prices.get(code, 0)
            for code in self.positions
        )) * risk_params['final_position'] / len(selected_codes)
        
        for code in selected_codes:
            if code not in prices or code in self.positions:
                continue
            
            price = prices[code]
            shares = int(target_value / price / 100) * 100
            
            if shares > 0 and shares * price <= self.cash:
                cost = shares * price
                self.cash -= cost
                self.positions[code] = {'shares': shares, 'cost': price}
                self.trades.append({
                    'date': date, 'code': code, 'action': 'buy',
                    'shares': shares, 'price': price, 'reason': 'rebalance'
                })
    
    def _calculate_performance(self) -> Dict:
        """计算绩效"""
        if not self.portfolio_value:
            return {}
        
        df = pd.DataFrame(self.portfolio_value)
        df['date'] = pd.to_datetime(df['date'])
        df = df.set_index('date')
        
        df['return'] = df['total_value'].pct_change()
        df['cum_return'] = (1 + df['return']).cumprod() - 1
        
        total_days = (df.index[-1] - df.index[0]).days
        total_return = df['cum_return'].iloc[-1]
        annual_return = (1 + total_return) ** (365 / total_days) - 1 if total_days > 0 else 0
        volatility = df['return'].std() * np.sqrt(252)
        sharpe = annual_return / volatility if volatility > 0 else 0
        
        df['cum_max'] = df['total_value'].cummax()
        df['drawdown'] = (df['total_value'] - df['cum_max']) / df['cum_max']
        max_drawdown = df['drawdown'].min()
        
        result = {
            'strategy': self.strategy,
            'initial_capital': self.initial_capital,
            'final_value': df['total_value'].iloc[-1],
            'total_return': total_return,
            'annual_return': annual_return,
            'volatility': volatility,
            'sharpe_ratio': sharpe,
            'max_drawdown': max_drawdown,
            'win_rate': (df['return'] > 0).mean(),
            'trade_count': len(self.trades),
        }
        
        print(f"\n{'='*70}")
        print(f"增强回测结果 - 策略: {self.strategy}")
        print(f"{'='*70}")
        print(f"初始资金: {result['initial_capital']:,.0f}")
        print(f"期末资产: {result['final_value']:,.0f}")
        print(f"总收益率: {result['total_return']*100:+.2f}%")
        print(f"年化收益: {result['annual_return']*100:+.2f}%")
        print(f"年化波动: {result['volatility']*100:.2f}%")
        print(f"夏普比率: {result['sharpe_ratio']:.2f}")
        print(f"最大回撤: {result['max_drawdown']*100:.2f}%")
        print(f"日胜率: {result['win_rate']*100:.1f}%")
        print(f"交易次数: {result['trade_count']}")
        print(f"{'='*70}")
        
        return result


def compare_enhanced_strategies(start_date: str, end_date: str):
    """对比增强策略"""
    print("="*70)
    print(f"增强策略对比: {start_date} - {end_date}")
    print("="*70)
    
    strategies = ['adaptive', 'offensive', 'defensive', 'balanced']
    results = []
    
    for strategy in strategies:
        engine = EnhancedBacktestEngine(strategy=strategy)
        result = engine.run_backtest(start_date, end_date)
        if result:
            results.append(result)
        print("\n")
    
    if results:
        print("\n" + "="*70)
        print("策略对比总结")
        print("="*70)
        print(f"{'策略':<12} {'总收益':<10} {'年化':<10} {'夏普':<8} {'回撤':<8} {'胜率':<8}")
        print("-"*70)
        for r in results:
            print(f"{r['strategy']:<12} {r['total_return']*100:>+8.2f}% {r['annual_return']*100:>+8.2f}% "
                  f"{r['sharpe_ratio']:>6.2f} {r['max_drawdown']*100:>6.2f}% {r['win_rate']*100:>6.1f}%")
        print("="*70)


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='增强回测')
    parser.add_argument('--start', type=str, default='20241001')
    parser.add_argument('--end', type=str, default='20250224')
    parser.add_argument('--strategy', type=str, default='adaptive',
                       choices=['adaptive', 'offensive', 'defensive', 'balanced'])
    parser.add_argument('--compare', action='store_true')
    
    args = parser.parse_args()
    
    if args.compare:
        compare_enhanced_strategies(args.start, args.end)
    else:
        engine = EnhancedBacktestEngine(strategy=args.strategy)
        engine.run_backtest(args.start, args.end)
