#!/bin/bash
# 加载OpenClaw投资策略系统环境变量
# 使用: source setup_env.sh

WORKSPACE="/root/.openclaw/workspace"

echo "🚀 加载OpenClaw投资策略系统环境..."

# 加载长桥API配置
if [ -f "$WORKSPACE/.longbridge.env" ]; then
    export $(cat $WORKSPACE/.longbridge.env | xargs)
    echo "✅ 长桥API配置已加载"
else
    echo "⚠️ 长桥API配置未找到: $WORKSPACE/.longbridge.env"
fi

# 加载Tushare配置
if [ -f "$WORKSPACE/.tushare.env" ]; then
    export $(cat $WORKSPACE/.tushare.env | xargs)
    echo "✅ Tushare配置已加载"
fi

# 设置Python路径
export PYTHONPATH="$WORKSPACE/tools:$PYTHONPATH"

echo ""
echo "📊 可用命令:"
echo "  python3 skills/us-market-analysis/scripts/generate_report_longbridge.py"
echo "  python3 skills/ah-market-preopen/scripts/generate_report_longbridge.py"
echo "  python3 tools/zsxq_fetcher.py search 存储芯片"
echo ""
echo "✨ 环境加载完成!"
