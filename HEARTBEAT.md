# HEARTBEAT.md - 心跳机制任务调度

> **前置要求：执行本Skill前，必须先读取 `SOUL.md` 确认身份和行为准则。**

---

## 机制说明

**外层Cron** (每10分钟触发):
- 任务ID: `heartbeat-scheduler`
- 执行: `tools/heartbeat_scheduler.py`
- 方式: AgentTurn (isolated session)

**Heartbeat内部逻辑**:
1. **每次执行** (每10分钟) → 生成执行日志 → 保存到 `logs/heartbeat/`
2. **整点汇报** (HH:00) → 汇总最近6个日志 → 生成综合报告 → 发送并保存
3. **Git同步** → 每次执行后自动同步变更

---

## 定时任务配置

| 时间 | 任务名称 | 执行脚本 | 超时时间 | 汇报方式 |
|:---:|:---|:---|:---:|:---|
| 08:30 | 美股隔夜总结 | `skills/us-market-analysis/scripts/generate_report_longbridge.py` | 10分钟 | 即时发送结果 |
| 09:30 | A+H开盘前瞻 | `skills/ah-market-preopen/scripts/generate_report_longbridge.py` | 10分钟 | 即时发送结果 |
| 15:00 | 收盘深度报告 | `tools/daily_market_report.py` | 5分钟 | 即时发送结果 |
| 15:30 | 模拟盘交易 | `skills/quant-data-system/scripts/sim_portfolio.py` | 5分钟 | 即时发送结果 |
| 16:00 | 当日数据更新 | `tools/update_daily_basic.py` | 后台运行 | 完成后整点汇报 |
| 23:30 | 知识星球日终抓取 | `tools/zsxq_fetcher_prod.py` | 10分钟 | 即时发送结果 |

---

## 任务执行流程

```
Cron触发 (每10分钟)
    ↓
执行 heartbeat_scheduler.py
    ↓
生成执行日志 → logs/heartbeat/heartbeat_YYYYMMDD_HHMM.log
    ↓
如果是整点(HH:00) → 汇总最近6个日志 → 生成综合报告
    ↓
发送报告 + 保存到 reports/heartbeat_latest.md
    ↓
Git同步变更
```

**文件保留策略**:
- 日志文件: 保留最近 **6个** (约1小时)
- 整点报告: 只保留最新 **1份** (覆盖旧文件)

---

## 整点汇报内容（HH:00）

```
📊 **Heartbeat整点汇报** (HH:00)

【数据回补进度】
- 2018年: XX/3354只 (XX%)
- 2019年: XX/3556只 (XX%)
- 2020年: XX/3700只 (XX%)
- 2021年: XX/3900只 (XX%)
- 2022年: XX/4100只 (XX%)
- 2023年: ✅ 完成
- 2024年: ✅ 完成
- 2025年: 🟢 进行中

【当日数据更新】(16:00后)
- daily_basic: 20260303, 5485只股票 ✅
- daily_price: 20260303, 5485只股票 ✅
- 状态: 当日更新完成

【策略效果】
- 版本: WFO v5
- 年化收益: XX%
- Top3因子: price_pos_high | sharpe_like | vol_20

【最近执行记录】
- 20260303_2230: 任务执行摘要...
- 20260303_2220: 任务执行摘要...
...
```

---

## 产出文件路径

| 类型 | 路径 | 保留策略 |
|:---|:---|:---|
| 执行日志 | `logs/heartbeat/heartbeat_YYYYMMDD_HHMM.log` | 保留6个 |
| 整点报告 | `reports/heartbeat_latest.md` | 保留1份 |
| 美股报告 | `data/us_market_daily_YYYYMMDD.md` | 永久保留 |
| AH股报告 | `data/ah_market_preopen_YYYYMMDD.md` | 永久保留 |
| 收盘报告 | `data/daily_report_YYYYMMDD.md` | 永久保留 |
| 模拟盘数据 | `data/sim_portfolio.json` | 最新1份 |
| 数据回补日志 | `reports/supplement_batch_v3.log` | 当前任务 |
| 数据回补状态 | `data/supplement_v3_state.json` | 当前状态 |

---

## 状态追踪文件

| 文件 | 用途 |
|:---|:---|
| `~/.openclaw/cron/jobs.json` | Cron任务配置 |
| `data/supplement_v3_state.json` | 数据回补状态 |
| `logs/heartbeat/heartbeat_*.log` | Heartbeat执行日志 |
| `reports/heartbeat_latest.md` | 最新整点报告 |
| `quant/optimizer/wfo_v5_optimized_*.json` | WFO优化结果 |

---

## 核心文件

- `tools/heartbeat_scheduler.py` - 心跳调度主程序
  - `check_and_run_tasks()` - 定时任务触发
  - `check_supplement_progress()` - 数据回补监控
  - `check_daily_data_update()` - 当日数据更新监控
  - `generate_strategy_report()` - 策略效果汇报
  - `get_recent_logs_summary()` - 汇总最近日志
  - `cleanup_old_logs()` - 清理旧日志
  - `git_sync()` - Git同步
- `tools/daily_market_report.py` - 收盘深度报告
- `HEARTBEAT.md` - 本配置文件

---

## Git同步要求

**每次Heartbeat执行后必须进行Git同步**:
1. 检查工作区变更 (`git status --porcelain`)
2. 添加所有变更 (`git add -A`)
3. 提交变更 (`git commit -m "HH:MM Heartbeat"`)
4. 推送到远程 (`git push`)

**同步内容包括**:
- 数据回补进度
- Heartbeat日志
- 整点报告
- 策略优化结果

---

## 手动检查命令

```bash
# 检查Cron状态
openclaw cron status

# 检查数据回补进程
ps aux | grep supplement_batch

# 查看数据回补进度
cat data/supplement_v3_state.json | python3 -c "import json,sys; d=json.load(sys.stdin); print(f'已处理: {len(d[\"processed_stocks\"])}只')"

# 数据库统计
sqlite3 data/historical/historical.db "SELECT substr(period,1,4) as year, COUNT(*) as records, COUNT(DISTINCT ts_code) as stocks FROM fina_tushare GROUP BY year ORDER BY year;"

# 查看最新Heartbeat日志
tail -f logs/heartbeat/heartbeat_*.log

# 查看最新整点报告
cat reports/heartbeat_latest.md
```

---

*版本: v3.0 - 优化日志管理，增加Git同步*
*更新: 2026-03-03*
