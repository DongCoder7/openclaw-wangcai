# 修正Cron配置 - 添加23:30调度

## 问题
当前Cron只配置整点执行（20,21,22,23,00...），23:30任务无法触发

## 解决方案

### 方案1: 添加23:30专用Cron（推荐）
```json
{
  "id": "zsxq-fetcher-2330",
  "agentId": "main",
  "name": "知识星球日终抓取-2330",
  "enabled": true,
  "schedule": {
    "kind": "cron",
    "expr": "30 23 * * *",
    "tz": "Asia/Shanghai"
  },
  "sessionTarget": "isolated",
  "wakeMode": "immediate",
  "payload": {
    "kind": "agentTurn",
    "task": "执行知识星球日终抓取: /root/.openclaw/workspace/venv/bin/python3 /root/.openclaw/workspace/tools/zsxq_fetcher_prod.py"
  }
}
```

### 方案2: 修改Heartbeat调度频率
将夜间调度改为每30分钟执行：
```
*/30 20-23,0-7 * * *
```

### 方案3: 立即手动补偿
现在执行昨日错过的任务：
```bash
cd /root/.openclaw/workspace
./venv_runner.sh tools/zsxq_fetcher_prod.py
```

## 建议
采用方案1，为23:30任务配置独立Cron，不受Heartbeat调度影响
