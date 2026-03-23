#!/root/.openclaw/workspace/venv/bin/python3
"""
检查知识星球特定消息是否有引用源
"""

import requests
import json
from datetime import datetime

GROUP_ID = "88512145458842"
COOKIE = "sensorsdata2015jssdkcross=%7B%22distinct_id%22%3A%22421882554581888%22%2C%22first_id%22%3A%2219957298c826cb-08f4b144c21fe3-1f525631-1484784-19957298c83903%22%2C%22props%22%3A%7B%22%24latest_traffic_source_type%22%3A%22%E8%87%AA%84%E6%90%9C%E7%B4%A2%E6%B5%81%E9%87%8F%22%2C%22%24latest_search_keyword%22%3A%22%E6%9C%AA%E5%8F%96%E5%88%B0%E5%80%BC%22%2C%22%24latest_referrer%22%3A%22https%3A%2F%2Fwww.baidu.com%2Flink%22%7D%2C%22identities%22%3A%22eyIkaWRlbnRpdHlfY29va2llX2lkIjoiMTk5NTcyOThjODI2Y2ItMDhmNGIxNDRjMjFmZTMtMWY1MjU2MzEtMTQ4NDc4NC0xOTk1NzI5OGM4MzkwMyIsIiRpZGVudGl0eV9sb2dpbl9pZCI6IjQyMTg4MjU0NDU4MTg4OCJ9%22%2C%22history_login_id%22%3A%7B%22name%22%3A%22%24identity_login_id%22%2C%22value%22%3A%22NDIxODgyNTQ0NTgxODg4%22%7D%2C%22%24device_id%22%3A%221OTk1NzI5OGM4MzkwMyJ9; abtest_env=product; zsxq_access_token=AD5BC203-E94C-4B32-9BA2-6BFD0C435426_C1F959E538CA66E8"

BASE_URL = "https://api.zsxq.com/v2"

headers = {
    "Cookie": COOKIE,
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json"
}

print("="*80)
print("🔍 检查消息是否有引用源")
print("="*80)
print(f"👤 作者: 反诈先锋")
print(f"🕐 时间: 18:02 (2026-03-22)")
print(f"💬 内容: 古往今来，这故事怎么一直不变啊")
print()

# 获取最新一页消息
url = f"{BASE_URL}/groups/{GROUP_ID}/topics?count=20"
response = requests.get(url, headers=headers, timeout=30)
data = response.json()

if not data.get("succeeded"):
    print(f"❌ API错误: {data}")
    exit(1)

topics = data.get("resp_data", {}).get("topics", [])
print(f"📄 获取到 {len(topics)} 条消息，查找目标...\n")

# 查找反诈先锋的最新消息
target_topic = None
for topic in topics:
    talk = topic.get("talk", {})
    owner = talk.get("owner", {})
    author = owner.get("name", "")
    text = talk.get("text", "")
    create_time = topic.get("create_time", "")
    
    # 匹配作者和内容
    if author == "反诈先锋" and "古往今来" in text:
        target_topic = topic
        print("🎯 找到目标消息！")
        print(f"   topic_id: {topic.get('topic_id')}")
        print(f"   create_time: {create_time}")
        print()
        break

if not target_topic:
    print("❌ 未找到目标消息")
    print("   搜索到的反诈先锋消息:")
    for topic in topics:
        talk = topic.get("talk", {})
        owner = talk.get("owner", {})
        if owner.get("name") == "反诈先锋":
            print(f"   - {topic.get('create_time')}: {talk.get('text', '')[:50]}...")
    exit(1)

# 分析引用源
print("="*80)
print("📋 【消息完整结构分析】")
print("="*80)

# 打印完整JSON（格式化）
print("\n📄 完整JSON数据结构:\n")
print(json.dumps(target_topic, ensure_ascii=False, indent=2))

print("\n" + "="*80)
print("🔍 【引用源检查】")
print("="*80)

# 检查quoted字段
quoted = target_topic.get("quoted")
if quoted:
    print("\n✅ 存在引用源 (quoted)!")
    print(f"\n📎 引用的原帖信息:")
    print(f"   - topic_id: {quoted.get('topic_id')}")
    print(f"   - type: {quoted.get('type')}")
    print(f"   - create_time: {quoted.get('create_time')}")
    
    # 提取引用的内容
    quoted_talk = quoted.get("talk", {})
    quoted_question = quoted.get("question", {})
    
    if quoted_talk:
        quoted_author = quoted_talk.get("owner", {}).get("name", "")
        quoted_text = quoted_talk.get("text", "")
        print(f"\n👤 引用作者: {quoted_author}")
        print(f"📝 引用内容:\n{'-'*60}")
        print(quoted_text[:800] if len(quoted_text) > 800 else quoted_text)
        if len(quoted_text) > 800:
            print(f"\n... (内容过长，共 {len(quoted_text)} 字符)")
        print("-"*60)
        
        # 检查引用的附件
        quoted_files = quoted_talk.get("files", [])
        if quoted_files:
            print(f"\n📎 引用的附件:")
            for f in quoted_files:
                print(f"   - {f.get('name')} (ID: {f.get('file_id')})")
    
    elif quoted_question:
        quoted_author = quoted_question.get("owner", {}).get("name", "")
        quoted_text = quoted_question.get("text", "")
        print(f"\n👤 引用作者: {quoted_author}")
        print(f"📝 引用内容: {quoted_text[:500]}")
        
else:
    print("\n❌ 不存在引用源 (quoted字段为空)")
    print("   这是一条独立发布的帖子，没有引用其他内容。")

# 检查其他相关字段
print("\n" + "="*80)
print("📊 【其他字段检查】")
print("="*80)

talk = target_topic.get("talk", {})

# comments
comments = target_topic.get("comments", [])
print(f"\n💬 评论数量: {len(comments)}")
if comments:
    for i, c in enumerate(comments[:3]):
        comment_text = c.get("talk", {}).get("text", "")
        print(f"   评论{i+1}: {comment_text[:80]}...")

# files
files = talk.get("files", [])
print(f"\n📎 附件数量: {len(files)}")
for f in files:
    print(f"   - {f.get('name')}")

# images
images = talk.get("images", [])
print(f"\n🖼️ 图片数量: {len(images)}")

# likes
likes = target_topic.get("likes_count", 0)
readers = target_topic.get("readers_count", 0)
print(f"\n👍 点赞: {likes} | 👀 阅读: {readers}")

print("\n" + "="*80)
print("✅ 分析完成")
print("="*80)
