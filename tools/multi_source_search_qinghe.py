#!/root/.openclaw/workspace/venv/bin/python3
"""
多源搜索工具 - 青禾晶元 + 键合技术
使用多种方式搜索：
1. 百度搜索
2. 企查查/天眼查API
3. 行业数据库
"""

import requests
import json
import re
from urllib.parse import quote, urlencode
from bs4 import BeautifulSoup

def search_baidu(keyword):
    """百度搜索 - 使用移动端接口"""
    try:
        url = f"https://m.baidu.com/s?word={quote(keyword)}"
        headers = {
            'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X) AppleWebKit/605.1.15',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9'
        }
        response = requests.get(url, headers=headers, timeout=15, allow_redirects=True)
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            # 提取搜索结果
            results = []
            for div in soup.find_all(['div', 'section'], class_=re.compile('result|c-container')):
                title_tag = div.find(['h3', 'a'])
                if title_tag:
                    title = title_tag.get_text(strip=True)
                    if len(title) > 5:  # 过滤无效内容
                        results.append(title)
            return {
                'keyword': keyword,
                'status': 'success',
                'results': results[:10],
                'url': url
            }
        return {'keyword': keyword, 'status': 'error', 'code': response.status_code}
    except Exception as e:
        return {'keyword': keyword, 'status': 'error', 'message': str(e)}

def search_tianyancha(company_name):
    """天眼查搜索 - 通过网页抓取"""
    try:
        url = f"https://www.tianyancha.com/search?key={quote(company_name)}"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        response = requests.get(url, headers=headers, timeout=15)
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            companies = []
            for item in soup.find_all('a', class_=re.compile('name|title')):
                name = item.get_text(strip=True)
                if name and len(name) > 2:
                    companies.append(name)
            return {
                'keyword': company_name,
                'status': 'success',
                'companies': companies[:5]
            }
        return {'keyword': company_name, 'status': 'error', 'code': response.status_code}
    except Exception as e:
        return {'keyword': company_name, 'status': 'error', 'message': str(e)}

def search_sogou(keyword):
    """搜狗搜索 - 微信文章搜索"""
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
                    articles.append(title)
            return {
                'keyword': keyword,
                'status': 'success',
                'articles': articles[:5],
                'source': 'wechat_sogou'
            }
        return {'keyword': keyword, 'status': 'error', 'code': response.status_code}
    except Exception as e:
        return {'keyword': keyword, 'status': 'error', 'message': str(e)}

if __name__ == '__main__':
    print("="*70)
    print("多源搜索: 青禾晶元 + 键合技术产业链")
    print("="*70)
    
    # 搜索1: 青禾晶元
    print("\n【搜索1】青禾晶元 公司")
    result1 = search_baidu("青禾晶元 公司")
    print(json.dumps(result1, indent=2, ensure_ascii=False))
    
    # 搜索2: 青禾晶元 半导体
    print("\n【搜索2】青禾晶元 半导体")
    result2 = search_baidu("青禾晶元 半导体 封装")
    print(json.dumps(result2, indent=2, ensure_ascii=False))
    
    # 搜索3: 键合技术产业链
    print("\n【搜索3】键合技术 Wire Bonding 产业链")
    result3 = search_baidu("键合技术 Wire Bonding 产业链 A股")
    print(json.dumps(result3, indent=2, ensure_ascii=False))
    
    # 搜索4: 微信文章
    print("\n【搜索4】微信公众号文章")
    result4 = search_sogou("青禾晶元 半导体封装")
    print(json.dumps(result4, indent=2, ensure_ascii=False))
    
    # 搜索5: 天眼查
    print("\n【搜索5】天眼查企业信息")
    result5 = search_tianyancha("青禾晶元")
    print(json.dumps(result5, indent=2, ensure_ascii=False))
