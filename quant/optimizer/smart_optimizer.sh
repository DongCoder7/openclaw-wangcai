#!/bin/bash
# 智能策略优化器 - 根据时间决定是否运行
# 只在22:00-08:00之间运行

HOUR=$(date +%H)

# 检查是否在允许的时间范围内
# 22,23,00,01,02,03,04,05,06,07
if [ "$HOUR" -ge 22 ] || [ "$HOUR" -lt 8 ]; then
    echo "在允许的时间范围内,开始优化..."
    cd /root/.openclaw/workspace/quant/optimizer
    python3 strategy_optimizer.py
else
    echo "当前时间 $HOUR:00, 不在优化时间范围内(22:00-08:00), 跳过"
fi
