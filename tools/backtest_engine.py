#!/usr/bin/env python3
"""
豆奶多因子模型 - 事件驱动回测引擎
支持多因子策略的完整回测
"""
import sqlite3
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass
import sys

sys.path.insert(0, '/root/.openclaw/workspace/tools')
from factor_library import FactorLibrary, DataLoader
from multi_factor_model import MultiFactorModel

DB_PATH = '/root/.openclaw/workspace/data/historical/historical.db'


@dataclass
class Order:
    """订单"""
    code: str
    action: str  # 'buy' or 'sell'
    shares: int
    price: float
    date: str


@dataclass
class Position:
    """持仓"""
    code: str
    shares: int
    avg_cost: float
    buy_date: str


class Portfolio:
    """投资组合"""
    
    def __init__(self, initial_capital: float = 1000000.0):
        self.initial_capital = initial_capital
        self.cash = initial_capital
        self.positions: Dict[str, Position] = {}
        self.trade_history: List[Order] = []
        self.value_history: List[Dict] = []
    
    def get_market_value(self, prices: Dict[str, float]) -> float:
        """计算市值"""
        market_value = 0
        for code, pos in self.positions.items():
            if code in prices:
                market_value += pos.shares * prices[code]
        return market_value
    
    def get_total_value(self, prices: Dict[str, float]) -> float:
        """计算总资产"""
        return self.cash + self.get_market_value(prices)
    
    def buy(self, code: str, shares: int, price: float, date: str) -> bool:
        """买入"""
        cost = shares * price
        if cost > self.cash:
            return False
        
        self.cash -= cost
        
        if code in self.positions:
            # 加仓
            pos = self.positions[code]
            total_cost = pos.shares * pos.avg_cost + cost
            total_shares = pos.shares + shares
            pos.shares = total_shares
            pos.avg_cost = total_cost / total_shares
        else:
            # 新建仓
            self.positions[code] = Position(code, shares, price, date)
        
        self.trade_history.append(Order(code, 'buy', shares, price, date))
        return True
    
    def sell(self, code: str, shares: int, price: float, date: str) -> bool:
        """卖出"""
        if code not in self.positions:
            return False
        
        pos = self.positions[code]
        if shares > pos.shares:
            shares = pos.shares
        
        proceeds = shares * price
        self.cash += proceeds
        
        pos.shares -= shares
        if pos.shares == 0:
            del self.positions[code]
        
        self.trade_history.append(Order(code, 'sell', shares, price, date))
        return True
    
    def sell_all(self, prices: Dict[str, float], date: str):
        """清仓"""
        for code in list(self.positions.keys()):
            if code in prices:
                self.sell(code, self.positions[code].shares, prices[code], date)


class BacktestEngine:
    """回测引擎"""
    
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self.loader = DataLoader(db_path)
        self.model = MultiFactorModel()
        self.portfolio = None
        
        # 回测参数
        self.rebalance_freq = 20  # 调仓周期（交易日）
        self.max_positions = 20   # 最大持仓数
        self.position_pct = 0.95  # 仓位比例
        self.stop_loss = -0.08    # 止损线
        self.stop_profit = 0.15   # 止盈线
    
    def get_prices(self, date: str) -> Dict[str, float]:
        """获取指定日期的价格数据 - 使用ma_20作为代理"""
        conn = sqlite3.connect(self.db_path)
        
        query = f"""
        SELECT ts_code, ma_20 as close FROM stock_factors
        WHERE trade_date = '{date}'
        """
        
        df = pd.read_sql(query, conn)
        conn.close()
        
        return dict(zip(df['ts_code'], df['close']))
    
    def get_valuation_data(self, date: str) -> pd.DataFrame:
        """获取指定日期的估值数据"""
        conn = sqlite3.connect(self.db_path)
        
        query = f"""
        SELECT 
            f.ts_code,
            f.ret_20, f.ret_60, f.ret_120,
            f.vol_20, f.vol_ratio,
            f.price_pos_20, f.money_flow, f.rel_strength, f.mom_accel, f.profit_mom,
            v.pe, v.pb, v.market_cap
        FROM stock_factors f
        LEFT JOIN stock_valuation v ON f.ts_code = v.ts_code AND f.trade_date = v.trade_date
        WHERE f.trade_date = '{date}'
        """
        
        df = pd.read_sql(query, conn)
        conn.close()
        
        return df
    
    def run_backtest(self, start_date: str, end_date: str) -> Dict:
        """
        运行回测
        
        Args:
            start_date: 开始日期 (YYYYMMDD)
            end_date: 结束日期 (YYYYMMDD)
        
        Returns:
            回测结果
        """
        print(f"\n{'='*70}")
        print(f"回测: {start_date} - {end_date}")
        print(f"{'='*70}")
        
        # 初始化
        self.portfolio = Portfolio()
        
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
        
        # 回测循环
        last_rebalance_idx = -self.rebalance_freq
        
        for i, date in enumerate(trade_dates):
            # 获取价格
            prices = self.get_prices(date)
            
            if not prices:
                continue
            
            # 记录净值
            total_value = self.portfolio.get_total_value(prices)
            self.portfolio.value_history.append({
                'date': date,
                'cash': self.portfolio.cash,
                'market_value': self.portfolio.get_market_value(prices),
                'total_value': total_value,
                'positions': len(self.portfolio.positions)
            })
            
            # 每日风控检查
            self._risk_check(prices, date)
            
            # 定期调仓
            if i - last_rebalance_idx >= self.rebalance_freq:
                print(f"\n[{date}] 调仓")
                self._rebalance(date, prices)
                last_rebalance_idx = i
        
        # 计算绩效
        return self._calculate_performance()
    
    def _risk_check(self, prices: Dict[str, float], date: str):
        """风控检查"""
        for code in list(self.portfolio.positions.keys()):
            if code not in prices:
                continue
            
            pos = self.portfolio.positions[code]
            ret = (prices[code] - pos.avg_cost) / pos.avg_cost
            
            # 止损
            if ret < self.stop_loss:
                self.portfolio.sell(code, pos.shares, prices[code], date)
            # 止盈
            elif ret > self.stop_profit:
                self.portfolio.sell(code, pos.shares, prices[code], date)
    
    def _rebalance(self, date: str, prices: Dict[str, float]):
        """调仓 - 使用包含估值的数据"""
        # 获取包含估值的数据
        try:
            df = self.get_valuation_data(date)
            if df.empty:
                print(f"  [{date}] 无数据")
                return
            
            # 过滤有效数据
            df = df.dropna(subset=['ret_20'])
            
            # 过滤PE/PB异常值
            df = df[(df['pe'].isna()) | ((df['pe'] > 0) & (df['pe'] < 500))]
            df = df[(df['pb'].isna()) | ((df['pb'] > 0) & (df['pb'] < 100))]
            
            if len(df) < self.max_positions:
                print(f"  [{date}] 数据不足: {len(df)} 只")
                return
            
            # 计算综合评分
            df = self.model.calc_composite_score(df, neutralize=True)
            
            # 排序并选择
            df = df.sort_values('composite_score', ascending=False)
            selected = df.head(self.max_positions)
            
            print(f"  [{date}] 选中 {len(selected)} 只")
            
        except Exception as e:
            print(f"  [{date}] 选股失败: {e}")
            return
        
        # 清仓不在新组合中的股票
        new_codes = set(selected['ts_code'].tolist())
        for code in list(self.portfolio.positions.keys()):
            if code not in new_codes:
                if code in prices:
                    self.portfolio.sell_all({code: prices[code]}, date)
        
        # 计算目标持仓
        target_value = self.portfolio.get_total_value(prices) * self.position_pct
        target_per_stock = target_value / len(selected)
        
        # 买入新股票
        for _, row in selected.iterrows():
            code = row['ts_code']
            if code not in prices:
                continue
            
            price = prices[code]
            shares = int(target_per_stock / price / 100) * 100  # 取整手
            
            if shares > 0 and code not in self.portfolio.positions:
                self.portfolio.buy(code, shares, price, date)
    
    def _calculate_performance(self) -> Dict:
        """计算回测绩效"""
        if not self.portfolio.value_history:
            return {}
        
        df = pd.DataFrame(self.portfolio.value_history)
        df['date'] = pd.to_datetime(df['date'])
        df = df.set_index('date')
        
        # 收益率
        df['return'] = df['total_value'].pct_change()
        df['cum_return'] = (1 + df['return']).cumprod() - 1
        
        # 年化收益
        total_days = (df.index[-1] - df.index[0]).days
        total_return = df['cum_return'].iloc[-1]
        annual_return = (1 + total_return) ** (365 / total_days) - 1
        
        # 波动率
        volatility = df['return'].std() * np.sqrt(252)
        
        # 夏普比率
        sharpe = annual_return / volatility if volatility > 0 else 0
        
        # 最大回撤
        df['cum_max'] = df['total_value'].cummax()
        df['drawdown'] = (df['total_value'] - df['cum_max']) / df['cum_max']
        max_drawdown = df['drawdown'].min()
        
        # 胜率
        win_rate = (df['return'] > 0).mean()
        
        # 交易统计
        trades = self.portfolio.trade_history
        
        result = {
            'initial_capital': self.portfolio.initial_capital,
            'final_value': df['total_value'].iloc[-1],
            'total_return': total_return,
            'annual_return': annual_return,
            'volatility': volatility,
            'sharpe_ratio': sharpe,
            'max_drawdown': max_drawdown,
            'win_rate': win_rate,
            'trade_count': len(trades),
            'value_curve': df[['total_value', 'cum_return']].to_dict(),
        }
        
        # 打印结果
        print(f"\n{'='*70}")
        print("回测结果")
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


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='策略回测')
    parser.add_argument('--start', type=str, default='20230101', help='开始日期')
    parser.add_argument('--end', type=str, default='20241231', help='结束日期')
    parser.add_argument('--rebalance', type=int, default=20, help='调仓周期')
    parser.add_argument('--positions', type=int, default=20, help='持仓数')
    
    args = parser.parse_args()
    
    # 创建回测引擎
    engine = BacktestEngine()
    engine.rebalance_freq = args.rebalance
    engine.max_positions = args.positions
    
    # 运行回测
    result = engine.run_backtest(args.start, args.end)
    
    if result:
        # 保存结果
        output_file = f'/root/.openclaw/workspace/data/backtest_result_{args.start}_{args.end}.json'
        import json
        with open(output_file, 'w') as f:
            json.dump({k: v for k, v in result.items() if k != 'value_curve'}, f, indent=2)
        print(f"\n结果已保存: {output_file}")


if __name__ == '__main__':
    main()
