#!/usr/bin/env python3
"""
知识星球智能搜索工具 - 修复版
支持多关键词、自动重试、30秒间隔
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
            print(f"⏳ 等待 {wait_time:.1f} 秒 (30秒间隔)...")
            time.sleep(wait_time)
    
    _last_query_time = datetime.now()

def search_topics_single(keyword: str, limit: int = 20):
    """单次搜索知识星球话题"""
    import urllib.request
    import ssl
    
    token = get_zsxq_token()
    if not token:
        print("❌ 未找到知识星球token")
        return None
    
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
            error_code = data.get('code', 'unknown')
            print(f"⚠️ API返回失败: {error_code}")
            return None
        
        topics = data.get('resp_data', {}).get('topics', [])
        
        # 过滤包含关键词的内容
        results = []
        keyword_lower = keyword.lower()
        
        for topic in topics:
            talk = topic.get('talk', {})
            text = talk.get('text', '')
            title = topic.get('title', '')
            
            # 检查标题和内容是否包含关键词
            if keyword_lower in text.lower() or keyword_lower in title.lower():
                results.append({
                    'title': title or text[:50],
                    'text': text[:800],  # 增加内容长度
                    'time': topic.get('create_time', ''),
                    'likes': topic.get('likes_count', 0),
                    'keyword': keyword
                })
        
        return results
        
    except Exception as e:
        print(f"⚠️ 获取失败: {e}")
        return None

def smart_search(keywords: list, limit: int = 20, max_retries: int = 3):
    """
    智能搜索 - 多关键词 + 自动重试
    
    Args:
        keywords: 关键词列表，按优先级排序
        limit: 每关键词获取数量
        max_retries: 每个关键词重试次数
    """
    all_results = []
    searched_keywords = []
    
    print(f"🔍 智能搜索启动，关键词列表: {keywords}")
    print("="*70)
    
    for keyword in keywords:
        print(f"\n📌 搜索关键词: '{keyword}'")
        
        for attempt in range(max_retries):
            # 检查30秒间隔
            check_interval()
            
            results = search_topics_single(keyword, limit)
            
            if results is not None:
                print(f"✅ 获取成功，找到 {len(results)} 条相关记录")
                all_results.extend(results)
                searched_keywords.append(keyword)
                break
            else:
                if attempt < max_retries - 1:
                    print(f"⏳ 第{attempt+1}次失败，等待重试...")
                    time.sleep(5)
                else:
                    print(f"❌ 关键词'{keyword}'搜索失败，尝试下一个...")
    
    # 去重（按标题）
    seen_titles = set()
    unique_results = []
    for r in all_results:
        title_key = r['title'][:50]  # 取前50字符作为去重key
        if title_key not in seen_titles:
            seen_titles.add(title_key)
            unique_results.append(r)
    
    # 按时间排序
    unique_results.sort(key=lambda x: x['time'], reverse=True)
    
    print(f"\n" + "="*70)
    print(f"📊 搜索结果汇总:")
    print(f"  搜索关键词: {searched_keywords}")
    print(f"  原始记录: {len(all_results)} 条")
    print(f"  去重后: {len(unique_results)} 条")
    
    return unique_results

def get_industry_keywords(stock_code: str, stock_name: str):
    """
    根据股票代码获取行业关键词列表
    """
    # 行业关键词映射表
    industry_map = {
        # 光模块/光通信
        '300548': ['光模块', '光通信', '光器件', '算力', '通信'],
        '300502': ['光模块', '光通信', '算力'],
        '300308': ['光模块', '光通信', '中际旭创'],
        
        # PCB
        '603920': ['PCB', '印制电路板', '电路板', '英伟达'],
        '002938': ['PCB', '鹏鼎控股'],
        '002384': ['PCB', '东山精密'],
        
        # 半导体/芯片
        '002371': ['半导体', '芯片', '设备', '北方华创'],
        '688012': ['半导体', '芯片', '中微公司'],
        
        # 存储
        '688525': ['存储', '存储芯片', '存储模组'],
        
        # 算力
        '688521': ['算力', '芯原股份', 'AI芯片'],
    }
    
    # 基础关键词
    keywords = [stock_name]
    
    # 添加行业关键词
    code_short = stock_code.split('.')[0]
    if code_short in industry_map:
        keywords.extend(industry_map[code_short])
    
    # 通用关键词
    keywords.extend(['A股', '调研', '纪要'])
    
    return keywords

def save_to_db(results, stock_code):
    """保存到数据库"""
    if not results:
        return
    
    conn = sqlite3.connect(DB_PATH)
    
    for topic in results:
        conn.execute('''
            INSERT OR REPLACE INTO research_notes 
            (source, keyword, title, content, publish_time, likes, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            'zsxq',
            topic['keyword'],
            topic['title'],
            topic['text'],
            topic['time'],
            topic['likes'],
            datetime.now().isoformat()
        ))
    
    conn.commit()
    conn.close()
    print(f"💾 已保存 {len(results)} 条记录到数据库")

def analyze_stock_with_zsxq(stock_code: str, stock_name: str):
    """
    完整分析流程：搜索知识星球 + 输出报告
    """
    print(f"\n{'='*70}")
    print(f"🔍 {stock_name}({stock_code}) - 知识星球调研搜索")
    print(f"{'='*70}\n")
    
    # 获取行业关键词
    keywords = get_industry_keywords(stock_code, stock_name)
    print(f"📋 搜索关键词列表: {keywords}\n")
    
    # 智能搜索
    results = smart_search(keywords, limit=20, max_retries=3)
    
    if not results:
        print("⚠️ 未找到相关调研纪要")
        return []
    
    # 保存到数据库
    save_to_db(results, stock_code)
    
    # 输出结果
    print(f"\n📋 调研纪要详情:")
    print("-"*70)
    
    for i, r in enumerate(results[:5], 1):
        print(f"\n{i}. 【{r['keyword']}】{r['title'][:40]}...")
        print(f"   点赞: {r['likes']} | 时间: {r['time'][:10]}")
        print(f"   摘要: {r['text'][:150]}...")
    
    return results

if __name__ == '__main__':
    if len(sys.argv) >= 3:
        stock_code = sys.argv[1]
        stock_name = sys.argv[2]
        analyze_stock_with_zsxq(stock_code, stock_name)
    else:
        print("Usage: python3 zsxq_smart_search.py <stock_code> <stock_name>")
        print("Example: python3 zsxq_smart_search.py 300548.SZ 长芯博创")
        print("\n演示模式: 搜索长芯博创...")
        analyze_stock_with_zsxq('300548.SZ', '长芯博创')
