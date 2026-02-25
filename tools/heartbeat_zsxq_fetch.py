#!/usr/bin/env python3
"""
Heartbeat任务: 定时获取知识星球调研纪要
每2小时执行一次，获取最新行业信息
"""
import sys
import os
sys.path.insert(0, '/root/.openclaw/workspace/tools')

from zsxq_fetcher import get_latest, search_industry_info
from datetime import datetime

def main():
    """主函数"""
    print(f"🫘 {datetime.now().strftime('%H:%M')} 知识星球信息获取")
    print("="*60)
    
    # 获取最新5条文章
    print("\n📥 获取最新调研纪要...")
    topics = get_latest(count=5)
    
    if not topics:
        print("❌ 获取失败或暂无新内容")
        return
    
    # 检查是否包含重要行业信息
    keywords = ['存储', '芯片', '半导体', 'PCB', '设备', '材料', '涨价', '订单']
    important_topics = []
    
    for t in topics:
        text = t.get('text', '')
        if any(kw in text for kw in keywords):
            important_topics.append(t)
    
    # 输出结果
    if important_topics:
        print(f"\n🎯 发现 {len(important_topics)} 条重要行业信息:")
        for t in important_topics:
            print(f"\n【{t['time']}】 {t['author']}")
            print(f"{t['text'][:150]}...")
            print(f"📊 阅读:{t['read_count']} | 👍 {t['like_count']}")
    else:
        print(f"\nℹ️ 最新 {len(topics)} 条文章无重要行业信息")
    
    # 保存到日志
    log_file = '/root/.openclaw/workspace/data/zsxq_updates.log'
    with open(log_file, 'a') as f:
        f.write(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M')}] 获取 {len(topics)} 条")
        if important_topics:
            f.write(f", 重要信息 {len(important_topics)} 条")
        f.write("\n")
    
    print("\n✅ 完成")

if __name__ == "__main__":
    main()
