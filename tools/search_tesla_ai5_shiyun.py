#!/root/.openclaw/workspace/venv/bin/python3
# search_tesla_ai5_shiyun.py - 搜索特斯拉AI5流片和世运电路的联系

import json
import urllib.request
import urllib.parse
import ssl

# 忽略SSL验证
ssl._create_default_https_context = ssl._create_unverified_context

def search_baidu(keyword):
    """使用百度新闻搜索"""
    try:
        url = f"https://www.baidu.com/s?wd={urllib.parse.quote(keyword)}&tn=news"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=10) as response:
            return response.read().decode('utf-8', errors='ignore')[:5000]
    except Exception as e:
        return f"Error: {e}"

# 搜索关键词
keywords = [
    "特斯拉AI5芯片 流片 世运电路",
    "世运电路 特斯拉 Dojo 供应商",
    "世运电路 汽车电子 PCB 特斯拉",
    "Tesla AI5 tape out 603920",
    "世运电路 投资者互动 AI芯片",
    "世运电路 603920 特斯拉 机器人"
]

results = {}
for kw in keywords:
    print(f"\n{'='*60}")
    print(f"搜索关键词: {kw}")
    print('='*60)
    content = search_baidu(kw)
    results[kw] = content[:3000]
    print(content[:2000])
    print("\n")

# 保存结果
output_file = "/root/.openclaw/workspace/data/tesla_ai5_shiyun_search.json"
with open(output_file, 'w', encoding='utf-8') as f:
    json.dump(results, f, ensure_ascii=False, indent=2)

print(f"\n搜索结果已保存到: {output_file}")
