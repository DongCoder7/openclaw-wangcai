#!/root/.openclaw/workspace/venv/bin/python3
"""
获取知识星球单条消息原始API数据结构
用于分析quoted、comments、files等字段
"""

import requests
import json
import os
from datetime import datetime

# Group ID (从文件名推断: 88512145458842)
GROUP_ID = "88512145458842"
COOKIE = "sensorsdata2015jssdkcross=%7B%22distinct_id%22%3A%22421882554581888%22%2C%22first_id%22%3A%2219957298c826cb-08f4b144c21fe3-1f525631-1484784-19957298c83903%22%2C%22props%22%3A%7B%22%24latest_traffic_source_type%22%3A%22%E8%87%AA%84%E6%90%9C%E7%B4%A2%E6%B5%81%E9%87%8F%22%2C%22%24latest_search_keyword%22%3A%22%E6%9C%AA%E5%8F%96%E5%88%B0%E5%80%BC%22%2C%22%24latest_referrer%22%3A%22https%3A%2F%2Fwww.baidu.com%2Flink%22%7D%2C%22identities%22%3A%22eyIkaWRlbnRpdHlfY29va2llX2lkIjoiMTk5NTcyOThjODI2Y2ItMDhmNGIxNDRjMjFmZTMtMWY1MjU2MzEtMTQ4NDc4NC0xOTk1NzI5OGM4MzkwMyIsIiRpZGVudGl0eV9sb2dpbl9pZCI6IjQyMTg4MjU0NDU4MTg4OCJ9%22%2C%22history_login_id%22%3A%7B%22name%22%3A%22%24identity_login_id%22%2C%22value%22%3A%22NDIxODgyNTQ0NTgxODg4%22%7D%2C%22%24device_id%22%3A%221OTk1NzI5OGM4MzkwMyJ9; abtest_env=product; zsxq_access_token=AD5BC203-E94C-4B32-9BA2-6BFD0C435426_C1F959E538CA66E8"

BASE_URL = "https://api.zsxq.com/v2"

headers = {
    "Cookie": COOKIE,
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json"
}

print(f"🚀 抓取 Group: {GROUP_ID}")
print(f"   时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print("="*80)

# 获取最新一页
try:
    url = f"{BASE_URL}/groups/{GROUP_ID}/topics?count=20"
    response = requests.get(url, headers=headers, timeout=30)
    response.raise_for_status()
    data = response.json()
    
    if not data.get("succeeded"):
        print(f"❌ API错误: {data}")
        exit(1)
    
    resp_data = data.get("resp_data", {})
    topics = resp_data.get("topics", [])
    
    print(f"📄 获取到 {len(topics)} 条消息\n")
    
    # 找反诈先锋的消息
    for topic in topics:
        talk = topic.get("talk", {})
        owner = talk.get("owner", {}) if talk else {}
        author = owner.get("name", "")
        
        if author == "反诈先锋":
            print("🎯 找到目标消息！")
            print("="*80)
            
            # 打印完整原始数据结构
            print("\n📋 【完整原始数据结构】\n")
            print(json.dumps(topic, ensure_ascii=False, indent=2))
            
            # 关键字段分析
            print("\n" + "="*80)
            print("🔍 【关键字段分析】")
            print("="*80)
            
            print(f"\n1️⃣ topic_id: {topic.get('topic_id')}")
            print(f"   type: {topic.get('type')}")
            print(f"   create_time: {topic.get('create_time')}")
            
            # talk字段
            if talk:
                print(f"\n2️⃣ talk (发帖内容):")
                print(f"   title: {talk.get('title', '')[:100]}")
                print(f"   text: {talk.get('text', '')[:200]}...")
                print(f"   owner.name: {talk.get('owner', {}).get('name')}")
            
            # quoted字段 (引用的内容)
            quoted = topic.get("quoted")
            if quoted:
                print(f"\n3️⃣ quoted (引用的原帖) ✅ 存在！:")
                print(json.dumps(quoted, ensure_ascii=False, indent=2)[:2000])
            else:
                print(f"\n3️⃣ quoted (引用的原帖): ❌ 不存在")
            
            # comments字段
            comments = topic.get("comments")
            if comments:
                print(f"\n4️⃣ comments (评论列表) ✅ 存在！ 数量: {len(comments)}")
                for i, c in enumerate(comments[:3]):
                    print(f"   评论{i+1}: {str(c)[:100]}...")
            else:
                print(f"\n4️⃣ comments (评论列表): ❌ 不存在")
            
            # show_comments
            show_comments = topic.get("show_comments")
            print(f"\n5️⃣ show_comments: {show_comments}")
            
            # files字段
            files = topic.get("files", [])
            if files:
                print(f"\n6️⃣ files (附件列表) ✅ 存在！ 数量: {len(files)}")
                for f in files:
                    print(f"   - name: {f.get('name')}")
                    print(f"     download_url: {f.get('download_url', 'N/A')[:100]}...")
                    print(f"     file_id: {f.get('file_id')}")
                    print(f"     size: {f.get('size')}")
            else:
                print(f"\n6️⃣ files (附件列表): ❌ 为空")
            
            # images字段
            images = topic.get("images", [])
            if images:
                print(f"\n7️⃣ images (图片列表) ✅ 存在！ 数量: {len(images)}")
                for img in images[:3]:
                    print(f"   - {img.get('large', {}).get('url', 'N/A')[:80]}...")
            else:
                print(f"\n7️⃣ images (图片列表): ❌ 为空")
            
            # tags/channels
            tags = topic.get("tags", [])
            if tags:
                print(f"\n8️⃣ tags (频道标签): {[t.get('name') for t in tags]}")
            
            print("\n" + "="*80)
            break
    else:
        print("❌ 未找到反诈先锋的消息")
        print(f"   作者列表: {[t.get('talk', {}).get('owner', {}).get('name') for t in topics]}")
        
except Exception as e:
    print(f"❌ 错误: {e}")
    import traceback
    traceback.print_exc()
