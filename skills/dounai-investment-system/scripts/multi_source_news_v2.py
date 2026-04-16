#!/root/.openclaw/workspace/venv/bin/python3
"""
多源新闻聚合搜索模块 v2.0
集成知识星球优化版搜索功能（支持keyword参数）
"""

import sys
import subprocess
import re
import requests
import urllib.parse
import time
from typing import List, Dict, Optional
from datetime import datetime

sys.path.insert(0, '/root/.openclaw/workspace/tools')
sys.path.insert(0, '/root/.openclaw/workspace')


class ZsxqSearcher:
    """知识星球搜索器（优化版）"""
    
    def __init__(self):
        self.cookie = 'sensorsdata2015jssdkcross=%7B%22distinct_id%22%3A%22421882554581888%22%2C%22first_id%22%3A%2219957298c826cb-08f4b144c21fe3-1f525631-1484784-19957298c83903%22%2C%22props%22%3A%7B%22%24latest_traffic_source_type%22%3A%22%E7%A4%BE%E4%BA%A4%E7%BD%91%E7%AB%99%E6%B5%81%E9%87%8F%22%2C%22%24latest_search_keyword%22%3A%22%E6%9C%AA%E5%8F%96%E5%88%B0%E5%80%BC%22%2C%22%24latest_referrer%22%3A%22https%3A%2F%2Fopen.weixin.qq.com%2F%22%7D%2C%22identities%22%3A%22eyIkaWRlbnRpdHlfY29va2llX2lkIjoiMTk5NTcyOThjODI2Y2ItMDhmNGIxNDRjMjFmZTMtMWY1MjU2MzEtMTQ4NDc4NC0xOTk1NzI5OGM4MzkwMyIsIiRpZGVudGl0eV9sb2dpbl9pZCI6IjQyMTg4MjU1NDU4MTg4OCJ9%22%2C%22history_login_id%22%3A%7B%22name%22%3A%22%24identity_login_id%22%2C%22value%22%3A%22421882554581888%22%7D%2C%22%24device_id%22%3A%2219957298c826cb-08f4b144c21fe3-1f525631-1484784-19957298c83903%22%7D; abtest_env=product; zsxq_access_token=26FC1241-0A1A-42BF-87B9-BE97A4A42AB1_2ECB6A0A4CD9622F'
        self.headers = {
            'Cookie': self.cookie,
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'application/json'
        }
        self.group_id = '28855458518111'
        self.last_query_time = None
    
    def _check_interval(self):
        """检查请求间隔（频率控制）"""
        if self.last_query_time is not None:
            elapsed = (datetime.now() - self.last_query_time).total_seconds()
            if elapsed < 3:  # 最少3秒间隔
                wait_time = 3 - elapsed
                print(f"   ⏳ 等待 {wait_time:.1f}s (频率控制)...")
                time.sleep(wait_time)
        self.last_query_time = datetime.now()
    
    def search(self, keyword: str, count: int = 20) -> List[Dict]:
        """
        知识星球关键词搜索
        
        Args:
            keyword: 搜索关键词
            count: 获取数量
            
        Returns:
            搜索结果列表
        """
        results = []
        
        # 频率控制
        self._check_interval()
        
        try:
            # URL编码关键词
            keyword_encoded = urllib.parse.quote(keyword)
            url = f'https://api.zsxq.com/v2/groups/{self.group_id}/topics?count={count}&keyword={keyword_encoded}'
            
            response = requests.get(url, headers=self.headers, timeout=15)
            
            if response.status_code != 200:
                print(f"   ⚠️ HTTP错误: {response.status_code}")
                return results
            
            data = response.json()
            
            if not data.get('succeeded'):
                code = data.get('code', 0)
                if code == 1059:
                    print(f"   ⚠️ 触发限流，等待后重试...")
                    time.sleep(30)
                    return self.search(keyword, count)  # 重试
                print(f"   ⚠️ API错误: code={code}")
                return results
            
            topics = data.get('resp_data', {}).get('topics', [])
            
            for topic in topics:
                talk = topic.get('talk', {})
                text = talk.get('text', '')
                title = talk.get('title', '') or text[:50]
                owner = talk.get('owner', {})
                author = owner.get('name', '未知')
                
                results.append({
                    'title': title[:100],
                    'content': text[:300],
                    'author': author,
                    'time': topic.get('create_time', '')[:16],
                    'likes': topic.get('likes_count', 0),
                    'source': '知识星球',
                    'priority': 2
                })
            
            print(f"   ✅ 找到 {len(results)} 条")
            
        except Exception as e:
            print(f"   ⚠️ 搜索失败: {e}")
        
        return results
    
    def search_industry(self, industry: str, sub_keywords: List[str] = None) -> List[Dict]:
        """
        行业深度搜索 - 多关键词组合
        
        Args:
            industry: 行业主关键词
            sub_keywords: 子关键词列表
            
        Returns:
            合并去重后的结果
        """
        all_results = []
        
        # 主关键词搜索
        print(f"   🔍 主关键词: '{industry}'")
        results = self.search(industry, count=20)
        all_results.extend(results)
        
        # 子关键词搜索
        if sub_keywords:
            for sub_kw in sub_keywords[:3]:  # 限制子关键词数量
                print(f"   🔍 子关键词: '{industry} {sub_kw}'")
                results = self.search(f"{industry} {sub_kw}", count=10)
                all_results.extend(results)
                time.sleep(3)  # 频率控制
        
        # 去重
        seen = set()
        unique = []
        for r in all_results:
            key = r['title'][:40]
            if key not in seen:
                seen.add(key)
                unique.append(r)
        
        print(f"   📊 去重后: {len(unique)} 条")
        return unique


class MultiSourceNewsSearcher:
    """多源新闻聚合搜索器 v2.0"""
    
    def __init__(self):
        self.all_news = []
        self.sources_stats = {}
        self.zsxq_searcher = ZsxqSearcher()
    
    def search_all(self, keyword: str, stock_code: str = "", stock_name: str = "") -> List[Dict]:
        """
        同时搜索多个数据源（优化版）
        
        Args:
            keyword: 搜索关键词
            stock_code: 股票代码
            stock_name: 股票名称
            
        Returns:
            合并去重后的新闻列表
        """
        self.all_news = []
        self.sources_stats = {}
        
        print(f"\n🔍 启动多源新闻搜索: {keyword}")
        print("="*60)
        
        # P1: Exa全网搜索
        print("\n🔥 [P1] Exa全网语义搜索...")
        # 重要：Exa搜索必须拼接stock_name+keyword，确保搜索"标的+关键词"
        if stock_name and keyword:
            exa_keyword = f"{stock_name} {keyword}"
        elif stock_name:
            exa_keyword = stock_name
        else:
            exa_keyword = keyword
        exa_news = self._search_exa(exa_keyword, 8)
        self.all_news.extend(exa_news)
        self.sources_stats['Exa全网'] = len(exa_news)
        print(f"   ✅ 获取 {len(exa_news)} 条 (关键词: {exa_keyword})")
        
        # P2: 知识星球优化版搜索
        print("\n📚 [P2] 知识星球调研纪要...")
        search_terms = [keyword]
        if stock_name:
            search_terms.insert(0, stock_name)  # 优先用股票名搜索
        
        zsxq_news = []
        for term in search_terms[:2]:  # 最多2个搜索词
            results = self.zsxq_searcher.search(term, count=15)
            zsxq_news.extend(results)
            if len(search_terms) > 1:
                time.sleep(3)  # 频率控制
        
        # 去重
        seen_titles = set()
        unique_zsxq = []
        for n in zsxq_news:
            title_key = n['title'][:40]
            if title_key not in seen_titles:
                seen_titles.add(title_key)
                unique_zsxq.append(n)
        
        self.all_news.extend(unique_zsxq)
        self.sources_stats['知识星球'] = len(unique_zsxq)
        print(f"   ✅ 获取 {len(unique_zsxq)} 条（去重后）")
        
        # P3: 新浪财经
        print("\n📰 [P3] 新浪财经...")
        sina_news = self._search_sina(keyword)
        self.all_news.extend(sina_news)
        self.sources_stats['新浪财经'] = len(sina_news)
        print(f"   ✅ 获取 {len(sina_news)} 条")
        
        # P4: 东方财富
        print("\n📰 [P4] 东方财富...")
        em_news = self._search_eastmoney(keyword)
        self.all_news.extend(em_news)
        self.sources_stats['东方财富'] = len(em_news)
        print(f"   ✅ 获取 {len(em_news)} 条")
        
        # P5: 腾讯财经
        print("\n📰 [P5] 腾讯财经...")
        qq_news = self._search_qq(keyword)
        self.all_news.extend(qq_news)
        self.sources_stats['腾讯财经'] = len(qq_news)
        print(f"   ✅ 获取 {len(qq_news)} 条")
        
        # P6: 华尔街见闻
        print("\n📰 [P6] 华尔街见闻...")
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
    
    def search_industry_chain(self, industry: str, upstream: str = "", downstream: str = "") -> List[Dict]:
        """
        产业链上下游搜索
        
        Args:
            industry: 行业名称
            upstream: 上游关键词
            downstream: 下游关键词
            
        Returns:
            产业链相关新闻
        """
        print(f"\n🔗 产业链搜索: {industry}")
        print("="*60)
        
        all_news = []
        
        # 搜索主行业
        print(f"\n1️⃣ 主行业: {industry}")
        news = self.zsxq_searcher.search_industry(industry, ['产业链', '景气度', '供需'])
        all_news.extend(news)
        
        # 搜索上游
        if upstream:
            print(f"\n2️⃣ 上游: {upstream}")
            time.sleep(3)
            news = self.zsxq_searcher.search(upstream, count=15)
            all_news.extend(news)
        
        # 搜索下游
        if downstream:
            print(f"\n3️⃣ 下游: {downstream}")
            time.sleep(3)
            news = self.zsxq_searcher.search(downstream, count=15)
            all_news.extend(news)
        
        # 去重
        seen = set()
        unique = []
        for n in all_news:
            key = n['title'][:40]
            if key not in seen:
                seen.add(key)
                unique.append(n)
        
        print(f"\n✅ 产业链搜索完成: {len(unique)} 条")
        return unique
    
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
    
    def _search_sina(self, keyword: str) -> List[Dict]:
        """新浪财经搜索"""
        news = []
        try:
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
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
            url = "https://api-one.wallstcn.com/apiv1/content/information-flow?accept=article%2Cad&limit=8"
            
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code == 200:
                data = response.json()
                if data.get('code') == 20000 and data.get('data'):
                    items = data['data'].get('items', [])
                    for item in items[:5]:
                        resource = item.get('resource', {})
                        title = resource.get('title', '')
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
    
    def _search_eastmoney(self, keyword: str) -> List[Dict]:
        """东方财富搜索"""
        news = []
        try:
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
            # 东方财富搜索API
            url = f"https://searchapi.eastmoney.com/api/suggest/get?input={keyword}&type=14&count=10"
            
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code == 200:
                data = response.json()
                if 'QuotationCodeTable' in data and 'Data' in data['QuotationCodeTable']:
                    items = data['QuotationCodeTable']['Data']
                    # 尝试获取相关新闻
                    time.sleep(0.5)  # 频率控制
                    
            # 备用：东方财富财经新闻
            url2 = f"https://searchapi.eastmoney.com/api/Search/GetSearchList?keyword={keyword}&pageIndex=1&pageSize=10"
            response = requests.get(url2, headers=headers, timeout=10)
            if response.status_code == 200:
                data = response.json()
                if data.get('result') and 'data' in data:
                    for item in data['data'][:8]:
                        title = item.get('title', '').replace('<em>', '').replace('</em>', '')
                        if title:
                            news.append({
                                'title': title,
                                'source': '东方财富',
                                'url': item.get('url', ''),
                                'priority': 3
                            })
        except Exception as e:
            print(f"   ⚠️ 东方财富搜索失败: {e}")
        return news
    
    def _search_qq(self, keyword: str) -> List[Dict]:
        """腾讯财经搜索"""
        news = []
        try:
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
            # 腾讯财经新闻搜索
            url = f"https://i.news.qq.com/trpc.qqnews_web.kv_srv.kv_srv_http/GetSearchRes?buss=news_web&page=1&per_page=10&keyword={keyword}"
            
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code == 200:
                data = response.json()
                if data.get('ret') == 0 and 'data' in data:
                    items = data['data'].get('list', [])
                    for item in items[:8]:
                        news.append({
                            'title': item.get('title', ''),
                            'source': '腾讯财经',
                            'url': item.get('url', ''),
                            'priority': 3
                        })
        except Exception as e:
            print(f"   ⚠️ 腾讯财经搜索失败: {e}")
        return news
    
    def _deduplicate(self, news_list: List[Dict]) -> List[Dict]:
        """新闻去重"""
        seen = set()
        unique = []
        sorted_news = sorted(news_list, key=lambda x: x.get('priority', 5))
        
        for news in sorted_news:
            title = news.get('title', '')
            simple = ''.join(c for c in title if c.isalnum())[:20]
            if simple and simple not in seen:
                seen.add(simple)
                unique.append(news)
        
        return unique
    
    def format_news_section(self, news_list: List[Dict], max_items: int = 15) -> str:
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
        
        lines.extend(["", "**热门新闻**：", ""])
        
        for i, news in enumerate(news_list[:max_items], 1):
            source = news.get('source', '未知')
            title = news.get('title', '')[:70]
            author = news.get('author', '')
            
            source_mark = {
                'Exa全网': '🔥',
                '知识星球': '📚',
                '新浪财经': '📰',
                '华尔街见闻': '📰'
            }.get(source, '•')
            
            author_info = f" [{author}]" if author and source == '知识星球' else ""
            lines.append(f"{i}. {source_mark} [{source}]{author_info} {title}...")
        
        return "\n".join(lines)


def search_stock_comprehensive(stock_code: str, stock_name: str, industry: str = "") -> Dict:
    """
    个股全面搜索 - 包含所有必要关键词分类
    
    Args:
        stock_code: 股票代码
        stock_name: 股票名称
        industry: 所属行业（可选）
        
    Returns:
        分类汇总的新闻数据
    """
    searcher = MultiSourceNewsSearcher()
    all_results = {}
    
    print(f"\n{'='*80}")
    print(f"🔍 启动个股全面搜索: {stock_name} ({stock_code})")
    print(f"{'='*80}")
    
    # 1. 基础信息搜索
    print("\n📌 【1/6】基础业务搜索")
    if industry:
        all_results['基础'] = searcher.search_all(industry, stock_code, stock_name)
    else:
        all_results['基础'] = searcher.search_all("业务 产品", stock_code, stock_name)
    
    # 2. 重大资本运作（并购/收购/定增/重组）- 必须有！
    print("\n📌 【2/6】重大资本运作搜索")
    all_results['资本运作'] = searcher.search_all("并购 收购 定增 重组 借壳", stock_code, stock_name)
    
    # 3. 风险警示（减持/违规/监管/问询函）- 必须有！
    print("\n📌 【3/6】风险警示搜索")
    all_results['风险'] = searcher.search_all("减持 增持 违规 处罚 监管 问询函 关注函 警示函", stock_code, stock_name)
    
    # 4. 业务驱动（订单/合同/产能/技术）- 必须有！
    print("\n📌 【4/6】业务驱动搜索")
    all_results['业务驱动'] = searcher.search_all("订单 合同 中标 产能扩张 技术突破 专利 产品认证 导入", stock_code, stock_name)
    
    # 5. 业绩相关（预增/变脸/下修/快报）- 必须有！
    print("\n📌 【5/6】业绩相关搜索")
    all_results['业绩'] = searcher.search_all("业绩预增 业绩快报 业绩下修 业绩变脸 扭亏 亏损", stock_code, stock_name)
    
    # 6. 资本市场（研报/评级/机构调研/资金流向）
    print("\n📌 【6/6】资本市场搜索")
    all_results['资本市场'] = searcher.search_all("研报 评级 目标价 机构调研 龙虎榜 大宗交易 北向资金", stock_code, stock_name)
    
    # 统计汇总
    print(f"\n{'='*80}")
    print("📊 搜索结果汇总")
    print(f"{'='*80}")
    total = 0
    for category, news_list in all_results.items():
        count = len(news_list)
        total += count
        print(f"  {category}: {count} 条")
    print(f"  {'-'*40}")
    print(f"  总计: {total} 条")
    print(f"{'='*80}")
    
    return all_results


def search_multi_source_news(keyword: str, stock_code: str = "", stock_name: str = "") -> str:
    """便捷函数：多源新闻搜索"""
    searcher = MultiSourceNewsSearcher()
    news = searcher.search_all(keyword, stock_code, stock_name)
    return searcher.format_news_section(news)


def search_industry_chain_news(industry: str, upstream: str = "", downstream: str = "") -> str:
    """便捷函数：产业链搜索"""
    searcher = MultiSourceNewsSearcher()
    news = searcher.search_industry_chain(industry, upstream, downstream)
    return searcher.format_news_section(news)


if __name__ == "__main__":
    print("🧪 测试多源新闻搜索 v2.0")
    print("="*60)
    
    # 测试个股搜索
    print("\n【测试1】个股搜索：华懋科技")
    result = search_multi_source_news("华懋科技", "603306.SH", "华懋科技")
    print(result[:1000])
    
    print("\n...")
    print("\n✅ 测试完成!")
    
# 添加search_stock_comprehensive方法到MultiSourceNewsSearcher类
MultiSourceNewsSearcher.search_stock_comprehensive = search_stock_comprehensive
