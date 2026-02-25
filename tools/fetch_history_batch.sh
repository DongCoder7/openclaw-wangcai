#!/bin/bash
# 后台批量获取历史数据脚本
# 分批次获取，避免API限制

WORKSPACE=/root/.openclaw/workspace
LOG_FILE=$WORKSPACE/data/fetch_history.log

echo "Starting batch fetch at $(date)" >> $LOG_FILE

# 获取2021-2024年数据（分4批，每年一批）
for year in 2021 2022 2023 2024; do
    echo "Fetching year $year..." >> $LOG_FILE
    python3 $WORKSPACE/tools/batch_fetch_history.py --fetch --start $year --end $year >> $LOG_FILE 2>&1
    echo "Year $year completed at $(date)" >> $LOG_FILE
    sleep 60  # 休息1分钟
done

echo "Batch fetch completed at $(date)" >> $LOG_FILE
