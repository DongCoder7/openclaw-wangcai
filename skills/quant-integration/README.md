# qteasy与量化系统集成方案

## 架构说明

将qteasy作为「快速验证+实盘执行」层，与现有量化系统分层集成：

```
┌─────────────────────────────────────────────────────────┐
│  策略研发层（我们的核心系统）                              │
│  ├── Data: Tushare/Akshare → parquet                    │
│  ├── Factors: 26因子 + 机器学习                          │
│  ├── Strategy: 智能优化器 + WFO回测                      │
│  └── Portfolio: 模拟盘跟踪                               │
└─────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────┐
│  qteasy集成层（新增）                                     │
│  ├── FastBacktest: 向量化快速验证                        │
│  ├── Benchmark: 经典策略基准对比                         │
│  ├── PortfolioOpt: 马科维茨等经典优化                    │
│  └── LiveTrading: 实盘交易执行                           │
└─────────────────────────────────────────────────────────┘
```

## 安装说明

由于系统限制，qteasy需要在虚拟环境中安装：

```bash
# 创建虚拟环境
python3 -m venv /root/.openclaw/workspace/.venv/qteasy

# 激活环境
source /root/.openclaw/workspace/.venv/qteasy/bin/activate

# 安装qteasy
pip install qteasy

# 验证安装
python -c "import qteasy; print(qteasy.__version__)"
```

## 使用方法

### 1. 快速策略验证

```python
from skills.quant-integration.scripts.qteasy_wrapper import FastBacktest

# 快速验证双均线策略
fb = FastBacktest()
result = fb.test_strategy(
    symbols=['000001.SZ', '000002.SZ'],
    strategy='SMA',  # qteasy内置策略
    params=(20, 60), # 20日/60日均线
    start='20240101',
    end='20241231'
)
print(f"收益率: {result['return']:.2%}")
```

### 2. 实盘交易执行

```python
from skills.quant-integration.scripts.qteasy_wrapper import LiveTrader

# 初始化实盘交易（需要券商接口配置）
trader = LiveTrader(
    broker='ths',  # 同花顺/通达信
    account='your_account',
    strategy_signals=our_strategy_signals  # 从我们系统导入信号
)

# 执行交易
trader.execute()
```

### 3. 经典策略基准

```python
from skills.quant-integration.scripts.qteasy_wrapper import Benchmark

# 对比我们的AI策略 vs 经典策略
bm = Benchmark()
comparison = bm.compare(
    our_strategy='our_ai_strategy.pkl',
    benchmarks=['SMA', 'MACD', 'RSI'],
    period='20240101-20241231'
)
```

## 核心优势

| 功能 | 我们系统 | qteasy补充 | 集成效果 |
|:---|:---|:---|:---|
| 数据管理 | 手动parquet | 自动缓存 | 统一用我们的parquet |
| 回测速度 | WFO慢但精确 | 向量化快 | 快速筛选+深度验证 |
| 策略库 | 自定义因子 | 100+经典策略 | 丰富策略选择 |
| 组合优化 | 进化算法 | 马科维茨 | 对比验证 |
| 实盘交易 | ❌ 无 | ✅ 有 | 弥补最大短板 |

## 注意事项

1. 数据统一：qteasy使用我们的parquet数据，不重复下载
2. 回测精度：qteasy快速回测用于筛选，WFO用于最终验证
3. 实盘风险：充分测试后再使用实盘功能

## 文件结构

```
skills/quant-integration/
├── SKILL.md
├── scripts/
│   ├── qteasy_wrapper.py      # qteasy封装接口
│   ├── fast_backtest.py       # 快速回测
│   ├── live_trading.py        # 实盘交易
│   └── benchmark.py           # 基准对比
└── examples/
    └── integration_demo.py    # 集成示例
```
