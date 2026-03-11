#!/bin/bash
# 添加23:30知识星球定时任务

# 方法：使用openclaw cron add命令
# 或者修改jobs.json

echo "建议执行以下命令添加23:30定时任务："
echo ""
echo "openclaw cron add --id zsxq-fetcher-2330 \\"
echo "  --name '知识星球日终抓取-2330' \\"
echo "  --agent main \\"
echo "  --schedule '30 23 * * *' \\"
echo "  --task './venv_runner.sh tools/zsxq_fetcher_prod.py'"
echo ""
echo "或者修改 ~/.openclaw/cron/jobs.json 添加以下配置："
cat <> 'CONFIG'
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
    "task": "cd /root/.openclaw/workspace && ./venv_runner.sh tools/zsxq_fetcher_prod.py"
  }
}
CONFIG
