#!/root/.openclaw/workspace/venv/bin/python3
"""
知识星球多Group分组抓取器 v3.1
- 支持多个Group配置
- 相同token的Group合并到同一文件
- 不同token的Group单独输出
"""

import json
import os
import sys
import re
from pathlib import Path
from datetime import datetime

# 配置路径
BASE_DIR = Path("/root/.openclaw/workspace")
CONFIG_FILE = BASE_DIR / "data/zsxq/groups.json"
BASE_DATA_DIR = BASE_DIR / "data/zsxq"

def load_groups():
    """加载Group配置"""
    if not CONFIG_FILE.exists():
        print(f"❌ 配置文件不存在: {CONFIG_FILE}")
        return []
    
    with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    return [g for g in config.get('groups', []) if g.get('enabled', False)]

def group_by_cookie(groups):
    """按cookie分组"""
    # 提取zsxq_access_token作为标识
    cookie_groups = {}
    
    for g in groups:
        cookie = g['cookie']
        # 提取token部分
        if 'zsxq_access_token=' in cookie:
            token = cookie.split('zsxq_access_token=')[-1].split(';')[0][:20]
        else:
            token = cookie[:20]  # 取前20字符作为标识
        
        if token not in cookie_groups:
            cookie_groups[token] = []
        cookie_groups[token].append(g)
    
    return cookie_groups

def generate_summary(all_topics_by_group, target_date, group_names):
    """生成汇总报告"""
    
    # 合并所有文本
    all_topics = []
    for group_name, topics in all_topics_by_group.items():
        all_topics.extend(topics)
    
    if not all_topics:
        return f"📭 {target_date} 无数据"
    
    full_text = '\n'.join([f"{t.get('title', '')} {t.get('content', '')}" for t in all_topics if t])
    
    # Group统计
    group_stats = {}
    for group_name, topics in all_topics_by_group.items():
        group_text = '\n'.join([f"{t.get('title', '')} {t.get('content', '')}" for t in topics])
        group_stats[group_name] = {'count': len(topics), 'chars': len(group_text)}
    
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
    
    # 情绪统计
    bullish = ['买入', '增持', '看好', '推荐', '上涨', '机会', '利好']
    bearish = ['卖出', '减持', '看空', '回避', '下跌', '风险', '利空']
    
    bullish_count = sum(len(re.findall(w, full_text)) for w in bullish)
    bearish_count = sum(len(re.findall(w, full_text)) for w in bearish)
    total_sentiment = bullish_count + bearish_count
    
    # 生成报告
    lines = []
    lines.append("=" * 70)
    lines.append(f"📊 知识星球日终汇总报告")
    lines.append(f"📅 {target_date} | Groups: {', '.join(group_names)}")
    lines.append("=" * 70)
    
    lines.append(f"\n【一、Group数据统计】")
    total_count = sum(s['count'] for s in group_stats.values())
    for name, stats in group_stats.items():
        lines.append(f"  • {name}: {stats['count']} 条")
    lines.append(f"  • 总计: {total_count} 条")
    
    if industry_stats:
        lines.append(f"\n【二、热点行业分布】")
        for i, (industry, count) in enumerate(sorted(industry_stats.items(), key=lambda x: -x[1])[:5], 1):
            lines.append(f"  {i}. {industry}: {count}次")
    
    if total_sentiment > 0:
        lines.append(f"\n【三、市场情绪】")
        sentiment = (bullish_count - bearish_count) / total_sentiment * 100
        emoji = "📈" if sentiment > 20 else "📉" if sentiment < -20 else "➡️"
        lines.append(f"  • 🟢 看多: {bullish_count} | 🔴 看空: {bearish_count}")
        lines.append(f"  • {emoji} 情绪指数: {sentiment:+.1f}")
    
    lines.append(f"\n【四、生成时间】{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("=" * 70)
    
    return "\n".join(lines)

def fetch_single_group(group):
    """抓取单个Group"""
    group_id = group['group_id']
    group_name = group['name']
    cookie = group['cookie']
    
    print(f"\n📦 抓取: {group_name} ({group_id})")
    
    os.environ['ZSXQ_GROUP_ID'] = group_id
    os.environ['ZSXQ_COOKIE'] = cookie
    
    try:
        sys.path.insert(0, str(BASE_DIR / "tools"))
        from zsxq_fetcher_prod import ZsxqFetcher
        
        fetcher = ZsxqFetcher(cookie, group_id)
        topics, _ = fetcher.get_topics(count=50)
        
        print(f"  ✅ {len(topics)} 条")
        return topics
    except Exception as e:
        print(f"  ❌ 失败: {e}")
        return []

def main():
    print("=" * 70)
    print(f"🚀 知识星球分组抓取器 v3.1")
    print(f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)
    
    groups = load_groups()
    if not groups:
        print("❌ 没有启用的Group")
        return
    
    # 按cookie分组
    cookie_groups = group_by_cookie(groups)
    target_date = datetime.now().strftime("%Y-%m-%d")
    
    print(f"📋 发现 {len(cookie_groups)} 个不同的token组")
    
    # 为每个token组创建独立的抓取任务
    for token_id, group_list in cookie_groups.items():
        group_names = [g['name'] for g in group_list]
        group_ids = [g['group_id'] for g in group_list]
        
        print(f"\n{'='*70}")
        print(f"🔑 Token组: {', '.join(group_names)}")
        print(f"{'='*70}")
        
        # 抓取这个token组的所有group
        all_topics_by_group = {}
        merged_data = []
        
        for i, group in enumerate(group_list):
            topics = fetch_single_group(group)
            all_topics_by_group[group['name']] = topics
            merged_data.append({
                'group_id': group['group_id'],
                'group_name': group['name'],
                'topics': topics,
                'fetch_time': datetime.now().isoformat()
            })
            
            if i < len(group_list) - 1:
                print(f"  ⏳ 等待8秒...")
                import time
                time.sleep(8)
        
        # 确定输出文件名
        if len(group_list) == 1:
            # 单个group
            output_suffix = group_list[0]['group_id']
        else:
            # 多个group合并
            output_suffix = "merged"
        
        # 保存数据
        raw_dir = BASE_DATA_DIR / "raw"
        raw_dir.mkdir(parents=True, exist_ok=True)
        
        output_file = raw_dir / f"{target_date}_{output_suffix}.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(merged_data, f, ensure_ascii=False, indent=2)
        
        print(f"\n✅ 数据保存: {output_file}")
        
        # 生成报告
        summary = generate_summary(all_topics_by_group, target_date, group_names)
        summary_file = BASE_DATA_DIR / f"summary_{target_date}_{output_suffix}.md"
        with open(summary_file, 'w', encoding='utf-8') as f:
            f.write(summary)
        
        print(f"✅ 报告保存: {summary_file}")
        print("\n" + summary)
    
    print(f"\n{'='*70}")
    print("✅ 所有Group抓取完成")
    print("=" * 70)

if __name__ == "__main__":
    main()
