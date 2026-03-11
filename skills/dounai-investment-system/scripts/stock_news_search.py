#!/root/.openclaw/workspace/venv/bin/python3
"""
个股分析 - Exa全网新闻搜索工具
用于个股/标的的实时新闻、公告、研报搜索

集成到:
- dounai-investment-system skill
- industry-chain-analysis skill (个股层面)
"""

import subprocess
import re
import json
from typing import List, Dict, Optional
from datetime import datetime


class StockNewsSearcher:
    """个股新闻搜索器"""
    
    def __init__(self):
        self.source_name = "Exa全网搜索"
    
    def search_stock_news(self, stock_name: str, stock_code: Optional[str] = None, 
                         num_results: int = 10) -> List[Dict]:
        """
        搜索个股相关新闻
        
        Args:
            stock_name: 股票名称 (如: 北方华创, 英伟达)
            stock_code: 股票代码 (可选, 如: 002371.SZ)
            num_results: 返回结果数量
            
        Returns:
            新闻列表
        """
        news_items = []
        
        # 构建搜索查询
        queries = [
            f"{stock_name} 最新消息",
            f"{stock_name} 公告",
            f"{stock_name} 研报"
        ]
        
        if stock_code:
            queries.append(f"{stock_code} 股票")
        
        for query in queries[:2]:  # 限制查询数量
            results = self._exa_search(query, num_results=5)
            news_items.extend(results)
        
        # 去重
        return self._deduplicate(news_items)
    
    def search_sector_news(self, sector: str, sub_sectors: List[str] = None) -> List[Dict]:
        """
        搜索板块/概念新闻
        
        Args:
            sector: 板块名称 (如: AI算力, 半导体, 新能源)
            sub_sectors: 子板块列表
            
        Returns:
            新闻列表
        """
        news_items = []
        
        # 主搜索
        results = self._exa_search(f"{sector} 板块最新", num_results=5)
        news_items.extend(results)
        
        # 子板块搜索
        if sub_sectors:
            for sub in sub_sectors[:2]:
                results = self._exa_search(f"{sub} 最新", num_results=3)
                news_items.extend(results)
        
        return self._deduplicate(news_items)
    
    def _exa_search(self, query: str, num_results: int = 5) -> List[Dict]:
        """执行Exa搜索"""
        news_items = []
        
        try:
            cmd = [
                'mcporter', 'call',
                f'exa.web_search_exa({{"query": "{query}", "numResults": {num_results}}})'
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=20
            )
            
            if result.returncode == 0:
                output = result.stdout
                titles = re.findall(r'Title: (.+)', output)
                urls = re.findall(r'URL: (.+)', output)
                
                for i, title in enumerate(titles[:num_results]):
                    news_items.append({
                        'title': title.strip(),
                        'url': urls[i] if i < len(urls) else '',
                        'source': self.source_name,
                        'query': query,
                        'search_time': datetime.now().isoformat()
                    })
            else:
                print(f"Exa搜索错误: {result.stderr[:100]}")
                
        except Exception as e:
            print(f"Exa搜索异常: {e}")
        
        return news_items
    
    def _deduplicate(self, news_list: List[Dict]) -> List[Dict]:
        """新闻去重"""
        seen = set()
        unique = []
        for news in news_list:
            simple = ''.join(c for c in news['title'] if c.isalnum())[:20]
            if simple and simple not in seen:
                seen.add(simple)
                unique.append(news)
        return unique
    
    def format_news(self, news_list: List[Dict], max_items: int = 10) -> str:
        """格式化新闻为报告文本"""
        if not news_list:
            return "📰 暂无相关新闻"
        
        lines = [f"📰 {self.source_name} - 最新动态 ({len(news_list)}条)", "=" * 60]
        
        for i, news in enumerate(news_list[:max_items], 1):
            title = news['title'][:55]
            lines.append(f"{i:2d}. {title}...")
        
        return "\n".join(lines)


# 常用板块搜索配置
SECTOR_SEARCH_QUERIES = {
    "AI算力": ["AI算力", "光模块", "铜连接", "英伟达", "算力芯片"],
    "半导体": ["半导体设备", "光刻机", "国产替代", "芯片设计"],
    "存储芯片": ["存储芯片", "DRAM", "NAND", "长鑫存储", "长江存储"],
    "PCB": ["PCB", "覆铜板", "AI服务器", "HDI"],
    "光通讯": ["光模块", "CPO", "光芯片", "800G"],
    "新能源": ["锂电池", "储能", "光伏", "新能源车"],
    "高股息": ["高股息", "煤炭", "银行", "电力", "红利"],
    "创新药": ["创新药", "CXO", "生物医药", "医保谈判"]
}


def get_stock_news(stock_name: str, stock_code: str = None) -> List[Dict]:
    """
    获取个股新闻入口函数
    
    Args:
        stock_name: 股票名称
        stock_code: 股票代码 (可选)
        
    Returns:
        新闻列表
    """
    searcher = StockNewsSearcher()
    return searcher.search_stock_news(stock_name, stock_code)


def get_sector_news(sector: str) -> List[Dict]:
    """
    获取板块新闻入口函数
    
    Args:
        sector: 板块名称
        
    Returns:
        新闻列表
    """
    searcher = StockNewsSearcher()
    queries = SECTOR_SEARCH_QUERIES.get(sector, [sector])
    return searcher.search_sector_news(sector, queries)


if __name__ == "__main__":
    # 测试
    print("🧪 个股新闻搜索工具测试")
    print("=" * 60)
    
    # 测试个股搜索
    print("\n🔍 测试: 北方华创")
    news = get_stock_news("北方华创", "002371.SZ")
    print(f"\n获取到 {len(news)} 条新闻:")
    for i, item in enumerate(news[:5], 1):
        print(f"{i}. {item['title'][:50]}...")
    
    # 测试板块搜索
    print("\n🔍 测试: AI算力板块")
    news = get_sector_news("AI算力")
    print(f"\n获取到 {len(news)} 条新闻:")
    for i, item in enumerate(news[:5], 1):
        print(f"{i}. {item['title'][:50]}...")
