#!/root/.openclaw/workspace/venv/bin/python3
# -*- coding: utf-8 -*-
"""
伟测科技 - 完整多源搜索（包含1-2月经营数据）
使用更新后的知识星球token
"""

import sys
sys.path.insert(0, '/root/.openclaw/workspace/skills/a-stock-analysis/scripts')

from multi_source_news_v2 import search_stock_comprehensive, MultiSourceNewsSearcher
import os

# 设置环境变量
os.environ['ZSXQ_TOKEN'] = '26FC1241-0A1A-42BF-87B9-BE97A4A42AB1_2ECB6A0A4CD9622F'

def search_weicetech_comprehensive():
    """执行完整的多源搜索"""
    print("="*80)
    print("伟测科技（688372.SH）完整多源搜索")
    print("="*80)
    
    # 1. 执行6类关键词搜索
    print("\n【第一步】执行6类关键词搜索...")
    results = search_stock_comprehensive("688372.SH", "伟测科技", "半导体测试")
    
    # 2. 额外搜索1-2月经营数据
    print("\n【第二步】额外搜索1-2月经营数据...")
    searcher = MultiSourceNewsSearcher()
    
    monthly_keywords = [
        "伟测科技 1月 经营数据",
        "伟测科技 2月 经营数据",
        "伟测科技 月度 自愿性披露",
        "伟测科技 2025年1月",
        "伟测科技 2025年2月"
    ]
    
    monthly_results = []
    for kw in monthly_keywords:
        print(f"\n🔍 搜索: {kw}")
        results_month = searcher.search_all(kw, "688372.SH", "伟测科技")
        monthly_results.extend(results_month)
        print(f"   找到 {len(results_month)} 条")
    
    # 3. 汇总结果
    print("\n" + "="*80)
    print("搜索结果汇总")
    print("="*80)
    
    total = 0
    for category, news_list in results.items():
        count = len(news_list)
        total += count
        print(f"  {category}: {count} 条")
    
    print(f"  {'-'*40}")
    print(f"  6类搜索总计: {total} 条")
    print(f"  月度数据搜索: {len(monthly_results)} 条")
    print(f"  总计: {total + len(monthly_results)} 条")
    print("="*80)
    
    # 4. 显示业绩相关的重要发现
    print("\n【重要发现 - 业绩相关】")
    print("-"*80)
    for i, news in enumerate(results.get('业绩', [])[:10], 1):
        print(f"{i}. [{news.get('source', '?')}] {news.get('title', '')[:70]}...")
    
    # 5. 显示月度数据搜索结果
    print("\n【月度经营数据搜索结果】")
    print("-"*80)
    seen = set()
    unique_monthly = []
    for news in monthly_results:
        title = news.get('title', '')[:50]
        if title not in seen:
            seen.add(title)
            unique_monthly.append(news)
    
    for i, news in enumerate(unique_monthly[:15], 1):
        print(f"{i}. [{news.get('source', '?')}] {news.get('title', '')[:70]}...")
    
    return results, unique_monthly

if __name__ == "__main__":
    search_weicetech_comprehensive()
