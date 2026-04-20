#!/root/.openclaw/workspace/venv/bin/python3
"""
搜索元晶青禾公司和键合技术信息
"""

import requests
import json
import sys
from urllib.parse import quote

def search_baidu(keyword):
    """百度搜索"""
    try:
        url = f"https://www.baidu.com/s?wd={quote(keyword)}"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        response = requests.get(url, headers=headers, timeout=10)
        return response.text[:5000]
    except Exception as e:
        return f"Error: {e}"

def search_bing(keyword):
    """必应搜索"""
    try:
        url = f"https://cn.bing.com/search?q={quote(keyword)}"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        response = requests.get(url, headers=headers, timeout=10)
        return response.text[:5000]
    except Exception as e:
        return f"Error: {e}"

if __name__ == '__main__':
    # 搜索元晶青禾
    print("="*60)
    print("搜索: 元晶青禾")
    print("="*60)
    result1 = search_bing("元晶青禾 公司")
    print(result1[:3000])
    
    print("\n" + "="*60)
    print("搜索: 元晶青禾 键合")
    print("="*60)
    result2 = search_bing("元晶青禾 键合技术")
    print(result2[:3000])
    
    print("\n" + "="*60)
    print("搜索: 键合技术 产业链")
    print("="*60)
    result3 = search_bing("键合技术 Wire Bonding 产业链")
    print(result3[:3000])
