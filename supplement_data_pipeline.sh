#!/bin/bash
# 量化系统数据补充脚本 - 后台运行版本
# 使用方式: nohup ./supplement_data_pipeline.sh > supplement.log 2>&1 &

set -e

# 配置
WORKSPACE="/root/.openclaw/workspace"
VENV_PATH="$WORKSPACE/venv"
LOG_DIR="$WORKSPACE/logs/supplement"
DB_PATH="$WORKSPACE/data/historical/historical.db"
SCRIPT_DIR="$WORKSPACE/skills/quant-data-system/scripts"

# 创建日志目录
mkdir -p "$LOG_DIR"

# 日志函数 (写入文件)
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_DIR/supplement_$(date +%Y%m%d).log"
}

# 激活虚拟环境
activate_venv() {
    log "激活虚拟环境..."
    if [ -f "$VENV_PATH/bin/activate" ]; then
        source "$VENV_PATH/bin/activate"
        log "✅ 虚拟环境已激活: $(which python3)"
    else
        log "❌ 虚拟环境不存在: $VENV_PATH"
        exit 1
    fi
}

# 检查数据库连接
check_db() {
    log "检查数据库连接..."
    
    # 等待数据库解锁
    local retries=0
    local max_retries=10
    
    while [ $retries -lt $max_retries ]; do
        python3 << 'PYCODE' 2>/dev/null
import sqlite3
import sys
try:
    conn = sqlite3.connect('/root/.openclaw/workspace/data/historical/historical.db', timeout=10)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM daily_price LIMIT 1")
    conn.close()
    sys.exit(0)
except Exception as e:
    print(f"DB locked: {e}")
    sys.exit(1)
PYCODE
        
        if [ $? -eq 0 ]; then
            log "✅ 数据库连接正常"
            return 0
        fi
        
        retries=$((retries + 1))
        log "⏳ 数据库被锁定，等待10秒 (尝试 $retries/$max_retries)..."
        sleep 10
    done
    
    log "❌ 数据库无法连接，退出"
    exit 1
}

# 测试Python环境
test_env() {
    log "测试Python环境..."
    python3 --version
    
    python3 -c "import pandas; import numpy; import tushare; print('✅ 依赖检查通过')" 2>/dev/null || {
        log "❌ 依赖检查失败"
        exit 1
    }
}

# 执行数据补充脚本
run_data_supplement() {
    log "================================"
    log "开始数据补充"
    log "================================"
    
    cd "$SCRIPT_DIR"
    
    # 步骤1: Tushare财务数据
    log "步骤1: Tushare财务数据 (2018-2024)..."
    for year in 2018 2019 2020 2021 2022 2023 2024; do
        log "  处理 $year 年..."
        
        python3 <> PYEOF 2>&1 | tee -a "$LOG_DIR/step1_${year}.log"
import sys
sys.path.insert(0, '/root/.openclaw/workspace/skills/quant-data-system/scripts')
import supplement_data as sd

try:
    sd.supplement_fina_tushare_for_year('$year')
    print(f"✅ $year 完成")
except Exception as e:
    print(f"⚠️ $year 错误: {e}")
PYEOF
        
        sleep 3  # 避免请求过快
    done
    
    # 步骤2: 技术指标
    log "步骤2: 技术指标..."
    python3 <> PYEOF 2>&1 | tee -a "$LOG_DIR/step2.log"
import sys
sys.path.insert(0, '/root/.openclaw/workspace/skills/quant-data-system/scripts')
import supplement_data as sd

try:
    sd.supplement_technical_factors()
    print("✅ 技术指标完成")
except Exception as e:
    print(f"⚠️ 技术指标错误: {e}")
PYEOF
    
    # 步骤3: 财务因子
    log "步骤3: 财务因子..."
    python3 <> PYEOF 2>&1 | tee -a "$LOG_DIR/step3.log"
import sys
sys.path.insert(0, '/root/.openclaw/workspace/skills/quant-data-system/scripts')
import supplement_data as sd

try:
    sd.supplement_fina_factors()
    print("✅ 财务因子完成")
except Exception as e:
    print(f"⚠️ 财务因子错误: {e}")
PYEOF
    
    # 步骤4: efinance数据
    log "步骤4: efinance数据 (2022-2024)..."
    for year in 2022 2023 2024; do
        log "  处理 $year 年..."
        
        python3 <> PYEOF 2>&1 | tee -a "$LOG_DIR/step4_${year}.log"
import sys
sys.path.insert(0, '/root/.openclaw/workspace/skills/quant-data-system/scripts')
import supplement_data as sd

try:
    sd.supplement_efinance_data('$year')
    print(f"✅ $year 完成")
except Exception as e:
    print(f"⚠️ $year 错误: {e}")
PYEOF
        
        sleep 3
    done
    
    log "================================"
    log "数据补充完成"
    log "================================"
}

# 生成最终报告
generate_report() {
    log "生成数据报告..."
    
    python3 <> PYEOF
try:
    import sqlite3
    
    conn = sqlite3.connect('/root/.openclaw/workspace/data/historical/historical.db')
    cursor = conn.cursor()
    
    print("\n=== 数据回补最终统计 ===\n")
    
    tables = [
        ('daily_price', '日线价格'),
        ('fina_tushare', 'Tushare财务'),
        ('stock_fina', '财务数据'),
        ('stock_factors', '综合因子'),
        ('stock_defensive_factors', '防御性因子'),
        ('stock_valuation_factors', '估值因子'),
        ('stock_efinance', '东方财富财务')
    ]
    
    for table, name in tables:
        try:
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            count = cursor.fetchone()[0]
            print(f"{name:20s}: {count:10,} 条记录")
        except:
            print(f"{name:20s}: 表不存在或为空")
    
    conn.close()
    
except Exception as e:
    print(f"生成报告失败: {e}")
PYEOF
    
    log "报告已保存到: $LOG_DIR/"
}

# 主流程
main() {
    log "================================"
    log "数据补充管道启动"
    log "PID: $$"
    log "================================"
    
    activate_venv
    test_env
    check_db
    run_data_supplement
    generate_report
    
    log "✅ 所有步骤完成"
    log "日志: $LOG_DIR/supplement_$(date +%Y%m%d).log"
}

# 运行
main
