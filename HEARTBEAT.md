# HEARTBEAT.md - 豆奶投资策略系统心跳任务

## 每次Heartbeat必须执行的三件事

### 1. 整点状态汇报
- **只在整点(0分)执行**
- 汇报任务状态、数据库股票数(分年度)、策略状态(文件后半部分有参考样式)
- 自动修复问题

### 2. 模拟盘跟踪
- 检查持仓状态
- 生成交易信号
- 汇报持仓变化

### 3. Git同步
- 同步新增的数据文件
- 同步报告文件
- 同步配置文件

---

## 定时任务触发点（自然语言）

| 时间 | 任务 | 执行脚本路径 |
|------|------|-------------|
| 08:30 | 美股隔夜总结 | `skills/us-market-analysis/scripts/generate_report_longbridge.py` |
| 09:20 | A+H开盘前瞻 | `skills/ah-market-preopen/scripts/generate_report_longbridge.py` |
| 15:00 | 收盘深度报告 | `tools/daily_market_report.py` |
| 15:30 | 模拟盘交易 | `skills/quant-data-system/scripts/sim_portfolio.py` |
| 23:30 | 知识星球日终抓取 | `tools/zsxq_fetcher_prod.py` |
| 每小时 | 数据采集 | `tools/fetch_all_stocks_factors.py` |
| 每2小时 | 知识星球信息 | `tools/zsxq_fetcher.py` |
| 每15分钟 | 策略自动优化 | `tools/heartbeat_wfo_optimizer.py` |
| 整点 | 策略效果汇报 | `tools/heartbeat_scheduler.py` (自身汇报) |
| 每周日 | 数据补充 | `skills/quant-data-system/scripts/supplement_data.py` |
| 每月初 | WFO回测 | `skills/quant-data-system/scripts/wfo_backtest.py` |

---

## 状态追踪

Heartbeat会记录：
- `heartbeat_state.json` - 任务执行状态
- `quant/optimizer/latest_report.txt` - 最新优化结果
- `data/daily_report_YYYYMMDD.md` - 每日收盘报告
- `quant/optimizer/factor_usage_report.json` - 因子使用情况报告

---

## 因子与策略汇报要求

### 整点汇报内容（简洁，聚焦结果）：

```
📊 **策略状态汇报** (HH:00)

【当前策略组合】
- 仓位: 70% | 止损: 8% | 持仓: 5只 | 调仓: 10天
- 回测表现: 2018:+12% | 2019:+18% | 2020:+25% | 2021:+15%
- 平均年化: +17.5% ✅

【因子使用情况】
- 已采用: 8/26 个因子 (31%)
- 未采用: 18/26 个因子 (69%)
- Top 3: price_pos_high | sharpe_like | vol_20
- 数据覆盖: 技术5177/防御5166/财务3772 ✅

【后续优化点】
- 有18个因子未采用，建议逐步引入测试效果
- 建议优先尝试: roe, revenue_growth, netprofit_growth
- 持续运行优化器，每15分钟迭代寻找更优组合
```

### 汇报原则：
1. **不说过程** - 不汇报"优化器正在运行/完成"
2. **只说结果** - 当前策略参数、回测收益、因子采用/未采用数量
3. **给出建议** - 明确的后续优化方向（具体未采用因子）
4. **自动执行** - 优化任务无需请示，持续运行，只汇报结果变化

### 执行逻辑：
- **每15分钟检查** - 自动检查优化器状态
- **持续运行** - 如未运行则自动启动最新优化器，持续寻找最佳组合
- **每4小时迭代** - 超过4小时自动重新优化，探索新组合
- **自动发现最新版本** - enhanced_optimizer_v26 > v25 > v24 > ...
- **整点汇报** - 读取最新结果，汇报策略状态

### 触发条件：
- 每15分钟检查一次优化器状态
- 无优化器运行时自动启动
- 上次优化超过4小时自动重新运行
- 无需请示，全自动执行

### 相关文件：
- `tools/auto_optimizer.py` - 自动执行优化 (自动发现最新版本)
- `tools/generate_strategy_report.py` - 生成策略效果报告
- `quant/optimizer/latest_report.txt` - 最新策略报告

### 优化器命名规范：
- 增强优化器: `enhanced_optimizer_v{版本号}.py` (如 v25, v26...)
- 旧版优化器: `smart_optimizer_v{版本号}.py`
- 结果文件: `enhanced_optimizer_v{版本号}_result_{时间戳}.json`

---

## 核心文件

- `tools/heartbeat_scheduler.py` - 心跳任务调度器
- `tools/sim_portfolio_tracker.py` - 模拟盘跟踪
- `tools/daily_market_report.py` - 收盘深度报告
- `tools/fetch_all_stocks_factors.py` - 多数据源采集
