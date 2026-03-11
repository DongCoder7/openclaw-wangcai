#!/bin/bash
# 发送Group 2 & 3 增量报告
export ZSXQ_TARGET_USER=ou_efbad805767f4572e8f93ebafa8d5402
cd /root/.openclaw/workspace
./venv_runner.sh tools/send_zsxq_report.py all >> /tmp/zsxq_send_incr.log 2>&1
