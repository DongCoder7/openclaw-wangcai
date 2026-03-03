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
## 核心定时任务

| 时间 | 任务 | 执行脚本 |
|:---:|:---|:---|
| 08:30 | 美股隔夜总结 | `skills/us-market-analysis/scripts/generate_report_longbridge.py` |
| 09:20 | A+H开盘前瞻 | `skills/ah-market-preopen/scripts/generate_report_longbridge.py` |
| 15:00 | 收盘深度报告 | `tools/daily_market_report.py` |
| 15:30 | 模拟盘交易 | `skills/quant-data-system/scripts/sim_portfolio.py` |
| 16:00 | 当日数据库补充 | `tools/update_daily_basic.py` + `tools/fetch_all_stocks_factors.py` |
| 18:00 | 当日数据更新汇报 | 查询并汇报各表最新数据量 |
| 23:30 | 知识星球日终抓取并总结 | `tools/zsxq_fetcher_prod.py` |

---

## 状态追踪文件

- `heartbeat_state.json` - 任务执行状态
- `quant/optimizer/latest_report.txt` - 最新优化结果
- `data/daily_report_YYYYMMDD.md` - 每日收盘报告
- `data/supplement_state.json` - 数据回补状态
- `reports/supplement_progress.json` - 数据回补进度报告

---

## 数据回补监控

### 整点自动汇报
Heartbeat每小时自动汇报：
- 数据回补进程状态
- 各年度数据进度（2018-2025）
- 入库率统计

### 手动检查命令
```bash
# 检查进程
ps aux | grep supplement_batch_v2

# 查看进度
cat reports/supplement_progress.json

# 数据库统计
sqlite3 data/historical/historical.db "SELECT substr(period,1,4) as year, COUNT(*) as records, COUNT(DISTINCT ts_code) as stocks FROM fina_tushare GROUP BY year ORDER BY year;"
```

---

## 核心文件

- `tools/heartbeat_scheduler.py` - 心跳任务调度器
- `tools/daily_market_report.py` - 收盘深度报告
- `tools/sim_portfolio_tracker.py` - 模拟盘跟踪
- `~/.openclaw/cron/jobs.json` - Cron任务配置
