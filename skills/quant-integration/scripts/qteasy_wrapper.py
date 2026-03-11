#!/root/.openclaw/workspace/venv/bin/python3
"""
qteasy与量化系统集成封装
提供快速验证、基准对比、实盘交易功能
"""

import sys
import os
import json
from typing import List, Dict, Optional, Tuple
from datetime import datetime
from pathlib import Path

# 尝试导入qteasy
try:
    import qteasy as qt
    QTEASY_AVAILABLE = True
except ImportError:
    QTEASY_AVAILABLE = False
    print("⚠️ qteasy未安装，请先安装: pip install qteasy")


class QteasyWrapper:
    """qteasy基础封装类"""
    
    def __init__(self, data_path: str = None):
        """
        初始化qteasy封装
        
        Args:
            data_path: 数据存储路径，默认使用workspace/data
        """
        self.data_path = data_path or '/root/.openclaw/workspace/data'
        
        if QTEASY_AVAILABLE:
            # 配置qteasy使用我们的数据路径
            qt.configure(
                data_path=self.data_path,
                local_data_source='tushare'  # 优先使用Tushare
            )
    
    def is_available(self) -> bool:
        """检查qteasy是否可用"""
        return QTEASY_AVAILABLE


class FastBacktest(QteasyWrapper):
    """
    快速回测 - 使用qteasy向量化回测快速验证策略想法
    """
    
    # qteasy内置策略映射
    BUILTIN_STRATEGIES = {
        'SMA': 'SMA',           # 简单移动平均
        'EMA': 'EMA',           # 指数移动平均
        'MACD': 'MACD',         # MACD策略
        'RSI': 'RSI',           # RSI策略
        'BOLL': 'BBANDS',       # 布林带
        'MOM': 'MOMENTUM',      # 动量策略
        'CROSS': 'CROSSLINE',   # 均线交叉
    }
    
    def test_strategy(self, 
                      symbols: List[str],
                      strategy: str,
                      params: Tuple,
                      start: str,
                      end: str,
                      init_cash: float = 1000000) -> Dict:
        """
        快速测试单个策略
        
        Args:
            symbols: 股票代码列表 ['000001.SZ', '000002.SZ']
            strategy: 策略名称，如'SMA', 'MACD'
            params: 策略参数，如(20, 60)表示20日/60日均线
            start: 开始日期 '20240101'
            end: 结束日期 '20241231'
            init_cash: 初始资金
            
        Returns:
            回测结果字典
        """
        if not self.is_available():
            return {'error': 'qteasy not installed'}
        
        try:
            # 获取qteasy策略类
            strategy_class = getattr(qt, self.BUILTIN_STRATEGIES.get(strategy, 'SMA'))
            
            # 创建策略实例
            if params:
                stg = strategy_class(pars=params)
            else:
                stg = strategy_class()
            
            # 创建操作器
            op = qt.Operator(stg)
            
            # 运行回测
            result = op.run(
                mode=1,  # 回测模式
                invest_start=start,
                invest_end=end,
                invest_cash=init_cash,
                symbol_list=symbols
            )
            
            # 提取关键指标
            return {
                'strategy': strategy,
                'params': params,
                'symbols': symbols,
                'total_return': result.get('total_return', 0),
                'annual_return': result.get('annual_return', 0),
                'sharpe': result.get('sharpe', 0),
                'max_drawdown': result.get('max_drawdown', 0),
                'volatility': result.get('volatility', 0),
                'trade_count': result.get('trade_count', 0),
                'win_rate': result.get('win_rate', 0)
            }
            
        except Exception as e:
            return {'error': str(e)}
    
    def batch_test(self,
                   symbols: List[str],
                   strategies: List[Dict],
                   start: str,
                   end: str) -> List[Dict]:
        """
        批量测试多个策略
        
        Args:
            strategies: [{'name': 'SMA', 'params': (20, 60)}, ...]
            
        Returns:
            多个策略回测结果
        """
        results = []
        for stg_conf in strategies:
            result = self.test_strategy(
                symbols=symbols,
                strategy=stg_conf['name'],
                params=stg_conf.get('params'),
                start=start,
                end=end
            )
            results.append(result)
        
        # 按收益率排序
        results.sort(key=lambda x: x.get('total_return', 0), reverse=True)
        return results


class LiveTrader(QteasyWrapper):
    """
    实盘交易 - 使用qteasy执行实盘交易（需要券商接口）
    """
    
    def __init__(self, 
                 broker: str = 'ths',
                 account: str = None,
                 config_path: str = None):
        """
        初始化实盘交易器
        
        Args:
            broker: 券商接口，如'ths'(同花顺), 'tdx'(通达信)
            account: 资金账号
            config_path: 配置文件路径
        """
        super().__init__()
        self.broker = broker
        self.account = account
        self.config_path = config_path
        
        # 加载配置
        if config_path and os.path.exists(config_path):
            with open(config_path, 'r') as f:
                self.config = json.load(f)
        else:
            self.config = {}
    
    def setup(self, 
              broker: str = None,
              account: str = None,
              password: str = None):
        """
        配置实盘交易参数
        
        Args:
            broker: 券商代码
            account: 账号
            password: 密码（建议从环境变量读取）
        """
        if not self.is_available():
            return {'error': 'qteasy not installed'}
        
        try:
            qt.configure(
                mode='live',
                broker=broker or self.broker,
                account=account or self.account
            )
            return {'status': 'configured'}
        except Exception as e:
            return {'error': str(e)}
    
    def execute_signals(self, 
                        signals: List[Dict],
                        dry_run: bool = True) -> List[Dict]:
        """
        执行交易信号
        
        Args:
            signals: [{'symbol': '000001.SZ', 'action': 'buy', 'amount': 1000}, ...]
            dry_run: 模拟执行（不实际下单）
            
        Returns:
            执行结果
        """
        if not self.is_available():
            return [{'error': 'qteasy not installed'}]
        
        results = []
        for signal in signals:
            try:
                if dry_run:
                    # 模拟执行
                    result = {
                        'symbol': signal['symbol'],
                        'action': signal['action'],
                        'amount': signal['amount'],
                        'status': 'simulated',
                        'message': '模拟执行成功'
                    }
                else:
                    # 实际执行（需要配置好券商接口）
                    # TODO: 实际下单逻辑
                    result = {
                        'symbol': signal['symbol'],
                        'action': signal['action'],
                        'amount': signal['amount'],
                        'status': 'pending',
                        'message': '实盘执行待实现'
                    }
                
                results.append(result)
                
            except Exception as e:
                results.append({
                    'symbol': signal.get('symbol'),
                    'error': str(e)
                })
        
        return results


class Benchmark(QteasyWrapper):
    """
    基准对比 - 对比我们的策略与经典策略
    """
    
    def compare(self,
                our_strategy_result: Dict,
                benchmarks: List[str],
                symbols: List[str],
                period: str) -> Dict:
        """
        对比我们的策略与qteasy内置策略
        
        Args:
            our_strategy_result: 我们策略的回测结果
            benchmarks: 基准策略列表 ['SMA', 'MACD', 'RSI']
            symbols: 标的列表
            period: 回测期间 '20240101-20241231'
            
        Returns:
            对比结果
        """
        if not self.is_available():
            return {'error': 'qteasy not installed'}
        
        start, end = period.split('-')
        
        # 批量测试基准策略
        fb = FastBacktest()
        benchmark_results = fb.batch_test(
            symbols=symbols,
            strategies=[{'name': b, 'params': None} for b in benchmarks],
            start=start,
            end=end
        )
        
        # 构建对比表
        comparison = {
            'our_strategy': our_strategy_result,
            'benchmarks': benchmark_results,
            'period': period,
            'symbols': symbols
        }
        
        # 计算相对表现
        our_return = our_strategy_result.get('total_return', 0)
        for bm in benchmark_results:
            bm['excess_return'] = our_return - bm.get('total_return', 0)
        
        return comparison
    
    def generate_report(self, comparison: Dict) -> str:
        """生成对比报告"""
        lines = [
            "# 策略对比报告",
            f"\n回测期间: {comparison['period']}",
            f"标的: {', '.join(comparison['symbols'][:5])}...",
            "",
            "## 我们的策略",
            f"- 总收益: {comparison['our_strategy'].get('total_return', 0):.2%}",
            f"- 年化收益: {comparison['our_strategy'].get('annual_return', 0):.2%}",
            f"- 夏普比率: {comparison['our_strategy'].get('sharpe', 0):.2f}",
            f"- 最大回撤: {comparison['our_strategy'].get('max_drawdown', 0):.2%}",
            "",
            "## 基准策略对比",
            ""
        ]
        
        for bm in comparison['benchmarks']:
            lines.extend([
                f"### {bm['strategy']}",
                f"- 总收益: {bm.get('total_return', 0):.2%}",
                f"- 超额收益: {bm.get('excess_return', 0):+.2%}",
                ""
            ])
        
        return "\n".join(lines)


def check_qteasy_installation():
    """检查qteasy安装状态"""
    if QTEASY_AVAILABLE:
        print(f"✅ qteasy已安装，版本: {qt.__version__}")
        return True
    else:
        print("❌ qteasy未安装")
        print("\n安装方法:")
        print("1. 创建虚拟环境: python3 -m venv ~/.openclaw/workspace/.venv/qteasy")
        print("2. 激活环境: source ~/.openclaw/workspace/.venv/qteasy/bin/activate")
        print("3. 安装: pip install qteasy")
        return False


if __name__ == "__main__":
    # 测试
    print("🧪 测试qteasy集成封装")
    check_qteasy_installation()
    
    if QTEASY_AVAILABLE:
        # 测试快速回测
        fb = FastBacktest()
        result = fb.test_strategy(
            symbols=['000001.SZ'],
            strategy='SMA',
            params=(20, 60),
            start='20240101',
            end='20241231'
        )
        print(f"\n回测结果: {result}")
