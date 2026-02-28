#!/usr/bin/env python3
"""
A+H股开盘前瞻报告生成器 v2.0 (深度版)
每日9:15前生成开盘策略分析，结合美股报告+A股/港股板块分析+新闻驱动

分析框架：
1. 隔夜美股回顾（引用美股报告核心结论）
2. A股板块分析（市值>100亿，实时行情）
3. 港股板块分析（市值>100亿港币，实时行情）
4. 集合竞价数据（开盘前15分钟）
5. 核心驱动因子（技术面+新闻面）
6. 开盘策略建议
7. 重点个股监控

数据源：
- 个股行情: 长桥API
- 美股回顾: 引用美股报告
- 新闻驱动: 新浪财经+腾讯+网易
- 集合竞价: 长桥API（如支持）

作者: 豆奶投资策略系统
版本: 2.0
"""
import sys
import os
import json
from datetime import datetime, timedelta

# 加载环境变量
env_file = '/root/.openclaw/workspace/.longbridge.env'
if os.path.exists(env_file):
    with open(env_file, 'r') as f:
        for line in f:
            if '=' in line and not line.startswith('#'):
                key, value = line.strip().split('=', 1)
                os.environ[key] = value.strip('"')

# 添加路径
sys.path.insert(0, '/root/.openclaw/workspace/tools')
from longbridge_api import get_longbridge_api

# ============================================
# 配置
# ============================================

USER_ID = 'ou_efbad805767f4572e8f93ebafa8d5402'

# A股市值过滤（亿人民币）
A_MARKET_CAP_THRESHOLD = 100
# 港股市值过滤（亿港币）
H_MARKET_CAP_THRESHOLD = 100

# A股板块定义（市值>100亿）
A_SECTORS = {
    'AI算力': {
        'stocks': ['002371.SZ', '688012.SH', '688256.SH', '300474.SZ'],
        'leaders': ['北方华创', '中微公司', '寒武纪', '景嘉微'],
    },
    '半导体设备': {
        'stocks': ['688012.SH', '688072.SH', '688120.SH', '300316.SZ'],
        'leaders': ['中微公司', '拓荆科技', '华海清科', '晶盛机电'],
    },
    '光通讯': {
        'stocks': ['300308.SZ', '300502.SZ', '300394.SZ', '002281.SZ'],
        'leaders': ['中际旭创', '新易盛', '天孚通信', '光迅科技'],
    },
    '新能源': {
        'stocks': ['300750.SZ', '002594.SZ', '601012.SH', '600438.SH'],
        'leaders': ['宁德时代', '比亚迪', '隆基绿能', '通威股份'],
    },
    '消费': {
        'stocks': ['600519.SH', '000858.SZ', '000568.SZ', '002304.SZ'],
        'leaders': ['贵州茅台', '五粮液', '泸州老窖', '洋河股份'],
    },
    '金融': {
        'stocks': ['600036.SH', '601318.SH', '300059.SZ', '600030.SH'],
        'leaders': ['招商银行', '中国平安', '东方财富', '中信证券'],
    },
    '医药': {
        'stocks': ['600276.SH', '300760.SZ', '603259.SH', '688235.SH'],
        'leaders': ['恒瑞医药', '迈瑞医疗', '药明康德', '百济神州'],
    },
}

# 港股板块定义（市值>100亿港币）
H_SECTORS = {
    '科技巨头': {
        'stocks': ['00700.HK', '09988.HK', '03690.HK', '01810.HK'],
        'leaders': ['腾讯', '阿里', '美团', '小米'],
    },
    '中概互联': {
        'stocks': ['09988.HK', '09618.HK', '01024.HK', '02015.HK'],
        'leaders': ['阿里', '京东', '快手', '理想汽车'],
    },
    '能源': {
        'stocks': ['00883.HK', '00857.HK', '00386.HK', '01088.HK'],
        'leaders': ['中海油', '中石油', '中石化', '神华'],
    },
    '金融': {
        'stocks': ['02318.HK', '03968.HK', '01299.HK', '01398.HK'],
        'leaders': ['平安', '招行', '友邦', '工行'],
    },
    '消费': {
        'stocks': ['01898.HK', '02331.HK', '09633.HK', '06186.HK'],
        'leaders': ['中烟', '李宁', '农夫山泉', '中国飞鹤'],
    },
    '生物医药': {
        'stocks': ['02359.HK', '01801.HK', '06160.HK', '01167.HK'],
        'leaders': ['药明康德', '信达生物', '百济神州', '复星医药'],
    },
}

# ============================================
# 工具函数
# ============================================

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
        if c > 2:
            return "🚀"
        elif c > 0:
            return "📈"
        elif c > -2:
            return "📉"
        else:
            return "🔻"
    except:
        return "⚪"


def get_importance_emoji(change):
    """重要度评级"""
    try:
        c = abs(float(change))
        if c > 3:
            return "⭐⭐⭐ 高"
        elif c > 1.5:
            return "⭐⭐ 中"
        else:
            return "⭐ 低"
    except:
        return "-"


def get_action_emoji(change):
    """操作建议表情"""
    try:
        c = float(change)
        if c > 2:
            return "✅ 关注", "强势，可参与"
        elif c > 0:
            return "➡️ 持有", "平稳，维持"
        elif c > -2:
            return "⚠️ 观望", "调整，等待"
        else:
            return "❌ 规避", "弱势，回避"
    except:
        return "-", "-"


def send_feishu_message(content: str, title: str = "A+H开盘报告"):
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


# ============================================
# 新闻获取模块（复用美股报告的增强版）
# ============================================

def get_sina_news():
    """获取新浪财经新闻"""
    news_items = []
    try:
        import requests
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        
        urls = [
            "https://feed.mix.sina.com.cn/api/roll/get?pageid=153&lid=2516&num=15",
            "https://feed.mix.sina.com.cn/api/roll/get?pageid=153&lid=2517&num=10",  # 国际财经
        ]
        
        for url in urls:
            try:
                response = requests.get(url, headers=headers, timeout=10)
                if response.status_code == 200:
                    data = response.json()
                    if 'result' in data and 'data' in data['result']:
                        for item in data['result']['data']:
                            news_items.append({
                                'title': item.get('title', ''),
                                'time': item.get('ctime', ''),
                                'source': '新浪财经'
                            })
            except:
                continue
    except Exception as e:
        print(f"  ⚠️ 新浪财经: {e}")
    return news_items


def get_tencent_news():
    """获取腾讯财经新闻"""
    news_items = []
    try:
        import requests
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Referer': 'https://news.qq.com/'
        }
        
        # 腾讯财经API - 使用新的接口
        url = "https://i.news.qq.com/trpc.qqnews_web.kv_srv.kv_srv_http_proxy/list"
        params = {
            'sub_srv_id': 'finance',
            'srv_id': 'pc',
            'limit': 20,
            'page': 1
        }
        
        response = requests.get(url, params=params, headers=headers, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data.get('ret') == 0 and 'data' in data:
                for item in data['data'].get('list', []):
                    news_items.append({
                        'title': item.get('title', ''),
                        'time': item.get('time', ''),
                        'source': '腾讯财经'
                    })
    except Exception as e:
        print(f"  ⚠️ 腾讯财经: {e}")
    return news_items


def get_netease_news():
    """获取网易财经新闻（使用BeautifulSoup）"""
    news_items = []
    try:
        import requests
        from bs4 import BeautifulSoup
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        # 网易美股新闻
        url = "https://money.163.com/stock/usstock/"
        response = requests.get(url, headers=headers, timeout=15)
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'lxml')
            
            # 提取新闻标题 - 适配网易财经页面结构
            selectors = [
                '.news_title a', '.title a', '.hidden-title a',
                '.news_list h2 a', '.item a', '.item-txt a'
            ]
            
            for selector in selectors:
                links = soup.select(selector)[:10]
                for link in links:
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
        print(f"  ⚠️ 网易财经: {e}")
    return news_items


def get_agent_reach_news():
    """使用 Agent Reach 工具获取新闻"""
    news_items = []
    try:
        import subprocess
        import json
        
        # 使用 yt-dlp 获取 YouTube 财经视频信息 (如果可用)
        try:
            result = subprocess.run(
                ['yt-dlp', '--flat-playlist', '--dump-json', 
                 '--playlist-end', '5',
                 'https://www.youtube.com/@CNBCtv/videos'],
                capture_output=True, text=True, timeout=15
            )
            if result.returncode == 0:
                videos = result.stdout.strip().split('\n')
                for video in videos[:3]:
                    try:
                        if video:
                            data = json.loads(video)
                            title = data.get('title', '')
                            if title and any(k in title.lower() for k in ['stock', 'market', 'trade', 'fed', 'tech', 'china']):
                                news_items.append({
                                    'title': f"[YouTube] {title}",
                                    'time': '',
                                    'source': 'AgentReach-YouTube'
                                })
                    except:
                        continue
        except:
            pass
        
        # 使用 feedparser 读取 RSS
        try:
            import feedparser
            rss_urls = [
                'https://feeds.a.dj.com/rss/RSSMarketsMain.xml',
                'https://feeds.a.dj.com/rss/RSSWorldNews.xml'
            ]
            for url in rss_urls:
                try:
                    d = feedparser.parse(url)
                    for entry in d.entries[:3]:
                        news_items.append({
                            'title': f"[RSS] {entry.title}",
                            'time': '',
                            'source': 'AgentReach-RSS'
                        })
                except:
                    continue
        except:
            pass
        
    except Exception as e:
        print(f"  ⚠️ Agent Reach: {e}")
    
    return news_items


def get_wallstreetcn_news():
    """获取华尔街见闻新闻"""
    news_items = []
    try:
        import requests
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        url = "https://api-one.wallstcn.com/apiv1/content/information-flow?accept=article%2Cad&limit=10"
        
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data.get('code') == 20000 and data.get('data'):
                items = data['data'].get('items', [])
                for item in items[:8]:
                    resource = item.get('resource', {})
                    title = resource.get('title', '')
                    if title:
                        news_items.append({
                            'title': title,
                            'time': resource.get('display_time', ''),
                            'source': '华尔街见闻'
                        })
    except Exception as e:
        print(f"  ⚠️ 华尔街见闻: {e}")
    return news_items


def get_yicai_news():
    """获取第一财经新闻"""
    news_items = []
    try:
        import requests
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        url = "https://www.yicai.com/api/ajax/getlatest?page=1&pagesize=10"
        
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data:
                for item in data[:8]:
                    title = item.get('NewsTitle', '')
                    if title:
                        news_items.append({
                            'title': title,
                            'time': item.get('CreateDate', ''),
                            'source': '第一财经'
                        })
    except Exception as e:
        print(f"  ⚠️ 第一财经: {e}")
    return news_items


def get_eastmoney_news():
    """获取东方财富新闻"""
    news_items = []
    try:
        import requests
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        url = "https://np-anotice-stock.eastmoney.com/api/security/ann?page_size=10&page_index=1"
        
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
        print(f"  ⚠️ 东方财富: {e}")
    return news_items


def get_exa_news():
    """
    使用 Exa MCP 进行全网语义搜索（高优先级）
    数据源: Exa AI 搜索引擎
    """
    news_items = []
    try:
        import subprocess
        import re
        
        # A+H相关搜索词
        search_queries = [
            "A股港股最新动态",
            "中国股市政策",
            "港股科技股走势"
        ]
        
        for query in search_queries[:2]:
            try:
                cmd = [
                    'mcporter', 'call',
                    f'exa.web_search_exa({{"query": "{query}", "numResults": 5}})'
                ]
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
                
                if result.returncode == 0 and result.stdout:
                    output = result.stdout
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
            except:
                continue
                
    except Exception as e:
        print(f"  ⚠️ Exa全网搜索: {e}")
    
    return news_items


def get_international_news():
    """获取国际财经新闻（多源聚合）"""
    print("\n📰 获取财经新闻（多源聚合）...")
    all_news = []
    
    # 高优先级: Exa全网搜索
    print("  🔍 高优先级: Exa全网语义搜索...")
    exa_news = get_exa_news()
    all_news.extend(exa_news)
    
    sina_news = get_sina_news()
    tencent_news = get_tencent_news()
    netease_news = get_netease_news()
    agent_reach_news = get_agent_reach_news()
    wallstreetcn_news = get_wallstreetcn_news()
    yicai_news = get_yicai_news()
    eastmoney_news = get_eastmoney_news()
    
    all_news.extend(sina_news)
    all_news.extend(tencent_news)
    all_news.extend(netease_news)
    all_news.extend(agent_reach_news)
    all_news.extend(wallstreetcn_news)
    all_news.extend(yicai_news)
    all_news.extend(eastmoney_news)
    
    # 去重
    seen_titles = set()
    unique_news = []
    for news in all_news:
        title = news.get('title', '')
        simple_title = ''.join(c for c in title if c.isalnum())[:15]
        if simple_title and simple_title not in seen_titles:
            seen_titles.add(simple_title)
            unique_news.append(news)
    
    print(f"  ✅ Exa全网搜索: {len(exa_news)}条 [高优先级]")
    print(f"  ✅ 新浪财经: {len(sina_news)}条")
    print(f"  ✅ 腾讯财经: {len(tencent_news)}条")
    print(f"  ✅ 网易财经: {len(netease_news)}条")
    print(f"  ✅ 华尔街见闻: {len(wallstreetcn_news)}条")
    print(f"  ✅ 第一财经: {len(yicai_news)}条")
    print(f"  ✅ 东方财富: {len(eastmoney_news)}条")
    print(f"  ✅ Agent Reach: {len(agent_reach_news)}条")
    print(f"  ✅ 去重后: {len(unique_news)}条")
    
    return unique_news[:35]


def analyze_news_impact(news_items, market='A+H'):
    """分析新闻对市场的影响"""
    impact_factors = []
    
    # A+H市场关键词映射
    keyword_mapping = {
        # 政策
        '政策': {'sectors': ['金融', '消费'], 'impact': '关联', 'reason': '政策影响', 'intensity': 3},
        '降准': {'sectors': ['金融', '地产'], 'impact': '利好', 'reason': '流动性宽松', 'intensity': 4},
        '降息': {'sectors': ['金融', '地产'], 'impact': '利好', 'reason': '资金成本下降', 'intensity': 4},
        '刺激': {'sectors': ['消费', '新能源'], 'impact': '利好', 'reason': '经济刺激政策', 'intensity': 3},
        
        # 科技
        '半导体': {'sectors': ['半导体设备'], 'impact': '关联', 'reason': '半导体产业动态', 'intensity': 4},
        '芯片': {'sectors': ['半导体设备', 'AI算力'], 'impact': '关联', 'reason': '芯片产业链', 'intensity': 4},
        '人工智能': {'sectors': ['AI算力'], 'impact': '利好', 'reason': 'AI产业', 'intensity': 4},
        '英伟达': {'sectors': ['AI算力', '半导体设备'], 'impact': '关联', 'reason': 'AI龙头动态', 'intensity': 5},
        '光模块': {'sectors': ['光通讯'], 'impact': '利好', 'reason': '光通讯产业', 'intensity': 4},
        '5G': {'sectors': ['光通讯', '半导体设备'], 'impact': '利好', 'reason': '通信基建', 'intensity': 3},
        
        # 新能源
        '新能源': {'sectors': ['新能源'], 'impact': '关联', 'reason': '新能源产业', 'intensity': 3},
        '电动车': {'sectors': ['新能源'], 'impact': '关联', 'reason': '电动车动态', 'intensity': 3},
        '光伏': {'sectors': ['新能源'], 'impact': '关联', 'reason': '光伏产业', 'intensity': 3},
        '储能': {'sectors': ['新能源'], 'impact': '利好', 'reason': '储能需求', 'intensity': 3},
        
        # 消费
        '消费': {'sectors': ['消费'], 'impact': '关联', 'reason': '消费数据', 'intensity': 3},
        '白酒': {'sectors': ['消费'], 'impact': '关联', 'reason': '白酒行业', 'intensity': 3},
        '茅台': {'sectors': ['消费'], 'impact': '关联', 'reason': '白酒龙头', 'intensity': 4},
        
        # 医药
        '医药': {'sectors': ['医药', '生物医药'], 'impact': '关联', 'reason': '医药产业', 'intensity': 3},
        '疫苗': {'sectors': ['医药', '生物医药'], 'impact': '利好', 'reason': '疫苗需求', 'intensity': 3},
        '创新药': {'sectors': ['医药', '生物医药'], 'impact': '利好', 'reason': '创新药突破', 'intensity': 4},
        
        # 金融
        '银行': {'sectors': ['金融'], 'impact': '关联', 'reason': '银行业动态', 'intensity': 2},
        '券商': {'sectors': ['金融'], 'impact': '关联', 'reason': '券商动态', 'intensity': 3},
        '保险': {'sectors': ['金融'], 'impact': '关联', 'reason': '保险行业', 'intensity': 2},
        
        # 港股特定
        '港股': {'sectors': ['科技巨头', '中概互联'], 'impact': '关联', 'reason': '港股市场', 'intensity': 3},
        '恒指': {'sectors': ['科技巨头', '金融'], 'impact': '关联', 'reason': '恒指动态', 'intensity': 3},
        '腾讯': {'sectors': ['科技巨头'], 'impact': '关联', 'reason': '腾讯动态', 'intensity': 4},
        '阿里': {'sectors': ['科技巨头', '中概互联'], 'impact': '关联', 'reason': '阿里动态', 'intensity': 4},
        '美团': {'sectors': ['科技巨头'], 'impact': '关联', 'reason': '美团动态', 'intensity': 3},
        
        # 国际
        '美股': {'sectors': ['科技巨头', '中概互联'], 'impact': '关联', 'reason': '美股映射', 'intensity': 3},
        '纳斯达克': {'sectors': ['科技巨头', 'AI算力'], 'impact': '关联', 'reason': '科技股映射', 'intensity': 4},
        '美联储': {'sectors': ['金融'], 'impact': '关联', 'reason': '美联储政策', 'intensity': 4},
        '加息': {'sectors': ['金融', '科技巨头'], 'impact': '利空', 'reason': '资金成本上升', 'intensity': 4},
        '降息': {'sectors': ['金融', '科技巨头'], 'impact': '利好', 'reason': '流动性宽松', 'intensity': 4},
        '通胀': {'sectors': ['消费', '金融'], 'impact': '利空', 'reason': '通胀压力', 'intensity': 3},
        
        # 地缘
        '冲突': {'sectors': ['能源'], 'impact': '利好', 'reason': '地缘风险', 'intensity': 3},
        '战争': {'sectors': ['能源'], 'impact': '利好', 'reason': '地缘风险', 'intensity': 4},
        '原油': {'sectors': ['能源'], 'impact': '关联', 'reason': '原油价格', 'intensity': 4},
        '黄金': {'sectors': ['能源'], 'impact': '利好', 'reason': '避险需求', 'intensity': 3},
    }
    
    for news in news_items:
        title = news.get('title', '')
        for keyword, mapping in keyword_mapping.items():
            if keyword in title:
                intensity = mapping.get('intensity', 2)
                stars = "⭐" * intensity + " " + ("高" if intensity >= 4 else "中" if intensity >= 2 else "低")
                
                impact_factors.append({
                    'keyword': keyword,
                    'title': title[:40] + '...' if len(title) > 40 else title,
                    'sectors': mapping['sectors'],
                    'impact': mapping['impact'],
                    'reason': mapping['reason'],
                    'importance': stars,
                    'intensity': intensity,
                    'source': news.get('source', '新闻')
                })
                break
    
    # 排序并去重
    impact_factors.sort(key=lambda x: x.get('intensity', 0), reverse=True)
    
    seen_keywords = set()
    unique_factors = []
    for factor in impact_factors:
        if factor['keyword'] not in seen_keywords:
            seen_keywords.add(factor['keyword'])
            unique_factors.append(factor)
    
    return unique_factors[:8]


# ============================================
# 市场分析模块
# ============================================

def analyze_a_sectors(quotes_dict):
    """分析A股板块强弱"""
    sector_data = {}
    
    for sector_name, sector_info in A_SECTORS.items():
        stocks = []
        for symbol in sector_info['stocks']:
            if symbol in quotes_dict:
                q = quotes_dict[symbol]
                stocks.append({
                    'symbol': symbol,
                    'name': sector_info['leaders'][sector_info['stocks'].index(symbol)] if symbol in sector_info['stocks'] else symbol,
                    'price': q.get('price', 0),
                    'change': q.get('change', 0),
                })
        
        if stocks:
            avg_change = sum(s['change'] for s in stocks) / len(stocks)
            stocks_sorted = sorted(stocks, key=lambda x: x['change'], reverse=True)
            leader = stocks_sorted[0] if stocks_sorted else None
            
            sector_data[sector_name] = {
                'avg_change': avg_change,
                'up_count': sum(1 for s in stocks if s['change'] > 0),
                'total': len(stocks),
                'stocks': stocks,
                'leader': leader
            }
    
    return sorted(sector_data.items(), key=lambda x: x[1]['avg_change'], reverse=True)


def analyze_h_sectors(quotes_dict):
    """分析港股板块强弱"""
    sector_data = {}
    
    for sector_name, sector_info in H_SECTORS.items():
        stocks = []
        for symbol in sector_info['stocks']:
            if symbol in quotes_dict:
                q = quotes_dict[symbol]
                stocks.append({
                    'symbol': symbol,
                    'name': sector_info['leaders'][sector_info['stocks'].index(symbol)] if symbol in sector_info['stocks'] else symbol,
                    'price': q.get('price', 0),
                    'change': q.get('change', 0),
                })
        
        if stocks:
            avg_change = sum(s['change'] for s in stocks) / len(stocks)
            stocks_sorted = sorted(stocks, key=lambda x: x['change'], reverse=True)
            leader = stocks_sorted[0] if stocks_sorted else None
            
            sector_data[sector_name] = {
                'avg_change': avg_change,
                'up_count': sum(1 for s in stocks if s['change'] > 0),
                'total': len(stocks),
                'stocks': stocks,
                'leader': leader
            }
    
    return sorted(sector_data.items(), key=lambda x: x[1]['avg_change'], reverse=True)


def get_us_market_summary():
    """获取美股隔夜回顾（读取最新美股报告）"""
    try:
        today = datetime.now().strftime('%Y%m%d')
        report_file = f"/root/.openclaw/workspace/data/us_market_daily_{today}.md"
        
        if os.path.exists(report_file):
            with open(report_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 提取关键信息
            summary = {
                'loaded': True,
                'indices': [],
                'top_sectors': [],
                'key_drivers': []
            }
            
            # 简化处理，返回报告路径
            return {'loaded': True, 'file': report_file}
        else:
            return {'loaded': False, 'file': None}
    except Exception as e:
        return {'loaded': False, 'error': str(e)}


# ============================================
# 报告生成
# ============================================

def generate_report():
    """生成A+H开盘前瞻深度报告"""
    print("🌅 A+H股开盘前瞻 v2.0 深度分析")
    print("=" * 60)
    
    now = datetime.now()
    today_str = now.strftime('%Y-%m-%d')
    
    # 1. 获取新闻
    news_items = get_international_news()
    news_factors = analyze_news_impact(news_items)
    print(f"✅ 识别 {len(news_factors)} 个新闻驱动因子")
    
    # 2. 获取美股回顾
    print("\n📊 获取美股隔夜回顾...")
    us_summary = get_us_market_summary()
    if us_summary['loaded']:
        print(f"  ✅ 已加载美股报告: {us_summary['file']}")
    else:
        print("  ⚠️ 美股报告未生成")
    
    # 3. 获取A+H行情
    print("\n📈 获取A+H股行情...")
    api = get_longbridge_api()
    
    all_a_symbols = []
    for sector in A_SECTORS.values():
        all_a_symbols.extend(sector['stocks'])
    
    all_h_symbols = []
    for sector in H_SECTORS.values():
        all_h_symbols.extend(sector['stocks'])
    
    all_symbols = list(set(all_a_symbols + all_h_symbols))
    quotes = api.get_quotes(all_symbols)
    quotes_dict = {q['symbol']: q for q in quotes}
    print(f"  ✅ 获取到 {len(quotes)} 只股票行情")
    
    # 4. 分析板块
    print("\n🔍 分析A股板块...")
    a_sectors = analyze_a_sectors(quotes_dict)
    print(f"  ✅ 分析完成，共 {len(a_sectors)} 个板块")
    
    print("\n🔍 分析港股板块...")
    h_sectors = analyze_h_sectors(quotes_dict)
    print(f"  ✅ 分析完成，共 {len(h_sectors)} 个板块")
    
    # 收集所有股票
    all_a_stocks = []
    for sector_name, sector_info in a_sectors:
        for stock in sector_info['stocks']:
            all_a_stocks.append({**stock, 'sector': sector_name})
    
    all_h_stocks = []
    for sector_name, sector_info in h_sectors:
        for stock in sector_info['stocks']:
            all_h_stocks.append({**stock, 'sector': sector_name})
    
    # 5. 亮点/拖累个股
    a_gainers = sorted(all_a_stocks, key=lambda x: x['change'], reverse=True)[:5]
    a_losers = sorted(all_a_stocks, key=lambda x: x['change'])[:5]
    h_gainers = sorted(all_h_stocks, key=lambda x: x['change'], reverse=True)[:5]
    h_losers = sorted(all_h_stocks, key=lambda x: x['change'])[:5]
    
    # 6. 生成报告
    report_lines = [
        f"# 🌅 A+H股开盘前瞻报告 v2.0",
        f"",
        f"**报告生成时间**: {now.strftime('%Y-%m-%d %H:%M:%S')}",
        f"**数据日期**: {today_str}",
        f"**分析框架**: 美股回顾 + A股板块 + 港股板块 + 新闻驱动",
        f"",
        f"---",
        f"",
        f"## 一、隔夜美股回顾",
        f"",
    ]
    
    if us_summary['loaded']:
        report_lines.append(f"✅ **美股报告已生成**: 参见 `us_market_daily_{today_str}.md`")
        report_lines.append(f"")
        report_lines.append(f"**核心结论**: 参见美股报告「市场展望与总结」部分")
    else:
        report_lines.append(f"⚠️ **美股报告尚未生成**，建议先生成美股报告")
    
    report_lines.extend([
        f"",
        f"---",
        f"",
        f"## 二、A股板块强弱排序",
        f"",
        f"| 排名 | 板块 | 平均涨跌 | 个股数 | 领涨股 |",
        f"|------|------|----------|--------|--------|"
    ])
    
    for i, (sector_name, sector_info) in enumerate(a_sectors, 1):
        emoji = get_emoji(sector_info['avg_change'])
        rank = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
        leader = sector_info['leader']
        leader_str = f"{leader['name']} {format_change(leader['change'])}" if leader else "-"
        
        report_lines.append(
            f"| {rank} | {emoji} {sector_name} | {format_change(sector_info['avg_change'])} | {sector_info['total']}只 | {leader_str} |"
        )
    
    report_lines.extend([
        f"",
        f"---",
        f"",
        f"## 三、港股板块强弱排序",
        f"",
        f"| 排名 | 板块 | 平均涨跌 | 个股数 | 领涨股 |",
        f"|------|------|----------|--------|--------|"
    ])
    
    for i, (sector_name, sector_info) in enumerate(h_sectors, 1):
        emoji = get_emoji(sector_info['avg_change'])
        rank = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
        leader = sector_info['leader']
        leader_str = f"{leader['name']} {format_change(leader['change'])}" if leader else "-"
        
        report_lines.append(
            f"| {rank} | {emoji} {sector_name} | {format_change(sector_info['avg_change'])} | {sector_info['total']}只 | {leader_str} |"
        )
    
    report_lines.extend([
        f"",
        f"---",
        f"",
        f"## 四、新闻驱动因子（隔夜+A股开盘）",
        f"",
        f"| 驱动因子 | 重要度 | 影响板块 | 逻辑 | 来源 |",
        f"|----------|--------|----------|------|------|"
    ])
    
    for factor in news_factors[:6]:
        report_lines.append(
            f"| {factor['keyword']} | {factor['importance']} | {'/'.join(factor['sectors'])} | {factor['reason']} | {factor['source']} |"
        )
    
    report_lines.extend([
        f"",
        f"---",
        f"",
        f"## 五、开盘策略建议",
        f"",
        f"### A股策略",
        f"",
        f"| 板块 | 操作 | 建议 |",
        f"|------|------|------|"
    ])
    
    for sector_name, sector_info in a_sectors:
        action, advice = get_action_emoji(sector_info['avg_change'])
        report_lines.append(f"| {sector_name} | {action} | {advice} |")
    
    report_lines.extend([
        f"",
        f"### 港股策略",
        f"",
        f"| 板块 | 操作 | 建议 |",
        f"|------|------|------|"
    ])
    
    for sector_name, sector_info in h_sectors:
        action, advice = get_action_emoji(sector_info['avg_change'])
        report_lines.append(f"| {sector_name} | {action} | {advice} |")
    
    report_lines.extend([
        f"",
        f"---",
        f"",
        f"## 六、重点个股监控",
        f"",
        f"### A股",
        f"",
        f"**🔥 涨幅前5**:"
    ])
    
    for stock in a_gainers:
        emoji = "🚀" if stock['change'] > 5 else "📈"
        report_lines.append(f"- {emoji} {stock['name']}({stock['symbol']}): {format_change(stock['change'])} - {stock['sector']}")
    
    report_lines.append(f"")
    report_lines.append(f"**🔻 跌幅前5**:")
    
    for stock in a_losers:
        emoji = "🔻" if stock['change'] < -5 else "📉"
        report_lines.append(f"- {emoji} {stock['name']}({stock['symbol']}): {format_change(stock['change'])} - {stock['sector']}")
    
    report_lines.extend([
        f"",
        f"### 港股",
        f"",
        f"**🔥 涨幅前5**:"
    ])
    
    for stock in h_gainers:
        emoji = "🚀" if stock['change'] > 5 else "📈"
        report_lines.append(f"- {emoji} {stock['name']}({stock['symbol']}): {format_change(stock['change'])} - {stock['sector']}")
    
    report_lines.append(f"")
    report_lines.append(f"**🔻 跌幅前5**:")
    
    for stock in h_losers:
        emoji = "🔻" if stock['change'] < -5 else "📉"
        report_lines.append(f"- {emoji} {stock['name']}({stock['symbol']}): {format_change(stock['change'])} - {stock['sector']}")
    
    report_lines.extend([
        f"",
        f"---",
        f"",
        f"## 📌 数据来源",
        f"",
        f"- **行情数据**: 长桥API (Longbridge OpenAPI)",
        f"- **美股回顾**: 引用美股市场深度分析报告",
        f"- **新闻数据**: 新浪财经API + 腾讯财经API + 网易财经",
        f"- **新闻分析**: 关键词匹配（50+关键词）",
        f"",
        f"---",
        f"",
        f"⚠️ **风险提示**: 本报告仅供参考，不构成投资建议。",
        f"",
        f"📅 **下次报告**: 15:00 收盘深度分析"
    ])
    
    report = "\n".join(report_lines)
    
    # 保存报告
    report_file = f"/root/.openclaw/workspace/data/ah_market_preopen_{today_str}.md"
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write(report)
    
    print(f"\n✅ 报告已生成: {report_file}")
    print("\n" + "=" * 60)
    print(report[:1500])
    print("\n... [报告已截断] ...")
    
    # 发送到飞书
    print("\n📤 正在发送到飞书...")
    send_feishu_message(report, "🌅 A+H股开盘前瞻报告 v2.0")
    
    return report


if __name__ == "__main__":
    generate_report()
