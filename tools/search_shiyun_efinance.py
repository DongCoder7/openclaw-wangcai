#!/root/.openclaw/workspace/venv/bin/python3
# search_shiyun_efinance.py - 使用efinance搜索世运电路相关新闻

import sys
sys.path.insert(0, '/root/.openclaw/workspace/venv/lib/python3.12/site-packages')

import json
import efinance as ef

# 世运电路股票代码
stock_code = "603920"

print("="*60)
print(f"获取世运电路({stock_code})最新资讯")
print("="*60)

# 获取个股新闻
try:
    news_df = ef.stock.get_latest_company_news(stock_code)
    if news_df is not None and len(news_df) > 0:
        print(f"\n找到 {len(news_df)} 条新闻:")
        print(news_df.head(10).to_string())
        
        # 保存完整数据
        news_df.to_json("/root/.openclaw/workspace/data/shiyun_news.json", 
                       orient='records', force_ascii=False, indent=2)
        print("\n新闻已保存到: data/shiyun_news.json")
    else:
        print("未获取到新闻数据")
except Exception as e:
    print(f"获取新闻出错: {e}")

# 获取公司公告
print("\n" + "="*60)
print(f"获取世运电路({stock_code})公司公告")
print("="*60)

try:
    # 尝试获取公告
    notice_df = ef.stock.get_company_announcement(stock_code)
    if notice_df is not None and len(notice_df) > 0:
        print(f"\n找到 {len(notice_df)} 条公告:")
        print(notice_df.head(10).to_string())
        
        # 保存完整数据
        notice_df.to_json("/root/.openclaw/workspace/data/shiyun_notices.json", 
                         orient='records', force_ascii=False, indent=2)
        print("\n公告已保存到: data/shiyun_notices.json")
    else:
        print("未获取到公告数据")
except Exception as e:
    print(f"获取公告出错: {e}")

# 获取股票基本信息
print("\n" + "="*60)
print(f"获取世运电路({stock_code})基本信息")
print("="*60)

try:
    basic_info = ef.stock.get_base_info(stock_code)
    if basic_info is not None:
        print(basic_info)
        
        # 保存
        with open("/root/.openclaw/workspace/data/shiyun_basic.json", 'w', encoding='utf-8') as f:
            json.dump(basic_info, f, ensure_ascii=False, indent=2)
        print("\n基本信息已保存到: data/shiyun_basic.json")
except Exception as e:
    print(f"获取基本信息出错: {e}")

# 搜索包含特斯拉相关的新闻
print("\n" + "="*60)
print("搜索与'特斯拉'相关的新闻")
print("="*60)

try:
    if 'news_df' in dir() and news_df is not None:
        # 筛选包含特斯拉关键词的新闻
        tesla_keywords = ['特斯拉', 'Tesla', 'Dojo', 'AI', '芯片', '机器人', 'Optimus', 'FSD']
        
        filtered_news = []
        for _, row in news_df.iterrows():
            title = str(row.get('标题', ''))
            content = str(row.get('内容', ''))
            full_text = title + content
            
            for keyword in tesla_keywords:
                if keyword.lower() in full_text.lower():
                    filtered_news.append({
                        '标题': title,
                        '内容': content[:200] + '...' if len(content) > 200 else content,
                        '关键词': keyword
                    })
                    break
        
        if filtered_news:
            print(f"\n找到 {len(filtered_news)} 条相关新闻:")
            for item in filtered_news:
                print(f"\n- 关键词: {item['关键词']}")
                print(f"  标题: {item['标题']}")
                print(f"  内容: {item['内容'][:100]}...")
        else:
            print("未找到与特斯拉相关的新闻")
except Exception as e:
    print(f"筛选新闻出错: {e}")
