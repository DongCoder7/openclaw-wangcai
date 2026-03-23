#!/root/.openclaw/workspace/venv/bin/python3
"""
尝试多种方式获取知识星球文件下载链接
"""

import requests
import json

FILE_ID = "812222181818442"
GROUP_ID = "88512145458842"
COOKIE = "sensorsdata2015jssdkcross=%7B%22distinct_id%22%3A%22421882554581888%22%2C%22first_id%22%3A%2219957298c826cb-08f4b144c21fe3-1f525631-1484784-19957298c83903%22%2C%22props%22%3A%7B%22%24latest_traffic_source_type%22%3A%22%E8%87%AA%84%E6%90%9C%E7%B4%A2%E6%B5%81%E9%87%8F%22%2C%22%24latest_search_keyword%22%3A%22%E6%9C%AA%E5%8F%96%E5%88%B0%E5%80%BC%22%2C%22%24latest_referrer%22%3A%22https%3A%2F%2Fwww.baidu.com%2Flink%22%7D%2C%22identities%22%3A%22eyIkaWRlbnRpdHlfY29va2llX2lkIjoiMTk5NTcyOThjODI2Y2ItMDhmNGIxNDRjMjFmZTMtMWY1MjU2MzEtMTQ4NDc4NC0xOTk1NzI5OGM4MzkwMyIsIiRpZGVudGl0eV9sb2dpbl9pZCI6IjQyMTg4MjU0NDU4MTg4OCJ9%22%2C%22history_login_id%22%3A%7B%22name%22%3A%22%24identity_login_id%22%2C%22value%22%3A%22NDIxODgyNTQ0NTgxODg4%22%7D%2C%22%24device_id%22%3A%221OTk1NzI5OGM4MzkwMyJ9; abtest_env=product; zsxq_access_token=AD5BC203-E94C-4B32-9BA2-6BFD0C435426_C1F959E538CA66E8"

headers = {
    "Cookie": COOKIE,
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json",
    "Content-Type": "application/json"
}

BASE_URL = "https://api.zsxq.com/v2"

# 尝试各种可能的API端点
endpoints = [
    # GET请求
    ("GET", f"{BASE_URL}/files/{FILE_ID}/download_url"),
    ("GET", f"{BASE_URL}/groups/{GROUP_ID}/files/{FILE_ID}/download_url"),
    ("GET", f"{BASE_URL}/files/{FILE_ID}"),
    
    # POST请求 (可能需要)
    ("POST", f"{BASE_URL}/files/{FILE_ID}/download_url"),
    ("POST", f"{BASE_URL}/files/{FILE_ID}"),
]

print("🔍 尝试各种API端点获取下载链接...\n")

for method, url in endpoints:
    print(f"🔄 {method} {url}")
    try:
        if method == "GET":
            resp = requests.get(url, headers=headers, timeout=10)
        else:
            resp = requests.post(url, headers=headers, json={}, timeout=10)
        
        print(f"   状态: {resp.status_code}")
        
        if resp.status_code == 200:
            data = resp.json()
            if data.get("succeeded"):
                print(f"   ✅ 成功!")
                print(f"   响应: {json.dumps(data, ensure_ascii=False, indent=2)[:500]}")
                
                # 检查是否有下载链接
                resp_data = data.get("resp_data", {})
                if "download_url" in resp_data:
                    print(f"\n🎉 找到下载链接: {resp_data['download_url'][:100]}...")
            else:
                print(f"   ⚠️ API返回失败: {data.get('resp_err', 'Unknown')}")
        else:
            print(f"   ❌ HTTP错误: {resp.status_code}")
            
    except Exception as e:
        print(f"   ❌ 异常: {e}")
    
    print()
