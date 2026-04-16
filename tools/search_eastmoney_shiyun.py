#!/root/.openclaw/workspace/venv/bin/python3
# search_eastmoney_shiyun.py - 使用东财搜索世运电路相关新闻

import json
import urllib.request
import urllib.parse

def search_eastmoney(keyword):
    """使用东财搜索接口"""
    try:
        # 东财搜索API
        url = f"https://searchapi.eastmoney.com/api/suggest/get?input={urllib.parse.quote(keyword)}&type=14&count=20"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Referer': 'https://so.eastmoney.com/'
        }
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=10) as response:
            return json.loads(response.read().decode('utf-8'))
    except Exception as e:
        return {"error": str(e)}

def get_stock_news(stock_code):
    """获取个股新闻"""
    try:
        url = f"https://search-api-web.eastmoney.com/search/json?keyword={stock_code}&pageIndex=1&pageSize=20&type=204&cb=jQuery"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Referer': 'https://emweb.securities.eastmoney.com/'
        }
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=10) as response:
            data = response.read().decode('utf-8')
            # 移除jQuery回调包装
            start = data.find('(')
            end = data.rfind(')')
            if start > 0 and end > 0:
                return json.loads(data[start+1:end])
            return json.loads(data)
    except Exception as e:
        return {"error": str(e)}

def get_stock_info(stock_code):
    """获取股票基本信息"""
    try:
        url = f"https://push2.eastmoney.com/api/qt/stock/get?secid=1.{stock_code}&fields=f43,f44,f45,f46,f47,f48,f57,f58,f60,f107,f116,f117,f162,f163,f170"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=10) as response:
            return json.loads(response.read().decode('utf-8'))
    except Exception as e:
        return {"error": str(e)}

# 搜索关键词
print("="*60)
print("搜索: 世运电路 603920")
print("="*60)

# 获取股票基本信息
info = get_stock_info("603920")
print(f"\n股票基本信息: {json.dumps(info, ensure_ascii=False, indent=2)[:2000]}")

# 获取股票新闻
news = get_stock_news("603920")
print(f"\n\n股票相关新闻: {json.dumps(news, ensure_ascii=False, indent=2)[:3000]}")

# 搜索特斯拉相关
print("\n" + "="*60)
print("搜索: 世运电路 特斯拉")
print("="*60)
tesla_search = search_eastmoney("世运电路 特斯拉")
print(json.dumps(tesla_search, ensure_ascii=False, indent=2)[:2000])

# 保存结果
output_file = "/root/.openclaw/workspace/data/shiyun_eastmoney.json"
result = {
    "stock_info": info,
    "news": news,
    "tesla_search": tesla_search
}
with open(output_file, 'w', encoding='utf-8') as f:
    json.dump(result, f, ensure_ascii=False, indent=2)

print(f"\n结果已保存到: {output_file}")
