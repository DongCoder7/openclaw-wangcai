#!/usr/bin/env python3
"""
豆奶多因子模型 - 事件驱动回测引擎 v3.0
支持多策略回测
"""
import sqlite3
import pandas as pd
import numpy as np
from typing import Dict, List, Optional
from datetime import datetime
import sys

sys.path.insert(0, '/root/.openclaw/workspace/tools')
from multi_factor_model_v3 import MultiFactorModelV3

DB_PATH = '/root/.openclaw/workspace/data/historical/historical.db'


class BacktestEngineV3:
    """回测引擎 v3.0 - 支持多策略"""
    
    def __init__(self, db_path: str = DB_PATH, strategy: str = 'balanced'):
        self.db_path = db_path
        self.strategy = strategy
        self.model = MultiFactorModelV3(strategy=strategy, db_path=db_path)
        
        # 回测参数
        self.rebalance_freq = 20
        self.max_positions = 20
        self.position_pct = 0.95
        self.stop_loss = -0.08
        self.stop_profit = 0.15
        
        # 结果
        self.portfolio_value = []
        self.trades = []
        self.positions = {}
        self.cash = 1000000.0
        self.initial_capital = 1000000.0
    
    def get_prices(self, date: str) -> Dict[str, float]:
        """获取价格数据"""
        conn = sqlite3.connect(self.db_path)
        query = f"SELECT ts_code, ma_20 as close FROM stock_factors WHERE trade_date = '{date}'"
        df = pd.read_sql(query, conn)
        conn.close()
        return dict(zip(df['ts_code'], df['close']))
    
    def select_stocks(self, date: str) -> List[str]:
        """选股"""
        try:
            df = self.model.get_data_with_all_factors(date)
            if df.empty:
                return []
            
            # 过滤
            df = df.dropna(subset=['ret_20'])
            if 'pe_ttm' in df.columns:
                df = df[(df['pe_ttm'].isna()) | ((df['pe_ttm'] > 0) & (df['pe_ttm'] < 500))]
            if 'pb_ttm' in df.columns:
                df = df[(df['pb_ttm'].isna()) | ((df['pb_ttm'] > 0) & (df['pb_ttm'] < 100))]
            
            if len(df) < self.max_positions:
                return []
            
            # 计算评分
            df = self.model.calc_composite_score(df)
            df = df.sort_values('composite_score', ascending=False)
            selected = df.head(self.max_positions)
            
            return selected['ts_code'].tolist()
            
        except Exception as e:
            print(f"选股失败: {e}")
            return []
    
    def run_backtest(self, start_date: str, end_date: str) -> Dict:
        """运行回测"""
        print(f"\n{'='*70}")
        print(f"回测: {start_date} - {end_date}")
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
        
        last_rebalance_idx = -self.rebalance_freq
        
        for i, date in enumerate(trade_dates):
            prices = self.get_prices(date)
            if not prices:
                continue
            
            # 计算总市值
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
            
            # 风控检查
            self._risk_check(prices, date)
            
            # 定期调仓
            if i - last_rebalance_idx >= self.rebalance_freq:
                print(f"\n[{date}] 调仓")
                self._rebalance(date, prices)
                last_rebalance_idx = i
        
        return self._calculate_performance()
    
    def _risk_check(self, prices: Dict[str, float], date: str):
        """风控检查"""
        for code in list(self.positions.keys()):
            if code not in prices:
                continue
            
            pos = self.positions[code]
            ret = (prices[code] - pos['cost']) / pos['cost']
            
            if ret < self.stop_loss or ret > self.stop_profit:
                # 卖出
                proceeds = pos['shares'] * prices[code]
                self.cash += proceeds
                del self.positions[code]
                self.trades.append({
                    'date': date, 'code': code, 'action': 'sell',
                    'shares': pos['shares'], 'price': prices[code]
                })
    
    def _rebalance(self, date: str, prices: Dict[str, float]):
        """调仓"""
        selected = self.select_stocks(date)
        
        if not selected:
            print(f"  [{date}] 无选中股票")
            return
        
        print(f"  [{date}] 选中 {len(selected)} 只")
        
        # 清仓不在组合中的
        for code in list(self.positions.keys()):
            if code not in selected and code in prices:
                pos = self.positions[code]
                proceeds = pos['shares'] * prices[code]
                self.cash += proceeds
                del self.positions[code]
        
        # 买入新股票
        total_value = self.cash + sum(
            self.positions[code]['shares'] * prices.get(code, 0)
            for code in self.positions
        )
        target_value = total_value * self.position_pct / len(selected)
        
        for code in selected:
            if code not in prices:
                continue
            
            if code not in self.positions:
                price = prices[code]
                shares = int(target_value / price / 100) * 100
                
                if shares > 0 and shares * price <= self.cash:
                    cost = shares * price
                    self.cash -= cost
                    self.positions[code] = {'shares': shares, 'cost': price}
                    self.trades.append({
                        'date': date, 'code': code, 'action': 'buy',
                        'shares': shares, 'price': price
                    })
    
    def _calculate_performance(self) -> Dict:
        """计算绩效"""
        if not self.portfolio_value:
            return {}
        
        df = pd.DataFrame(self.portfolio_value)
        df['date'] = pd.to_datetime(df['date'])
        df = df.set_index('date')
        
        # 收益率
        df['return'] = df['total_value'].pct_change()
        df['cum_return'] = (1 + df['return']).cumprod() - 1
        
        # 统计
        total_days = (df.index[-1] - df.index[0]).days
        total_return = df['cum_return'].iloc[-1]
        annual_return = (1 + total_return) ** (365 / total_days) - 1 if total_days > 0 else 0
        volatility = df['return'].std() * np.sqrt(252)
        sharpe = annual_return / volatility if volatility > 0 else 0
        
        # 最大回撤
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
        
        # 打印
        print(f"\n{'='*70}")
        print(f"回测结果 - 策略: {self.strategy}")
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


def compare_strategies(start_date: str, end_date: str):
    """对比所有策略"""
    print("="*70)
    print(f"策略对比回测: {start_date} - {end_date}")
    print("="*70)
    
    strategies = ['offensive', 'defensive', 'balanced', 'v2']
    results = []
    
    for strategy in strategies:
        engine = BacktestEngineV3(strategy=strategy)
        result = engine.run_backtest(start_date, end_date)
        if result:
            results.append(result)
        engine.model.close()
        print("\n")
    
    # 对比表
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


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='策略回测 v3.0')
    parser.add_argument('--start', type=str, default='20241001', help='开始日期')
    parser.add_argument('--end', type=str, default='20241130', help='结束日期')
    parser.add_argument('--strategy', type=str, default='balanced',
                       choices=['offensive', 'defensive', 'balanced', 'v2'],
                       help='策略类型')
    parser.add_argument('--rebalance', type=int, default=20, help='调仓周期')
    parser.add_argument('--positions', type=int, default=20, help='持仓数')
    parser.add_argument('--compare', action='store_true', help='对比所有策略')
    
    args = parser.parse_args()
    
    if args.compare:
        compare_strategies(args.start, args.end)
    else:
        engine = BacktestEngineV3(strategy=args.strategy)
        engine.rebalance_freq = args.rebalance
        engine.max_positions = args.positions
        result = engine.run_backtest(args.start, args.end)
        engine.model.close()


if __name__ == '__main__':
    main()
