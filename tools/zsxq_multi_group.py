#!/root/.openclaw/workspace/venv/bin/python3
"""
知识星球多Group抓取调度器
读取groups.json配置，依次抓取所有启用的group
"""

import json
import os
import sys
from pathlib import Path
from datetime import datetime

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

# 配置路径
CONFIG_FILE = Path(__file__).parent / "data/zsxq/groups.json"

def load_groups():
    """加载Group配置"""
    if not CONFIG_FILE.exists():
        print(f"❌ 配置文件不存在: {CONFIG_FILE}")
        return []
    
    with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    return [g for g in config.get('groups', []) if g.get('enabled', False)]

def main():
    print("=" * 60)
    print(f"🚀 知识星球多Group抓取调度器")
    print(f"⏰ 执行时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    groups = load_groups()
    
    if not groups:
        print("❌ 没有启用的Group")
        return
    
    print(f"📋 将抓取 {len(groups)} 个Group:")
    for g in groups:
        print(f"  - {g['name']} (ID: {g['group_id']})")
    print()
    
    # 依次抓取每个group
    for i, group in enumerate(groups, 1):
        print(f"\n{'='*60}")
        print(f"📦 [{i}/{len(groups)}] 抓取 Group: {group['name']}")
        print(f"{'='*60}")
        
        # 设置环境变量
        os.environ['ZSXQ_GROUP_ID'] = group['group_id']
        os.environ['ZSXQ_COOKIE'] = group['cookie']
        
        # 动态导入并运行抓取器
        from tools.zsxq_fetcher_prod import ZsxqFetcher, DATA_DIR
        
        try:
            fetcher = ZsxqFetcher(group['cookie'], group['group_id'])
            target_date = datetime.now().strftime("%Y-%m-%d")
            
            # 抓取（限制页数避免太长）
            fetcher.fetch_with_pagination(max_pages=50)
            
            # 生成报告
            summary = fetcher.generate_summary_report(target_date)
            print(summary)
            
        except Exception as e:
            print(f"❌ 抓取失败: {e}")
            import traceback
            traceback.print_exc()
    
    print(f"\n{'='*60}")
    print("✅ 全部Group抓取完成!")
    print("=" * 60)

if __name__ == "__main__":
    main()
