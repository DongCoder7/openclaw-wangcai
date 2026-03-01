#!/bin/bash
# 多因子自动循环批次脚本

WORKSPACE="/root/.openclaw/workspace"
LOG_FILE="$WORKSPACE/reports/auto_factors_batch.log"

echo "[$(date '+%H:%M:%S')] 多因子自动批次补充开始" >> $LOG_FILE

batch_num=1
while true; do
    echo "[$(date '+%H:%M:%S')] ========== 多因子批次 $batch_num 开始 ==========" >> $LOG_FILE
    
    # 检查剩余股票数
    remaining=$(sqlite3 $WORKSPACE/data/historical/historical.db "SELECT COUNT(DISTINCT ts_code) FROM daily_price WHERE trade_date BETWEEN '20180101' AND '20181231' AND ts_code NOT IN (SELECT DISTINCT ts_code FROM stock_factors WHERE trade_date BETWEEN '20180101' AND '20181231')")
    echo "[$(date '+%H:%M:%S')] 多因子剩余缺口: $remaining 只" >> $LOG_FILE
    
    if [ "$remaining" -eq 0 ]; then
        echo "[$(date '+%H:%M:%S')] ✅ 多因子所有股票处理完成!" >> $LOG_FILE
        break
    fi
    
    # 运行批次
    cd $WORKSPACE && python3 tools/supplement_factors_batch.py >> $LOG_FILE 2>&1
    
    echo "[$(date '+%H:%M:%S')] 多因子批次 $batch_num 结束，等待10秒..." >> $LOG_FILE
    sleep 10
    
    batch_num=$((batch_num + 1))
done

echo "[$(date '+%H:%M:%S')] 多因子全部批次完成" >> $LOG_FILE
