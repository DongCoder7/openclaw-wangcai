#!/root/.openclaw/workspace/venv/bin/python3
"""
检查topic详情中的文件下载链接
"""

import requests
import json

TOPIC_ID = "45811258122824288"
COOKIE = "sensorsdata2015jssdkcross=%7B%22distinct_id%22%3A%22421882554581888%22%2C%22first_id%22%3A%2219957298c826cb-08f4b144c21fe3-1f525631-1484784-19957298c83903%22%2C%22props%22%3A%7B%22%24latest_traffic_source_type%22%3A%22%E8%87%AA%84%E6%90%9C%E7%B4%A2%E6%B5%81%E9%87%8F%22%2C%22%24latest_search_keyword%22%3A%22%E6%9C%AA%E5%8F%96%E5%88%B0%E5%80%BC%22%2C%22%24latest_referrer%22%3A%22https%3A%2F%2Fwww.baidu.com%2Flink%22%7D%2C%22identities%22%3A%22eyIkaWRlbnRpdHlfY29va2llX2lkIjoiMTk5NTcyOThjODI2Y2ItMDhmNGIxNDRjMjFmZTMtMWY1MjU2MzEtMTQ4NDc4NC0xOTk1NzI5OGM4MzkwMyIsIiRpZGVudGl0eV9sb2dpbl9pZCI6IjQyMTg4MjU0NDU4MTg4OCJ9%22%2C%22history_login_id%22%3A%7B%22name%22%3A%22%24identity_login_id%22%2C%22value%22%3A%22NDIxODgyNTQ0NTgxODg4%22%7D%2C%22%24device_id%22%3A%221OTk1NzI5OGM4MzkwMyJ9; abtest_env=product; zsxq_access_token=AD5BC203-E94C-4B32-9BA2-6BFD0C435426_C1F959E538CA66E8"

BASE_URL = "https://api.zsxq.com/v2"

headers = {
    "Cookie": COOKIE,
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json"
}

# 获取topic详情
url = f"{BASE_URL}/topics/{TOPIC_ID}"
response = requests.get(url, headers=headers, timeout=30)
data = response.json()

print("📋 Topic详情中的文件信息:\n")

if data.get("succeeded"):
    topic = data.get("resp_data", {}).get("topic", {})
    talk = topic.get("talk", {})
    files = talk.get("files", [])
    
    for f in files:
        print(f"文件ID: {f.get('file_id')}")
        print(f"文件名: {f.get('name')}")
        print(f"大小: {f.get('size')} bytes")
        print(f"下载次数: {f.get('download_count')}")
        print(f"完整字段:")
        print(json.dumps(f, ensure_ascii=False, indent=2))
        print()
    
    # 检查是否有download_url字段
    print("\n🔍 检查talk中的其他字段...")
    for key in talk.keys():
        if 'url' in key.lower() or 'download' in key.lower() or 'file' in key.lower():
            print(f"  {key}: {talk[key]}")
else:
    print(f"❌ 错误: {data}")
