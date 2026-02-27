#!/usr/bin/env python3
"""
知识星球获取工具 - 带30秒间隔限制
"""
import os
import sys
import time
import json
import sqlite3
from datetime import datetime, timedelta

DB_PATH = '/root/.openclaw/workspace/data/historical/historical.db'
CONFIG_PATH = '/root/.openclaw/workspace/config/zsxq_source.md'

# 全局变量记录上次查询时间
_last_query_time = None

def get_zsxq_token():
    """获取知识星球token"""
    try:
        with open(CONFIG_PATH, 'r') as f:
            content = f.read()
        # 解析token
        for line in content.split('\n'):
            if 'zsxq_access_token=' in line:
                return line.split('=')[1].strip()
    except:
        return None

def check_interval():
    """检查30秒间隔"""
    global _last_query_time
    
    if _last_query_time is not None:
        elapsed = (datetime.now() - _last_query_time).total_seconds()
        if elapsed < 30:
            wait_time = 30 - elapsed
            print(f"⏳ 需要等待 {wait_time:.1f} 秒 (30秒间隔限制)...")
            time.sleep(wait_time)
    
    _last_query_time = datetime.now()

def search_topics(keyword: str, limit: int = 10):
    """搜索知识星球话题 - 带30秒间隔"""
    import urllib.request
    import ssl
    
    # 检查间隔
    check_interval()
    
    token = get_zsxq_token()
    if not token:
        print("❌ 未找到知识星球token")
        return []
    
    url = f"https://api.zsxq.com/v2/groups/28855458518111/topics?count={limit}"
    
    headers = {
        'Cookie': f'zsxq_access_token={token}',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'application/json'
    }
    
    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, context=ctx, timeout=30) as response:
            data = json.loads(response.read().decode('utf-8'))
        
        if not data.get('succeeded'):
            print(f"❌ API返回失败: {data.get('code', 'unknown')}")
            return []
        
        topics = data.get('resp_data', {}).get('topics', [])
        
        # 过滤包含关键词的内容
        results = []
        for topic in topics:
            talk = topic.get('talk', {})
            text = talk.get('text', '')
            title = topic.get('title', '')
            
            if keyword.lower() in text.lower() or keyword.lower() in title.lower():
                results.append({
                    'title': title or text[:50],
                    'text': text[:500],
                    'time': topic.get('create_time', ''),
                    'likes': topic.get('likes_count', 0)
                })
        
        print(f"✅ 获取成功，找到 {len(results)} 条相关记录")
        return results
        
    except Exception as e:
        print(f"❌ 获取失败: {e}")
        return []

def save_to_db(topics, keyword):
    """保存到数据库"""
    conn = sqlite3.connect(DB_PATH)
    
    for topic in topics:
        conn.execute('''
            INSERT OR REPLACE INTO research_notes 
            (source, keyword, title, content, publish_time, likes, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            'zsxq',
            keyword,
            topic['title'],
            topic['text'],
            topic['time'],
            topic['likes'],
            datetime.now().isoformat()
        ))
    
    conn.commit()
    conn.close()
    print(f"💾 已保存 {len(topics)} 条记录到数据库")

if __name__ == '__main__':
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python3 zsxq_fetcher_v2.py <keyword>")
        sys.exit(1)
    
    keyword = sys.argv[1]
    print(f"🔍 搜索知识星球: '{keyword}'")
    print("="*60)
    
    results = search_topics(keyword, limit=20)
    
    if results:
        print(f"\n📋 找到 {len(results)} 条相关记录:")
        for i, r in enumerate(results[:5], 1):
            print(f"\n{i}. {r['title']}")
            print(f"   点赞: {r['likes']} | 时间: {r['time'][:10]}")
            print(f"   内容: {r['text'][:200]}...")
        
        # 保存到数据库
        save_to_db(results, keyword)
    else:
        print("⚠️ 未找到相关记录")
