#!/root/.openclaw/workspace/venv/bin/python3
"""
企鹅的知识星球抓取器 v1.0
- 抓取新Group + 新Group2
- 合并输出到一个文件
- 生成统一汇总报告
"""

import json
import os
import sys
import re
from pathlib import Path
from datetime import datetime

# 配置
BASE_DIR = Path("/root/.openclaw/workspace")
BASE_DATA_DIR = BASE_DIR / "data/zsxq"

# 目标Group配置
TARGET_GROUPS = [
    {
        "group_id": "51111818455824",
        "group_name": "新Group"
    },
    {
        "group_id": "88512145458842",
        "group_name": "新Group2"
    }
]

def get_cookie():
    """获取cookie"""
    # 优先从环境变量获取
    cookie = os.environ.get('ZSXQ_COOKIE')
    if cookie:
        return cookie
    
    # 尝试从.zsxq.env读取
    env_file = BASE_DIR / '.zsxq.env'
    if env_file.exists():
        with open(env_file, 'r') as f:
            for line in f:
                if line.startswith('ZSXQ_COOKIE='):
                    return line.split('=', 1)[1].strip().strip('"')
    
    # 默认token
    return "sensorsdata2015jssdkcross=%7B%22distinct_id%22%3A%22421882554581888%22%2C%22first_id%22%3A%2219957298c826cb-08f4b144c21fe3-1f525631-1484784-19957298c83903%22%2C%22props%22%3A%7B%22%24latest_traffic_source_type%22%3A%22%E8%87%AA%E7%84%B6%E6%90%9C%E7%B4%A2%E6%B5%81%E9%87%8F%22%2C%22%24latest_search_keyword%22%3A%22%E6%9C%AA%E5%8F%96%E5%88%B0%E5%80%BC%22%2C%22%24latest_referrer%22%3A%22https%3A%2F%2Fwww.baidu.com%2Flink%22%7D%2C%22identities%22%3A%22eyIkaWRlbnRpdHlfY29va2llX2lkIjoiMTk5NTcyOThjODI2Y2ItMDhmNGIxNDRjMjFmZTMtMWY1MjU2MzEtMTQ4NDc4NC0xOTk1NzI5OGM4MzkwMyIsIiRpZGVudGl0eV9sb2dpbl9pZCI6IjQyMTg4MjU1NDU4MTg4OCJ9%22%2C%22history_login_id%22%3A%7B%22name%22%3A%22%24identity_login_id%22%2C%22value%22%3A%22421882554581888%22%7D%2C%22%24device_id%22%3A%2219957298c826cb-08f4b144c21fe3-1f525631-1484784-19957298c83903%22%7D; abtest_env=product; zsxq_access_token=AD5BC203-E94C-4B32-9BA2-6BFD0C435426_C1F959E538CA66E8"

def fetch_group(cookie, group_id, group_name):
    """抓取单个Group"""
    print(f"\n📦 抓取: {group_name} ({group_id})")
    
    sys.path.insert(0, str(BASE_DIR / "tools"))
    from zsxq_fetcher_prod import ZsxqFetcher
    
    try:
        fetcher = ZsxqFetcher(cookie, group_id)
        topics, _ = fetcher.get_topics(count=50)
        print(f"  ✅ 获取 {len(topics)} 条帖子")
        return topics
    except Exception as e:
        print(f"  ❌ 失败: {e}")
        return []

def generate_summary(all_topics_by_group, target_date):
    """生成合并汇总报告"""
    
    # 合并所有帖子
    all_topics = []
    for group_name, topics in all_topics_by_group.items():
        all_topics.extend(topics)
    
    if not all_topics:
        return f"📭 {target_date} 无数据"
    
    # 合并文本
    full_text = '\n'.join([
        f"{t.get('talk', {}).get('title', '')} {t.get('talk', {}).get('text', '')}"
        for t in all_topics
    ])
    
    # Group统计
    lines = []
    lines.append("=" * 70)
    lines.append(f"📊 企鹅的知识星球日终汇总报告")
    lines.append(f"📅 {target_date}")
    lines.append("=" * 70)
    
    lines.append(f"\n【一、Group数据统计】")
    total_count = 0
    for group_name, topics in all_topics_by_group.items():
        count = len(topics)
        total_count += count
        lines.append(f"  • {group_name}: {count} 条")
    lines.append(f"  ─────────────────────")
    lines.append(f"  • 总计: {total_count} 条")
    
    # 作者统计
    lines.append(f"\n【二、作者发帖统计】")
    author_stats = {}
    for t in all_topics:
        author = t.get('talk', {}).get('owner', {}).get('name', '未知')
        author_stats[author] = author_stats.get(author, 0) + 1
    
    sorted_authors = sorted(author_stats.items(), key=lambda x: x[1], reverse=True)
    for i, (author, count) in enumerate(sorted_authors[:10], 1):
        lines.append(f"  {i}. {author}: {count} 条")
    
    # 行业关键词
    industry_keywords = {
        '人工智能/AI': ['人工智能', 'AI', '算力', '大模型', 'AIGC'],
        '半导体/芯片': ['半导体', '芯片', '集成电路', '晶圆'],
        '新能源': ['新能源', '光伏', '储能', '锂电池', '电动车'],
        '军工': ['军工', '国防', '航空航天', '低空经济'],
        '医药': ['医药', '医疗', '创新药', 'CXO'],
        '通信': ['通信', '5G', '光模块', '光通讯'],
        '机器人': ['机器人', '人形机器人', '具身智能'],
    }
    
    industry_stats = {}
    for industry, keywords in industry_keywords.items():
        count = sum(len(re.findall(kw, full_text, re.I)) for kw in keywords)
        if count > 0:
            industry_stats[industry] = count
    
    if industry_stats:
        lines.append(f"\n【三、热点行业分布】")
        for i, (industry, count) in enumerate(sorted(industry_stats.items(), key=lambda x: x[1], reverse=True)[:5], 1):
            bar = "█" * min(count // 2, 20)
            lines.append(f"  {i}. {industry:12s}: {count:3d}次 {bar}")
    
    # 情绪分析
    bullish = ['买入', '增持', '看好', '推荐', '上涨', '机会', '利好', '强势']
    bearish = ['卖出', '减持', '看空', '回避', '下跌', '风险', '利空', '弱势']
    
    bullish_count = sum(len(re.findall(w, full_text)) for w in bullish)
    bearish_count = sum(len(re.findall(w, full_text)) for w in bearish)
    total_sentiment = bullish_count + bearish_count
    
    if total_sentiment > 0:
        lines.append(f"\n【四、市场情绪分析】")
        sentiment = (bullish_count - bearish_count) / total_sentiment * 100
        emoji = "📈" if sentiment > 20 else "📉" if sentiment < -20 else "➡️"
        lines.append(f"  • 🟢 看多: {bullish_count}次")
        lines.append(f"  • 🔴 看空: {bearish_count}次")
        lines.append(f"  • {emoji} 情绪指数: {sentiment:+.1f}")
    
    lines.append(f"\n【五、生成时间】")
    lines.append(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("=" * 70)
    
    return "\n".join(lines)

def main():
    print("=" * 70)
    print(f"🐧 企鹅的知识星球抓取器 v1.0")
    print(f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)
    
    # 获取cookie
    cookie = get_cookie()
    print(f"🔑 Token: {cookie[:40]}...")
    
    target_date = datetime.now().strftime("%Y-%m-%d")
    
    # 抓取两个Group
    all_topics_by_group = {}
    merged_data = []
    
    for i, group in enumerate(TARGET_GROUPS):
        topics = fetch_group(cookie, group['group_id'], group['group_name'])
        all_topics_by_group[group['group_name']] = topics
        
        merged_data.append({
            "group_id": group['group_id'],
            "group_name": group['group_name'],
            "topics": topics,
            "fetch_time": datetime.now().isoformat()
        })
        
        # 间隔避免限流
        if i < len(TARGET_GROUPS) - 1:
            print(f"  ⏳ 等待10秒避免限流...")
            import time
            time.sleep(10)
    
    # 保存合并数据
    raw_dir = BASE_DATA_DIR / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    
    output_file = raw_dir / f"{target_date}_penguin_merged.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(merged_data, f, ensure_ascii=False, indent=2)
    
    print(f"\n💾 合并数据保存: {output_file}")
    
    # 生成汇总报告
    summary = generate_summary(all_topics_by_group, target_date)
    summary_file = BASE_DATA_DIR / f"summary_{target_date}_penguin.md"
    with open(summary_file, 'w', encoding='utf-8') as f:
        f.write(summary)
    
    print(f"💾 汇总报告保存: {summary_file}")
    
    # 打印报告
    print("\n" + summary)
    
    # 最终统计
    total = sum(len(t) for t in all_topics_by_group.values())
    print(f"\n{'='*70}")
    print(f"✅ 抓取完成! 总计: {total} 条")
    print("=" * 70)

if __name__ == "__main__":
    main()
