---
name: qteasy-integration
description: |
  qteasy集成模块 - 与现有量化系统的桥接层
  
  核心功能:
  1. 快速策略验证 - 向量化回测，5分钟筛选策略idea
  2. 基准对照 - qteasy内置经典策略作为benchmark
  3. 组合优化 - 马科维茨等经典优化方法
  4. 实盘执行 - 交易信号执行层
  
  使用场景:
  - 快速验证新策略想法（vs WFO深度回测）
  - 证明AI策略优于传统技术指标
  - 实盘交易执行
  - 经典组合优化方法对比
  
  依赖: qteasy (pip3 install qteasy --user)

# qteasy集成模块 v1.0

## 🎯 设计目标

将qteasy作为现有量化系统的**补充层**，而非替代：

```
现有系统（核心）          qteasy（补充层）
├── 数据层 (parquet)  ←→  ├── 数据缓存
├── 26因子+ML           ├── 100+技术策略
├── WFO深度回测    ←→   ├── 快速筛选
├── 智能优化器     ←→   ├── 马科维茨优化
└── 模拟盘              └── 实盘执行
```

## 📦 核心类

### QteasyIntegration

主要集成桥接器，提供4大功能：

```python
from qteasy_integration import QteasyIntegration

integrator = QteasyIntegration(data_source='tushare')
```

#### 1. 快速策略验证

```python
# 5分钟出结果，筛选策略idea
result = integrator.quick_backtest(
    strategy_name='sma_cross',  # 双均线
    stock_codes=['000001.SZ', '000002.SZ'],
    start_date='20240101',
    end_date='20241231',
    params={'fast': 20, 'slow': 60}
)

# 返回结果
{
    'strategy': 'sma_cross',
    'annual_return': 0.15,      # 年化收益15%
    'sharpe_ratio': 1.2,        # 夏普1.2
    'max_drawdown': -0.08,      # 最大回撤8%
    'win_rate': 0.55            # 胜率55%
}
```

**可用策略**: `sma_cross`, `ema_cross`, `macd`, `rsi`, `boll`, `momentum`, `crossline`

#### 2. 基准对照

```python
# 我们的AI策略 vs qteasy经典策略
comparison = integrator.benchmark_comparison(
    our_strategy_returns=our_strategy_returns,  # 我们的策略日收益
    stock_codes=['000001.SZ', '000002.SZ'],
    start_date='20240101',
    end_date='20241231'
)

# 输出对照结果
{
    'our_strategy': {
        'annual_return': 0.25,
        'sharpe': 1.5
    },
    'benchmarks': {
        'sma_cross': {'annual_return': 0.12, 'sharpe': 0.8},
        'macd': {'annual_return': 0.15, 'sharpe': 0.9}
    },
    'comparison': {
        'sma_cross': {'excess_return': 0.13, 'sharpe_diff': 0.7}
        # 我们的策略超额收益13%，夏普高0.7
    }
}
```

#### 3. 组合优化

```python
# 马科维茨优化
result = integrator.optimize_portfolio(
    stock_codes=['000001.SZ', '000002.SZ', '600519.SH'],
    method='markowitz',      # markowitz/risk_parity/equal_weight
    target='sharpe',         # sharpe/return/risk
    risk_free_rate=0.03
)

# 返回优化权重
{
    'method': 'markowitz',
    'weights': {
        '000001.SZ': 0.4,
        '000002.SZ': 0.35,
        '600519.SH': 0.25
    },
    'expected_return': 0.15,
    'expected_risk': 0.20,
    'sharpe_ratio': 0.75
}
```

#### 4. 实盘执行

```python
# 执行交易信号
signals = pd.DataFrame({
    'date': ['2024-03-01', '2024-03-01'],
    'code': ['000001.SZ', '000002.SZ'],
    'action': ['buy', 'buy'],
    'weight': [0.5, 0.5]
})

# 模拟盘执行
result = integrator.execute_signals(signals, broker='simulator')

# 实盘执行 (需配置券商)
result = integrator.execute_signals(
    signals, 
    broker='ths',  # 同花顺
    account='your_account',
    password='your_password'
)
```

### QteasySignalBridge

信号格式转换器：

```python
from qteasy_integration import QteasySignalBridge

# 我们的信号格式 → qteasy格式
our_signals = pd.DataFrame({
    'date': ['2024-03-01'],
    'code': ['000001.SZ'],
    'signal_weight': [0.3]
})

qt_signals = QteasySignalBridge.convert_signals(our_signals)
# 输出: date, symbol, action, weight
```

## 💡 使用场景

### 场景1: 快速筛选策略idea

```python
# 有10个策略想法，用qteasy快速筛选
strategies = ['sma_cross', 'macd', 'rsi', 'boll']
stocks = ['000001.SZ', '000002.SZ', '600519.SH']

results = []
for strategy in strategies:
    result = quick_backtest(strategy, stocks, '20240101', '20241231')
    results.append({'strategy': strategy, 'sharpe': result['sharpe_ratio']})

# 选出夏普最高的3个，再用WFO深度优化
top3 = sorted(results, key=lambda x: x['sharpe'], reverse=True)[:3]
```

### 场景2: 证明AI策略优势

```python
# 我们的AI策略 vs 传统技术指标
comparison = compare_with_benchmark(
    our_strategy_returns=ai_strategy_returns,
    stocks=['000001.SZ', '000002.SZ'],
    start='20240101',
    end='20241231'
)

# 如果超额收益>10%，说明AI策略有效
for name, diff in comparison['comparison'].items():
    if diff['excess_return'] > 0.10:
        print(f"✅ AI策略跑赢{name} {diff['excess_return']:.1%}")
```

### 场景3: 组合权重优化对比

```python
# 对比我们的优化器 vs 马科维茨
our_weights = our_optimizer.optimize(stocks)  # 我们的智能优化器
qt_weights = optimize_weights(stocks, 'markowitz')  # qteasy马科维茨

# 回测对比两种权重的效果
```

### 场景4: 实盘交易执行

```python
# 我们的系统生成信号 → qteasy执行
from qteasy_integration import QteasySignalBridge, QteasyIntegration

# 1. 我们的策略生成信号
signals = our_strategy.generate_signals()

# 2. 转换为qteasy格式
qt_signals = QteasySignalBridge.convert_signals(signals)

# 3. qteasy执行交易
integrator = QteasyIntegration()
execution_result = integrator.execute_signals(qt_signals, broker='ths')
```

## 📁 文件结构

```
skills/quant-data-system/
├── scripts/
│   ├── qteasy_integration.py      # 核心集成代码
│   └── ...
├── examples/
│   └── qteasy_integration_examples.py  # 使用示例
└── ...
```

## 🔧 安装依赖

```bash
# 安装qteasy
pip3 install qteasy --user

# 验证安装
python3 -c "import qteasy; print(qteasy.__version__)"
```

## 🎓 最佳实践

1. **快速筛选用qteasy，深度优化用WFO**
   - qteasy向量化回测：5分钟筛选10个策略
   - WFO滚动回测：30分钟深度优化1个策略

2. **基准对照是必做项**
   - 任何新策略都要和经典技术指标对比
   - 跑不赢双均线就不要上实盘

3. **组合优化作为参考**
   - qteasy马科维茨 vs 我们的进化算法
   - 两者结合效果更好

4. **实盘执行逐步过渡**
   - 先在模拟盘跑通
   - 小资金实盘验证
   - 再逐步加大仓位

## ⚠️ 注意事项

1. **qteasy数据缓存**：首次运行会下载数据，较慢
2. **实盘风险**：实盘交易前务必充分测试
3. **版本兼容**：qteasy更新可能影响接口

---

*集成版本: v1.0*  
*依赖: qteasy >= 1.0*  
*创建时间: 2026-03-02*
