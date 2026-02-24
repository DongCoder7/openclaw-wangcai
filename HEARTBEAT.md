# HEARTBEAT.md - 豆奶投资策略系统心跳任务

## 心跳执行步骤 (每次收到心跳时)

### 1. 运行Heartbeat任务调度器
```bash
python3 /root/.openclaw/workspace/tools/heartbeat_scheduler.py
```

### 2. 定时任务 (精确时间窗口)

| 任务 | 时间 | 功能 |
|------|------|------|
| 美股分析 | 08:30 每日 | 美股隔夜总结 (08:30-08:35) |
| A+H开盘 | 09:15 每日 | A+H开盘前瞻 (09:15-09:20) |
| 每日汇报 | 15:00 每日 | 收盘汇报 (15:00-15:05) |

### 3. 24小时连续任务

| 任务 | 间隔 | 功能 |
|------|------|------|
| **策略优化器** | 每15分钟 | 24小时策略优化学习 |
| **全市场数据采集** | 每6小时 | 采集5000+只股票因子数据 |
| **模拟盘跟踪** | 每次heartbeat | 监控持仓并生成交易信号 |

### 4. Git同步检查
每次心跳自动同步脚本/配置/学习资料到远程git

---

## 任务配置

配置文件: `heartbeat_tasks.json`

```json
{
  "tasks": {
    "us-market-summary": {"schedule": "08:30", ...},
    "ah-preopen": {"schedule": "09:15", ...},
    "daily-report": {"schedule": "15:00", ...}
  },
  "optimizer": {
    "enabled": true,
    "schedule_start": "00:00",
    "schedule_end": "23:59",
    "interval_minutes": 15
  },
  "data_collection": {
    "enabled": true,
    "schedule_start": "00:00",
    "schedule_end": "23:59",
    "interval_minutes": 360
  }
}
```

---

## 全市场数据采集

- **目标**: A股全市场5000+只股票
- **数据源**: AKShare实时行情
- **采集内容**: 日K线 + 技术指标因子
- **频率**: 每6小时完整采集一次
- **进度**: 后台运行，自动增量更新

### 因子计算
- 收益率 (5日/20日/60日)
- 波动率 (20日)
- 均线 (5/20/60日)
- 趋势位置 (20日/60日)
- 资金流向 (20日)
- 动量加速
- 相对强度

---

## 核心文件

- `tools/heartbeat_scheduler.py` - 任务调度器
- `tools/fetch_all_stocks_factors.py` - 全市场数据采集
- `tools/sim_portfolio_tracker.py` - 模拟盘跟踪
- `heartbeat_tasks.json` - 任务配置
