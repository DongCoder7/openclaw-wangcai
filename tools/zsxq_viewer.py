#!/usr/bin/env python3
"""
知识星球数据查看工具
- 按天统计信息量
- 按频道筛选
- 生成周报/日报
"""

import json
import os
import sys
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict
from typing import List, Dict

# 数据目录
DATA_DIR = Path(os.getenv("ZSXQ_DATA_DIR", "/root/.openclaw/workspace/data/zsxq"))
RAW_DIR = DATA_DIR / "raw"


def load_topics_by_date(date: str) -> List[Dict]:
    """加载指定日期的主题"""
    file_path = RAW_DIR / f"{date}.json"
    if not file_path.exists():
        return []
    
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def load_all_topics(days: int = 7) -> Dict[str, List[Dict]]:
    """加载最近N天的所有主题"""
    result = {}
    for i in range(days):
        date = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
        topics = load_topics_by_date(date)
        if topics:
            result[date] = topics
    return result


def filter_by_channel(topics: List[Dict], channel: str) -> List[Dict]:
    """按频道筛选"""
    return [t for t in topics if channel in t.get("channels", [])]


def print_daily_stats(days: int = 7):
    """打印每日统计"""
    print("=" * 60)
    print("📊 知识星球每日信息量统计")
    print("=" * 60)
    
    total = 0
    for i in range(days):
        date = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
        topics = load_topics_by_date(date)
        count = len(topics)
        total += count
        
        if count > 0:
            bar = "█" * min(count, 20)
            print(f"{date}: {count:3d} 条 {bar}")
    
    print("-" * 60)
    print(f"最近{days}天总计: {total} 条")


def print_channel_stats(channel: str = None, days: int = 7):
    """打印频道统计"""
    target_channel = channel or "调研纪要"
    
    print("=" * 60)
    print(f"📋 频道统计: {target_channel}")
    print("=" * 60)
    
    total = 0
    for i in range(days):
        date = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
        topics = load_topics_by_date(date)
        filtered = filter_by_channel(topics, target_channel)
        count = len(filtered)
        total += count
        
        if count > 0:
            bar = "█" * min(count, 10)
            print(f"{date}: {count:3d} 条 {bar}")
            
            # 显示前3条标题
            for t in filtered[:3]:
                title = t.get("title", "")[:40]
                author = t.get("author", "")[:10]
                print(f"    • [{author}] {title}...")
    
    print("-" * 60)
    print(f"{target_channel} 最近{days}天总计: {total} 条")


def generate_weekly_report(output_file: str = None):
    """生成周报"""
    topics_by_date = load_all_topics(days=7)
    
    if not topics_by_date:
        print("⚠️ 没有数据")
        return
    
    lines = []
    lines.append("# 📊 知识星球周报")
    lines.append(f"**统计周期**: 最近7天")
    lines.append(f"**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append("")
    
    # 总体统计
    total = sum(len(t) for t in topics_by_date.values())
    lines.append(f"## 📈 总体概览")
    lines.append(f"- 总信息量: {total} 条")
    lines.append(f"- 统计天数: {len(topics_by_date)} 天")
    lines.append("")
    
    # 每日统计
    lines.append(f"## 📅 每日信息量")
    lines.append("")
    lines.append("| 日期 | 信息量 |")
    lines.append("|------|--------|")
    
    for date in sorted(topics_by_date.keys(), reverse=True):
        count = len(topics_by_date[date])
        lines.append(f"| {date} | {count} 条 |")
    
    lines.append("")
    
    # 频道分布
    channel_stats = defaultdict(int)
    for topics in topics_by_date.values():
        for t in topics:
            for ch in t.get("channels", []):
                channel_stats[ch] += 1
    
    if channel_stats:
        lines.append(f"## 📋 频道分布")
        lines.append("")
        lines.append("| 频道 | 信息量 |")
        lines.append("|------|--------|")
        
        for ch, count in sorted(channel_stats.items(), key=lambda x: -x[1]):
            lines.append(f"| {ch} | {count} 条 |")
        
        lines.append("")
    
    # 调研纪要专区
    research_topics = []
    for date, topics in topics_by_date.items():
        for t in topics:
            if "调研纪要" in t.get("channels", []):
                research_topics.append((date, t))
    
    if research_topics:
        lines.append(f"## 📝 调研纪要精选")
        lines.append("")
        
        for date, t in sorted(research_topics, key=lambda x: x[1].get("create_time", ""), reverse=True)[:10]:
            title = t.get("title", "无标题")
            author = t.get("author", "未知")
            content = t.get("content", "")[:100]
            lines.append(f"### {date} | {title}")
            lines.append(f"**作者**: {author}")
            lines.append(f"**摘要**: {content}...")
            lines.append("")
    
    report = "\n".join(lines)
    
    # 输出
    if output_file:
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(report)
        print(f"✅ 周报已保存: {output_file}")
    else:
        print(report)
    
    return report


def main():
    """主函数"""
    if len(sys.argv) < 2:
        print("""
用法:
  python3 zsxq_viewer.py stats [days]        - 查看每日统计
  python3 zsxq_viewer.py channel [name]      - 查看频道统计(默认:调研纪要)
  python3 zsxq_viewer.py weekly [output.md]  - 生成周报

示例:
  python3 zsxq_viewer.py stats 7
  python3 zsxq_viewer.py channel 调研纪要
  python3 zsxq_viewer.py weekly report.md
        """)
        return
    
    command = sys.argv[1]
    
    if command == "stats":
        days = int(sys.argv[2]) if len(sys.argv) > 2 else 7
        print_daily_stats(days)
    
    elif command == "channel":
        channel = sys.argv[2] if len(sys.argv) > 2 else "调研纪要"
        days = int(sys.argv[3]) if len(sys.argv) > 3 else 7
        print_channel_stats(channel, days)
    
    elif command == "weekly":
        output = sys.argv[2] if len(sys.argv) > 2 else None
        generate_weekly_report(output)
    
    else:
        print(f"❌ 未知命令: {command}")


if __name__ == "__main__":
    main()
