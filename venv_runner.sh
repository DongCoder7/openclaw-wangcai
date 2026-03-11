#!/bin/bash
# venv_runner.sh - 强制使用venv运行Python脚本
# 用法: ./venv_runner.sh <python_script.py> [args...]

VENV_PYTHON="/root/.openclaw/workspace/venv/bin/python3"

echo "=========================================="
echo "Venv Runner - 强制使用虚拟环境"
echo "=========================================="

if [ $# -eq 0 ]; then
    echo "用法: $0 <python_script.py> [args...]"
    echo ""
    echo "示例:"
    echo "  $0 tools/daily_market_report.py"
    echo "  $0 skills/us-market-analysis/scripts/generate_report.py --date 20260304"
    exit 1
fi

SCRIPT=$1
shift

# 检查venv是否存在
if [ ! -f "$VENV_PYTHON" ]; then
    echo "❌ 错误: venv不存在: $VENV_PYTHON"
    echo "请先创建venv: python3 -m venv /root/.openclaw/workspace/venv"
    exit 1
fi

# 检查脚本是否存在
if [ ! -f "$SCRIPT" ]; then
    echo "❌ 错误: 脚本不存在: $SCRIPT"
    exit 1
fi

# 加载环境变量（自动检测）
SCRIPT_NAME=$(basename "$SCRIPT")

# 加载长桥环境变量
ENV_FILE="/root/.openclaw/workspace/.longbridge.env"
if [ -f "$ENV_FILE" ]; then
    echo "📋 加载环境变量: .longbridge.env"
    export $(grep -v '^#' "$ENV_FILE" | xargs)
fi

# 如果是知识星球脚本，额外加载.zsxq.env
if [[ "$SCRIPT_NAME" == *"zsxq"* ]]; then
    ZSXQ_ENV="/root/.openclaw/workspace/.zsxq.env"
    if [ -f "$ZSXQ_ENV" ]; then
        echo "📋 加载环境变量: .zsxq.env"
        export $(grep -v '^#' "$ZSXQ_ENV" | xargs)
    fi
fi

echo "🐍 Python: $VENV_PYTHON"
echo "📄 脚本: $SCRIPT"
echo "⏰ 启动时间: $(date '+%Y-%m-%d %H:%M:%S')"
echo "=========================================="
echo ""

# 使用venv运行
exec "$VENV_PYTHON" "$SCRIPT" "$@"
