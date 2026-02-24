#!/bin/bash
# 异步策略优化器 - v23异步汇报版
# 每轮迭代都会更新报告文件，heartbeat会检测并汇报

cd /root/.openclaw/workspace/quant/optimizer
LOG_FILE="/root/.openclaw/workspace/quant/optimizer/cron.log"

echo "$(date '+%Y-%m-%d %H:%M:%S'): ====== 检查优化任务 ======" >> $LOG_FILE

# 检查是否有正在运行的任务
if [ -f "optimizer.lock" ]; then
    PID=$(cat optimizer.lock)
    if ps -p $PID > /dev/null 2>&1; then
        echo "$(date '+%Y-%m-%d %H:%M:%S'): 优化器正在运行中 (PID: $PID)，跳过本次" >> $LOG_FILE
        # 检查是否有新报告（每轮迭代产生的）
        if [ -f "latest_report.txt" ]; then
            REPORT_MTIME=$(stat -c %Y latest_report.txt)
            LAST_CHECK_FILE=".last_report_check"
            if [ -f "$LAST_CHECK_FILE" ]; then
                LAST_CHECK=$(cat $LAST_CHECK_FILE)
                if [ "$REPORT_MTIME" -gt "$LAST_CHECK" ]; then
                    echo "$(date '+%Y-%m-%d %H:%M:%S'): 检测到新报告" >> $LOG_FILE
                fi
            fi
            echo $REPORT_MTIME > $LAST_CHECK_FILE
        fi
        exit 0
    else
        echo "$(date '+%Y-%m-%d %H:%M:%S'): 检测到僵尸锁，清理中..." >> $LOG_FILE
        rm -f optimizer.lock
    fi
fi

# 启动新的优化任务（后台运行）
echo "$(date '+%Y-%m-%d %H:%M:%S'): 启动v23异步优化器..." >> $LOG_FILE

# 使用nohup运行异步版本
nohup bash -c '
    cd /root/.openclaw/workspace/quant/optimizer
    # 使用异步版本，每轮迭代都会写入报告
    python3 smart_optimizer_v23_async.py > v23_async_$(date +%Y%m%d_%H%M%S).log 2>&1
    echo "$(date '+%Y-%m-%d %H:%M:%S'): 优化完成" >> cron.log
    rm -f optimizer.lock
' > /dev/null 2>&1 &

OPTIMIZER_PID=$!
echo $OPTIMIZER_PID > optimizer.lock

echo "$(date '+%Y-%m-%d %H:%M:%S'): 优化器已在后台启动 (PID: $OPTIMIZER_PID)" >> $LOG_FILE
echo "$(date '+%Y-%m-%d %H:%M:%S'): 每轮迭代都会更新 latest_report.txt" >> $LOG_FILE
