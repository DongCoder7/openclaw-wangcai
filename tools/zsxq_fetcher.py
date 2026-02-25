#!/usr/bin/env python3
"""
知识星球调研纪要获取工具
自动获取"调研纪要"星球的最新内容
"""
import requests
import json
import os
from datetime import datetime

# 配置
GROUP_ID = "28855458518111"
# 完整的cookies (包含sensorsdata、abtest_env和token)
COOKIES = "sensorsdata2015jssdkcross=%7B%22distinct_id%22%3A%22421882554581888%22%2C%22first_id%22%3A%2219957298c826cb-08f4b144c21fe3-1f525631-1484784-19957298c83903%22%2C%22props%22%3A%7B%22%24latest_traffic_source_type%22%3A%22%E7%A4%BE%E4%BA%A4%E7%BD%91%E7%AB%99%E6%B5%81%E9%87%8F%22%2C%22%24latest_search_keyword%22%3A%22%E6%9C%AA%E5%8F%96%E5%88%B0%E5%80%BC%22%2C%22%24latest_referrer%22%3A%22https%3A%2F%2Fopen.weixin.qq.com%2F%22%7D%2C%22identities%22%3A%22eyIkaWRlbnRpdHlfY29va2llX2lkIjoiMTk5NTcyOThjODI2Y2ItMDhmNGIxNDRjMjFmZTMtMWY1MjU2MzEtMTQ4NDc4NC0xOTk1NzI5OGM4MzkwMyIsIiRpZGVudGl0eV9sb2dpbl9pZCI6IjQyMTg4MjU1NDU4MTg4OCJ9%22%2C%22history_login_id%22%3A%7B%22name%22%3A%22%24identity_login_id%22%2C%22value%22%3A%22421882554581888%22%7D%2C%22%24device_id%22%3A%2219957298c826cb-08f4b144c21fe3-1f525631-1484784-19957298c83903%22%7D; abtest_env=product; zsxq_access_token=26FC1241-0A1A-42BF-87B9-BE97A4A42AB1_2ECB6A0A4CD9622F"
BASE_URL = "https://api.zsxq.com/v2"

def get_topics(count=20, keyword=None):
    """获取知识星球文章
    
    Args:
        count: 获取文章数量
        keyword: 关键词筛选 (可选)
    
    Returns:
        list: 文章列表
    """
    url = f"{BASE_URL}/groups/{GROUP_ID}/topics?count={count}"
    
    headers = {
        "Cookie": COOKIES,
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json"
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=30)
        data = response.json()
        
        if not data.get('succeeded'):
            print(f"❌ 获取失败: {data.get('code', 'unknown error')}")
            return []
        
        topics = data.get('resp_data', {}).get('topics', [])
        
        # 关键词筛选
        if keyword:
            filtered = []
            for t in topics:
                text = t.get('talk', {}).get('text', '')
                if keyword in text:
                    filtered.append(t)
            topics = filtered
        
        return topics
        
    except Exception as e:
        print(f"❌ 请求异常: {e}")
        return []

def format_topic(topic):
    """格式化单篇文章"""
    talk = topic.get('talk', {})
    text = talk.get('text', '')
    owner = talk.get('owner', {})
    
    return {
        'id': topic.get('topic_id'),
        'time': topic.get('create_time', '')[:16],
        'author': owner.get('name', '未知'),
        'text': text[:300] + '...' if len(text) > 300 else text,
        'read_count': topic.get('reading_count', 0),
        'like_count': topic.get('likes_count', 0)
    }

def search_industry_info(industry, count=10):
    """搜索特定行业信息
    
    Args:
        industry: 行业关键词 (如: 存储芯片、半导体、PCB)
        count: 获取数量
    
    Returns:
        list: 相关文章
    """
    print(f"🔍 搜索 '{industry}' 相关信息...")
    topics = get_topics(count=50, keyword=industry)
    
    if not topics:
        print(f"⚠️ 未找到 '{industry}' 相关内容")
        return []
    
    print(f"✅ 找到 {len(topics)} 条相关内容\n")
    
    results = []
    for t in topics[:count]:
        info = format_topic(t)
        results.append(info)
        print(f"【{info['time']}】 {info['author']}")
        print(f"{info['text']}")
        print(f"📊 阅读:{info['read_count']} | 👍 {info['like_count']}")
        print("-" * 60)
    
    return results

def get_latest(count=5):
    """获取最新文章"""
    print(f"📥 获取最新 {count} 条文章...")
    topics = get_topics(count=count)
    
    if not topics:
        print("❌ 获取失败")
        return []
    
    results = []
    for t in topics:
        info = format_topic(t)
        results.append(info)
    
    return results

def main():
    """主函数"""
    import sys
    
    if len(sys.argv) < 2:
        print("""
用法:
  python3 zsxq_fetcher.py latest [数量]     - 获取最新文章
  python3 zsxq_fetcher.py search <关键词>   - 搜索行业信息
  
示例:
  python3 zsxq_fetcher.py latest 5
  python3 zsxq_fetcher.py search 存储芯片
  python3 zsxq_fetcher.py search 半导体
        """)
        return
    
    command = sys.argv[1]
    
    if command == "latest":
        count = int(sys.argv[2]) if len(sys.argv) > 2 else 5
        results = get_latest(count)
        for r in results:
            print(f"【{r['time']}】 {r['author']}")
            print(f"{r['text']}")
            print(f"📊 阅读:{r['read_count']} | 👍 {r['like_count']}")
            print("-" * 60)
    
    elif command == "search":
        if len(sys.argv) < 3:
            print("❌ 请提供搜索关键词")
            return
        keyword = sys.argv[2]
        search_industry_info(keyword)
    
    else:
        print(f"❌ 未知命令: {command}")

if __name__ == "__main__":
    main()
