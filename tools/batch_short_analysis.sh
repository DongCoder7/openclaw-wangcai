#!/bin/bash
# 批量短期分析 - HALO组合标的池

cd /root/.openclaw/workspace

# 定义标的池
# AI算力
AI_STOCKS="300308.SZ 300502.SZ 300394.SZ 688256.SH 688041.SH"

# 新能源
NEW_ENERGY_STOCKS="300750.SZ 601012.SH 600438.SH 002129.SZ 300274.SZ"

# HALO电力
POWER_STOCKS="601985.SH 600900.SH 600011.SH 600886.SH"

# 国产替代
SEMI_STOCKS="688981.SH 002371.SZ 688012.SH 603501.SH 603986.SH"

# 合并所有标的
ALL_STOCKS="$AI_STOCKS $NEW_ENERGY_STOCKS $POWER_STOCKS $SEMI_STOCKS"

echo "================================"
echo "开始批量短期走势分析"
echo "标的数量: 18只"
echo "================================"
echo ""

# 执行分析
./venv_runner.sh skills/short-term-analysis/scripts/analyze_short_term.py $ALL_STOCKS
