#!/bin/bash
# venv激活脚本
# 使用方法: source venv_activate.sh

VENV_PATH="/root/.openclaw/workspace/venv"

if [ -f "$VENV_PATH/bin/activate" ]; then
    source "$VENV_PATH/bin/activate"
    echo "✅ 虚拟环境已激活"
    echo "Python: $(which python3)"
    echo "Pip: $(which pip)"
    echo ""
    echo "已安装的关键包:"
    pip list | grep -E "(qteasy|pandas|numpy|tushare|akshare)"
else
    echo "❌ 虚拟环境不存在: $VENV_PATH"
    echo "请先运行: python3 -m venv $VENV_PATH"
fi
