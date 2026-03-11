#!/bin/bash
# 抓取调研纪要 (Group 51122188845424)
cd /root/.openclaw/workspace
export ZSXQ_GROUP_ID="51122188845424"
export ZSXQ_COOKIE="zsxq_access_token=4BA99A16-061A-4E9B-9517-3C8C2824B196_8577CEF494274298"
./venv_runner.sh tools/zsxq_fetcher_prod.py >> /tmp/zsxq_diaoyanji_cron.log 2>&1
