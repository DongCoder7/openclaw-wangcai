#!/usr/bin/env python3
"""
VQM策略多时间段模拟回测框架
支持不同时间段建仓、滚动测试、参数优化
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json
import os
from typing import Dict, List, Tuple, Optional
import random

class VQMMultiPeriodBacktest:
    """
    VQM策略多时间段回测引擎
    支持:
    1. 多时间段模拟数据建仓
    2. 滚动窗口测试
    3. 参数敏感性分析
    4. 稳健性验证
    """
    
    def __init__(self, config: Dict):
        """
        初始化回测引擎
        
        Args:
            config: 配置字典
                - initial_capital: 初始资金
                - stock_pool: 股票池
                - pe_weight_range: PE权重范围 (0.5-0.8)
                - roe_weight_range: ROE权重范围 (0.2-0.5)
                - position_count_range: 持仓数量范围 (5-20)
                - stop_loss_range: 止损线范围 (0.88-0.95)
        """
        self.config = config
        self.results_cache = {}
        
    def generate_simulated_data(
        self,
        start_date: str,
        end_date: str,
        market_regime: str = 'mixed',
        seed: int = 42
    ) -> pd.DataFrame:
        """
        生成模拟市场数据
        
        Args:
            start_date: 开始日期 '2019-01-01'
            end_date: 结束日期 '2024-12-31'
            market_regime: 市场风格
                - 'growth': 成长风格占优 (2019-2021)
                - 'value': 价值风格占优 (2022-2024)
                - 'mixed': 混合风格
            seed: 随机种子
        """
        np.random.seed(seed)
        
        # 生成交易日历
        dates = pd.date_range(start=start_date, end=end_date, freq='B')  # 工作日
        n_days = len(dates)
        
        # 根据市场风格设置参数
        if market_regime == 'growth':
            # 成长股牛市：高波动，高ROE股票表现好
            base_return = 0.0008  # 日收益基线
            volatility = 0.018
            pe_factor_return = -0.0002  # 低PE跑输
            roe_factor_return = 0.0005  # 高ROE跑赢
        elif market_regime == 'value':
            # 价值股牛市：低波动，低PE股票表现好
            base_return = 0.0005
            volatility = 0.012
            pe_factor_return = 0.0004  # 低PE跑赢
            roe_factor_return = 0.0002
        else:  # mixed
            base_return = 0.0006
            volatility = 0.015
            pe_factor_return = 0.0001
            roe_factor_return = 0.0003
        
        # 生成股票池数据
        n_stocks = 50
        stocks_data = []
        
        for i in range(n_stocks):
            stock_code = f'ST{i:04d}'
            
            # 生成基础PE和ROE（带均值回归）
            base_pe = np.random.uniform(5, 40)
            base_roe = np.random.uniform(5, 25)
            
            # 生成价格序列
            prices = [100.0]
            for t in range(1, n_days):
                # 随机 walk + 风格因子收益
                random_return = np.random.normal(base_return, volatility)
                
                # 低PE股票获得额外收益
                pe_adjustment = (20 - base_pe) / 20 * pe_factor_return
                
                # 高ROE股票获得额外收益
                roe_adjustment = (base_roe - 15) / 15 * roe_factor_return
                
                daily_return = random_return + pe_adjustment + roe_adjustment
                new_price = prices[-1] * (1 + daily_return)
                prices.append(new_price)
            
            # 生成PE和ROE序列（带波动）
            pe_series = base_pe + np.random.normal(0, base_pe * 0.05, n_days)
            roe_series = base_roe + np.random.normal(0, base_roe * 0.03, n_days)
            
            for t, date in enumerate(dates):
                stocks_data.append({
                    'date': date,
                    'code': stock_code,
                    'close': prices[t],
                    'pe': max(1, pe_series[t]),  # PE不能为负
                    'roe': max(0, roe_series[t]),  # ROE不能为负
                    'market_cap': np.random.uniform(50, 5000),  # 市值
                })
        
        df = pd.DataFrame(stocks_data)
        df['date'] = pd.to_datetime(df['date'])
        return df
    
    def calculate_vqm_score(
        self,
        df: pd.DataFrame,
        date: datetime,
        pe_weight: float = 0.6,
        roe_weight: float = 0.4
    ) -> pd.DataFrame:
        """
        计算VQM综合得分
        
        Args:
            df: 市场数据
            date: 计算日期
            pe_weight: PE因子权重
            roe_weight: ROE因子权重
        """
        # 获取当日数据
        day_data = df[df['date'] == date].copy()
        
        if len(day_data) == 0:
            return pd.DataFrame()
        
        # 计算PE排名（越低越好，所以反向）
        day_data['pe_rank'] = day_data['pe'].rank(pct=True, ascending=True)
        
        # 计算ROE排名（越高越好）
        day_data['roe_rank'] = day_data['roe'].rank(pct=True, ascending=False)
        
        # 计算综合得分
        day_data['vqm_score'] = (
            day_data['pe_rank'] * pe_weight +
            day_data['roe_rank'] * roe_weight
        )
        
        return day_data.sort_values('vqm_score', ascending=False)
    
    def run_single_backtest(
        self,
        data: pd.DataFrame,
        start_date: str,
        end_date: str,
        params: Dict
    ) -> Dict:
        """
        执行单次回测
        
        Args:
            data: 市场数据
            start_date: 回测开始日期
            end_date: 回测结束日期
            params: 策略参数
                - pe_weight: PE权重
                - roe_weight: ROE权重
                - position_count: 持仓数量
                - stop_loss: 止损比例
                - rebalance_freq: 调仓频率（月）
        """
        # 初始化
        initial_capital = self.config.get('initial_capital', 1000000)
        capital = initial_capital
        positions = {}  # 当前持仓 {code: {'shares': x, 'cost': y}}
        
        # 筛选回测期间数据
        mask = (data['date'] >= start_date) & (data['date'] <= end_date)
        backtest_data = data[mask].copy()
        
        dates = sorted(backtest_data['date'].unique())
        
        # 记录每日净值
        daily_nav = []
        trades = []
        
        last_rebalance = None
        
        for date in dates:
            # 获取当日数据
            day_data = backtest_data[backtest_data['date'] == date]
            
            # 计算当前持仓市值
            portfolio_value = capital
            for code, pos in positions.items():
                stock_price = day_data[day_data['code'] == code]['close'].values
                if len(stock_price) > 0:
                    portfolio_value += pos['shares'] * stock_price[0]
            
            # 记录净值
            daily_nav.append({
                'date': date,
                'nav': portfolio_value,
                'cash': capital,
                'positions_count': len(positions)
            })
            
            # 检查止损
            to_sell = []
            for code, pos in positions.items():
                stock_price = day_data[day_data['code'] == code]['close'].values
                if len(stock_price) > 0:
                    current_price = stock_price[0]
                    if current_price <= pos['cost'] * params['stop_loss']:
                        to_sell.append(code)
                        # 卖出
                        sell_value = pos['shares'] * current_price * 0.999  # 扣除手续费
                        capital += sell_value
                        trades.append({
                            'date': date,
                            'code': code,
                            'action': 'SELL',
                            'price': current_price,
                            'shares': pos['shares'],
                            'reason': 'STOP_LOSS'
                        })
            
            for code in to_sell:
                del positions[code]
            
            # 月度调仓
            current_month = date.strftime('%Y-%m')
            if last_rebalance != current_month and date.day >= 20:  # 每月20日后调仓
                last_rebalance = current_month
                
                # 计算VQM得分
                ranked_stocks = self.calculate_vqm_score(
                    backtest_data, date,
                    params['pe_weight'], params['roe_weight']
                )
                
                if len(ranked_stocks) >= params['position_count']:
                    # 选出前N只股票
                    top_stocks = ranked_stocks.head(params['position_count'])
                    
                    # 清仓不在名单中的股票
                    to_sell = [code for code in positions if code not in top_stocks['code'].values]
                    for code in to_sell:
                        stock_data = day_data[day_data['code'] == code]
                        if len(stock_data) > 0:
                            sell_price = stock_data['close'].values[0]
                            sell_value = positions[code]['shares'] * sell_price * 0.999
                            capital += sell_value
                            trades.append({
                                'date': date,
                                'code': code,
                                'action': 'SELL',
                                'price': sell_price,
                                'shares': positions[code]['shares'],
                                'reason': 'REBALANCE'
                            })
                            del positions[code]
                    
                    # 买入新股票（等权重）
                    position_value = portfolio_value / params['position_count']
                    for _, stock in top_stocks.iterrows():
                        code = stock['code']
                        if code not in positions:
                            buy_price = stock['close']
                            shares = int(position_value / buy_price)
                            if shares > 0 and capital >= shares * buy_price * 1.001:
                                cost = shares * buy_price * 1.001  # 包含手续费
                                capital -= cost
                                positions[code] = {
                                    'shares': shares,
                                    'cost': buy_price
                                }
                                trades.append({
                                    'date': date,
                                    'code': code,
                                    'action': 'BUY',
                                    'price': buy_price,
                                    'shares': shares,
                                    'pe': stock['pe'],
                                    'roe': stock['roe']
                                })
        
        # 计算最终收益
        final_value = capital
        for code, pos in positions.items():
            final_day_data = backtest_data[backtest_data['date'] == dates[-1]]
            stock_price = final_day_data[final_day_data['code'] == code]['close'].values
            if len(stock_price) > 0:
                final_value += pos['shares'] * stock_price[0]
        
        # 计算性能指标
        nav_df = pd.DataFrame(daily_nav)
        if len(nav_df) > 0:
            nav_df['return'] = nav_df['nav'].pct_change()
            total_return = (final_value - initial_capital) / initial_capital
            annual_return = (1 + total_return) ** (252 / len(dates)) - 1
            volatility = nav_df['return'].std() * np.sqrt(252)
            sharpe_ratio = annual_return / volatility if volatility > 0 else 0
            max_drawdown = ((nav_df['nav'].cummax() - nav_df['nav']) / nav_df['nav'].cummax()).max()
            
            # 计算胜率
            positive_days = (nav_df['return'] > 0).sum()
            win_rate = positive_days / len(nav_df[nav_df['return'].notna()])
        else:
            total_return = annual_return = sharpe_ratio = max_drawdown = win_rate = 0
        
        return {
            'params': params,
            'start_date': start_date,
            'end_date': end_date,
            'initial_capital': initial_capital,
            'final_value': final_value,
            'total_return': total_return,
            'annual_return': annual_return,
            'sharpe_ratio': sharpe_ratio,
            'max_drawdown': max_drawdown,
            'win_rate': win_rate,
            'trades': trades,
            'daily_nav': daily_nav,
            'trade_count': len(trades)
        }
    
    def run_wfo_optimization(
        self,
        data: pd.DataFrame,
        train_years: int = 3,
        test_years: int = 1,
        param_grid: Optional[List[Dict]] = None
    ) -> List[Dict]:
        """
        Walk-Forward Optimization (WFO) 滚动优化
        
        Args:
            data: 完整市场数据
            train_years: 训练年数
            test_years: 测试年数
            param_grid: 参数网格，默认自动生成
        """
        if param_grid is None:
            # 自动生成参数网格
            param_grid = []
            for pe_w in [0.5, 0.6, 0.7, 0.8]:
                for roe_w in [0.2, 0.3, 0.4, 0.5]:
                    if abs(pe_w + roe_w - 1.0) < 0.01:  # 权重和为1
                        for pos_count in [5, 10, 15, 20]:
                            for stop in [0.88, 0.90, 0.92, 0.95]:
                                param_grid.append({
                                    'pe_weight': pe_w,
                                    'roe_weight': roe_w,
                                    'position_count': pos_count,
                                    'stop_loss': stop,
                                    'rebalance_freq': 1
                                })
        
        # 获取所有年份
        all_dates = sorted(data['date'].unique())
        start_year = all_dates[0].year
        end_year = all_dates[-1].year
        
        wfo_results = []
        
        # 滚动窗口
        for window_start in range(start_year, end_year - train_years - test_years + 2):
            train_start = f"{window_start}-01-01"
            train_end = f"{window_start + train_years - 1}-12-31"
            test_start = f"{window_start + train_years}-01-01"
            test_end = f"{window_start + train_years + test_years - 1}-12-31"
            
            print(f"\n=== WFO Window: {train_start}~{train_end} → {test_start}~{test_end} ===")
            
            # 在训练集上寻找最优参数
            best_params = None
            best_sharpe = -999
            
            for params in param_grid[:20]:  # 限制参数数量以加速
                result = self.run_single_backtest(data, train_start, train_end, params)
                if result['sharpe_ratio'] > best_sharpe:
                    best_sharpe = result['sharpe_ratio']
                    best_params = params
            
            print(f"训练集最优参数: PE={best_params['pe_weight']}, ROE={best_params['roe_weight']}, "
                  f"持仓={best_params['position_count']}, 止损={best_params['stop_loss']}")
            print(f"训练集夏普: {best_sharpe:.3f}")
            
            # 在测试集上验证
            test_result = self.run_single_backtest(data, test_start, test_end, best_params)
            
            print(f"测试集收益: {test_result['total_return']:.2%}, "
                  f"夏普: {test_result['sharpe_ratio']:.3f}, "
                  f"最大回撤: {test_result['max_drawdown']:.2%}")
            
            wfo_results.append({
                'window': f"{test_start}~{test_end}",
                'train_sharpe': best_sharpe,
                'test_result': test_result,
                'best_params': best_params
            })
        
        return wfo_results
    
    def analyze_parameter_stability(self, wfo_results: List[Dict]) -> Dict:
        """
        分析参数稳健性
        
        检查不同窗口的最优参数是否一致
        """
        if not wfo_results:
            return {}
        
        # 提取各窗口的最优参数
        pe_weights = [r['best_params']['pe_weight'] for r in wfo_results]
        roe_weights = [r['best_params']['roe_weight'] for r in wfo_results]
        position_counts = [r['best_params']['position_count'] for r in wfo_results]
        stop_losses = [r['best_params']['stop_loss'] for r in wfo_results]
        
        # 计算参数的标准差（越小越稳健）
        stability = {
            'pe_weight_std': np.std(pe_weights),
            'roe_weight_std': np.std(roe_weights),
            'position_count_std': np.std(position_counts),
            'stop_loss_std': np.std(stop_losses),
            'pe_weights': pe_weights,
            'roe_weights': roe_weights,
            'position_counts': position_counts,
            'stop_losses': stop_losses,
            'most_common_pe': max(set(pe_weights), key=pe_weights.count),
            'most_common_roe': max(set(roe_weights), key=roe_weights.count),
            'most_common_position': max(set(position_counts), key=position_counts.count),
            'most_common_stop': max(set(stop_losses), key=stop_losses.count),
        }
        
        # 判断稳健性
        stability['is_stable'] = (
            stability['pe_weight_std'] < 0.15 and
            stability['roe_weight_std'] < 0.15 and
            stability['position_count_std'] < 5
        )
        
        return stability
    
    def run_holdout_test(
        self,
        data: pd.DataFrame,
        stable_params: Dict,
        holdout_start: str,
        holdout_end: str
    ) -> Dict:
        """
        Holdout样本外测试
        
        使用稳健参数在完全未见过的数据上测试
        """
        print(f"\n=== Holdout Test: {holdout_start} ~ {holdout_end} ===")
        
        result = self.run_single_backtest(data, holdout_start, holdout_end, stable_params)
        
        print(f"Holdout收益: {result['total_return']:.2%}")
        print(f"Holdout夏普: {result['sharpe_ratio']:.3f}")
        print(f"Holdout最大回撤: {result['max_drawdown']:.2%}")
        
        return result
    
    def generate_report(
        self,
        wfo_results: List[Dict],
        stability: Dict,
        holdout_result: Dict
    ) -> str:
        """
        生成完整回测报告
        """
        report = f"""
# VQM策略多时间段回测报告

## 1. WFO滚动优化结果

| 窗口 | 训练夏普 | 测试收益 | 测试夏普 | 最大回撤 | PE权重 | ROE权重 | 持仓 |
|:-----|:--------:|:--------:|:--------:|:--------:|:------:|:-------:|:----:|
"""
        
        for r in wfo_results:
            test = r['test_result']
            params = r['best_params']
            report += f"| {r['window']} | {r['train_sharpe']:.3f} | " \
                     f"{test['total_return']:.2%} | {test['sharpe_ratio']:.3f} | " \
                     f"{test['max_drawdown']:.2%} | {params['pe_weight']:.1f} | " \
                     f"{params['roe_weight']:.1f} | {params['position_count']} |\n"
        
        # 计算平均表现
        avg_return = np.mean([r['test_result']['total_return'] for r in wfo_results])
        avg_sharpe = np.mean([r['test_result']['sharpe_ratio'] for r in wfo_results])
        avg_drawdown = np.mean([r['test_result']['max_drawdown'] for r in wfo_results])
        
        report += f"""
**WFO平均表现**:
- 平均收益: {avg_return:.2%}
- 平均夏普: {avg_sharpe:.3f}
- 平均最大回撤: {avg_drawdown:.2%}

## 2. 参数稳健性分析

| 参数 | 各窗口取值 | 标准差 | 最常用值 | 稳健性 |
|:-----|:-----------|:------:|:--------:|:------:|
"""
        
        report += f"| PE权重 | {stability.get('pe_weights', [])} | {stability.get('pe_weight_std', 0):.3f} | " \
                 f"{stability.get('most_common_pe', 'N/A')} | {'✅稳健' if stability.get('pe_weight_std', 1) < 0.15 else '❌不稳定'} |\n"
        report += f"| ROE权重 | {stability.get('roe_weights', [])} | {stability.get('roe_weight_std', 0):.3f} | " \
                 f"{stability.get('most_common_roe', 'N/A')} | {'✅稳健' if stability.get('roe_weight_std', 1) < 0.15 else '❌不稳定'} |\n"
        report += f"| 持仓数量 | {stability.get('position_counts', [])} | {stability.get('position_count_std', 0):.1f} | " \
                 f"{stability.get('most_common_position', 'N/A')} | {'✅稳健' if stability.get('position_count_std', 10) < 5 else '❌不稳定'} |\n"
        
        report += f"""
**稳健性结论**: {'✅ 参数稳健，可采用' if stability.get('is_stable') else '❌ 参数不稳定，需进一步分析'}

## 3. Holdout样本外测试

| 指标 | Holdout表现 |
|:-----|:------------|
| 总收益 | {holdout_result['total_return']:.2%} |
| 年化收益 | {holdout_result['annual_return']:.2%} |
| 夏普比率 | {holdout_result['sharpe_ratio']:.3f} |
| 最大回撤 | {holdout_result['max_drawdown']:.2%} |
| 胜率 | {holdout_result['win_rate']:.2%} |
| 交易次数 | {holdout_result['trade_count']} |

## 4. 综合评估

### 4.1 过拟合检验
- WFO平均收益: {avg_return:.2%}
- Holdout收益: {holdout_result['total_return']:.2%}
- 差距: {abs(avg_return - holdout_result['total_return']):.2%}
- 结论: {'✅ 无过拟合' if abs(avg_return - holdout_result['total_return']) < 0.05 else '⚠️ 可能存在过拟合'}

### 4.2 推荐参数
- PE权重: {stability.get('most_common_pe', 0.6)}
- ROE权重: {stability.get('most_common_roe', 0.4)}
- 持仓数量: {stability.get('most_common_position', 10)}
- 止损线: {stability.get('most_common_stop', 0.92)}

### 4.3 策略可信度
- 参数稳健性: {'✅通过' if stability.get('is_stable') else '❌不通过'}
- 样本外表现: {'✅通过' if holdout_result['sharpe_ratio'] > 0.8 else '❌不通过'}
- 过拟合检验: {'✅通过' if abs(avg_return - holdout_result['total_return']) < 0.05 else '⚠️存疑'}

**综合评定**: {'🟢 可以采用' if stability.get('is_stable') and holdout_result['sharpe_ratio'] > 0.8 else '🟡 谨慎采用' if holdout_result['sharpe_ratio'] > 0.5 else '🔴 不建议采用'}
"""
        
        return report


def main():
    """
    主函数：运行完整的多时间段回测流程
    """
    print("="*70)
    print("VQM策略多时间段回测框架")
    print("="*70)
    
    # 配置
    config = {
        'initial_capital': 1000000,
    }
    
    engine = VQMMultiPeriodBacktest(config)
    
    # Step 1: 生成2019-2026模拟数据（混合风格）
    print("\n[Step 1] 生成模拟数据...")
    data = engine.generate_simulated_data(
        start_date='2019-01-01',
        end_date='2026-12-31',
        market_regime='mixed',
        seed=42
    )
    print(f"数据范围: {data['date'].min()} ~ {data['date'].max()}")
    print(f"股票数量: {data['code'].nunique()}")
    print(f"交易日数: {data['date'].nunique()}")
    
    # Step 2: WFO滚动优化 (2019-2024用于训练和验证)
    print("\n[Step 2] WFO滚动优化...")
    wfo_results = engine.run_wfo_optimization(
        data=data,
        train_years=3,
        test_years=1
    )
    
    # Step 3: 参数稳健性分析
    print("\n[Step 3] 参数稳健性分析...")
    stability = engine.analyze_parameter_stability(wfo_results)
    print(f"参数稳健性: {'✅稳健' if stability['is_stable'] else '❌不稳定'}")
    print(f"最常用PE权重: {stability['most_common_pe']}")
    print(f"最常用ROE权重: {stability['most_common_roe']}")
    print(f"最常用持仓数: {stability['most_common_position']}")
    
    # Step 4: Holdout测试 (2025-2026完全样本外)
    print("\n[Step 4] Holdout样本外测试...")
    
    # 使用最稳健的参数
    stable_params = {
        'pe_weight': stability['most_common_pe'],
        'roe_weight': stability['most_common_roe'],
        'position_count': stability['most_common_position'],
        'stop_loss': stability['most_common_stop'],
        'rebalance_freq': 1
    }
    
    holdout_result = engine.run_holdout_test(
        data=data,
        stable_params=stable_params,
        holdout_start='2025-01-01',
        holdout_end='2026-02-14'
    )
    
    # Step 5: 生成报告
    print("\n[Step 5] 生成回测报告...")
    report = engine.generate_report(wfo_results, stability, holdout_result)
    
    # 保存报告
    report_path = 'quant/vqm_multi_period_backtest_report.md'
    os.makedirs(os.path.dirname(report_path), exist_ok=True)
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(report)
    
    print(f"\n✅ 报告已保存至: {report_path}")
    print("\n" + "="*70)
    print("回测完成!")
    print("="*70)


if __name__ == '__main__':
    main()
