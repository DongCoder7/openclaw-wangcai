#!/usr/bin/env python3
"""
美股市场深度分析 - 长桥API版 (v2.0)
每日生成美股板块、个股行情报告

数据源说明（严格标注）：
- 个股行情: 长桥API (Longbridge OpenAPI)
- 个股市值: 长桥API静态数据 (总股本×当前股价)
- 美股指数: 腾讯财经API (qt.gtimg.cn)
- 涨跌幅计算: (现价-昨收)/昨收 × 100%

分析框架：
1. 主要指数表现（道琼斯、纳斯达克、标普500）
2. 板块强弱排序（市值>500亿美元）
3. 核心驱动因子识别
4. 美股→A股传导逻辑
5. 应对策略建议
6. 市场展望与风险提示

作者: 豆奶投资策略系统
版本: 2.0
"""
import sys
import os
import json
from datetime import datetime, timedelta

# 添加路径
sys.path.insert(0, '/root/.openclaw/workspace/tools')
from longbridge_api import get_longbridge_api

# ============================================
# 数据源配置
# ============================================

# 主要指数 (腾讯财经API代码)
# 数据源: 腾讯财经 https://qt.gtimg.cn
INDICES = {
    'usDJI': {'name': '道琼斯', 'source': '腾讯财经API'},
    'usIXIC': {'name': '纳斯达克', 'source': '腾讯财经API'},
    'usINX': {'name': '标普500', 'source': '腾讯财经API'}
}

# 美股板块定义 - 含市值筛选基准
# 数据源: 长桥API (行情+静态数据)
US_SECTORS = {
    'AI算力': {
        'stocks': ['NVDA.US', 'AVGO.US', 'AMD.US', 'MRVL.US', 'SMCI.US', 'ARM.US', 'PLTR.US'],
        'a_share_map': ['寒武纪', '海光信息', '浪潮信息', '中科曙光'],
        'source': '长桥API'
    },
    '半导体': {
        'stocks': ['NVDA.US', 'AMD.US', 'INTC.US', 'TSM.US', 'ASML.US', 'AMAT.US', 'LRCX.US', 'KLAC.US', 'QCOM.US'],
        'a_share_map': ['中芯国际', '北方华创', '中微公司', '拓荆科技'],
        'source': '长桥API'
    },
    '科技巨头': {
        'stocks': ['AAPL.US', 'MSFT.US', 'GOOGL.US', 'META.US', 'AMZN.US', 'TSLA.US', 'NFLX.US'],
        'a_share_map': ['小米集团', '美团', '比亚迪', '立讯精密'],
        'source': '长桥API'
    },
    '光通讯': {
        'stocks': ['ANET.US', 'LITE.US', 'CIEN.US', 'NPTN.US', 'AAOI.US'],
        'a_share_map': ['中际旭创', '新易盛', '天孚通信', '光迅科技'],
        'source': '长桥API'
    },
    '生物医药': {
        'stocks': ['LLY.US', 'NVO.US', 'JNJ.US', 'PFE.US', 'MRK.US', 'UNH.US', 'ABBV.US'],
        'a_share_map': ['恒瑞医药', '迈瑞医疗', '药明康德', '百济神州'],
        'source': '长桥API'
    },
    '存储/数据中心': {
        'stocks': ['WDC.US', 'STX.US', 'SNOW.US', 'NET.US', 'DDOG.US', 'CRWD.US'],
        'a_share_map': ['兆易创新', '澜起科技', '紫光国微', '江波龙'],
        'source': '长桥API'
    },
    '能源': {
        'stocks': ['XOM.US', 'CVX.US', 'COP.US', 'OXY.US', 'SLB.US', 'BP.US'],
        'a_share_map': ['中国石油', '中国海油', '中国石化', '陕西煤业'],
        'source': '长桥API'
    },
    '金融': {
        'stocks': ['V.US', 'MA.US', 'JPM.US', 'BAC.US', 'GS.US', 'MS.US', 'WFC.US'],
        'a_share_map': ['招商银行', '中国平安', '东方财富', '中信证券'],
        'source': '长桥API'
    },
    '消费': {
        'stocks': ['WMT.US', 'COST.US', 'HD.US', 'NKE.US', 'MCD.US', 'SBUX.US', 'KO.US'],
        'a_share_map': ['贵州茅台', '五粮液', '美的集团', '伊利股份'],
        'source': '长桥API'
    },
    '中概互联': {
        'stocks': ['BABA.US', 'JD.US', 'PDD.US', 'NIO.US', 'LI.US', 'XPEV.US', 'TME.US', 'DIDI.US'],
        'a_share_map': ['阿里巴巴', '京东', '拼多多', '蔚来'],
        'source': '长桥API'
    }
}

# 用户ID
USER_ID = 'ou_efbad805767f4572e8f93ebafa8d5402'

# 市值过滤阈值（亿美元）
MARKET_CAP_THRESHOLD = 500


def format_change(value):
    """格式化涨跌幅"""
    try:
        change = float(value)
        return f"+{change:.2f}%" if change > 0 else f"{change:.2f}%"
    except:
        return "--"


def get_emoji(change):
    """根据涨跌幅返回表情"""
    try:
        c = float(change)
        if c > 3:
            return "🚀"
        elif c > 0:
            return "📈"
        elif c > -3:
            return "📉"
        else:
            return "🔻"
    except:
        return "⚪"


def get_importance_emoji(change):
    """重要度评级"""
    try:
        c = abs(float(change))
        if c > 5:
            return "⭐⭐⭐ 高"
        elif c > 2:
            return "⭐⭐ 中"
        else:
            return "⭐ 低"
    except:
        return "-"


def get_rank_emoji(rank):
    """排名表情"""
    if rank == 1:
        return "🥇"
    elif rank == 2:
        return "🥈"
    elif rank == 3:
        return "🥉"
    else:
        return f"{rank}."


def get_action_emoji(change):
    """操作建议表情"""
    try:
        c = float(change)
        if c > 3:
            return "✅ 关注", "强势上涨，可择机参与"
        elif c > 0:
            return "➡️ 持有", "走势平稳，维持仓位"
        elif c > -3:
            return "⚠️ 观望", "短期调整，等待企稳"
        else:
            return "❌ 规避", "大幅下跌，暂时回避"
    except:
        return "-", "-"


def send_feishu_message(content: str, title: str = "美股报告"):
    """发送飞书消息"""
    try:
        import subprocess
        result = subprocess.run([
            'openclaw', 'message', 'send',
            '--channel', 'feishu',
            '--target', USER_ID,
            '--message', content
        ], capture_output=True, text=True)

        if result.returncode == 0:
            print("✅ 飞书消息已发送")
            return True
        else:
            print(f"⚠️ 飞书发送失败: {result.stderr[:200]}")
            return False
    except Exception as e:
        print(f"⚠️ 飞书发送异常: {e}")
        return False


def get_us_index_quote(symbol):
    """
    获取美股指数行情
    数据源: 腾讯财经API (https://qt.gtimg.cn)
    """
    try:
        import requests
        url = f"https://qt.gtimg.cn/q={symbol}"
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            text = response.text
            if '"' in text and 'none_match' not in text:
                inner = text.split('"')[1]
                parts = inner.split('~')
                if len(parts) > 32:
                    name = parts[1] if len(parts) > 1 else symbol
                    price = float(parts[3]) if len(parts) > 3 else 0
                    change = float(parts[32]) if len(parts) > 32 else 0
                    return {
                        'symbol': symbol,
                        'name': name,
                        'price': price,
                        'change': change
                    }
    except Exception as e:
        print(f"获取指数失败 {symbol}: {e}")
    return None


def get_sina_news():
    """
    获取新浪财经新闻
    数据源: 新浪财经API
    """
    news_items = []
    try:
        import requests
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        
        # 新浪财经国际财经新闻
        news_url = "https://feed.mix.sina.com.cn/api/roll/get?pageid=153&lid=2516&k=&num=20&r=0.5"
        response = requests.get(news_url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            if 'result' in data and 'data' in data['result']:
                for item in data['result']['data'][:15]:
                    news_items.append({
                        'title': item.get('title', ''),
                        'time': item.get('ctime', ''),
                        'source': '新浪财经'
                    })
    except Exception as e:
        print(f"  ⚠️ 新浪财经获取失败: {e}")
    return news_items


def get_tencent_news():
    """
    获取腾讯财经新闻
    数据源: 腾讯财经API / 备用: Jina Reader解析
    注意: 腾讯财经有反爬机制，API经常返回空数据
    """
    news_items = []
    try:
        import requests
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        
        # 尝试多种腾讯财经数据源
        urls = [
            # API方式
            "https://i.news.qq.com/trpc.qqnews_web.kv_srv.kv_srv_http_proxy/list?sub_srv_id=finance&srv_id=pc&limit=10",
            "https://i.news.qq.com/trpc.qqnews_web.kv_srv.kv_srv_http_proxy/list?sub_srv_id=24hours&srv_id=pc&limit=10",
        ]
        
        for url in urls:
            try:
                response = requests.get(url, headers=headers, timeout=10)
                if response.status_code == 200:
                    data = response.json()
                    # 腾讯API经常返回 {"data": null}
                    if data.get('ret') == 0 and data.get('data') and 'list' in data['data']:
                        for item in data['data']['list'][:8]:
                            news_items.append({
                                'title': item.get('title', ''),
                                'time': item.get('time', ''),
                                'source': '腾讯财经'
                            })
            except:
                continue
                
    except Exception as e:
        print(f"  ⚠️ 腾讯财经获取失败: {e}")
    
    # 如果API获取不到，尝试备用方案
    if not news_items:
        print("  ⚠️ 腾讯财经API返回空数据，尝试备用源...")
    
    return news_items


def get_wy_news():
    """
    获取网易财经新闻（美股相关）
    数据源: 网易财经
    注意: 网易财经页面经常改版，需多尝试几个选择器
    """
    news_items = []
    try:
        import requests
        from bs4 import BeautifulSoup
        
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        
        # 网易美股新闻
        url = "https://money.163.com/stock/usstock/"
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            # 提取新闻标题 - 多尝试几个选择器
            selectors = [
                '.hidden-title a', '.news_title a', '.title a',
                '.news-list h2 a', '.news-item h3 a', 'h2 a', 'h3 a'
            ]
            for selector in selectors:
                news_links = soup.select(selector)[:10]
                for link in news_links:
                    title = link.get_text().strip()
                    if title and len(title) > 5:
                        news_items.append({
                            'title': title,
                            'time': '',
                            'source': '网易财经'
                        })
                if news_items:
                    break
    except Exception as e:
        print(f"  ⚠️ 网易财经获取失败: {e}")
    return news_items


def get_eastmoney_news():
    """
    获取东方财富新闻（备用源）
    数据源: 东方财富API
    """
    news_items = []
    try:
        import requests
        
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        
        # 东方财富财经要闻API
        url = "https://np-anotice-stock.eastmoney.com/api/security/ann?page_size=20&page_index=1"
        
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data.get('data') and 'list' in data['data']:
                for item in data['data']['list'][:8]:
                    news_items.append({
                        'title': item.get('art_title', ''),
                        'time': item.get('art_time', ''),
                        'source': '东方财富'
                    })
    except Exception as e:
        print(f"  ⚠️ 东方财富获取失败: {e}")
    return news_items


def get_cls_news():
    """
    获取财联社新闻（备用源）
    数据源: 财联社RSS
    """
    news_items = []
    try:
        import feedparser
        
        # 财联社 RSS
        rss_url = "https://www.cls.cn/telegraph"
        
        # 使用 feedparser 解析
        d = feedparser.parse(rss_url)
        for entry in d.entries[:5]:
            news_items.append({
                'title': entry.title,
                'time': '',
                'source': '财联社'
            })
    except Exception as e:
        print(f"  ⚠️ 财联社获取失败: {e}")
    return news_items


def get_wallstreetcn_news():
    """
    获取华尔街见闻新闻
    数据源: 华尔街见闻API
    """
    news_items = []
    try:
        import requests
        
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        
        # 华尔街见闻快讯API
        url = "https://api-one.wallstcn.com/apiv1/content/information-flow?accept=article%2Cad&limit=20"
        
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data.get('code') == 20000 and data.get('data'):
                items = data['data'].get('items', [])
                for item in items[:10]:
                    resource = item.get('resource', {})
                    title = resource.get('title', '')
                    if title:
                        news_items.append({
                            'title': title,
                            'time': resource.get('display_time', ''),
                            'source': '华尔街见闻'
                        })
    except Exception as e:
        print(f"  ⚠️ 华尔街见闻获取失败: {e}")
    return news_items


def get_yicai_news():
    """
    获取第一财经新闻
    数据源: 第一财经API
    """
    news_items = []
    try:
        import requests
        
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        
        # 第一财经新闻API
        url = "https://www.yicai.com/api/ajax/getlatest?page=1&pagesize=15"
        
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data:
                for item in data[:10]:
                    title = item.get('NewsTitle', '')
                    if title:
                        news_items.append({
                            'title': title,
                            'time': item.get('CreateDate', ''),
                            'source': '第一财经'
                        })
    except Exception as e:
        print(f"  ⚠️ 第一财经获取失败: {e}")
    return news_items


def get_hexun_news():
    """
    获取和讯网新闻
    数据源: 和讯网RSS
    """
    news_items = []
    try:
        import feedparser
        
        # 和讯网财经RSS
        rss_urls = [
            "http://rss.hexun.com/finance.xml",
            "http://rss.hexun.com/stock.xml"
        ]
        
        for rss_url in rss_urls:
            try:
                d = feedparser.parse(rss_url)
                for entry in d.entries[:5]:
                    news_items.append({
                        'title': entry.title,
                        'time': '',
                        'source': '和讯网'
                    })
            except:
                continue
    except Exception as e:
        print(f"  ⚠️ 和讯网获取失败: {e}")
    return news_items


def get_ftchinese_news():
    """
    获取FT中文网新闻
    数据源: FT中文网RSS
    """
    news_items = []
    try:
        import feedparser
        
        # FT中文网RSS
        rss_url = "https://www.ftchinese.com/rss/news"
        
        d = feedparser.parse(rss_url)
        for entry in d.entries[:8]:
            news_items.append({
                'title': entry.title,
                'time': '',
                'source': 'FT中文网'
            })
    except Exception as e:
        print(f"  ⚠️ FT中文网获取失败: {e}")
    return news_items


def get_agent_reach_news():
    """
    使用 Agent Reach 工具获取新闻
    信息源: 新浪财经/腾讯财经/国际新闻网页
    """
    news_items = []
    try:
        import subprocess
        import json
        
        # 使用 Agent Reach 的 xreach 搜索国际财经新闻
        keywords = ["美股", "美联储", "科技股", "中概股", "AI", "半导体"]
        
        for keyword in keywords[:3]:  # 限制关键词数量
            try:
                # 使用 curl + Jina Reader 获取新浪财经新闻
                url = f"https://r.jina.ai/http://finance.sina.com.cn/roll/index.d.html?keyword={keyword}"
                result = subprocess.run(
                    ['curl', '-s', '-L', '--max-time', '8', url],
                    capture_output=True, text=True, timeout=10
                )
                if result.returncode == 0 and result.stdout:
                    # 解析新闻标题（简单提取）
                    lines = result.stdout.strip().split('\n')[:5]
                    for line in lines:
                        if len(line) > 10 and '{' not in line:
                            news_items.append({
                                'title': line[:80],
                                'time': '',
                                'source': f'AgentReach-{keyword}'
                            })
            except:
                continue
        
        # 使用 yt-dlp 获取 YouTube 财经视频标题 (如果可用)
        try:
            result = subprocess.run(
                ['yt-dlp', '--flat-playlist', '--dump-json', 
                 'https://www.youtube.com/@CNBCtv/videos'],
                capture_output=True, text=True, timeout=15
            )
            if result.returncode == 0:
                videos = result.stdout.strip().split('\n')[:3]
                for video in videos:
                    try:
                        data = json.loads(video)
                        title = data.get('title', '')
                        if title and any(k in title.lower() for k in ['stock', 'market', 'trade', 'fed', 'tech']):
                            news_items.append({
                                'title': f"[YouTube] {title}",
                                'time': '',
                                'source': 'AgentReach-YouTube'
                            })
                    except:
                        continue
        except:
            pass
        
    except Exception as e:
        print(f"  ⚠️ Agent Reach 新闻获取失败: {e}")
    
    return news_items


def get_exa_news():
    """
    使用 Exa MCP 进行全网语义搜索（高优先级）
    数据源: Exa AI 搜索引擎
    """
    news_items = []
    try:
        import subprocess
        import json
        import re
        
        # 美股相关搜索词
        search_queries = [
            "美股科技股最新动态",
            "纳斯达克指数走势",
            "美联储利率决议影响"
        ]
        
        for query in search_queries[:2]:  # 限制查询数量
            try:
                # 使用 mcporter 调用 Exa 搜索
                cmd = [
                    'mcporter', 'call',
                    f'exa.web_search_exa({{"query": "{query}", "numResults": 5}})'
                ]
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
                
                if result.returncode == 0 and result.stdout:
                    # 解析搜索结果
                    output = result.stdout
                    # 提取标题和URL
                    titles = re.findall(r'Title: (.+)', output)
                    urls = re.findall(r'URL: (.+)', output)
                    
                    for i, title in enumerate(titles[:5]):
                        if title and len(title) > 10:
                            news_items.append({
                                'title': title.strip()[:100],
                                'time': '',
                                'source': 'Exa全网搜索',
                                'url': urls[i] if i < len(urls) else ''
                            })
            except Exception as e:
                print(f"    Exa搜索 '{query}' 失败: {str(e)[:50]}")
                continue
                
    except Exception as e:
        print(f"  ⚠️ Exa全网搜索失败: {e}")
    
    return news_items


def get_international_news():
    """
    获取国际财经新闻（多源聚合）
    数据源优先级: Exa全网搜索 > 新浪财经 > 其他中文源 > Agent Reach
    """
    print("\n📰 获取国际财经新闻...")
    all_news = []
    
    # 高优先级: Exa全网搜索
    print("  🔍 高优先级: Exa全网语义搜索...")
    exa_news = get_exa_news()
    all_news.extend(exa_news)
    
    # 主要中文新闻源
    sina_news = get_sina_news()
    wallstreetcn_news = get_wallstreetcn_news()
    yicai_news = get_yicai_news()
    eastmoney_news = get_eastmoney_news()
    
    # 备用源
    tencent_news = get_tencent_news()
    wy_news = get_wy_news()
    cls_news = get_cls_news()
    hexun_news = get_hexun_news()
    ftchinese_news = get_ftchinese_news()
    
    # Agent Reach
    agent_reach_news = get_agent_reach_news()
    
    # 按优先级添加
    all_news.extend(sina_news)
    all_news.extend(wallstreetcn_news)
    all_news.extend(yicai_news)
    all_news.extend(eastmoney_news)
    all_news.extend(tencent_news)
    all_news.extend(wy_news)
    all_news.extend(cls_news)
    all_news.extend(hexun_news)
    all_news.extend(ftchinese_news)
    all_news.extend(agent_reach_news)
    
    # 去重（基于标题相似度）
    unique_news = []
    seen_titles = set()
    
    for news in all_news:
        title = news.get('title', '')
        # 简化标题用于去重（去除空格和标点）
        simple_title = ''.join(c for c in title if c.isalnum())[:15]
        if simple_title and simple_title not in seen_titles:
            seen_titles.add(simple_title)
            unique_news.append(news)
    
    print(f"  ✅ Exa全网搜索: {len(exa_news)}条 [高优先级]")
    print(f"  ✅ 新浪财经: {len(sina_news)}条")
    print(f"  ✅ 华尔街见闻: {len(wallstreetcn_news)}条")
    print(f"  ✅ 第一财经: {len(yicai_news)}条")
    print(f"  ✅ 东方财富: {len(eastmoney_news)}条")
    print(f"  ✅ 腾讯财经: {len(tencent_news)}条")
    print(f"  ✅ 网易财经: {len(wy_news)}条")
    print(f"  ✅ 财联社: {len(cls_news)}条")
    print(f"  ✅ 和讯网: {len(hexun_news)}条")
    print(f"  ✅ FT中文网: {len(ftchinese_news)}条")
    print(f"  ✅ Agent Reach: {len(agent_reach_news)}条")
    print(f"  ✅ 去重后: {len(unique_news)}条")
    
    return unique_news[:30]  # 返回最多30条


def analyze_news_impact(news_items):
    """
    分析新闻对板块的影响（增强版）
    关键词映射到板块影响 + 影响强度评估
    """
    impact_factors = []
    
    # 扩展关键词-板块映射（更全面的财经词汇）
    keyword_mapping = {
        # ========== 地缘政治 -> 能源/黄金 ==========
        '冲突': {'sectors': ['能源'], 'impact': '利好', 'reason': '地缘风险推升油价', 'intensity': 3},
        '战争': {'sectors': ['能源'], 'impact': '利好', 'reason': '地缘风险推升油价', 'intensity': 5},
        '制裁': {'sectors': ['能源'], 'impact': '利好', 'reason': '供应担忧', 'intensity': 3},
        '伊朗': {'sectors': ['能源'], 'impact': '利好', 'reason': '中东局势紧张', 'intensity': 4},
        '中东': {'sectors': ['能源'], 'impact': '利好', 'reason': '中东地缘政治', 'intensity': 3},
        '俄罗斯': {'sectors': ['能源'], 'impact': '关联', 'reason': '能源供应影响', 'intensity': 2},
        '黄金': {'sectors': ['能源'], 'impact': '利好', 'reason': '避险需求升温', 'intensity': 3},
        '避险': {'sectors': ['能源', '消费'], 'impact': '利好', 'reason': '资金避险需求', 'intensity': 2},
        
        # ========== AI/科技 -> AI算力/半导体 ==========
        '英伟达': {'sectors': ['AI算力', '半导体'], 'impact': '关联', 'reason': 'AI龙头动态', 'intensity': 5},
        'NVIDIA': {'sectors': ['AI算力', '半导体'], 'impact': '关联', 'reason': 'AI龙头动态', 'intensity': 5},
        '人工智能': {'sectors': ['AI算力'], 'impact': '利好', 'reason': 'AI产业政策/技术突破', 'intensity': 4},
        '芯片': {'sectors': ['半导体'], 'impact': '关联', 'reason': '芯片产业链动态', 'intensity': 3},
        '半导体': {'sectors': ['半导体'], 'impact': '关联', 'reason': '半导体产业动态', 'intensity': 3},
        '算力': {'sectors': ['AI算力'], 'impact': '利好', 'reason': '算力需求增长', 'intensity': 3},
        '数据中心': {'sectors': ['存储/数据中心', 'AI算力'], 'impact': '利好', 'reason': '数据中心投资', 'intensity': 2},
        '云计算': {'sectors': ['科技巨头', 'AI算力'], 'impact': '利好', 'reason': '云服务增长', 'intensity': 2},
        '大模型': {'sectors': ['AI算力', '科技巨头'], 'impact': '利好', 'reason': 'AI大模型竞赛', 'intensity': 3},
        
        # ========== 通胀/利率 -> 金融/科技 ==========
        '通胀': {'sectors': ['金融', '消费'], 'impact': '利空', 'reason': '加息预期升温', 'intensity': 4},
        '通胀超预期': {'sectors': ['金融', '科技巨头'], 'impact': '利空', 'reason': '紧缩担忧加剧', 'intensity': 5},
        '利率': {'sectors': ['金融'], 'impact': '关联', 'reason': '利率政策变化', 'intensity': 3},
        '加息': {'sectors': ['金融', '科技巨头', 'AI算力'], 'impact': '利空', 'reason': '资金成本上升', 'intensity': 4},
        '降息': {'sectors': ['金融', '科技巨头', 'AI算力'], 'impact': '利好', 'reason': '流动性宽松', 'intensity': 4},
        '美联储': {'sectors': ['金融'], 'impact': '关联', 'reason': '美联储政策动向', 'intensity': 4},
        '鲍威尔': {'sectors': ['金融'], 'impact': '关联', 'reason': '美联储主席讲话', 'intensity': 3},
        'CPI': {'sectors': ['金融', '消费'], 'impact': '关联', 'reason': '通胀数据发布', 'intensity': 4},
        'PPI': {'sectors': ['金融', '消费'], 'impact': '关联', 'reason': '通胀数据发布', 'intensity': 3},
        '非农数据': {'sectors': ['金融'], 'impact': '关联', 'reason': '就业数据影响', 'intensity': 3},
        
        # ========== 贸易 -> 中概互联/科技 ==========
        '贸易': {'sectors': ['中概互联', '科技巨头'], 'impact': '关联', 'reason': '贸易政策变化', 'intensity': 3},
        '关税': {'sectors': ['中概互联'], 'impact': '利空', 'reason': '贸易摩擦风险', 'intensity': 4},
        '中美': {'sectors': ['中概互联'], 'impact': '关联', 'reason': '中美关系动态', 'intensity': 3},
        '特朗普': {'sectors': ['中概互联'], 'impact': '关联', 'reason': '政策不确定性', 'intensity': 2},
        '脱钩': {'sectors': ['中概互联', '半导体'], 'impact': '利空', 'reason': '供应链风险', 'intensity': 4},
        
        # ========== 疫情/医药 -> 生物医药 ==========
        '疫情': {'sectors': ['生物医药'], 'impact': '利好', 'reason': '医药需求增加', 'intensity': 3},
        '疫苗': {'sectors': ['生物医药'], 'impact': '利好', 'reason': '疫苗企业受益', 'intensity': 2},
        '药品': {'sectors': ['生物医药'], 'impact': '关联', 'reason': '医药产业动态', 'intensity': 2},
        '新药': {'sectors': ['生物医药'], 'impact': '利好', 'reason': '新药研发突破', 'intensity': 3},
        '减肥药': {'sectors': ['生物医药'], 'impact': '利好', 'reason': 'GLP-1药物热潮', 'intensity': 4},
        '礼来': {'sectors': ['生物医药'], 'impact': '关联', 'reason': '医药龙头动态', 'intensity': 3},
        '诺和诺德': {'sectors': ['生物医药'], 'impact': '关联', 'reason': '医药龙头动态', 'intensity': 3},
        
        # ========== 光通讯/通信 ==========
        '光模块': {'sectors': ['光通讯'], 'impact': '利好', 'reason': '光模块需求增长', 'intensity': 4},
        '光通信': {'sectors': ['光通讯'], 'impact': '关联', 'reason': '光通讯产业', 'intensity': 3},
        '5G': {'sectors': ['光通讯', '半导体'], 'impact': '利好', 'reason': '通信基建投资', 'intensity': 2},
        '6G': {'sectors': ['光通讯', '半导体'], 'impact': '利好', 'reason': '下一代通信技术', 'intensity': 2},
        '通信': {'sectors': ['光通讯'], 'impact': '关联', 'reason': '通信行业动态', 'intensity': 2},
        
        # ========== 能源 ==========
        '原油': {'sectors': ['能源'], 'impact': '关联', 'reason': '原油价格波动', 'intensity': 4},
        '石油': {'sectors': ['能源'], 'impact': '关联', 'reason': '石油产业动态', 'intensity': 3},
        '天然气': {'sectors': ['能源'], 'impact': '关联', 'reason': '天然气价格', 'intensity': 2},
        'OPEC': {'sectors': ['能源'], 'impact': '关联', 'reason': 'OPEC政策', 'intensity': 3},
        '新能源': {'sectors': ['能源'], 'impact': '利好', 'reason': '能源转型', 'intensity': 2},
        '电动车': {'sectors': ['能源', '科技巨头'], 'impact': '关联', 'reason': '新能源汽车', 'intensity': 2},
        '特斯拉': {'sectors': ['科技巨头'], 'impact': '关联', 'reason': '电动车龙头', 'intensity': 4},
        
        # ========== 金融 ==========
        '银行': {'sectors': ['金融'], 'impact': '关联', 'reason': '银行业动态', 'intensity': 2},
        '华尔街': {'sectors': ['金融'], 'impact': '关联', 'reason': '金融中心动态', 'intensity': 2},
        '财报': {'sectors': ['金融', '科技巨头'], 'impact': '关联', 'reason': '财报季影响', 'intensity': 3},
        '业绩': {'sectors': ['金融', '科技巨头', 'AI算力'], 'impact': '关联', 'reason': '业绩发布', 'intensity': 3},
        '超预期': {'sectors': ['科技巨头'], 'impact': '利好', 'reason': '业绩超预期', 'intensity': 4},
        '不及预期': {'sectors': ['科技巨头'], 'impact': '利空', 'reason': '业绩不及预期', 'intensity': 4},
        
        # ========== 消费 ==========
        '消费': {'sectors': ['消费'], 'impact': '关联', 'reason': '消费数据', 'intensity': 2},
        '零售': {'sectors': ['消费'], 'impact': '关联', 'reason': '零售数据', 'intensity': 2},
        '电商': {'sectors': ['中概互联', '消费'], 'impact': '关联', 'reason': '电商动态', 'intensity': 2},
        
        # ========== 存储 ==========
        '存储': {'sectors': ['存储/数据中心'], 'impact': '关联', 'reason': '存储产业', 'intensity': 2},
        '存储芯片': {'sectors': ['存储/数据中心', '半导体'], 'impact': '关联', 'reason': '存储芯片动态', 'intensity': 3},
        'DDR': {'sectors': ['存储/数据中心'], 'impact': '关联', 'reason': '内存价格', 'intensity': 2},
        
        # ========== 中概互联 ==========
        '阿里': {'sectors': ['中概互联'], 'impact': '关联', 'reason': '中概龙头动态', 'intensity': 3},
        '阿里巴巴': {'sectors': ['中概互联'], 'impact': '关联', 'reason': '中概龙头动态', 'intensity': 3},
        '京东': {'sectors': ['中概互联'], 'impact': '关联', 'reason': '中概电商动态', 'intensity': 2},
        '拼多多': {'sectors': ['中概互联'], 'impact': '关联', 'reason': '中概电商动态', 'intensity': 2},
        '腾讯': {'sectors': ['中概互联'], 'impact': '关联', 'reason': '中概科技动态', 'intensity': 3},
        '港股': {'sectors': ['中概互联'], 'impact': '关联', 'reason': '港股市场联动', 'intensity': 2},
    }
    
    # 分析每条新闻
    for news in news_items:
        title = news.get('title', '')
        source = news.get('source', '未知')
        matched = False
        
        # 尝试匹配关键词（优先匹配长关键词）
        sorted_keywords = sorted(keyword_mapping.keys(), key=len, reverse=True)
        
        for keyword in sorted_keywords:
            if keyword in title:
                mapping = keyword_mapping[keyword]
                intensity = mapping.get('intensity', 2)
                stars = "⭐" * intensity + " " + ("高" if intensity >= 4 else "中" if intensity >= 2 else "低")
                
                impact_factors.append({
                    'source': f'新闻-{source}',
                    'title': title[:40] + '...' if len(title) > 40 else title,
                    'keyword': keyword,
                    'sectors': mapping['sectors'],
                    'impact': mapping['impact'],
                    'reason': mapping['reason'],
                    'importance': stars,
                    'intensity': intensity
                })
                matched = True
                break  # 每条新闻只匹配最重要的一个关键词
    
    # 按影响强度排序
    impact_factors.sort(key=lambda x: x.get('intensity', 0), reverse=True)
    
    # 去重（同一关键词的新闻合并）
    seen_keywords = set()
    unique_factors = []
    for factor in impact_factors:
        key = factor['keyword']
        if key not in seen_keywords:
            seen_keywords.add(key)
            unique_factors.append(factor)
    
    return unique_factors[:8]  # 最多返回8个因子


def get_market_cap_data(api, symbols):
    """
    获取市值数据
    数据源: 长桥API静态数据 (总股本×当前股价)
    """
    market_caps = {}
    try:
        # 分批获取静态数据（避免单次请求过多）
        batch_size = 20
        for i in range(0, len(symbols), batch_size):
            batch = symbols[i:i+batch_size]
            resp = api.ctx.static_info(batch)
            for r in resp:
                symbol = str(r.symbol)
                # 总股本（股）
                total_shares = getattr(r, 'total_shares', 0)
                market_caps[symbol] = {
                    'total_shares': total_shares,
                    'name_en': getattr(r, 'name_en', symbol),
                    'name_cn': getattr(r, 'name_cn', symbol)
                }
    except Exception as e:
        print(f"获取市值数据失败: {e}")
    return market_caps


def get_all_symbols():
    """获取所有需要查询的股票代码"""
    symbols = []
    for sector_data in US_SECTORS.values():
        symbols.extend(sector_data['stocks'])
    # 去重
    return list(set(symbols))


def analyze_sectors(quotes_dict, market_caps):
    """
    分析板块强弱（市值>500亿美元）
    过滤逻辑: 市值 = 股价 × 总股本 > 500亿美元
    """
    sector_data = {}

    for sector_name, sector_info in US_SECTORS.items():
        stocks = []
        for symbol in sector_info['stocks']:
            if symbol in quotes_dict:
                q = quotes_dict[symbol]
                price = q.get('price', 0)

                # 计算市值（亿美元）
                cap_info = market_caps.get(symbol, {})
                total_shares = cap_info.get('total_shares', 0)
                market_cap_usd = (price * total_shares) / 1e8  # 转换为亿美元

                # 市值过滤：只保留 > 500亿美元
                if market_cap_usd >= MARKET_CAP_THRESHOLD:
                    stocks.append({
                        'symbol': symbol.replace('.US', ''),
                        'name': cap_info.get('name_cn', symbol.replace('.US', '')),
                        'name_en': cap_info.get('name_en', symbol.replace('.US', '')),
                        'price': price,
                        'change': q.get('change', 0),
                        'turnover': q.get('turnover', 0),
                        'market_cap': market_cap_usd
                    })

        if stocks:
            avg_change = sum(s['change'] for s in stocks) / len(stocks)
            up_count = sum(1 for s in stocks if s['change'] > 0)
            stocks_sorted = sorted(stocks, key=lambda x: x['change'], reverse=True)
            leader = stocks_sorted[0] if stocks_sorted else None

            sector_data[sector_name] = {
                'avg_change': avg_change,
                'up_count': up_count,
                'total': len(stocks),
                'stocks': stocks,
                'leader': leader,
                'a_share_map': sector_info['a_share_map']
            }

    # 按板块平均涨跌幅排序
    return sorted(sector_data.items(), key=lambda x: x[1]['avg_change'], reverse=True)


def identify_key_drivers(sectors, all_stocks, indices_data, news_factors):
    """
    识别核心驱动因子（技术面+新闻面）
    分析维度: 指数表现、板块异动、个股极端行情、新闻驱动
    """
    drivers = []

    # 1. 指数层面驱动
    nasdaq_change = indices_data.get('纳斯达克', {}).get('change', 0)
    if abs(nasdaq_change) > 1.5:
        direction = "大跌" if nasdaq_change < 0 else "大涨"
        drivers.append({
            'factor': f"纳斯达克{direction}",
            'importance': get_importance_emoji(nasdaq_change),
            'impact': f"科技股集体{direction[:-1]}，AI算力板块承压" if nasdaq_change < 0 else "科技股强势，带动市场情绪",
            'a_share_effect': "A股AI/半导体板块同步承压" if nasdaq_change < 0 else "A股科技板块高开",
            'source': '技术面'
        })

    # 2. 板块层面驱动（涨跌幅>3%的板块）
    for sector_name, sector_info in sectors:
        avg_change = sector_info['avg_change']
        if abs(avg_change) > 3:
            direction = "大跌" if avg_change < 0 else "大涨"
            leader = sector_info['leader']
            leader_str = f"{leader['symbol']}{format_change(leader['change'])}领涨" if leader else ""

            # A股映射描述
            a_map = ", ".join(sector_info['a_share_map'][:3])

            drivers.append({
                'factor': f"{sector_name}{direction}",
                'importance': get_importance_emoji(avg_change),
                'impact': f"{sector_name}板块{direction}，{leader_str}",
                'a_share_effect': f"关注A股{a_map}等标的",
                'source': '技术面'
            })

    # 3. 个股极端行情（涨跌幅>5%的大市值股票）
    large_cap_moves = [s for s in all_stocks if abs(s['change']) > 5 and s.get('market_cap', 0) > 1000]
    for stock in large_cap_moves[:3]:  # 最多取3个
        direction = "暴跌" if stock['change'] < 0 else "暴涨"
        drivers.append({
            'factor': f"{stock['symbol']}{direction}",
            'importance': get_importance_emoji(stock['change']),
            'impact': f"{stock['name']}({stock['symbol']}){format_change(stock['change'])}",
            'a_share_effect': f"{'拖累' if stock['change'] < 0 else '提振'}同板块A股情绪",
            'source': '技术面'
        })

    # 4. 新闻驱动因子（优化后的格式）
    for nf in news_factors:
        drivers.append({
            'factor': f"[新闻]{nf.get('keyword', '驱动')}",
            'importance': nf.get('importance', '⭐⭐ 中'),
            'impact': nf['reason'],
            'a_share_effect': f"关注{'/'.join(nf['sectors'])}板块（{nf['impact']}）",
            'source': nf.get('source', '新闻面')
        })

    return drivers


def generate_strategy(sectors, drivers, indices_data):
    """
    生成应对策略
    维度: 板块级别操作建议、仓位管理、风险提示
    """
    strategies = []

    for sector_name, sector_info in sectors:
        avg_change = sector_info['avg_change']
        action, advice = get_action_emoji(avg_change)

        # 根据板块特点细化建议
        if sector_name == 'AI算力' and avg_change < -2:
            advice = "规避追涨，等待企稳，关注英伟达财报后走势"
        elif sector_name == '半导体' and avg_change < -1:
            advice = "短期承压，关注回调机会，设备股优先"
        elif sector_name in ['能源', '黄金/有色'] and avg_change > 2:
            advice = "重点关注，地缘风险+避险属性双击"
        elif sector_name == '中概互联' and avg_change < -2:
            advice = "港股科技股承压，控制仓位"

        strategies.append({
            'sector': sector_name,
            'action': action,
            'advice': advice,
            'a_share_map': ", ".join(sector_info['a_share_map'][:3])
        })

    return strategies


def generate_outlook(indices_data, sectors, drivers):
    """
    生成市场展望
    维度: 趋势判断、核心风险、A股映射、操作建议
    """
    # 趋势判断
    nasdaq = indices_data.get('纳斯达克', {}).get('change', 0)
    sp500 = indices_data.get('标普500', {}).get('change', 0)

    if nasdaq < -2 and sp500 < -1:
        trend = "三大指数齐跌，风险偏好急剧收缩"
        risk_level = "🔴 高风险"
    elif nasdaq < -1:
        trend = "科技股领跌，价值股相对抗跌"
        risk_level = "🟠 中高风险"
    elif nasdaq > 1 and sp500 > 0.5:
        trend = "科技股领涨，市场风险偏好回升"
        risk_level = "🟢 中低风险"
    else:
        trend = "指数震荡，等待方向选择"
        risk_level = "🟡 中性"

    # 核心风险
    risks = []
    if nasdaq < -1.5:
        risks.append("AI/科技股估值回调风险")
    if any(s['factor'].startswith('中概') for s in drivers):
        risks.append("中概股情绪波动")
    if not risks:
        risks.append("地缘政策不确定性")

    # A股影响
    a_impact = ""
    if nasdaq < -1.5:
        a_impact = "AI/半导体首当其冲，关注开盘低开幅度"
    elif nasdaq > 1:
        a_impact = "科技板块高开概率大，关注量能配合"
    else:
        a_impact = "A股可能独立走势，关注国内政策"

    # 操作建议
    if nasdaq < -2:
        operation = "规避科技追涨，配置防御资产（高股息、黄金）"
    elif nasdaq < -1:
        operation = "控制仓位，等待企稳信号"
    elif nasdaq > 1:
        operation = "积极参与科技主线，关注业绩验证"
    else:
        operation = "均衡配置，精选个股"

    return {
        'trend': trend,
        'risk_level': risk_level,
        'risks': risks,
        'a_impact': a_impact,
        'operation': operation
    }


def generate_report():
    """生成美股深度分析报告"""
    print("🌙 正在获取美股行情数据...")
    print("=" * 60)
    print("📊 数据源: 长桥API (个股行情+静态数据) + 腾讯财经API (指数)")
    print("💰 市值过滤: >500亿美元")
    print("=" * 60)

    api = get_longbridge_api()

    # 获取所有股票代码
    symbols = get_all_symbols()
    print(f"📋 共 {len(symbols)} 只关注股票")

    # 1. 获取行情数据
    print("\n📈 获取个股行情...")
    quotes = api.get_quotes(symbols)
    if not quotes:
        print("❌ 获取行情数据失败")
        return None
    quotes_dict = {q['symbol']: q for q in quotes}
    print(f"✅ 获取到 {len(quotes)} 只股票行情")

    # 2. 获取市值数据
    print("\n💰 获取市值数据...")
    market_caps = get_market_cap_data(api, symbols)
    print(f"✅ 获取到 {len(market_caps)} 只股票市值")

    # 3. 获取指数数据
    print("\n📊 获取主要指数...")
    indices_data = {}
    for symbol, info in INDICES.items():
        idx = get_us_index_quote(symbol)
        if idx:
            indices_data[info['name']] = idx
            print(f"  ✅ {info['name']}: {format_change(idx['change'])}")

    # 4. 获取国际新闻（多源）
    print("\n📰 获取国际财经新闻（多源聚合）...")
    news_items = get_international_news()
    news_factors = analyze_news_impact(news_items)
    print(f"✅ 识别 {len(news_factors)} 个新闻驱动因子")
    for nf in news_factors[:3]:
        print(f"  📰 [{nf.get('keyword', '')}] {nf.get('importance', '')} -> {'/'.join(nf.get('sectors', []))}")

    # 获取当前日期
    now = datetime.now()
    today = now.strftime('%Y-%m-%d')
    data_date = (now - timedelta(days=1)).strftime('%Y-%m-%d')

    # 4. 分析板块（市值过滤后）
    print("\n🔍 分析板块强弱（市值>500亿）...")
    sectors = analyze_sectors(quotes_dict, market_caps)
    print(f"✅ 分析完成，共 {len(sectors)} 个板块")

    # 收集所有股票（已过滤）
    all_stocks = []
    for sector_name, sector_info in sectors:
        for stock in sector_info['stocks']:
            all_stocks.append({**stock, 'sector': sector_name})
        print(f"  {sector_name}: {len(sector_info['stocks'])}只股, 平均{format_change(sector_info['avg_change'])}")

    # 5. 亮点/拖累个股（已过滤大市值）
    top_gainers = sorted(all_stocks, key=lambda x: x['change'], reverse=True)[:5]
    top_losers = sorted(all_stocks, key=lambda x: x['change'])[:5]

    # 6. 识别核心驱动（技术面+新闻面）
    print("\n🔍 识别核心驱动因子...")
    drivers = identify_key_drivers(sectors, all_stocks, indices_data, news_factors)
    print(f"✅ 识别 {len(drivers)} 个驱动因子")

    # 7. 生成策略
    strategies = generate_strategy(sectors, drivers, indices_data)

    # 8. 生成展望
    outlook = generate_outlook(indices_data, sectors, drivers)

    # ===== 生成报告 =====
    report_lines = [
        f"# 📊 美股市场深度分析报告",
        f"",
        f"**报告生成时间**: {now.strftime('%Y-%m-%d %H:%M:%S')}",
        f"**数据日期**: {data_date}（前一交易日）",
        f"**分析范围**: 市值>500亿美元美股",
        f"",
        f"---",
        f"",
        f"## 一、主要指数表现",
        f"",
        f"| 指数 | 涨跌幅 | 数据源 |",
        f"|------|--------|--------|"
    ]

    for name, idx in indices_data.items():
        source = INDICES.get(f"us{name}", {}).get('source', '腾讯财经API')
        report_lines.append(f"| {get_emoji(idx['change'])} **{name}** | {format_change(idx['change'])} | {source} |")

    report_lines.extend([
        f"",
        f"**趋势判断**: {outlook['trend']}",
        f"**风险等级**: {outlook['risk_level']}",
        f"",
        f"---",
        f"",
        f"## 二、板块强弱排序（市值>500亿）",
        f"",
        f"| 排名 | 板块 | 平均涨跌 | 个股数 | 领涨股 | A股映射 |",
        f"|------|------|----------|--------|--------|----------|"
    ])

    for i, (sector_name, sector_info) in enumerate(sectors, 1):
        emoji = get_emoji(sector_info['avg_change'])
        rank = get_rank_emoji(i)
        leader = sector_info['leader']
        leader_str = f"{leader['symbol']} {format_change(leader['change'])}" if leader else "-"
        a_map = ", ".join(sector_info['a_share_map'][:2])

        report_lines.append(
            f"| {rank} | {emoji} {sector_name} | {format_change(sector_info['avg_change'])} | {sector_info['total']}只 | {leader_str} | {a_map} |"
        )

    report_lines.extend([
        f"",
        f"---",
        f"",
        f"## 三、核心驱动因子（美股→A股传导）",
        f"",
        f"*驱动因子来源: 技术面（行情数据）+ 新闻面（财经新闻分析）*",
        f"",
        f"| 驱动因子 | 重要度 | 美股现象 | A股影响 | 来源 |",
        f"|----------|--------|----------|----------|------|"
    ])

    for driver in drivers[:8]:  # 最多显示8个
        source = driver.get('source', '技术面')
        report_lines.append(
            f"| {driver['factor']} | {driver['importance']} | {driver['impact']} | {driver['a_share_effect']} | {source} |"
        )

    report_lines.extend([
        f"",
        f"---",
        f"",
        f"## 四、应对策略",
        f"",
        f"| 板块 | 操作 | 建议 | A股关注标的 |",
        f"|------|------|------|-------------|"
    ])

    for strategy in strategies:
        report_lines.append(
            f"| {strategy['sector']} | {strategy['action']} | {strategy['advice']} | {strategy['a_share_map']} |"
        )

    report_lines.extend([
        f"",
        f"---",
        f"",
        f"## 五、重点个股（市值>500亿）",
        f"",
        f"### 🔥 亮点个股",
        f"",
        f"| 股票 | 涨跌幅 | 市值 | 板块 |",
        f"|------|--------|------|------|"
    ])

    for stock in top_gainers:
        emoji = "🚀" if stock['change'] > 5 else "📈"
        report_lines.append(
            f"| {emoji} {stock['symbol']} | {format_change(stock['change'])} | {stock['market_cap']:.0f}亿 | {stock['sector']} |"
        )

    report_lines.extend([
        f"",
        f"### 🔻 拖累因素",
        f"",
        f"| 股票 | 涨跌幅 | 市值 | 板块 |",
        f"|------|--------|------|------|"
    ])

    for stock in top_losers:
        emoji = "🔻" if stock['change'] < -5 else "📉"
        report_lines.append(
            f"| {emoji} {stock['symbol']} | {format_change(stock['change'])} | {stock['market_cap']:.0f}亿 | {stock['sector']} |"
        )

    report_lines.extend([
        f"",
        f"---",
        f"",
        f"## 六、市场展望与总结",
        f"",
        f"| 维度 | 结论 |",
        f"|------|------|",
        f"| **美股趋势** | {outlook['trend']} |",
        f"| **风险等级** | {outlook['risk_level']} |",
        f"| **A股影响** | {outlook['a_impact']} |",
        f"| **操作建议** | {outlook['operation']} |",
        f"",
        f"**核心风险**: {', '.join(outlook['risks'])}",
        f"",
        f"---",
        f"",
        f"## 📌 数据来源",
        f"",
        f"### 行情数据",
        f"- **个股实时行情**: 长桥API (Longbridge OpenAPI) - `QuoteContext.quote()`",
        f"- **个股市值**: 长桥API静态数据 - `QuoteContext.static_info()` (总股本×当前股价)",
        f"- **美股指数**: 腾讯财经API (https://qt.gtimg.cn)",
        f"- **涨跌幅计算**: (现价-昨收)/昨收 × 100%",
        f"",
        f"### 新闻数据（多源聚合）",
        f"- **新浪财经API**: https://feed.mix.sina.com.cn/api/roll/get",
        f"- **腾讯财经API**: https://i.news.qq.com/trpc.qqnews_web.kv_srv.kv_srv_http_proxy/list",
        f"- **网易财经**: https://money.163.com/stock/usstock/",
        f"- **新闻分析**: 关键词匹配（70+关键词）+ 板块映射 + 影响强度评估",
        f"",
        f"### 映射关系",
        f"- **A股映射**: 基于业务关联性人工梳理",
        f"",
        f"---",
        f"",
        f"⚠️ **风险提示**: 本报告仅供参考，不构成投资建议。股市有风险，投资需谨慎。",
        f"- 数据可能存在延迟（T-1日数据）",
        f"- 市值数据基于上一交易日收盘价计算",
        f"- A股映射关系基于业务关联性，可能存在偏差",
        f"- 新闻分析基于关键词匹配，可能遗漏或误判",
        f"",
        f"📅 **下次任务**: 09:15 A+H市场盘前分析"
    ])

    report = "\n".join(report_lines)

    # 保存报告
    report_file = f"/root/.openclaw/workspace/data/us_market_daily_{now.strftime('%Y%m%d')}.md"
    os.makedirs(os.path.dirname(report_file), exist_ok=True)
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write(report)

    print(f"\n✅ 报告已生成: {report_file}")
    print("\n" + "=" * 60)
    print(report[:1500])  # 打印前1500字符预览
    print("\n... [报告已截断] ...")

    # 发送到飞书
    print("\n📤 正在发送到飞书...")
    send_feishu_message(report, "📊 美股市场深度分析报告")

    # 记录日志
    with open('/root/.openclaw/workspace/tools/us_market_send.log', 'a') as f:
        f.write(f"{now}: v2.0报告生成并发送\n")

    return report


if __name__ == "__main__":
    generate_report()
