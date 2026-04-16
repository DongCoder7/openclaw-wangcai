#!/root/.openclaw/workspace/venv/bin/python3
# search_shiyun_guba.py - 使用东财股吧搜索世运电路相关讨论

import sys
sys.path.insert(0, '/root/.openclaw/workspace/venv/lib/python3.12/site-packages')

import json
import efinance as ef

# 世运电路股票代码
stock_code = "603920"

print("="*60)
print(f"获取世运电路({stock_code})股吧热门帖子")
print("="*60)

# 获取股吧热门帖子
try:
    guba_df = ef.stock.get_guba_hot_posts(stock_code)
    if guba_df is not None and len(guba_df) > 0:
        print(f"\n找到 {len(guba_df)} 条热门帖子:\n")
        
        # 搜索包含特斯拉/AI/Dojo相关关键词的帖子
        tesla_keywords = ['特斯拉', 'Tesla', 'Dojo', 'AI', '芯片', '机器人', 'Optimus', 'FSD', 'AI5', '流片', 'PCB']
        
        filtered_posts = []
        for idx, row in guba_df.iterrows():
            title = str(row.get('标题', row.get('post_title', '')))
            content = str(row.get('内容', row.get('post_content', '')))
            full_text = title + ' ' + content
            
            for keyword in tesla_keywords:
                if keyword in full_text:
                    filtered_posts.append({
                        '关键词': keyword,
                        '标题': title,
                        '内容': content[:300] + '...' if len(content) > 300 else content,
                        '作者': row.get('作者', row.get('author', '未知')),
                        '阅读': row.get('阅读', row.get('read_count', 0)),
                        '评论': row.get('评论', row.get('comment_count', 0))
                    })
                    break
        
        # 打印所有帖子前几条
        for idx, row in guba_df.head(5).iterrows():
            title = str(row.get('标题', row.get('post_title', '无标题')))
            print(f"\n标题: {title}")
            print("-" * 60)
        
        # 打印过滤后的相关帖子
        if filtered_posts:
            print("\n" + "="*60)
            print(f"找到 {len(filtered_posts)} 条与特斯拉/AI/Dojo相关的帖子")
            print("="*60)
            for post in filtered_posts[:10]:
                print(f"\n关键词: {post['关键词']}")
                print(f"标题: {post['标题']}")
                print(f"内容: {post['内容'][:200]}...")
                print(f"作者: {post['作者']} | 阅读: {post['阅读']} | 评论: {post['评论']}")
                print("-" * 60)
        else:
            print("\n未找到与特斯拉/AI/Dojo相关的帖子")
        
        # 保存完整数据
        guba_df.to_json("/root/.openclaw/workspace/data/shiyun_guba.json", 
                       orient='records', force_ascii=False, indent=2)
        print("\n股吧数据已保存到: data/shiyun_guba.json")
    else:
        print("未获取到股吧数据")
except Exception as e:
    print(f"获取股吧数据出错: {e}")
    import traceback
    traceback.print_exc()

# 获取个股概况
print("\n" + "="*60)
print(f"获取世运电路({stock_code})概况")
print("="*60)

try:
    profile = ef.stock.get_stock_profile(stock_code)
    if profile is not None:
        print(profile.to_string())
except Exception as e:
    print(f"获取概况出错: {e}")

# 获取最新研报
print("\n" + "="*60)
print(f"获取世运电路({stock_code})最新研报")
print("="*60)

try:
    reports = ef.stock.get_stock_reports(stock_code)
    if reports is not None and len(reports) > 0:
        print(f"\n找到 {len(reports)} 条研报:")
        for idx, row in reports.head(5).iterrows():
            title = str(row.get('标题', '无标题'))
            print(f"\n- {title}")
        
        # 搜索包含特斯拉相关的研报
        tesla_reports = []
        for idx, row in reports.iterrows():
            title = str(row.get('标题', ''))
            summary = str(row.get('摘要', ''))
            full_text = title + ' ' + summary
            
            for keyword in ['特斯拉', 'Tesla', 'Dojo', 'AI', '汽车电子']:
                if keyword in full_text:
                    tesla_reports.append({
                        '标题': title,
                        '摘要': summary[:200] if len(summary) > 200 else summary,
                        '机构': row.get('机构', '未知'),
                        '日期': row.get('日期', '')
                    })
                    break
        
        if tesla_reports:
            print(f"\n找到 {len(tesla_reports)} 条与特斯拉相关的研报:")
            for r in tesla_reports[:5]:
                print(f"\n- [{r['机构']}] {r['标题']}")
                print(f"  {r['摘要'][:150]}...")
        
        reports.to_json("/root/.openclaw/workspace/data/shiyun_reports.json", 
                       orient='records', force_ascii=False, indent=2)
        print("\n研报已保存到: data/shiyun_reports.json")
except Exception as e:
    print(f"获取研报出错: {e}")
    import traceback
    traceback.print_exc()
