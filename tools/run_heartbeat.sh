#!/bin/bash
# Heartbeat定时任务 - 每10分钟运行一次
# 添加到crontab: */10 * * * * /root/.openclaw/workspace/tools/run_heartbeat.sh

cd /root/.openclaw/workspace
python3 tools/heartbeat_scheduler.py > /tmp/heartbeat.log 2>&1
