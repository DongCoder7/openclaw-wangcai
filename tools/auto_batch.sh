#!/bin/bash
# 自动循环运行批次补充脚本

WORKSPACE="/root/.openclaw/workspace"
LOG_FILE="$WORKSPACE/reports/auto_batch.log"

echo "[$(date '+%H:%M:%S')] 自动批次补充开始" >> $LOG_FILE

batch_num=1
while true; do
    echo "[$(date '+%H:%M:%S')] ========== 批次 $batch_num 开始 ==========" >> $LOG_FILE
    
    # 检查剩余股票数
    remaining=$(sqlite3 $WORKSPACE/data/historical/historical.db "SELECT COUNT(*) FROM stock_basic WHERE ts_code NOT IN (SELECT DISTINCT ts_code FROM fina_tushare WHERE period LIKE '2024%')")
    echo "[$(date '+%H:%M:%S')] 剩余待处理: $remaining 只" >> $LOG_FILE
    
    if [ "$remaining" -eq 0 ]; then
        echo "[$(date '+%H:%M:%S')] ✅ 所有股票处理完成!" >> $LOG_FILE
        break
    fi
    
    # 运行批次
    cd $WORKSPACE && python3 tools/supplement_batch.py >> $LOG_FILE 2>&1
    
    echo "[$(date '+%H:%M:%S')] 批次 $batch_num 结束，等待10秒后启动下一批次..." >> $LOG_FILE
    sleep 10
    
    batch_num=$((batch_num + 1))
done

echo "[$(date '+%H:%M:%S')] 全部批次完成" >> $LOG_FILE
