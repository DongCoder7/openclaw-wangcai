#!/root/.openclaw/workspace/venv/bin/python3
# -*- coding: utf-8 -*-
"""
搜索伟测科技1-2月自愿性披露经营数据
"""

import sys
import subprocess
import re

sys.path.insert(0, '/root/.openclaw/workspace/skills/a-stock-analysis/scripts')
from multi_source_news_v2 import MultiSourceNewsSearcher

def search_monthly_data():
    """搜索月度经营数据"""
    print("="*70)
    print("搜索伟测科技1-2月自愿性披露经营数据")
    print("="*70)
    
    searcher = MultiSourceNewsSearcher()
    
    # 搜索关键词组合
    keywords = [
        "伟测科技 1月 经营数据",
        "伟测科技 2月 经营数据", 
        "伟测科技 月度 经营数据",
        "伟测科技 自愿性披露",
        "伟测科技 2025年1月",
        "伟测科技 2025年2月",
        "688372 经营数据"
    ]
    
    all_results = []
    
    for kw in keywords:
        print(f"\n🔍 搜索: {kw}")
        results = searcher.search_all(kw, "688372.SH", "伟测科技")
        all_results.extend(results)
        print(f"   找到 {len(results)} 条")
    
    # 去重
    seen = set()
    unique = []
    for r in all_results:
        title = r.get('title', '')[:50]
        if title not in seen:
            seen.add(title)
            unique.append(r)
    
    print(f"\n{'='*70}")
    print(f"去重后共 {len(unique)} 条结果")
    print("="*70)
    
    # 筛选与经营数据相关的内容
    print("\n📊 与经营数据相关的结果:")
    for i, r in enumerate(unique[:20], 1):
        title = r.get('title', '')
        source = r.get('source', '未知')
        print(f"{i}. [{source}] {title}")
    
    return unique

if __name__ == "__main__":
    search_monthly_data()
