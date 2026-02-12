"""
量化回测基础模板
基于Backtrader的单因子回测框架
"""

import backtrader as bt
import pandas as pd
import numpy as np
from datetime import datetime
import akshare as ak

class PEFactorStrategy(bt.Strategy):
    """
    PE因子策略：买入低PE股票，卖出高PE股票
    """
    params = (
        ('pe_threshold_low', 10),   # 低PE阈值
        ('pe_threshold_high', 30),  # 高PE阈值
        ('rebalance_days', 20),     # 再平衡周期（交易日）
    )
    
    def __init__(self):
        self.dataclose = self.datas[0].close
        self.datape = self.datas[0].pe  # 需要PE数据
        self.order = None
        self.rebalance_counter = 0
        
    def log(self, txt, dt=None):
        """日志函数"""
        dt = dt or self.datas[0].datetime.date(0)
        print(f'{dt.isoformat()} {txt}')
        
    def next(self):
        """每个交易日执行"""
        # 检查是否有待处理订单
        if self.order:
            return
            
        # 再平衡计数
        self.rebalance_counter += 1
        if self.rebalance_counter % self.params.rebalance_days != 0:
            return
            
        # 获取当前PE
        current_pe = self.datape[0]
        
        # 策略逻辑
        if not self.position:  # 没有持仓
            if current_pe < self.params.pe_threshold_low:
                # 低PE买入
                self.log(f'BUY CREATE, Price: {self.dataclose[0]:.2f}, PE: {current_pe:.2f}')
                self.order = self.buy()
        else:  # 有持仓
            if current_pe > self.params.pe_threshold_high:
                # 高PE卖出
                self.log(f'SELL CREATE, Price: {self.dataclose[0]:.2f}, PE: {current_pe:.2f}')
                self.order = self.sell()
                
    def notify_order(self, order):
        """订单状态回调"""
        if order.status in [order.Submitted, order.Accepted]:
            return
            
        if order.status in [order.Completed]:
            if order.isbuy():
                self.log(f'BUY EXECUTED, Price: {order.executed.price:.2f}, Cost: {order.executed.value:.2f}')
            else:
                self.log(f'SELL EXECUTED, Price: {order.executed.price:.2f}, Cost: {order.executed.value:.2f}')
        elif order.status in [order.Canceled, order.Margin, order.Rejected]:
            self.log('Order Canceled/Margin/Rejected')
            
        self.order = None
        
    def notify_trade(self, trade):
        """交易完成回调"""
        if not trade.isclosed:
            return
        self.log(f'TRADE PROFIT, GROSS: {trade.pnl:.2f}, NET: {trade.pnlcomm:.2f}')


def run_backtest(symbol='600900', start_date='20200101', end_date='20241231'):
    """
    运行回测
    
    参数:
        symbol: 股票代码
        start_date: 开始日期
        end_date: 结束日期
    """
    # 创建Cerebro引擎
    cerebro = bt.Cerebro()
    
    # 添加策略
    cerebro.addstrategy(PEFactorStrategy)
    
    # 获取数据（示例使用AKShare）
    try:
        # 这里需要根据实际情况获取数据
        # 示例使用模拟数据
        dates = pd.date_range(start=start_date, end=end_date, freq='B')
        n = len(dates)
        
        # 生成模拟数据（实际使用时替换为真实数据）
        np.random.seed(42)
        data = pd.DataFrame({
            'datetime': dates,
            'open': 100 + np.cumsum(np.random.randn(n) * 0.5),
            'high': 100 + np.cumsum(np.random.randn(n) * 0.5) + 2,
            'low': 100 + np.cumsum(np.random.randn(n) * 0.5) - 2,
            'close': 100 + np.cumsum(np.random.randn(n) * 0.5),
            'volume': np.random.randint(1000000, 5000000, n),
            'pe': np.random.uniform(5, 40, n),  # 模拟PE数据
        })
        data.set_index('datetime', inplace=True)
        
        # 创建数据源
        class PandasData(bt.feeds.PandasData):
            lines = ('pe',)
            params = (('pe', -1),)
            
        datafeed = PandasData(dataname=data)
        cerebro.adddata(datafeed)
        
    except Exception as e:
        print(f'数据获取失败: {e}')
        return
    
    # 设置初始资金
    cerebro.broker.setcash(1000000.0)
    
    # 设置佣金
    cerebro.broker.setcommission(commission=0.001)
    
    # 添加分析器
    cerebro.addanalyzer(bt.analyzers.SharpeRatio, _name='sharpe')
    cerebro.addanalyzer(bt.analyzers.DrawDown, _name='drawdown')
    cerebro.addanalyzer(bt.analyzers.Returns, _name='returns')
    
    # 打印初始资金
    print(f'初始资金: {cerebro.broker.getvalue():.2f}')
    
    # 运行回测
    results = cerebro.run()
    strat = results[0]
    
    # 打印最终资金
    print(f'最终资金: {cerebro.broker.getvalue():.2f}')
    
    # 打印分析结果
    print('\n========== 回测结果 ==========')
    print(f'夏普比率: {strat.analyzers.sharpe.get_analysis()["sharperatio"]:.2f}')
    print(f'最大回撤: {strat.analyzers.drawdown.get_analysis()["max"]["drawdown"]:.2f}%')
    print(f'年化收益: {strat.analyzers.returns.get_analysis()["rnorm100"]:.2f}%')
    
    # 绘制图表（需要matplotlib）
    # cerebro.plot()
    
    return strat


if __name__ == '__main__':
    # 运行示例回测
    print('开始PE因子回测...')
    run_backtest()
