#!/bin/bash
# 发送Group 2 & 3 增量报告到指定群聊
export ZSXQ_TARGET_USER="chat:oc_8006b69736d0f4c7698b51de3ea61914"
cd /root/.openclaw/workspace
./venv_runner.sh tools/send_zsxq_report.py all >> /tmp/zsxq_send_incr.log 2>&1
