# HEARTBEAT.md - 豆奶投资策略系统心跳任务

## 每次Heartbeat必须执行的三件事

### 1. 整点状态汇报
- **只在整点(0分)执行**
- 汇报任务状态、数据库股票数、优化器状态
- 自动修复问题（清理僵尸锁、启动进程）

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

| 时间 | 任务 | 说明 |
|------|------|------|
| 08:30 | 美股隔夜总结 | 读取美股报告并发送 |
| 09:15 | A+H开盘前瞻 | 发送开盘策略 |
| 15:00 | 收盘深度报告 | 生成并发送完整报告 |
| 每小时 | 数据采集 | 全市场因子采集 |
| 每15分钟 | 策略优化器 | 参数优化迭代 |

---

## 状态追踪

Heartbeat会记录：
- `heartbeat_state.json` - 任务执行状态
- `quant/optimizer/latest_report.txt` - 最新优化结果
- `data/daily_report_YYYYMMDD.md` - 每日收盘报告

---

## 核心文件

- `tools/heartbeat_scheduler.py` - 心跳任务调度器
- `tools/sim_portfolio_tracker.py` - 模拟盘跟踪
- `tools/daily_market_report.py` - 收盘深度报告
- `tools/fetch_all_stocks_factors.py` - 多数据源采集
