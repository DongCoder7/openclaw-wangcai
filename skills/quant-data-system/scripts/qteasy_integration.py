#!/root/.openclaw/workspace/venv/bin/python3
"""
qteasy集成模块 - 与现有量化系统的桥接层
提供快速回测验证、基准对照、实盘执行能力
"""

import sys
import os
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta

# qteasy集成标志
try:
    import qteasy as qt
    QTEASY_AVAILABLE = True
except ImportError:
    QTEASY_AVAILABLE = False
    print("⚠️ qteasy未安装，请先运行: pip3 install qteasy --user")

# 导入现有系统模块
sys.path.insert(0, '/root/.openclaw/workspace')
sys.path.insert(0, '/root/.openclaw/workspace/skills/quant-data-system/scripts')

try:
    from data_manager import QuantDataManager
    DATA_MANAGER_AVAILABLE = True
except ImportError:
    DATA_MANAGER_AVAILABLE = False


class QteasyIntegration:
    """
    qteasy与现有量化系统的集成桥接器
    
    核心功能:
    1. 快速策略验证 - 向量化回测筛选策略idea
    2. 基准对照 - 内置经典策略作为benchmark
    3. 组合优化 - 马科维茨等经典方法
    4. 实盘执行 - 交易信号执行层
    """
    
    def __init__(self, data_source: str = 'tushare'):
        """
        初始化集成器
        
        Args:
            data_source: 数据源 ('tushare' 或 'local')
        """
        if not QTEASY_AVAILABLE:
            raise ImportError("qteasy未安装，请先安装: pip3 install qteasy --user")
        
        self.qt = qt
        self.data_source = data_source
        
        # 配置qteasy数据源
        self._configure_datasource()
        
        # 内置策略映射
        self.builtin_strategies = {
            'sma_cross': self.qt.built_in.CROSSLINE,  # 均线交叉策略
            'macd': self.qt.built_in.MACD,             # MACD策略
            'rsi': self.qt.built_in.RSI,               # RSI策略
            'boll': self.qt.built_in.BBand,            # 布林带策略
            'cci': self.qt.built_in.CCI,               # CCI策略
            'adx': self.qt.built_in.ADX,               # ADX策略
        }
    
    def _configure_datasource(self):
        """配置qteasy数据源"""
        # 暂时不配置，使用默认设置
        # qteasy会自动使用环境或默认配置
        pass
    
    def quick_backtest(self, 
                       strategy_name: str,
                       stock_codes: List[str],
                       start_date: str,
                       end_date: str,
                       params: Optional[Dict] = None) -> Dict:
        """
        快速策略回测 - 向量化回测，5分钟出结果
        
        Args:
            strategy_name: 策略名称 ('sma_cross', 'macd', 'rsi', etc.)
            stock_codes: 股票代码列表 ['000001.SZ', '000002.SZ']
            start_date: 开始日期 '20240101'
            end_date: 结束日期 '20241231'
            params: 策略参数 {'window': 20}
            
        Returns:
            回测结果字典
        """
        if strategy_name not in self.builtin_strategies:
            raise ValueError(f"未知策略: {strategy_name}, 可用: {list(self.builtin_strategies.keys())}")
        
        # 获取策略类
        StrategyClass = self.builtin_strategies[strategy_name]
        
        # 创建策略实例
        if params:
            strategy = StrategyClass(pars=tuple(params.values()))
        else:
            strategy = StrategyClass()
        
        # 创建操作器
        op = qt.Operator(strategy)
        
        # 运行回测
        results = op.run(
            mode=1,  # 回测模式
            invest_start=start_date,
            invest_end=end_date,
            asset_pool=stock_codes,
            invest_cash=1000000,  # 100万初始资金
            benchmark='000300.SH'  # 沪深300基准
        )
        
        # 格式化结果
        return {
            'strategy': strategy_name,
            'stocks': stock_codes,
            'period': f"{start_date}-{end_date}",
            'total_return': results.get('total_return', 0),
            'annual_return': results.get('annual_return', 0),
            'sharpe_ratio': results.get('sharpe', 0),
            'max_drawdown': results.get('max_drawdown', 0),
            'win_rate': results.get('win_rate', 0),
            'benchmark_return': results.get('benchmark_return', 0),
            'alpha': results.get('alpha', 0),
            'beta': results.get('beta', 0),
            'trades': results.get('trade_log', [])
        }
    
    def benchmark_comparison(self,
                           our_strategy_returns: pd.Series,
                           stock_codes: List[str],
                           start_date: str,
                           end_date: str) -> Dict:
        """
        我们的策略 vs qteasy内置策略对照
        
        Args:
            our_strategy_returns: 我们策略的日收益率序列
            stock_codes: 股票代码列表
            start_date: 开始日期
            end_date: 结束日期
            
        Returns:
            对照结果
        """
        benchmarks = {}
        
        # 测试qteasy经典策略
        for name in ['sma_cross', 'macd', 'rsi']:
            try:
                result = self.quick_backtest(
                    name, stock_codes, start_date, end_date
                )
                benchmarks[name] = {
                    'annual_return': result['annual_return'],
                    'sharpe': result['sharpe_ratio'],
                    'max_dd': result['max_drawdown']
                }
            except Exception as e:
                print(f"回测{name}失败: {e}")
        
        # 计算我们策略的指标
        our_metrics = {
            'annual_return': our_strategy_returns.mean() * 252,
            'sharpe': our_strategy_returns.mean() / our_strategy_returns.std() * np.sqrt(252),
            'max_dd': (our_strategy_returns.cumsum() - our_strategy_returns.cumsum().cummax()).min()
        }
        
        return {
            'our_strategy': our_metrics,
            'benchmarks': benchmarks,
            'comparison': {
                name: {
                    'excess_return': our_metrics['annual_return'] - b['annual_return'],
                    'sharpe_diff': our_metrics['sharpe'] - b['sharpe']
                }
                for name, b in benchmarks.items()
            }
        }
    
    def optimize_portfolio(self,
                          stock_codes: List[str],
                          method: str = 'markowitz',
                          target: str = 'sharpe',
                          risk_free_rate: float = 0.03) -> Dict:
        """
        投资组合优化 - 马科维茨等经典方法
        
        Args:
            stock_codes: 股票代码列表
            method: 优化方法 ('markowitz', 'risk_parity', 'equal_weight')
            target: 优化目标 ('sharpe', 'return', 'risk')
            risk_free_rate: 无风险利率
            
        Returns:
            优化结果
        """
        if method == 'markowitz':
            # 马科维茨均值-方差优化
            result = qt.optimize_portfolio(
                symbols=stock_codes,
                method='markowitz',
                target=target,
                risk_free_rate=risk_free_rate
            )
        elif method == 'risk_parity':
            # 风险平价
            result = qt.optimize_portfolio(
                symbols=stock_codes,
                method='risk_parity'
            )
        else:
            # 等权重
            result = {code: 1.0/len(stock_codes) for code in stock_codes}
        
        return {
            'method': method,
            'target': target,
            'weights': result.get('weights', result),
            'expected_return': result.get('expected_return', 0),
            'expected_risk': result.get('expected_risk', 0),
            'sharpe_ratio': result.get('sharpe_ratio', 0)
        }
    
    def execute_signals(self,
                       signals: pd.DataFrame,
                       broker: str = 'simulator',
                       **broker_config) -> Dict:
        """
        执行交易信号 - 实盘/模拟盘交易层
        
        Args:
            signals: 交易信号DataFrame (code, date, action, weight)
            broker: 券商 ('simulator', 'ths', 'htsc')
            **broker_config: 券商配置参数
            
        Returns:
            执行结果
        """
        if broker == 'simulator':
            # 模拟盘执行
            return self._execute_simulator(signals)
        else:
            # 实盘执行 (需要配置券商API)
            # TODO: 配置实盘交易
            # qt.configure(mode='live', broker=broker, **broker_config)
            # return qt.execute_trade(signals)
            raise NotImplementedError("实盘交易需要配置券商API")
    
    def _execute_simulator(self, signals: pd.DataFrame) -> Dict:
        """模拟盘执行"""
        executed = []
        for _, row in signals.iterrows():
            executed.append({
                'date': row['date'],
                'code': row['code'],
                'action': row['action'],
                'weight': row['weight'],
                'status': 'simulated'
            })
        return {
            'mode': 'simulator',
            'executed_count': len(executed),
            'orders': executed
        }
    
    def get_builtin_strategy_list(self) -> List[Dict]:
        """获取内置策略列表"""
        return [
            {'name': name, 'class': cls.__name__, 'description': cls.__doc__}
            for name, cls in self.builtin_strategies.items()
        ]


class QteasySignalBridge:
    """
    信号桥接器 - 将我们的策略信号转换为qteasy可执行格式
    """
    
    @staticmethod
    def convert_signals(our_signals: pd.DataFrame) -> pd.DataFrame:
        """
        转换信号格式
        
        Args:
            our_signals: 我们的信号格式 (date, code, signal_weight)
            
        Returns:
            qteasy格式信号
        """
        # 转换列名
        qt_signals = our_signals.rename(columns={
            'date': 'date',
            'code': 'symbol',
            'signal_weight': 'weight'
        })
        
        # 添加action列
        qt_signals['action'] = qt_signals['weight'].apply(
            lambda x: 'buy' if x > 0 else ('sell' if x < 0 else 'hold')
        )
        
        return qt_signals[['date', 'symbol', 'action', 'weight']]


# 便捷函数
def quick_backtest(strategy: str, stocks: List[str], start: str, end: str) -> Dict:
    """快速回测便捷函数"""
    integrator = QteasyIntegration()
    return integrator.quick_backtest(strategy, stocks, start, end)


def compare_with_benchmark(our_returns: pd.Series, stocks: List[str], start: str, end: str) -> Dict:
    """基准对照便捷函数"""
    integrator = QteasyIntegration()
    return integrator.benchmark_comparison(our_returns, stocks, start, end)


def optimize_weights(stocks: List[str], method: str = 'markowitz') -> Dict:
    """组合优化便捷函数"""
    integrator = QteasyIntegration()
    return integrator.optimize_portfolio(stocks, method)


if __name__ == "__main__":
    # 测试
    if QTEASY_AVAILABLE:
        print("🧪 测试qteasy集成...")
        print("="*60)
        
        # 测试快速回测
        print("\n测试双均线策略回测...")
        result = quick_backtest(
            strategy='sma_cross',
            stocks=['000001.SZ', '000002.SZ'],
            start='20240101',
            end='20241231'
        )
        print(f"年化收益: {result['annual_return']:.2%}")
        print(f"夏普比率: {result['sharpe_ratio']:.2f}")
        
        # 测试组合优化
        print("\n测试组合优化...")
        opt_result = optimize_weights(
            stocks=['000001.SZ', '000002.SZ', '600519.SH'],
            method='markowitz'
        )
        print(f"优化权重: {opt_result['weights']}")
        
        print("\n✅ 测试完成!")
    else:
        print("❌ qteasy未安装，请先安装: pip3 install qteasy --user")
