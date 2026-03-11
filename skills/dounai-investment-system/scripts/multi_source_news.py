#!/root/.openclaw/workspace/venv/bin/python3
"""
多源新闻聚合搜索模块
同时搜索Exa、知识星球、新浪财经等多个数据源
"""

import sys
import subprocess
import re
import requests
from typing import List, Dict, Optional
from datetime import datetime

sys.path.insert(0, '/root/.openclaw/workspace/tools')
sys.path.insert(0, '/root/.openclaw/workspace')


class MultiSourceNewsSearcher:
    """多源新闻聚合搜索器"""
    
    def __init__(self):
        self.all_news = []
        self.sources_stats = {}
    
    def search_all(self, keyword: str, stock_code: str = "", stock_name: str = "") -> List[Dict]:
        """
        同时搜索多个数据源
        
        Args:
            keyword: 搜索关键词
            stock_code: 股票代码（用于知识星球搜索）
            stock_name: 股票名称（用于知识星球搜索）
            
        Returns:
            合并去重后的新闻列表
        """
        self.all_news = []
        self.sources_stats = {}
        
        print(f"\n🔍 启动多源新闻搜索: {keyword}")
        print("="*60)
        
        # 构建完整搜索关键词列表
        search_keywords = [keyword]
        
        # 增加公司事件关键词（重要！避免遗漏收购/并购/公告）
        if stock_name:
            event_keywords = [
                f"{stock_name} 收购 并购",
                f"{stock_name} 公告 减持 增持",
                f"{stock_name} 定增 重组",
                f"{stock_name} 股权激励 回购",
                f"{stock_name} 业绩 财报",
            ]
            search_keywords.extend(event_keywords)
            print(f"   扩展关键词: {len(search_keywords)} 组")
        
        # P1: Exa全网搜索（所有关键词）
        print("\n🔥 [P1] Exa全网语义搜索...")
        exa_news = []
        for kw in search_keywords[:3]:  # 限制前3个关键词避免过多
            news = self._search_exa(kw, 5)
            exa_news.extend(news)
        # 去重
        seen_titles = set()
        unique_exa = []
        for n in exa_news:
            title = n.get('title', '')[:30]
            if title not in seen_titles:
                seen_titles.add(title)
                unique_exa.append(n)
        self.all_news.extend(unique_exa)
        self.sources_stats['Exa全网'] = len(unique_exa)
        print(f"   ✅ 获取 {len(unique_exa)} 条（去重后）")
        
        # P2: 知识星球调研纪要
        if stock_code or stock_name:
            print("\n📚 [P2] 知识星球调研纪要...")
            zsxq_news = self._search_zsxq(stock_code, stock_name)
            self.all_news.extend(zsxq_news)
            self.sources_stats['知识星球'] = len(zsxq_news)
            print(f"   ✅ 获取 {len(zsxq_news)} 条")
        
        # P3: 新浪财经（所有关键词）
        print("\n📰 [P3] 新浪财经...")
        sina_news = []
        for kw in search_keywords[:2]:  # 前2个关键词
            news = self._search_sina(kw)
            sina_news.extend(news)
        # 去重
        seen_titles = set()
        unique_sina = []
        for n in sina_news:
            title = n.get('title', '')[:30]
            if title not in seen_titles:
                seen_titles.add(title)
                unique_sina.append(n)
        self.all_news.extend(unique_sina)
        self.sources_stats['新浪财经'] = len(unique_sina)
        print(f"   ✅ 获取 {len(unique_sina)} 条（去重后）")
        
        # P4: 华尔街见闻
        print("\n📰 [P4] 华尔街见闻...")
        ws_news = self._search_wallstreetcn(keyword)
        self.all_news.extend(ws_news)
        self.sources_stats['华尔街见闻'] = len(ws_news)
        print(f"   ✅ 获取 {len(ws_news)} 条")
        
        # 最终去重
        print("\n🔄 合并去重...")
        unique_news = self._deduplicate(self.all_news)
        print(f"   去重前: {len(self.all_news)} 条 → 去重后: {len(unique_news)} 条")
        
        print("="*60)
        return unique_news
    
    def _search_exa(self, keyword: str, num: int = 8) -> List[Dict]:
        """Exa全网搜索"""
        news = []
        try:
            result = subprocess.run(
                ['mcporter', 'call', f'exa.web_search_exa({{"query": "{keyword}", "numResults": {num}}})'],
                capture_output=True, text=True, timeout=20
            )
            if result.returncode == 0:
                titles = re.findall(r'Title: (.+)', result.stdout)
                urls = re.findall(r'URL: (.+)', result.stdout)
                for i, title in enumerate(titles[:num]):
                    news.append({
                        'title': title.strip(),
                        'source': 'Exa全网',
                        'url': urls[i] if i < len(urls) else '',
                        'priority': 1
                    })
        except Exception as e:
            print(f"   ⚠️ Exa搜索失败: {e}")
        return news
    
    def _search_zsxq(self, stock_code: str, stock_name: str) -> List[Dict]:
        """知识星球调研纪要搜索"""
        news = []
        try:
            from zsxq_fetcher import search_industry_info
            
            # 优先使用股票名称搜索
            search_term = stock_name if stock_name else stock_code
            topics = search_industry_info(search_term, count=5)
            
            if topics:
                for topic in topics[:5]:
                    news.append({
                        'title': topic.get('title', '')[:100],
                        'source': '知识星球',
                        'url': topic.get('url', ''),
                        'priority': 2
                    })
        except Exception as e:
            print(f"   ⚠️ 知识星球搜索失败: {e}")
        return news
    
    def _search_sina(self, keyword: str) -> List[Dict]:
        """新浪财经搜索"""
        news = []
        try:
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
            
            # 新浪财经API
            url = f"https://feed.mix.sina.com.cn/api/roll/get?pageid=153&lid=2516&num=10&keyword={keyword}"
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if 'result' in data and 'data' in data['result']:
                    for item in data['result']['data'][:8]:
                        news.append({
                            'title': item.get('title', ''),
                            'source': '新浪财经',
                            'url': item.get('url', ''),
                            'priority': 3
                        })
        except Exception as e:
            print(f"   ⚠️ 新浪财经搜索失败: {e}")
        return news
    
    def _search_wallstreetcn(self, keyword: str) -> List[Dict]:
        """华尔街见闻搜索"""
        news = []
        try:
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
            url = f"https://api-one.wallstcn.com/apiv1/content/information-flow?accept=article%2Cad&limit=8"
            
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code == 200:
                data = response.json()
                if data.get('code') == 20000 and data.get('data'):
                    items = data['data'].get('items', [])
                    for item in items[:5]:
                        resource = item.get('resource', {})
                        title = resource.get('title', '')
                        # 简单过滤相关性
                        if keyword in title or any(k in title for k in keyword.split()[:2]):
                            news.append({
                                'title': title,
                                'source': '华尔街见闻',
                                'url': '',
                                'priority': 4
                            })
        except Exception as e:
            print(f"   ⚠️ 华尔街见闻搜索失败: {e}")
        return news
    
    def _deduplicate(self, news_list: List[Dict]) -> List[Dict]:
        """新闻去重（基于标题相似度）"""
        seen = set()
        unique = []
        
        # 按优先级排序
        sorted_news = sorted(news_list, key=lambda x: x.get('priority', 5))
        
        for news in sorted_news:
            title = news.get('title', '')
            # 简化标题用于去重
            simple = ''.join(c for c in title if c.isalnum())[:20]
            if simple and simple not in seen:
                seen.add(simple)
                unique.append(news)
        
        return unique
    
    def format_news_section(self, news_list: List[Dict], max_items: int = 10) -> str:
        """格式化新闻章节"""
        if not news_list:
            return "暂无相关新闻"
        
        lines = [
            f"📰 多源新闻聚合（共{len(news_list)}条，去重后）",
            "",
            "**数据源统计**：",
        ]
        
        for source, count in self.sources_stats.items():
            if count > 0:
                lines.append(f"- {source}: {count}条")
        
        lines.extend([
            "",
            "**热门新闻**：",
            "",
        ])
        
        for i, news in enumerate(news_list[:max_items], 1):
            source = news.get('source', '未知')
            title = news.get('title', '')[:70]
            
            # 来源标记
            source_mark = {
                'Exa全网': '🔥',
                '知识星球': '📚',
                '新浪财经': '📰',
                '华尔街见闻': '📰'
            }.get(source, '•')
            
            lines.append(f"{i}. {source_mark} [{source}] {title}...")
        
        return "\n".join(lines)


# 便捷函数
def search_multi_source_news(keyword: str, stock_code: str = "", stock_name: str = "") -> str:
    """
    便捷函数：多源新闻搜索
    
    Args:
        keyword: 搜索关键词
        stock_code: 股票代码
        stock_name: 股票名称
        
    Returns:
        Markdown格式的新闻汇总
    """
    searcher = MultiSourceNewsSearcher()
    news = searcher.search_all(keyword, stock_code, stock_name)
    return searcher.format_news_section(news)


if __name__ == "__main__":
    # 测试
    print("🧪 测试多源新闻搜索")
    print("="*60)
    
    result = search_multi_source_news("华懋科技", "603306.SH", "华懋科技")
    print(result[:1500])
    print("\n... [后续内容省略] ...")
    print("\n✅ 测试完成!")
