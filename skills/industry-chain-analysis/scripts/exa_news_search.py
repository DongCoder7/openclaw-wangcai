#!/usr/bin/env python3
"""
Exa全网新闻搜索工具 - 产业链分析专用
集成到 industry-chain-analysis skill

功能:
1. 行业关键词全网搜索
2. 新闻聚合与去重
3. 新闻影响度评估
"""

import subprocess
import re
import json
from typing import List, Dict
from datetime import datetime


class ExaNewsSearcher:
    """Exa全网新闻搜索器"""
    
    def __init__(self):
        self.source_name = "Exa全网搜索"
    
    def search(self, query: str, num_results: int = 10) -> List[Dict]:
        """
        执行Exa全网搜索
        
        Args:
            query: 搜索关键词
            num_results: 返回结果数量
            
        Returns:
            新闻列表，每条包含title, url, source
        """
        news_items = []
        
        try:
            # 构建mcporter命令
            cmd = [
                'mcporter', 'call',
                f'exa.web_search_exa({{"query": "{query}", "numResults": {num_results}}})'
            ]
            
            # 执行搜索
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=20
            )
            
            if result.returncode == 0:
                # 解析结果
                output = result.stdout
                titles = re.findall(r'Title: (.+)', output)
                urls = re.findall(r'URL: (.+)', output)
                
                for i, title in enumerate(titles[:num_results]):
                    news_items.append({
                        'title': title.strip(),
                        'url': urls[i] if i < len(urls) else '',
                        'source': self.source_name,
                        'search_time': datetime.now().isoformat()
                    })
            else:
                print(f"Exa搜索错误: {result.stderr[:100]}")
                
        except Exception as e:
            print(f"Exa搜索异常: {e}")
        
        return news_items
    
    def search_industry_news(self, industry: str, sub_keywords: List[str] = None) -> List[Dict]:
        """
        行业新闻综合搜索
        
        Args:
            industry: 行业名称 (如: 存储芯片, PCB, 半导体)
            sub_keywords: 子关键词列表
            
        Returns:
            聚合后的新闻列表
        """
        all_news = []
        
        # 默认子关键词
        if sub_keywords is None:
            sub_keywords = ['涨价', '产能', '供需', '价格']
        
        # 主搜索
        print(f"🔍 搜索行业: {industry}")
        main_results = self.search(industry, num_results=5)
        all_news.extend(main_results)
        
        # 子关键词搜索
        for keyword in sub_keywords[:2]:  # 限制子搜索数量
            query = f"{industry} {keyword}"
            print(f"🔍 搜索: {query}")
            results = self.search(query, num_results=3)
            all_news.extend(results)
        
        # 去重
        seen = set()
        unique_news = []
        for news in all_news:
            simple = ''.join(c for c in news['title'] if c.isalnum())[:20]
            if simple and simple not in seen:
                seen.add(simple)
                unique_news.append(news)
        
        return unique_news
    
    def format_for_report(self, news_list: List[Dict]) -> str:
        """格式化为报告文本"""
        if not news_list:
            return "📰 暂无相关新闻"
        
        lines = [f"📰 Exa全网搜索 - 最新动态 ({len(news_list)}条)", "=" * 60]
        
        for i, news in enumerate(news_list[:15], 1):
            title = news['title'][:60]
            lines.append(f"{i:2d}. {title}...")
        
        return "\n".join(lines)


# 行业搜索预设配置
INDUSTRY_SEARCH_CONFIG = {
    "存储芯片": {
        "keywords": ["DRAM", "NAND", "涨价", "长鑫", "长江存储"],
        "queries": ["存储芯片涨价", "DRAM价格走势", "NAND闪存"]
    },
    "PCB": {
        "keywords": ["覆铜板", "涨价", "产能", "AI服务器"],
        "queries": ["PCB覆铜板涨价", "AI服务器PCB"]
    },
    "半导体设备": {
        "keywords": ["光刻机", "国产替代", "北方华创", "订单"],
        "queries": ["半导体设备国产替代", "光刻机突破"]
    },
    "AI算力": {
        "keywords": ["英伟达", "算力", "光模块", "铜连接"],
        "queries": ["AI算力芯片", "光模块涨价"]
    },
    "新能源": {
        "keywords": ["锂电池", "光伏", "储能", "新能源车"],
        "queries": ["锂电池产能", "光伏价格"]
    }
}


def search_industry_news(industry: str) -> List[Dict]:
    """
    行业新闻搜索入口函数
    
    Args:
        industry: 行业名称
        
    Returns:
        新闻列表
    """
    searcher = ExaNewsSearcher()
    
    # 获取行业配置
    config = INDUSTRY_SEARCH_CONFIG.get(industry, {})
    keywords = config.get("keywords", [])
    
    # 执行搜索
    news = searcher.search_industry_news(industry, keywords)
    
    return news


if __name__ == "__main__":
    # 测试
    print("🧪 Exa行业新闻搜索工具测试")
    print("=" * 60)
    
    # 测试存储芯片搜索
    print("\n🔍 测试: 存储芯片")
    news = search_industry_news("存储芯片")
    print(f"\n获取到 {len(news)} 条新闻:")
    for i, item in enumerate(news[:5], 1):
        print(f"{i}. {item['title'][:50]}...")
