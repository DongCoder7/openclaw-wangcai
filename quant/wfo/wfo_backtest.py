#!/usr/bin/env python3
"""
WFO (Walk-Forward Optimization) 回测系统
基于2年训练+1年测试的滚动窗口设计

核心特性:
- 训练窗口: 2年 (样本内 IS)
- 测试窗口: 1年 (样本外 OOS)
- 滚动步长: 每年滚动一次
- 优化方法: 遗传算法 + 早停机制
- 约束条件: 强回撤控制 (<15%)
"""

import os
import sys
import json
import sqlite3
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass, asdict
from concurrent.futures import ProcessPoolExecutor, as_completed
import multiprocessing as mp

sys.path.insert(0, '/root/.openclaw/workspace/tools')
sys.path.insert(0, '/root/.openclaw/workspace/quant')

# 配置路径
DB_PATH = '/root/.openclaw/workspace/data/historical/historical.db'
WFO_DIR = '/root/.openclaw/workspace/quant/wfo'
CONFIG_PATH = f'{WFO_DIR}/wfo_config.json'


@dataclass
class WFOWindow:
    """WFO时间窗口定义"""
    period: int
    train_start: str
    train_end: str
    test_start: str
    test_end: str
    
    def __repr__(self):
        return f"WFOWindow(P{self.period}: Train[{self.train_start}-{self.train_end}] -> Test[{self.test_start}-{self.test_end}])"


@dataclass
class StrategyParams:
    """策略参数"""
    position_pct: float = 0.7
    stop_loss: float = 0.08
    max_holding: int = 5
    rebalance_days: int = 10
    selected_factors: List[str] = None
    factor_weights_method: str = "equal"
    
    def __post_init__(self):
        if self.selected_factors is None:
            self.selected_factors = ['ret_20', 'vol_20', 'price_pos_20', 'sharpe_like']


@dataclass
class BacktestResult:
    """回测结果"""
    annual_return: float = 0.0
    max_drawdown: float = 0.0
    sharpe_ratio: float = 0.0
    calmar_ratio: float = 0.0
    win_rate: float = 0.0
    total_trades: int = 0
    profit_factor: float = 0.0
    volatility: float = 0.0
    equity_curve: List[Dict] = None
    
    def __post_init__(self):
        if self.equity_curve is None:
            self.equity_curve = []
    
    @property
    def risk_adjusted_score(self) -> float:
        """风险调整收益评分 (越高越好)"""
        return self.annual_return * 0.5 - self.max_drawdown * 1.5 + self.sharpe_ratio * 0.3
    
    @property
    def is_valid(self) -> bool:
        """是否满足硬约束条件"""
        return self.max_drawdown > -0.15  # 回撤不能超过15%


class WFOEngine:
    """WFO回测引擎"""
    
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self.config = self._load_config()
        self.windows: List[WFOWindow] = []
        self.results: List[Dict] = []
        
    def _load_config(self) -> Dict:
        """加载配置文件"""
        with open(CONFIG_PATH, 'r') as f:
            return json.load(f)
    
    def generate_windows(self) -> List[WFOWindow]:
        """
        生成WFO时间窗口
        
        配置: 2年训练 + 1年测试，每年滚动
        根据实际数据范围自动调整
        """
        cfg = self.config['wfo']
        train_years = cfg['train_window_years']
        test_years = cfg['test_window_years']
        
        # 获取实际数据范围
        _, _, min_year, max_year = self.get_available_data_range()
        
        # 调整起始年份，确保有足够数据
        # 第一个训练期: min_year ~ min_year + train_years - 1
        # 第一个测试期: min_year + train_years ~ min_year + train_years + test_years - 1
        start_year = min_year
        end_year = max_year
        
        windows = []
        period = 1
        
        current_start = start_year
        
        while current_start + train_years + test_years - 1 <= end_year:
            train_start = f"{current_start}0101"
            train_end = f"{current_start + train_years - 1}1231"
            test_start = f"{current_start + train_years}0101"
            test_end = f"{current_start + train_years + test_years - 1}1231"
            
            window = WFOWindow(
                period=period,
                train_start=train_start,
                train_end=train_end,
                test_start=test_start,
                test_end=test_end
            )
            windows.append(window)
            
            current_start += cfg['roll_step_years']
            period += 1
        
        self.windows = windows
        print(f"✅ 生成 {len(windows)} 个WFO窗口:")
        for w in windows:
            print(f"   {w}")
        
        return windows
    
    def get_available_data_range(self) -> Tuple[str, str]:
        """获取数据库中可用的数据时间范围"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT MIN(trade_date), MAX(trade_date) FROM daily_price')
        min_date, max_date = cursor.fetchone()
        
        conn.close()
        
        # 调整年份边界为完整年份
        min_year = int(min_date[:4])
        max_year = int(max_date[:4])
        
        # 如果数据开始于年初，使用完整年份
        adjusted_min = f"{min_year}0101"
        adjusted_max = f"{max_year}1231"
        
        return adjusted_min, adjusted_max, min_year, max_year
    
    def validate_windows(self) -> bool:
        """验证所有窗口是否在数据范围内"""
        _, _, min_year, max_year = self.get_available_data_range()
        print(f"\n📊 数据库时间范围: {min_year} ~ {max_year}")
        
        valid = True
        for window in self.windows:
            train_start_year = int(window.train_start[:4])
            test_end_year = int(window.test_end[:4])
            
            if train_start_year < min_year or test_end_year > max_year:
                print(f"⚠️ 窗口 {window.period} 超出数据范围!")
                valid = False
        
        if valid:
            print("✅ 所有窗口验证通过")
        
        return valid
    
    def run_single_period(self, window: WFOWindow, save_results: bool = True) -> Dict:
        """
        执行单个WFO周期
        
        步骤:
        1. 在训练期上优化参数 (IS优化)
        2. 在测试期上验证参数 (OOS验证)
        3. 返回完整结果
        """
        print(f"\n{'='*70}")
        print(f"🚀 WFO 周期 {window.period}")
        print(f"{'='*70}")
        print(f"训练期: {window.train_start} ~ {window.train_end}")
        print(f"测试期: {window.test_start} ~ {window.test_end}")
        print(f"{'='*70}\n")
        
        # 步骤1: 训练期优化
        print(f"📚 步骤1: 训练期优化...")
        optimizer = WFOOptimizer(self.db_path, self.config)
        best_params, train_result = optimizer.optimize(
            start_date=window.train_start,
            end_date=window.train_end,
            window_id=window.period
        )
        
        print(f"\n🏆 训练期最优参数:")
        print(f"   仓位: {best_params.position_pct*100:.0f}%")
        print(f"   止损: {best_params.stop_loss*100:.0f}%")
        print(f"   持仓: {best_params.max_holding}只")
        print(f"   调仓: {best_params.rebalance_days}天")
        print(f"   因子: {len(best_params.selected_factors)}个")
        print(f"\n   IS年化收益: {train_result.annual_return*100:+.2f}%")
        print(f"   IS最大回撤: {train_result.max_drawdown*100:.2f}%")
        print(f"   IS夏普比率: {train_result.sharpe_ratio:.2f}")
        
        # 步骤2: 测试期验证
        print(f"\n🧪 步骤2: 测试期验证...")
        validator = WFOValidator(self.db_path)
        test_result = validator.validate(
            start_date=window.test_start,
            end_date=window.test_end,
            params=best_params
        )
        
        print(f"\n📊 测试期结果:")
        print(f"   OOS年化收益: {test_result.annual_return*100:+.2f}%")
        print(f"   OOS最大回撤: {test_result.max_drawdown*100:.2f}%")
        print(f"   OOS夏普比率: {test_result.sharpe_ratio:.2f}")
        
        # 计算衰减
        return_decay = train_result.annual_return - test_result.annual_return
        drawdown_worsening = test_result.max_drawdown - train_result.max_drawdown
        
        print(f"\n📉 衰减分析:")
        print(f"   收益衰减: {return_decay*100:+.2f}%")
        print(f"   回撤恶化: {drawdown_worsening*100:+.2f}%")
        
        # 构建结果
        result = {
            'period': window.period,
            'window': asdict(window),
            'train': {
                'params': asdict(best_params),
                'result': asdict(train_result)
            },
            'test': {
                'result': asdict(test_result)
            },
            'stability': {
                'return_decay': return_decay,
                'drawdown_worsening': drawdown_worsening,
                'robust': abs(return_decay) < 0.10 and test_result.is_valid
            }
        }
        
        # 保存结果
        if save_results:
            self._save_period_result(result)
        
        return result
    
    def _save_period_result(self, result: Dict):
        """保存单个周期结果"""
        output_dir = f'{WFO_DIR}/results'
        os.makedirs(output_dir, exist_ok=True)
        
        filename = f"wfo_period_{result['period']}_{result['window']['test_start'][:4]}.json"
        filepath = f'{output_dir}/{filename}'
        
        with open(filepath, 'w') as f:
            json.dump(result, f, indent=2, default=str)
        
        print(f"\n💾 结果已保存: {filepath}")
    
    def run_full_wfo(self) -> Dict:
        """执行完整WFO流程"""
        print("\n" + "="*70)
        print("🚀 WFO Walk-Forward Optimization 启动")
        print("="*70)
        print(f"配置: 2年训练 + 1年测试 + 每年滚动")
        print(f"约束: 最大回撤 < 15%")
        print(f"优化: 遗传算法")
        print("="*70 + "\n")
        
        # 生成窗口
        self.generate_windows()
        
        # 验证窗口
        if not self.validate_windows():
            raise ValueError("窗口验证失败，请检查数据范围")
        
        # 执行每个周期
        all_results = []
        for window in self.windows:
            result = self.run_single_period(window)
            all_results.append(result)
        
        # 生成汇总报告
        summary = self._generate_summary(all_results)
        
        print(f"\n{'='*70}")
        print("✅ WFO完整流程执行完毕")
        print(f"{'='*70}\n")
        
        return summary
    
    def _generate_summary(self, results: List[Dict]) -> Dict:
        """生成WFO汇总报告"""
        print("\n📊 生成WFO汇总报告...")
        
        summary = {
            'timestamp': datetime.now().isoformat(),
            'config': self.config['wfo'],
            'total_periods': len(results),
            'periods': results,
            'aggregate': self._calculate_aggregate_stats(results),
            'stability_analysis': self._analyze_stability(results)
        }
        
        # 保存汇总报告
        output_dir = f'{WFO_DIR}/results'
        os.makedirs(output_dir, exist_ok=True)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filepath = f'{output_dir}/wfo_summary_{timestamp}.json'
        
        with open(filepath, 'w') as f:
            json.dump(summary, f, indent=2, default=str)
        
        print(f"💾 汇总报告已保存: {filepath}")
        
        # 打印汇总
        self._print_summary(summary)
        
        return summary
    
    def _calculate_aggregate_stats(self, results: List[Dict]) -> Dict:
        """计算汇总统计"""
        test_returns = [r['test']['result']['annual_return'] for r in results]
        test_drawdowns = [r['test']['result']['max_drawdown'] for r in results]
        test_sharpes = [r['test']['result']['sharpe_ratio'] for r in results]
        
        # 拼接OOS收益曲线
        total_return = 1.0
        for r in results:
            total_return *= (1 + r['test']['result']['annual_return'])
        
        years = len(results)
        cagr = (total_return ** (1/years) - 1) if years > 0 else 0
        
        return {
            'oos_cagr': cagr,
            'oos_avg_annual_return': np.mean(test_returns),
            'oos_std_annual_return': np.std(test_returns),
            'oos_avg_max_drawdown': np.mean(test_drawdowns),
            'oos_worst_drawdown': min(test_drawdowns),
            'oos_avg_sharpe': np.mean(test_sharpes),
            'period_count': len(results)
        }
    
    def _analyze_stability(self, results: List[Dict]) -> Dict:
        """分析策略稳定性"""
        decays = [r['stability']['return_decay'] for r in results]
        robust_count = sum(1 for r in results if r['stability']['robust'])
        
        return {
            'avg_return_decay': np.mean(decays),
            'max_return_decay': max(abs(d) for d in decays),
            'robust_periods': robust_count,
            'robust_ratio': robust_count / len(results) if results else 0,
            'is_stable': robust_count / len(results) > 0.6 if results else False
        }
    
    def _print_summary(self, summary: Dict):
        """打印汇总报告"""
        agg = summary['aggregate']
        stab = summary['stability_analysis']
        
        print(f"\n{'='*70}")
        print("📊 WFO 汇总报告")
        print(f"{'='*70}")
        
        print(f"\n【样本外业绩拼接】({summary['total_periods']}个周期)")
        for r in summary['periods']:
            w = r['window']
            year = w['test_start'][:4]
            is_ret = r['train']['result']['annual_return'] * 100
            oos_ret = r['test']['result']['annual_return'] * 100
            decay = r['stability']['return_decay'] * 100
            robust = "✅" if r['stability']['robust'] else "❌"
            print(f"  {year}: IS={is_ret:+.1f}% | OOS={oos_ret:+.1f}% | 衰减={decay:+.1f}% {robust}")
        
        print(f"\n【汇总统计】")
        print(f"  OOS年化收益(CAGR): {agg['oos_cagr']*100:+.2f}%")
        print(f"  OOS平均年化收益: {agg['oos_avg_annual_return']*100:+.2f}%")
        print(f"  OOS平均最大回撤: {agg['oos_avg_max_drawdown']*100:.2f}%")
        print(f"  OOS最差回撤: {agg['oos_worst_drawdown']*100:.2f}%")
        print(f"  OOS平均夏普: {agg['oos_avg_sharpe']:.2f}")
        
        print(f"\n【稳定性分析】")
        print(f"  平均收益衰减: {stab['avg_return_decay']*100:.2f}%")
        print(f"  最大衰减: {stab['max_return_decay']*100:.2f}%")
        print(f"  稳健周期: {stab['robust_periods']}/{summary['total_periods']}")
        print(f"  稳健率: {stab['robust_ratio']*100:.0f}%")
        print(f"  策略稳定性: {'✅ 稳定' if stab['is_stable'] else '⚠️ 不稳定'}")
        
        print(f"\n{'='*70}\n")


class WFOOptimizer:
    """WFO优化器 - 遗传算法实现"""
    
    def __init__(self, db_path: str, config: Dict):
        self.db_path = db_path
        self.config = config
        self.population_size = config['optimization']['population_size']
        self.generations = config['optimization']['generations']
        self.mutation_rate = config['optimization']['mutation_rate']
        self.crossover_rate = config['optimization']['crossover_rate']
        
    def optimize(self, start_date: str, end_date: str, window_id: int) -> Tuple[StrategyParams, BacktestResult]:
        """在训练期上优化参数"""
        print(f"   初始化种群 ({self.population_size}个体)...")
        
        population = self._init_population()
        best_individual = None
        best_fitness = -np.inf
        generations_without_improvement = 0
        
        for gen in range(self.generations):
            # 评估种群
            fitness_scores = []
            for individual in population:
                fitness = self._evaluate_individual(individual, start_date, end_date)
                fitness_scores.append(fitness)
                
                if fitness > best_fitness:
                    best_fitness = fitness
                    best_individual = individual
                    generations_without_improvement = 0
            
            generations_without_improvement += 1
            
            # 早停检查
            if self.config['optimization']['early_stopping']['enabled']:
                patience = self.config['optimization']['early_stopping']['patience']
                if generations_without_improvement >= patience:
                    print(f"   ⏹️ 早停于第 {gen+1} 代 (无改善{patience}代)")
                    break
            
            if (gen + 1) % 5 == 0:
                print(f"   第 {gen+1}/{self.generations} 代: 最佳适应度={best_fitness:.4f}")
            
            # 选择、交叉、变异
            population = self._evolve_population(population, fitness_scores)
        
        # 最终评估最优个体
        result = self._run_backtest(best_individual, start_date, end_date)
        
        return best_individual, result
    
    def _init_population(self) -> List[StrategyParams]:
        """初始化种群"""
        population = []
        param_space = self.config['param_space']
        
        for _ in range(self.population_size):
            params = StrategyParams(
                position_pct=self._random_float(param_space['position_pct']),
                stop_loss=self._random_float(param_space['stop_loss']),
                max_holding=self._random_int(param_space['max_holding']),
                rebalance_days=self._random_int(param_space['rebalance_days']),
                selected_factors=self._random_factors(param_space['factor_selection']),
                factor_weights_method=np.random.choice(param_space['factor_weights_method']['options'])
            )
            population.append(params)
        
        return population
    
    def _random_float(self, spec: Dict) -> float:
        """随机生成浮点数"""
        min_val, max_val, step = spec['min'], spec['max'], spec['step']
        steps = int((max_val - min_val) / step)
        return min_val + np.random.randint(0, steps + 1) * step
    
    def _random_int(self, spec: Dict) -> int:
        """随机生成整数"""
        return np.random.randint(spec['min'], spec['max'] + 1)
    
    def _random_factors(self, spec: Dict) -> List[str]:
        """随机选择因子子集"""
        available = spec['available_factors']
        count = np.random.randint(spec['min_factors'], spec['max_factors'] + 1)
        return list(np.random.choice(available, size=count, replace=False))
    
    def _evaluate_individual(self, params: StrategyParams, start_date: str, end_date: str) -> float:
        """评估单个个体"""
        result = self._run_backtest(params, start_date, end_date)
        
        # 应用约束惩罚
        fitness = result.risk_adjusted_score
        
        # 硬约束: 最大回撤
        if result.max_drawdown < -0.15:
            fitness -= 10.0  # 大幅惩罚
        
        # 软约束: 最低收益
        if result.annual_return < 0.10:
            fitness -= (0.10 - result.annual_return) * 2
        
        return fitness
    
    def _run_backtest(self, params: StrategyParams, start_date: str, end_date: str) -> BacktestResult:
        """执行回测 (简化版，实际应连接数据库)"""
        # TODO: 实现真实回测逻辑
        # 这里使用模拟数据演示框架
        
        # 模拟: 参数越好，收益越高
        base_return = 0.10
        pos_bonus = (params.position_pct - 0.5) * 0.20
        sl_penalty = (params.stop_loss - 0.08) * 0.10
        factor_bonus = len(params.selected_factors) * 0.005
        
        annual_return = base_return + pos_bonus - sl_penalty + factor_bonus + np.random.randn() * 0.05
        max_drawdown = -(0.08 + np.random.rand() * 0.10)
        sharpe = annual_return / 0.15 if annual_return > 0 else 0
        
        return BacktestResult(
            annual_return=annual_return,
            max_drawdown=max_drawdown,
            sharpe_ratio=sharpe
        )
    
    def _evolve_population(self, population: List[StrategyParams], fitness_scores: List[float]) -> List[StrategyParams]:
        """进化种群"""
        new_population = []
        
        # 保留精英
        elite_idx = np.argmax(fitness_scores)
        new_population.append(population[elite_idx])
        
        # 轮盘赌选择 + 交叉 + 变异
        while len(new_population) < len(population):
            parent1 = self._select_parent(population, fitness_scores)
            parent2 = self._select_parent(population, fitness_scores)
            
            if np.random.rand() < self.crossover_rate:
                child = self._crossover(parent1, parent2)
            else:
                child = parent1
            
            if np.random.rand() < self.mutation_rate:
                child = self._mutate(child)
            
            new_population.append(child)
        
        return new_population
    
    def _select_parent(self, population: List[StrategyParams], fitness_scores: List[float]) -> StrategyParams:
        """轮盘赌选择"""
        fitness_array = np.array(fitness_scores)
        fitness_array = fitness_array - fitness_array.min() + 1e-6  # 确保正数
        probs = fitness_array / fitness_array.sum()
        idx = np.random.choice(len(population), p=probs)
        return population[idx]
    
    def _crossover(self, p1: StrategyParams, p2: StrategyParams) -> StrategyParams:
        """交叉操作"""
        return StrategyParams(
            position_pct=p1.position_pct if np.random.rand() < 0.5 else p2.position_pct,
            stop_loss=p1.stop_loss if np.random.rand() < 0.5 else p2.stop_loss,
            max_holding=p1.max_holding if np.random.rand() < 0.5 else p2.max_holding,
            rebalance_days=p1.rebalance_days if np.random.rand() < 0.5 else p2.rebalance_days,
            selected_factors=p1.selected_factors if np.random.rand() < 0.5 else p2.selected_factors,
            factor_weights_method=p1.factor_weights_method if np.random.rand() < 0.5 else p2.factor_weights_method
        )
    
    def _mutate(self, params: StrategyParams) -> StrategyParams:
        """变异操作"""
        param_space = self.config['param_space']
        
        if np.random.rand() < 0.2:
            params.position_pct = self._random_float(param_space['position_pct'])
        if np.random.rand() < 0.2:
            params.stop_loss = self._random_float(param_space['stop_loss'])
        if np.random.rand() < 0.2:
            params.max_holding = self._random_int(param_space['max_holding'])
        if np.random.rand() < 0.2:
            params.rebalance_days = self._random_int(param_space['rebalance_days'])
        if np.random.rand() < 0.2:
            params.selected_factors = self._random_factors(param_space['factor_selection'])
        
        return params


class WFOValidator:
    """WFO验证器 - OOS测试"""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
    
    def validate(self, start_date: str, end_date: str, params: StrategyParams) -> BacktestResult:
        """在测试期上验证参数"""
        # TODO: 实现真实回测验证
        # 这里使用与optimizer相同的简化逻辑
        
        base_return = 0.08  # OOS通常比IS略低
        pos_bonus = (params.position_pct - 0.5) * 0.18
        sl_penalty = (params.stop_loss - 0.08) * 0.08
        factor_bonus = len(params.selected_factors) * 0.004
        
        annual_return = base_return + pos_bonus - sl_penalty + factor_bonus + np.random.randn() * 0.04
        max_drawdown = -(0.10 + np.random.rand() * 0.08)
        sharpe = annual_return / 0.14 if annual_return > 0 else 0
        
        return BacktestResult(
            annual_return=annual_return,
            max_drawdown=max_drawdown,
            sharpe_ratio=sharpe
        )


def main():
    """主函数"""
    engine = WFOEngine()
    summary = engine.run_full_wfo()
    
    # 生成Markdown报告
    report_generator = WFOReportGenerator()
    report_path = report_generator.generate(summary)
    
    print(f"\n📄 Markdown报告: {report_path}")
    
    return summary


class WFOReportGenerator:
    """WFO报告生成器"""
    
    def generate(self, summary: Dict) -> str:
        """生成Markdown报告"""
        output_dir = f'{WFO_DIR}/results'
        os.makedirs(output_dir, exist_ok=True)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filepath = f'{output_dir}/wfo_report_{timestamp}.md'
        
        lines = [
            "# WFO (Walk-Forward Optimization) 回测报告",
            "",
            f"**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            f"**配置**: 2年训练 + 1年测试 + 每年滚动",
            "",
            "## 一、执行摘要",
            "",
        ]
        
        agg = summary['aggregate']
        stab = summary['stability_analysis']
        
        lines.append(f"- **OOS年化收益(CAGR)**: {agg['oos_cagr']*100:+.2f}%")
        lines.append(f"- **OOS平均年化收益**: {agg['oos_avg_annual_return']*100:+.2f}%")
        lines.append(f"- **OOS平均最大回撤**: {agg['oos_avg_max_drawdown']*100:.2f}%")
        lines.append(f"- **OOS平均夏普比率**: {agg['oos_avg_sharpe']:.2f}")
        lines.append(f"- **稳健周期比例**: {stab['robust_ratio']*100:.0f}%")
        lines.append(f"- **策略稳定性**: {'✅ 通过' if stab['is_stable'] else '❌ 未通过'}")
        lines.append("")
        
        lines.append("## 二、各周期详细结果")
        lines.append("")
        lines.append("| 周期 | 年份 | IS收益 | OOS收益 | 衰减 | 回撤 | 夏普 | 稳健 |")
        lines.append("|:----:|:----:|:------:|:-------:|:----:|:----:|:----:|:----:|")
        
        for r in summary['periods']:
            year = r['window']['test_start'][:4]
            is_ret = r['train']['result']['annual_return'] * 100
            oos_ret = r['test']['result']['annual_return'] * 100
            decay = r['stability']['return_decay'] * 100
            dd = r['test']['result']['max_drawdown'] * 100
            sharpe = r['test']['result']['sharpe_ratio']
            robust = "✅" if r['stability']['robust'] else "❌"
            lines.append(f"| {r['period']} | {year} | {is_ret:+.1f}% | {oos_ret:+.1f}% | {decay:+.1f}% | {dd:.1f}% | {sharpe:.2f} | {robust} |")
        
        lines.append("")
        lines.append("## 三、样本外拼接业绩曲线")
        lines.append("")
        lines.append("```")
        lines.append("累计收益计算:")
        
        total_return = 1.0
        for r in summary['periods']:
            year = r['window']['test_start'][:4]
            ret = r['test']['result']['annual_return']
            total_return *= (1 + ret)
            lines.append(f"  {year}: {ret*100:+.2f}% (累计: {(total_return-1)*100:+.2f}%)")
        
        lines.append("```")
        lines.append("")
        
        lines.append("## 四、结论与建议")
        lines.append("")
        
        if stab['is_stable'] and agg['oos_cagr'] > 0.10:
            lines.append("✅ **策略通过WFO验证**")
            lines.append("")
            lines.append("- 样本外表现稳定，参数鲁棒性良好")
            lines.append("- 建议将该策略投入实盘交易")
        elif stab['is_stable']:
            lines.append("⚠️ **策略表现一般**")
            lines.append("")
            lines.append("- 参数稳定性尚可，但收益未达预期")
            lines.append("- 建议优化因子选择或调整策略逻辑")
        else:
            lines.append("❌ **策略未通过WFO验证**")
            lines.append("")
            lines.append("- 样本外表现不稳定，存在过拟合风险")
            lines.append("- 建议：")
            lines.append("  1. 增加训练窗口长度")
            lines.append("  2. 减少参数搜索空间")
            lines.append("  3. 增加正则化约束")
        
        lines.append("")
        lines.append("---")
        lines.append(f"*报告生成: WFO系统 v1.0*")
        
        with open(filepath, 'w') as f:
            f.write('\n'.join(lines))
        
        return filepath


if __name__ == '__main__':
    main()
