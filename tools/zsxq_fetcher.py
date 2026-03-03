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

# 从环境变量获取cookies（避免token硬编码）
COOKIES = os.environ.get('ZSXQ_COOKIES', '')
if not COOKIES:
    # 尝试从.env文件加载
    env_path = os.path.join(os.path.dirname(__file__), '..', '.zsxq.env')
    if os.path.exists(env_path):
        with open(env_path, 'r') as f:
            for line in f:
                if line.startswith('ZSXQ_COOKIES='):
                    COOKIES = line.strip().split('=', 1)[1].strip('"\'')
                    break

if not COOKIES:
    raise ValueError("未找到ZSXQ_COOKIES，请设置环境变量或创建.zsxq.env文件")

BASE_URL = "https://api.zsxq.com/v2"

def get_topics(count=5, keyword=None):
    """获取文章列表
    
    Args:
        count: 获取文章数量 (注意: API限制，单次最多约15条)
        keyword: 关键词筛选 (可选)
    
    Returns:
        list: 文章列表
    """
    # API对count有限制，count>15可能返回空
    # 采用分页方式获取更多数据
    all_topics = []
    per_page = 10  # 每页获取数量
    pages = (count + per_page - 1) // per_page  # 计算需要的页数
    
    headers = {
        "Cookie": COOKIES,
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json"
    }
    
    for page in range(pages):
        url = f"{BASE_URL}/groups/{GROUP_ID}/topics?count={per_page}"
        
        try:
            response = requests.get(url, headers=headers, timeout=30)
            data = response.json()
            
            if not data.get('succeeded'):
                print(f"⚠️ 第{page+1}页获取失败: {data.get('code', 'unknown')}")
                continue
            
            topics = data.get('resp_data', {}).get('topics', [])
            if not topics:
                break
                
            all_topics.extend(topics)
            
            # 如果获取到的话题少于per_page，说明没有更多数据了
            if len(topics) < per_page:
                break
                
        except Exception as e:
            print(f"⚠️ 第{page+1}页请求异常: {e}")
            continue
    
    print(f"✅ 共获取 {len(all_topics)} 条话题")
    
    # 关键词筛选
    if keyword and all_topics:
        filtered = []
        keyword_lower = keyword.lower()
        for t in all_topics:
            text = t.get('talk', {}).get('text', '').lower()
            if keyword_lower in text:
                filtered.append(t)
        print(f"🔍 关键词'{keyword}'筛选: {len(filtered)} 条匹配")
        return filtered
    
    return all_topics

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
