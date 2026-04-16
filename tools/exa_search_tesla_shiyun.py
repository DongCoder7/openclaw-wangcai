#!/root/.openclaw/workspace/venv/bin/python3
"""
Exa MCP搜索工具 - 搜索特斯拉AI5流片和世运电路的联系
使用Exa API进行语义搜索
"""

import os
import sys
import json
import urllib.request
import urllib.parse
import ssl

# 忽略SSL验证
ssl._create_default_https_context = ssl._create_unverified_context

# Exa API配置
EXA_API_URL = "https://api.exa.ai/search"
EXA_API_KEY = os.environ.get("EXA_API_KEY", "")

def exa_search(query, num_results=10, use_autoprompt=True, highlights=True):
    """
    使用Exa API进行语义搜索
    """
    if not EXA_API_KEY:
        print("错误: 未设置EXA_API_KEY环境变量")
        return None
    
    headers = {
        "Content-Type": "application/json",
        "x-api-key": EXA_API_KEY
    }
    
    data = {
        "query": query,
        "numResults": num_results,
        "useAutoprompt": use_autoprompt,
        "type": "auto",
        "contents": {
            "text": {
                "maxCharacters": 1000,
                "includeHtmlTags": False
            }
        } if highlights else None
    }
    
    data = {k: v for k, v in data.items() if v is not None}
    
    try:
        req = urllib.request.Request(
            EXA_API_URL,
            data=json.dumps(data).encode('utf-8'),
            headers=headers,
            method='POST'
        )
        
        with urllib.request.urlopen(req, timeout=30) as response:
            result = json.loads(response.read().decode('utf-8'))
            return result
    except Exception as e:
        print(f"搜索出错: {e}")
        return None

def print_results(results, query_name):
    """格式化打印搜索结果"""
    print(f"\n{'='*60}")
    print(f"搜索: {query_name}")
    print('='*60)
    
    if not results or 'results' not in results:
        print("未获取到结果")
        return []
    
    extracted_results = []
    for i, result in enumerate(results['results'], 1):
        title = result.get('title', '无标题')
        url = result.get('url', '')
        score = result.get('score', 0)
        
        text = ""
        if 'text' in result:
            text = result['text'][:500] + "..." if len(result['text']) > 500 else result['text']
        
        print(f"\n[{i}] {title}")
        print(f"    URL: {url}")
        print(f"    相关度: {score:.4f}")
        if text:
            print(f"    内容: {text[:300]}...")
        
        extracted_results.append({
            'title': title,
            'url': url,
            'score': score,
            'text': text
        })
    
    return extracted_results

def main():
    queries = [
        ("世运电路 特斯拉 AI5 流片 Dojo", "世运电路与特斯拉AI5/Dojo关系"),
        ("世运电路 603920 特斯拉 PCB供应商", "世运电路作为特斯拉PCB供应商"),
        ("Tesla AI5 tape out Dojo supercomputer", "特斯拉AI5流片与Dojo"),
        ("世运电路 汽车电子 AI芯片 机器人", "世运电路AI芯片与机器人业务"),
    ]
    
    all_results = {}
    
    for query, name in queries:
        print(f"\n正在搜索: {name}...")
        results = exa_search(query, num_results=5)
        if results:
            all_results[name] = print_results(results, name)
        else:
            all_results[name] = []
    
    # 保存结果
    output_file = "/root/.openclaw/workspace/data/exa_search_tesla_shiyun.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)
    
    print(f"\n\n搜索结果已保存到: {output_file}")
    return all_results

if __name__ == "__main__":
    results = main()
