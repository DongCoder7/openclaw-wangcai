#!/usr/bin/env python3
"""
VQM策略回测优化系统 v2.1 (优化版)
- 每月第一个交易日建仓
- 最多8只股票
- 初始资金100万
- 3年投资期
- 最大回撤 <= 7.5%
- 50次参数优化
"""

import os
import sys
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
import sqlite3
import json
import random
import warnings
warnings.filterwarnings('ignore')

DB_PATH = '/root/.openclaw/workspace/data/historical/historical.db'

class VQMOptimizer:
    """VQM策略参数优化器 - 内存优化版"""
    
    def __init__(self, db_path: str, initial_capital: float = 1000000):
        self.db_path = db_path
        self.initial_capital = initial_capital
        
        if not os.path.exists(db_path):
            raise FileNotFoundError(f"数据库不存在: {db_path}")
        
        # 获取股票列表
        self.stock_list = self.get_stock_list()
        
        # 获取交易日列表
        self.trading_dates = self.get_trading_dates('20180101', '20210104')
        
        print(f"✅ 初始化完成")
        print(f"   股票数量: {len(self.stock_list)}")
        print(f"   交易日数量: {len(self.trading_dates)}")
    
    def get_stock_list(self) -> List[str]:
        """获取股票列表"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT ts_code FROM daily_price")
        stocks = [row[0] for row in cursor.fetchall()]
        conn.close()
        return stocks
    
    def get_trading_dates(self, start_date: str, end_date: str) -> List[str]:
        """获取交易日列表"""
        conn = sqlite3.connect(self.db_path)
        query = '''
            SELECT DISTINCT trade_date 
            FROM daily_price 
            WHERE trade_date BETWEEN ? AND ?
            ORDER BY trade_date
        '''
        dates = pd.read_sql(query, conn, params=[start_date, end_date])
        conn.close()
        return dates['trade_date'].tolist()
    
    def get_first_trading_day_of_month(self, year: int, month: int) -> Optional[str]:
        """获取某月第一个交易日"""
        if month == 12:
            next_month = f"{year+1}01"
        else:
            next_month = f"{year}{month+1:02d}01"
        
        for date in self.trading_dates:
            if date.startswith(f"{year}{month:02d}"):
                return date
            if date >= next_month:
                break
        return None
    
    def get_monthly_rebalance_dates(self, start_year: int, num_months: int) -> List[str]:
        """获取每月调仓日期"""
        dates = []
        for i in range(num_months):
            total_months = (start_year - 2018) * 12 + i
            year = 2018 + total_months // 12
            month = total_months % 12 + 1
            
            first_day = self.get_first_trading_day_of_month(year, month)
            if first_day:
                dates.append(first_day)
        
        return dates
    
    def get_factors_for_date(self, trade_date: str, stock_pool: List[str]) -> pd.DataFrame:
        """获取指定日期的因子数据"""
        conn = sqlite3.connect(self.db_path)
        
        # 获取该日及之前的数据计算因子
        query = '''
            SELECT ts_code, trade_date, close, volume
            FROM daily_price
            WHERE trade_date <= ? AND ts_code IN ({})
            ORDER BY ts_code, trade_date
        '''.format(','.join(['?'] * min(len(stock_pool), 100)))
        
        params = [trade_date] + stock_pool[:100]
        df = pd.read_sql(query, conn, params=params)
        conn.close()
        
        if df.empty:
            return pd.DataFrame()
        
        # 计算因子
        df = df.sort_values(['ts_code', 'trade_date'])
        
        # 20日收益率 (动量因子)
        df['return_20d'] = df.groupby('ts_code')['close'].pct_change(20)
        
        # 20日波动率
        df['return_1d'] = df.groupby('ts_code')['close'].pct_change(1)
        df['volatility_20d'] = df.groupby('ts_code')['return_1d'].rolling(20).std().reset_index(level=0, drop=True)
        
        # 成交量均值
        df['volume_ma20'] = df.groupby('ts_code')['volume'].rolling(20).mean().reset_index(level=0, drop=True)
        df['volume_ratio'] = df['volume'] / df['volume_ma20']
        
        # 获取最新数据
        latest = df.groupby('ts_code').last().reset_index()
        
        return latest[latest['trade_date'] == trade_date]
    
    def select_stocks(self, 
                     trade_date: str, 
                     stock_pool: List[str],
                     num_stocks: int,
                     params: Dict) -> List[str]:
        """基于因子选择股票"""
        
        date_data = self.get_factors_for_date(trade_date, stock_pool)
        
        if date_data.empty:
            return random.sample(stock_pool, min(num_stocks, len(stock_pool)))
        
        # 过滤有效数据
        date_data = date_data.dropna(subset=['return_20d', 'volatility_20d'])
        
        if date_data.empty:
            return random.sample(stock_pool, min(num_stocks, len(stock_pool)))
        
        # 提取参数
        alpha_w = params.get('alpha_weight', 0.4)
        beta_w = params.get('beta_weight', 0.3)
        vol_w = params.get('volume_weight', 0.2)
        low_vol = params.get('low_volatility', 0.1)
        
        # 计算评分
        date_data['momentum_score'] = date_data['return_20d'].rank(pct=True) * alpha_w
        date_data['vol_score'] = (1 - date_data['volatility_20d'].rank(pct=True)) * beta_w
        date_data['vol_ratio_score'] = (1 - abs(date_data['volume_ratio'] - 1).rank(pct=True)) * vol_w
        date_data['low_vol_score'] = (1 - date_data['volatility_20d'].rank(pct=True)) * low_vol
        
        date_data['total_score'] = (date_data['momentum_score'] + 
                                    date_data['vol_score'] + 
                                    date_data['vol_ratio_score'] +
                                    date_data['low_vol_score'])
        
        date_data = date_data.sort_values('total_score', ascending=False)
        
        return date_data.head(num_stocks)['ts_code'].tolist()
    
    def get_price(self, ts_code: str, trade_date: str) -> float:
        """获取指定日期的收盘价"""
        conn = sqlite3.connect(self.db_path)
        query = 'SELECT close FROM daily_price WHERE ts_code = ? AND trade_date = ?'
        result = pd.read_sql(query, conn, params=[ts_code, trade_date])
        conn.close()
        
        if result.empty:
            return 0.0
        return result.iloc[0]['close']
    
    def run_backtest(self, 
                    params: Dict,
                    start_date: str,
                    end_date: str,
                    num_stocks: int = 8,
                    max_drawdown_limit: float = 0.075) -> Dict:
        """运行单次回测"""
        
        rebalance_dates = self.get_monthly_rebalance_dates(2018, 36)
        rebalance_dates = [d for d in rebalance_dates if d >= start_date and d <= end_date]
        
        if not rebalance_dates:
            return {'success': False, 'error': 'No rebalance dates'}
        
        cash = self.initial_capital
        holdings = {}
        portfolio_values = []
        trade_log = []
        
        all_dates = self.get_trading_dates(start_date, end_date)
        current_rebalance_idx = 0
        
        # 预加载股价数据以加速
        price_cache = {}
        
        for i, date in enumerate(all_dates):
            # 调仓检查
            if current_rebalance_idx < len(rebalance_dates):
                rebalance_date = rebalance_dates[current_rebalance_idx]
                
                if date >= rebalance_date:
                    # 卖出
                    for stock in list(holdings.keys()):
                        price = self.get_price(stock, date)
                        if price > 0:
                            cash += holdings[stock] * price
                            trade_log.append({'date': date, 'action': 'sell', 'stock': stock, 'price': price})
                    
                    holdings = {}
                    
                    # 选股买入
                    selected_stocks = self.select_stocks(date, self.stock_list, num_stocks, params)
                    
                    if selected_stocks and cash > 0:
                        per_stock_cash = cash / len(selected_stocks)
                        
                        for stock in selected_stocks:
                            price = self.get_price(stock, date)
                            if price > 0:
                                shares = int(per_stock_cash / price / 100) * 100
                                if shares > 0:
                                    cost = shares * price
                                    cash -= cost
                                    holdings[stock] = shares
                                    trade_log.append({'date': date, 'action': 'buy', 'stock': stock, 'shares': shares, 'price': price})
                    
                    current_rebalance_idx += 1
            
            # 计算组合价值
            portfolio_value = cash
            for stock, shares in holdings.items():
                price = self.get_price(stock, date)
                portfolio_value += shares * price
            
            portfolio_values.append({'date': date, 'value': portfolio_value})
        
        # 计算指标
        if not portfolio_values:
            return {'success': False, 'error': 'No portfolio values'}
        
        portfolio_df = pd.DataFrame(portfolio_values)
        portfolio_df['return'] = portfolio_df['value'].pct_change()
        
        total_return = (portfolio_df.iloc[-1]['value'] - self.initial_capital) / self.initial_capital
        
        num_days = len(portfolio_df)
        years = num_days / 252
        annual_return = (1 + total_return) ** (1 / years) - 1 if years > 0 else 0
        
        portfolio_df['cummax'] = portfolio_df['value'].cummax()
        portfolio_df['drawdown'] = (portfolio_df['value'] - portfolio_df['cummax']) / portfolio_df['cummax']
        max_drawdown = abs(portfolio_df['drawdown'].min())
        
        if portfolio_df['return'].std() > 0:
            sharpe = (annual_return - 0.03) / portfolio_df['return'].std() * np.sqrt(252)
        else:
            sharpe = 0
        
        success = max_drawdown <= max_drawdown_limit
        
        return {
            'success': success,
            'total_return': total_return,
            'annual_return': annual_return,
            'max_drawdown': max_drawdown,
            'sharpe': sharpe,
            'num_trades': len(trade_log),
            'final_value': portfolio_df.iloc[-1]['value'],
            'trade_log': trade_log[-20:],
            'params': params
        }
    
    def optimize(self, num_iterations: int = 50) -> Tuple[List, Dict]:
        """运行参数优化"""
        
        results = []
        
        print(f"\n🚀 开始 {num_iterations} 次参数优化...")
        print("="*60)
        
        best_result = None
        best_return = -float('inf')
        
        for i in range(num_iterations):
            params = {
                'alpha_weight': random.uniform(0.1, 0.8),
                'beta_weight': random.uniform(0.1, 0.6),
                'volume_weight': random.uniform(0.0, 0.4),
                'low_volatility': random.uniform(0.0, 0.3),
            }
            
            # 归一化
            total_w = params['alpha_weight'] + params['beta_weight'] + params['volume_weight'] + params['low_volatility']
            params['alpha_weight'] /= total_w
            params['beta_weight'] /= total_w
            params['volume_weight'] /= total_w
            params['low_volatility'] /= total_w
            
            result = self.run_backtest(
                params=params,
                start_date='20180102',
                end_date='20210102',
                num_stocks=8,
                max_drawdown_limit=0.075
            )
            
            results.append({
                'iteration': i + 1,
                'params': params,
                'result': result
            })
            
            status = "✅" if result['success'] else "❌"
            print(f"{status} 迭代 {i+1:02d}/{num_iterations} | "
                  f"收益: {result.get('total_return', 0)*100:+.1f}% | "
                  f"年化: {result.get('annual_return', 0)*100:+.1f}% | "
                  f"回撤: {result.get('max_drawdown', 0)*100:.1f}% | "
                  f"夏普: {result.get('sharpe', 0):.2f}")
            
            if result.get('total_return', -float('inf')) > best_return:
                best_return = result.get('total_return', -float('inf'))
                best_result = result
                best_result['iteration'] = i + 1
                best_result['params'] = params
        
        print("="*60)
        print(f"✅ 优化完成! 最佳收益: {best_return*100:.1f}%")
        
        return results, best_result


def generate_report(iteration: int, result: Dict, params: Dict) -> str:
    """生成回测报告"""
    
    report = f"""
📊 回测报告 #{iteration}
{'='*50}

🎯 参数配置:
   • 动量因子(α)权重: {params.get('alpha_weight', 0):.2%}
   • 波动率因子(β)权重: {params.get('beta_weight', 0):.2%}
   • 成交量因子权重: {params.get('volume_weight', 0):.2%}
   • 低波动偏好: {params.get('low_volatility', 0):.2%}

📈 收益指标:
   • 总收益率: {result.get('total_return', 0)*100:+.2f}%
   • 年化收益率: {result.get('annual_return', 0)*100:+.2f}%
   • 最终净值: ¥{result.get('final_value', 0):,.0f}

⚠️ 风险指标:
   • 最大回撤: {result.get('max_drawdown', 0)*100:.2f}%
   • 夏普比率: {result.get('sharpe', 0):.2f}

📊 交易统计:
   • 总交易次数: {result.get('num_trades', 0)}次

✅ 状态: {'成功 (回撤<7.5%)' if result.get('success') else '失败 (回撤超标)'}
{'='*50}
"""
    return report


if __name__ == '__main__':
    optimizer = VQMOptimizer(DB_PATH, initial_capital=1000000)
    
    all_results, best = optimizer.optimize(num_iterations=50)
    
    # 保存结果
    output = {
        'timestamp': datetime.now().isoformat(),
        'best_result': {
            'iteration': best.get('iteration'),
            'params': best.get('params'),
            'metrics': {
                'total_return': best.get('total_return'),
                'annual_return': best.get('annual_return'),
                'max_drawdown': best.get('max_drawdown'),
                'sharpe': best.get('sharpe'),
                'final_value': best.get('final_value'),
            }
        },
        'all_results': [
            {
                'iteration': r['iteration'],
                'params': r['params'],
                'total_return': r['result'].get('total_return'),
                'max_drawdown': r['result'].get('max_drawdown'),
                'success': r['result'].get('success')
            }
            for r in all_results
        ]
    }
    
    with open('/root/.openclaw/workspace/quant/backtest_optimization_results.json', 'w') as f:
        json.dump(output, f, indent=2, default=str)
    
    # 生成最终报告
    print(generate_report(best.get('iteration'), best, best.get('params')))
    
    print(f"\n💾 结果已保存到: /root/.openclaw/workspace/quant/backtest_optimization_results.json")
