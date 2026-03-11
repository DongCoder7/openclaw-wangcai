#!/root/.openclaw/workspace/venv/bin/python3
"""
知识星球多Group抓取调度器 v2.0
- 支持多个Group配置
- 每个Group独立目录保存
- 每个Group独立汇总报告
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

def generate_summary_report(topics, target_date, group_name):
    """生成结构化汇总报告"""
    if not topics:
        return f"📭 {target_date} 无数据"
    
    # 合并所有文本
    all_text = []
    for t in topics:
        text = f"{t.get('title', '')} {t.get('content', '')}"
        if text.strip():
            all_text.append(text)
    
    full_text = '\n'.join(all_text)
    
    # 行业关键词统计
    industry_keywords = {
        '人工智能/AI': ['人工智能', 'AI', '算力', '大模型', 'AIGC', 'ChatGPT'],
        '半导体/芯片': ['半导体', '芯片', '集成电路', '晶圆', '光刻'],
        '新能源': ['新能源', '光伏', '储能', '锂电池', '电动车', '风电'],
        '军工': ['军工', '国防', '航空航天', '导弹', '军舰', '低空经济'],
        '医药': ['医药', '医疗', '创新药', 'CXO', '医疗器械', '生物'],
        '金融': ['金融', '银行', '保险', '证券', '券商', '基金'],
        '消费': ['消费', '白酒', '食品饮料', '家电', '零售'],
        '通信': ['通信', '5G', '光模块', '光通讯', '基站', '运营商'],
        '计算机': ['计算机', '软件', 'IT', '云计算', '大数据'],
        '机器人': ['机器人', '人形机器人', '具身智能', '自动化'],
    }
    
    industry_stats = {}
    for industry, keywords in industry_keywords.items():
        count = 0
        for kw in keywords:
            count += len(re.findall(kw, full_text, re.IGNORECASE))
        if count > 0:
            industry_stats[industry] = count
    
    # 情绪统计
    bullish_words = ['买入', '增持', '看好', '推荐', '上行', '反弹', '上涨', '机会', '利好', '强势', '突破', '加仓']
    bearish_words = ['卖出', '减持', '看空', '回避', '下行', '调整', '下跌', '风险', '利空', '弱势', '回调', '减仓']
    
    bullish_count = sum(len(re.findall(w, full_text)) for w in bullish_words)
    bearish_count = sum(len(re.findall(w, full_text)) for w in bearish_words)
    total_sentiment = bullish_count + bearish_count
    
    # 政策/事件关键词
    policy_keywords = ['政府工作报告', '两会', '政策', '补贴', '规划', '十四五', '十五五']
    policy_count = sum(len(re.findall(kw, full_text)) for kw in policy_keywords)
    
    # 生成报告
    lines = []
    lines.append("=" * 60)
    lines.append(f"📊 知识星球日终汇总报告 - {group_name}")
    lines.append(f"📅 {target_date}")
    lines.append("=" * 60)
    
    lines.append(f"\n【一、数据概览】")
    lines.append(f"  • 抓取帖子数: {len(topics)} 条")
    lines.append(f"  • 总字数: {len(full_text):,} 字")
    lines.append(f"  • 平均单帖长度: {len(full_text)//max(len(topics),1):,} 字")
    
    lines.append(f"\n【二、热点行业分布】")
    sorted_industries = sorted(industry_stats.items(), key=lambda x: -x[1])
    for i, (industry, count) in enumerate(sorted_industries[:8], 1):
        bar = "█" * min(count // 3, 25)
        lines.append(f"  {i}. {industry:12s}: {count:3d}次 {bar}")
    
    if total_sentiment > 0:
        lines.append(f"\n【三、市场情绪统计】")
        bullish_pct = bullish_count * 100 // total_sentiment
        bearish_pct = bearish_count * 100 // total_sentiment
        lines.append(f"  • 🟢 看多情绪: {bullish_count}次 ({bullish_pct}%)")
        lines.append(f"  • 🔴 看空情绪: {bearish_count}次 ({bearish_pct}%)")
        sentiment_score = (bullish_count - bearish_count) / total_sentiment * 100
        sentiment_emoji = "📈" if sentiment_score > 20 else "📉" if sentiment_score < -20 else "➡️"
        lines.append(f"  • {sentiment_emoji} 情绪指数: {sentiment_score:+.1f} (正值看多)")
    
    lines.append(f"\n【四、政策/事件关注度】")
    lines.append(f"  • 政策相关提及: {policy_count}次")
    if policy_count > 10:
        lines.append(f"  • 🔥 今日政策热点密集")
    
    lines.append(f"\n【五、核心观点归纳】")
    top_industries = [k for k, v in sorted_industries[:3]]
    if '人工智能/AI' in top_industries:
        lines.append(f"  1️⃣ AI产业: 算力、大模型、应用持续高关注度")
    if '军工' in top_industries:
        lines.append(f"  2️⃣ 军工板块: 国防预算、航空航天、低空经济受关注")
    if '新能源' in top_industries:
        lines.append(f"  3️⃣ 新能源: 储能、光伏、电动车产业链")
    if policy_count > 10:
        lines.append(f"  4️⃣ 政策面: 政府工作报告/两会政策解读密集")
    
    if total_sentiment > 0:
        if sentiment_score > 20:
            lines.append(f"  5️⃣ 市场情绪: 整体偏多，积极信号较多")
        elif sentiment_score < -20:
            lines.append(f"  5️⃣ 市场情绪: 整体偏空，谨慎情绪较浓")
        else:
            lines.append(f"  5️⃣ 市场情绪: 中性震荡，结构性机会为主")
    else:
        lines.append(f"  5️⃣ 市场情绪: 数据不足以判断")
    
    lines.append(f"\n【六、明日关注方向】")
    for i, industry in enumerate(top_industries[:3], 1):
        lines.append(f"  {i}. {industry}")
    
    lines.append(f"\n【七、数据质量】")
    lines.append(f"  • 抓取状态: {'✅ 完整' if len(topics) > 200 else '⚠️ 部分(可能限流)' if len(topics) > 50 else '⚠️ 数据较少'}")
    lines.append(f"  • Group名称: {group_name}")
    lines.append(f"  • 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    lines.append("=" * 60)
    
    return "\n".join(lines)

def fetch_single_group(group, target_date):
    """抓取单个Group"""
    group_id = group['group_id']
    group_name = group['name']
    cookie = group['cookie']
    
    # 为每个Group创建独立目录
    group_dir = BASE_DATA_DIR / f"group_{group_id}"
    raw_dir = group_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"\n📁 数据目录: {group_dir}")
    
    # 临时修改环境变量让fetcher使用正确目录
    old_data_dir = os.environ.get('ZSXQ_DATA_DIR')
    os.environ['ZSXQ_DATA_DIR'] = str(group_dir)
    os.environ['ZSXQ_GROUP_ID'] = group_id
    os.environ['ZSXQ_COOKIE'] = cookie
    
    try:
        # 动态导入fetcher
        sys.path.insert(0, str(BASE_DIR / "tools"))
        from zsxq_fetcher_prod import ZsxqFetcher
        
        fetcher = ZsxqFetcher(cookie, group_id)
        
        # 抓取（限制页数避免太长）
        fetcher.fetch_with_pagination(max_pages=50)
        
        # 读取今日数据
        data_file = raw_dir / f"{target_date}.json"
        topics = []
        if data_file.exists():
            with open(data_file, 'r', encoding='utf-8') as f:
                topics = json.load(f)
        
        # 生成并保存汇总报告
        summary = generate_summary_report(topics, target_date, group_name)
        summary_file = group_dir / f"summary_{target_date}.md"
        with open(summary_file, 'w', encoding='utf-8') as f:
            f.write(summary)
        
        print(summary)
        print(f"\n✅ {group_name} 汇总报告: {summary_file}")
        
        return len(topics)
        
    except Exception as e:
        print(f"❌ {group_name} 抓取失败: {e}")
        import traceback
        traceback.print_exc()
        return 0
    finally:
        # 恢复环境变量
        if old_data_dir:
            os.environ['ZSXQ_DATA_DIR'] = old_data_dir
        else:
            os.environ.pop('ZSXQ_DATA_DIR', None)

def main():
    print("=" * 60)
    print(f"🚀 知识星球多Group抓取调度器 v2.0")
    print(f"⏰ 执行时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    groups = load_groups()
    
    if not groups:
        print("❌ 没有启用的Group")
        return
    
    target_date = datetime.now().strftime("%Y-%m-%d")
    
    print(f"📋 将抓取 {len(groups)} 个Group:")
    for g in groups:
        print(f"  - {g['name']} (ID: {g['group_id']})")
    print()
    
    results = []
    
    # 依次抓取每个group
    for i, group in enumerate(groups, 1):
        print(f"\n{'='*60}")
        print(f"📦 [{i}/{len(groups)}] 抓取 Group: {group['name']}")
        print(f"{'='*60}")
        
        count = fetch_single_group(group, target_date)
        results.append({
            'name': group['name'],
            'count': count
        })
    
    # 最终汇总
    print(f"\n{'='*60}")
    print("📊 抓取结果汇总")
    print("=" * 60)
    for r in results:
        print(f"  • {r['name']}: {r['count']} 条")
    total = sum(r['count'] for r in results)
    print(f"  ─────────────────────")
    print(f"  • 总计: {total} 条")
    print("=" * 60)

if __name__ == "__main__":
    main()
