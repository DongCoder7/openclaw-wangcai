# HEARTBEAT.md - 心跳机制任务调度

> **核心原则：所有任务由Heartbeat机制控制，不再使用Cron。**
> 
> **重要说明：Heartbeat机制由OpenClaw系统自动调用，无需手动启动或保持 `heartbeat_scheduler.py` 运行。**

---

## 机制说明

**Heartbeat执行方式**（由系统自动管理）：
- OpenClaw系统**每分钟自动调用** `tools/heartbeat_scheduler.py`
- **无需手动启动**，不需要 `nohup` 或后台运行
- 系统会自动保持Heartbeat持续执行

**Heartbeat每分钟执行**：
1. **定时任务触发** - 在指定时间（精确到分钟）触发任务执行
2. **任务状态监控** - 检查任务是否完成，发送完成汇报
3. **整点汇总汇报** - 整点（HH:00）发送所有状态报告

---

## 定时任务配置

| 时间 | 任务名称 | 执行脚本 | 超时时间 | 汇报方式 |
|:---:|:---|:---|:---:|:---|
| 08:30 | 美股隔夜总结 | `skills/us-market-analysis/scripts/generate_report_longbridge.py` | 10分钟 | 即时发送结果 |
| 09:20 | A+H开盘前瞻 | `skills/ah-market-preopen/scripts/generate_report_longbridge.py` | 10分钟 | 即时发送结果 |
| 15:00 | 收盘深度报告 | `tools/daily_market_report.py` | 5分钟 | 即时发送结果 |
| 15:30 | 模拟盘交易 | `skills/quant-data-system/scripts/sim_portfolio.py` | 5分钟 | 即时发送结果 |
| 16:00 | 当日数据更新 | `tools/update_daily_basic.py` | 后台运行 | 完成后整点汇报 |
| 23:30 | 知识星球日终抓取 | `tools/zsxq_fetcher_prod.py` | 10分钟 | 即时发送结果 |

---

## 任务执行流程

```
Heartbeat (每分钟)
    ↓
检查当前时间
    ↓
如果是指定时间 → 触发任务 → 即时汇报结果
    ↓
如果是整点 → 发送汇总汇报
    ↓
持续监控WFO优化器
```

**关键改进**：
- ✅ 任务触发后立即汇报执行结果
- ✅ 后台任务完成后整点汇报
- ✅ 所有状态统一由Heartbeat监控
- ❌ 不再依赖Cron（jobs.json已清空）

---

## 整点汇报内容（HH:00）

```
📊 **Heartbeat整点汇报** (HH:00)

【定时任务状态】
- 今日已执行: 美股隔夜总结、A+H开盘前瞻...
- 下次任务: 15:00 收盘深度报告

【数据回补进度】
- 2018年: XX/5000只 (XX%)
- 2019年: XX/5000只 (XX%)
- 2020年: XX/5000只 (XX%)
- 2021年: XX/5000只 (XX%)
- 2022年: XX/5000只 (XX%)
- 2023年: ✅ 完成
- 2024年: ✅ 完成
- 2025年: 🟢 89.5%

【当日数据更新】
- daily_basic: 20260303, 5485只股票 ✅
- 状态: 当日更新完成

【策略效果】
- 版本: WFO v5
- 年化收益: XX%
- Top3因子: price_pos_high | sharpe_like | vol_20
```

---

## 状态追踪文件

| 文件 | 用途 |
|:---|:---|
| `heartbeat_state.json` | Heartbeat执行状态 |
| `data/supplement_state.json` | 数据回补状态 |
| `reports/supplement_progress.json` | 数据回补进度报告 |
| `quant/optimizer/latest_report.txt` | 最新优化结果 |
| `data/daily_report_YYYYMMDD.md` | 每日收盘报告 |

---

## 核心文件

- `tools/heartbeat_scheduler.py` - 心跳调度主程序
  - `check_and_run_tasks()` - 定时任务触发
  - `check_supplement_progress()` - 数据回补监控
  - `check_daily_data_update()` - 当日数据更新监控
  - `generate_strategy_report()` - 策略效果汇报
  - `run_task()` - 任务执行封装
  - `run_optimizer_if_needed()` - WFO优化器监控
- `tools/daily_market_report.py` - 收盘深度报告
- `HEARTBEAT.md` - 本配置文件

---

## 手动检查命令

```bash
# 检查数据回补进程
ps aux | grep supplement_batch_v2

# 查看数据回补进度
cat reports/supplement_progress.json

# 数据库统计
sqlite3 data/historical/historical.db "SELECT substr(period,1,4) as year, COUNT(*) as records, COUNT(DISTINCT ts_code) as stocks FROM fina_tushare GROUP BY year ORDER BY year;"

# 查看最新Heartbeat日志
tail -f /root/.openclaw/workspace/logs/heartbeat_*.log
```

---

*版本: v2.0 - 移除Cron，统一Heartbeat控制*
*更新: 2026-03-03*
