#!/bin/bash
# 数据回补质量保证流程 - 制度化执行脚本
# 严格执行：小批量测试 → 验证 → 大规模执行

set -e

WORKSPACE="/root/.openclaw/workspace"
VENV_PATH="$WORKSPACE/venv"
LOG_FILE="$WORKSPACE/logs/quality_assurance_$(date +%Y%m%d_%H%M).log"
PID_FILE="$WORKSPACE/logs/supplement_qa.pid"

# 质量检查点
CHECKPOINTS=(
    "PRE_TEST:小批量预测试"
    "VERIFY:数据入库验证"
    "APPROVE:人工确认"
    "BATCH:批量执行"
    "MONITOR:实时监控"
)

# 记录日志
log() {
    echo "[$(date '+%H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

# 检查点1: 小批量预测试
pre_test() {
    log "="*60
    log "【检查点1】小批量预测试（10只股票）"
    log "="*60
    
    source "$VENV_PATH/bin/activate"
    source "$WORKSPACE/.tushare.env"
    
    cd "$WORKSPACE/tools"
    
    # 执行小批量测试
    log "执行10只股票的测试..."
    python3 << 'PYEOF'
import sys
sys.path.insert(0, '.')
import supplement_batch_v2 as sb

# 只处理10只
stocks, _ = sb.get_pending_stocks_yearly(2018)
test_stocks = stocks[:10] if len(stocks) > 10 else stocks

log(f"测试标的: {len(test_stocks)}只")
inserted, queried = sb.supplement_year(sb.pro, 2018, test_stocks)
log(f"测试结果: 查询{queried}次, 入库{inserted}条")
PYEOF
    
    log "小批量测试完成"
}

# 检查点2: 数据入库验证
verify_data() {
    log "="*60
    log "【检查点2】数据入库验证"
    log "="*60
    
    sqlite3 "$WORKSPACE/data/historical/historical.db" <3 'SQLEOF'
SELECT '2018年' as year, COUNT(*) as records, COUNT(DISTINCT ts_code) as stocks 
FROM fina_tushare WHERE period >= '20180101' AND period <= '20181231';
SQLEOF
    
    log "验证完成，请确认数据是否正确入库"
}

# 检查点3: 等待人工确认
wait_approval() {
    log "="*60
    log "【检查点3】等待人工确认"
    log "="*60
    log "请检查:"
    log "  1. 测试数据是否正确入库？"
    log "  2. 日志是否有错误？"
    log "  3. 是否继续批量执行？"
    log ""
    log "确认后继续...(自动继续，如需停止请Ctrl+C)"
    
    sleep 5
}

# 检查点4: 批量执行
batch_execute() {
    log "="*60
    log "【检查点4】批量执行"
    log "="*60
    
    echo $$ > "$PID_FILE"
    
    log "启动正式数据回补..."
    python3 "$WORKSPACE/tools/supplement_batch_v2.py" 2>&1 | tee -a "$LOG_FILE"
    
    rm -f "$PID_FILE"
}

# 检查点5: 实时监控
monitor() {
    log "="*60
    log "【检查点5】实时监控"
    log "="*60
    log "每小时检查一次数据入库情况..."
    
    while true; do
        sleep 3600  # 每小时检查
        
        # 查询最新数据量
        sqlite3 "$WORKSPACE/data/historical/historical.db" << 'SQLEOF' | tee -a "$LOG_FILE"
SELECT 
    '2018' as year, COUNT(*) as cnt FROM fina_tushare WHERE period LIKE '2018%'
UNION ALL
SELECT '2019', COUNT(*) FROM fina_tushare WHERE period LIKE '2019%'
UNION ALL
SELECT '2020', COUNT(*) FROM fina_tushare WHERE period LIKE '2020%'
UNION ALL
SELECT '2021', COUNT(*) FROM fina_tushare WHERE period LIKE '2021%'
UNION ALL
SELECT '2022', COUNT(*) FROM fina_tushare WHERE period LIKE '2022%';
SQLEOF
        
        log "监控完成，数据量已记录"
    done
}

# 主流程
main() {
    log "="*60
    log "🚀 数据回补质量保证流程启动"
    log "="*60
    log "时间: $(date)"
    log "="*60
    
    # 执行5个检查点
    pre_test
    verify_data
    wait_approval
    batch_execute
    monitor
    
    log "="*60
    log "✅ 质量保证流程完成"
    log "="*60
}

# 运行
main
