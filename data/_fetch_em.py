#!/root/.openclaw/workspace/venv/bin/python3
"""用东方财富API获取A股涨跌统计数据"""
import requests
import json
from datetime import datetime

# 东方财富 - 涨跌家数统计
url = 'http://push2ex.eastmoney.com/getTopicZDFStat?ut=7eea3edcaed734bea9cbfc24409ed989&dpt=wz.ztzt'
r = requests.get(url, timeout=10)
data = r.json()

print(json.dumps(data, ensure_ascii=False, indent=2))
