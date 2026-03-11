#!/bin/bash
# HALO组合完整分析

cd /root/.openclaw/workspace

echo "================================"
echo "HALO组合 - 完整短期分析"
echo "================================"
echo ""

# HALO组合标的
STOCKS="601985.SH 600900.SH 300308.SZ 600938.SH 600011.SH 688981.SH"

./venv_runner.sh skills/short-term-analysis/scripts/analyze_short_term.py $STOCKS
