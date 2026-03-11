#!/bin/bash
# generate_daily_report.sh - 生成每日收盘深度报告（标准模板）

echo "=========================================="
echo "生成A股收盘深度报告 - 标准模板 v6"
echo "=========================================="
echo ""

# 切换到workspace目录
cd /root/.openclaw/workspace

# 使用venv运行脚本
./venv_runner.sh tools/daily_market_report_template_v6.py

echo ""
echo "=========================================="
echo "报告生成完成"
echo "=========================================="
echo ""

# 显示最新报告
latest_report=$(ls -t data/daily_report_*.md 2>/dev/null | head -1)
if [ -n "$latest_report" ]; then
    echo "最新报告: $latest_report"
    echo "生成时间: $(stat -c '%y' "$latest_report" | cut -d'.' -f1)"
    echo ""
    echo "报告预览:"
    echo "----------------------------------------"
    head -30 "$latest_report"
fi
