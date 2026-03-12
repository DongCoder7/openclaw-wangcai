#!/bin/bash
# Group 3: 行业研究 - 增量抓取 (V2带重试)
export ZSXQ_GROUP_ID="88512145458842"
export ZSXQ_COOKIE="zsxq_access_token=AD5BC203-E94C-4B32-9BA2-6BFD0C435426_C1F959E538CA66E8"
cd /root/.openclaw/workspace
./venv_runner.sh tools/zsxq_fetcher_incremental_v2.py >> /tmp/zsxq_g3_incr.log 2>&1
