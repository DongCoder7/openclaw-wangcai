#!/bin/bash
# Group 3: 行业研究 - 增量抓取 (V2带重试)
# 从.zsxq_env读取完整cookie
export ZSXQ_GROUP_ID="88512145458842"
export ZSXQ_COOKIE=$(grep 'ZSXQ_COOKIES_GROUP23' /root/.openclaw/workspace/.zsxq_env | cut -d'"' -f2)
cd /root/.openclaw/workspace
./venv_runner.sh tools/zsxq_fetcher_incremental_v2.py >> /tmp/zsxq_g3_incr.log 2>&1
