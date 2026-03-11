#!/bin/bash
# 生成A股收盘深度报告 - Skill快捷入口

cd /root/.openclaw/workspace
./venv_runner.sh skills/daily-market-report/scripts/generate_report.py
