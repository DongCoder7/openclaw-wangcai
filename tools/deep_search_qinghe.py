#!/root/.openclaw/workspace/venv/bin/python3
"""
深度搜索青禾晶元公司信息
基于已发现的关键线索继续深挖
"""

import requests
import json
import re
from urllib.parse import quote
from bs4 import BeautifulSoup

def search_baidu(keyword):
    """百度搜索"""
    try:
        url = f"https://m.baidu.com/s?word={quote(keyword)}"
        headers = {
            'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X) AppleWebKit/605.1.15',
        }
        response = requests.get(url, headers=headers, timeout=15)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            results = []
            for div in soup.find_all(['div', 'section']):
                text = div.get_text(strip=True)
                if len(text) > 10 and len(text) < 200:
                    results.append(text)
            return {'keyword': keyword, 'status': 'success', 'results': list(set(results))[:15]}
        return {'keyword': keyword, 'status': 'error'}
    except Exception as e:
        return {'keyword': keyword, 'status': 'error', 'message': str(e)}

def search_sogou(keyword):
    """搜狗微信搜索"""
    try:
        url = f"https://weixin.sogou.com/weixin?type=2&query={quote(keyword)}"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        response = requests.get(url, headers=headers, timeout=15)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            articles = []
            for item in soup.find_all('li', id=re.compile('sogou')):
                title_tag = item.find('h3')
                if title_tag:
                    title = title_tag.get_text(strip=True)
                    if len(title) > 5:
                        articles.append(title)
            return {'keyword': keyword, 'status': 'success', 'articles': articles[:10]}
        return {'keyword': keyword, 'status': 'error'}
    except Exception as e:
        return {'keyword': keyword, 'status': 'error', 'message': str(e)}

if __name__ == '__main__':
    print("="*70)
    print("深度搜索：青禾晶元(天津)半导体材料有限公司")
    print("="*70)
    
    # 搜索1: 公司详细信息
    print("\n【搜索1】青禾晶元 天津 半导体材料 键合")
    r1 = search_sogou("青禾晶元 天津 半导体材料")
    print(json.dumps(r1, indent=2, ensure_ascii=False))
    
    # 搜索2: 融资信息
    print("\n【搜索2】青禾晶元 融资 中微公司 领投")
    r2 = search_sogou("青禾晶元 融资 中微公司")
    print(json.dumps(r2, indent=2, ensure_ascii=False))
    
    # 搜索3: 键合技术细节
    print("\n【搜索3】青禾晶元 键合技术 先进封装")
    r3 = search_sogou("青禾晶元 键合技术 先进封装")
    print(json.dumps(r3, indent=2, ensure_ascii=False))
    
    # 搜索4: 化合物半导体
    print("\n【搜索4】青禾晶元 化合物半导体 氮化镓 GaN")
    r4 = search_sogou("青禾晶元 化合物半导体 GaN")
    print(json.dumps(r4, indent=2, ensure_ascii=False))
    
    # 搜索5: 键合技术产业链完整版
    print("\n【搜索5】键合技术产业链 A股上市公司")
    r5 = search_sogou("键合技术 半导体封装 A股 奥特维 新益昌")
    print(json.dumps(r5, indent=2, ensure_ascii=False))
