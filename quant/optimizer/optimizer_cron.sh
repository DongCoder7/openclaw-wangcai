#!/bin/bash
# 策略优化 cron任务 - v23版本
# 运行时间: 22:00-08:00, 每15分钟

cd /root/.openclaw/workspace/quant/optimizer
python3 smart_optimizer_v23.py >> optimizer.log 2>&1

echo "v23优化完成: $(date)" >> optimizer.log
