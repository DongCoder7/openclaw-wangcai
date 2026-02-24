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

### 3. 24小时连续任务 (异步汇报机制)

| 任务 | 间隔 | 汇报机制 |
|------|------|----------|
| **策略优化器** | 每15分钟运行 | 每轮迭代写入文件，heartbeat检测新报告并汇报 |
| **全市场数据采集** | 每小时1次 | 后台运行，每小时更新因子数据 |
| **模拟盘跟踪** | 每次heartbeat | 监控持仓并生成交易信号 |

### 4. Git同步检查
每次心跳自动同步脚本/配置/学习资料到远程git

---

## 异步汇报机制说明

### 策略优化器异步汇报流程

```
策略优化器 (后台24小时运行)
    ↓
每轮参数迭代完成 → 写入 latest_report.txt
    ↓
Heartbeat检测到文件更新 → 读取内容
    ↓
发送汇报到Feishu
```

### 报告文件位置

- **策略优化器报告**: `quant/optimizer/latest_report.txt`
- **迭代日志**: `quant/optimizer/iteration_log.txt`
- **Heartbeat记录上次发送时间**，避免重复发送相同报告

### 数据采集频率

- **目标**: A股全市场5000+只股票
- **频率**: 每小时1次
- **采集内容**: 日K线 + 技术指标因子
- **脚本**: `tools/fetch_all_stocks_factors.py`

---

## 核心文件

- `tools/heartbeat_scheduler.py` - 任务调度器 (带报告检测功能)
- `quant/optimizer/smart_optimizer_v23_async.py` - 异步优化器
- `tools/fetch_all_stocks_factors.py` - 全市场数据采集
- `tools/sim_portfolio_tracker.py` - 模拟盘跟踪
- `heartbeat_tasks.json` - 任务配置
