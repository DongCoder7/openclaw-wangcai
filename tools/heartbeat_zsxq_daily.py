#!/usr/bin/env python3
"""
Heartbeat任务: 知识星球日终抓取（23:30运行）
整理当日数据并保存
"""
import sys
import os
sys.path.insert(0, '/root/.openclaw/workspace/tools')

from zsxq_fetcher_prod import ZsxqFetcher
from datetime import datetime
from pathlib import Path
import json

def main():
    """主函数"""
    print(f"🌙 {datetime.now().strftime('%Y-%m-%d %H:%M')} 知识星球日终抓取")
    print("="*60)
    
    # 抓取当日数据（回补一天）
    print("\n📥 开始抓取当日数据...")
    
    try:
        fetcher = ZsxqFetcher(
            cookie=None,  # 使用默认cookie
            group_id="28855458518111"
        )
        
        # 抓取当天数据
        today = datetime.now().strftime("%Y-%m-%d")
        fetcher.fetch_with_pagination(target_date=today, max_pages=50)
        
        # 生成日报
        print("\n📊 生成日报...")
        report = fetcher.generate_daily_report()
        print(report)
        
        # 保存到日报文件
        report_file = Path(f'/root/.openclaw/workspace/data/zsxq/daily_report_{today}.txt')
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write(f"知识星球日报 - {today}\n")
            f.write("="*60 + "\n\n")
            f.write(report)
        
        print(f"\n✅ 日报已保存: {report_file}")
        
    except Exception as e:
        print(f"❌ 抓取失败: {e}")
        return
    
    # 更新周统计数据
    print("\n📈 更新周统计数据...")
    try:
        raw_dir = Path('/root/.openclaw/workspace/data/zsxq/raw')
        weekly_stats = {}
        
        for json_file in sorted(raw_dir.glob('*.json')):
            date = json_file.stem
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                weekly_stats[date] = len(data)
        
        # 保存周统计
        weekly_file = Path('/root/.openclaw/workspace/data/zsxq/weekly_stats.json')
        with open(weekly_file, 'w', encoding='utf-8') as f:
            json.dump(weekly_stats, f, ensure_ascii=False, indent=2)
        
        total = sum(weekly_stats.values())
        print(f"   本周累计: {total} 条")
        print(f"   统计天数: {len(weekly_stats)} 天")
        
    except Exception as e:
        print(f"⚠️ 统计更新失败: {e}")
    
    print("\n" + "="*60)
    print("✅ 日终任务完成")

if __name__ == "__main__":
    main()
