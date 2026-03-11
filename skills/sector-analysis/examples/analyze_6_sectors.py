#!/root/.openclaw/workspace/venv/bin/python3
"""
6大板块投资分析示例
液冷、PCB、燃气轮机、半导体设备、光芯片、AI电源
"""

import sys
sys.path.insert(0, '/root/.openclaw/workspace/skills/sector-analysis/scripts')

from sector_analyzer import analyze_multiple_sectors

print("="*80)
print("🚀 6大板块投资分析 - 2026年3月2日")
print("="*80)

# 定义6大板块
sectors = {
    "AI电源": [
        "AI电源", 
        "数据中心电源", 
        "服务器电源", 
        "UPS电源",
        "泰嘉股份",
        "欧陆通"
    ],
    "燃气轮机": [
        "燃气轮机",
        "发电设备",
        "AI缺电",
        "分布式能源",
        "杰瑞股份",
        "应流股份",
        "东方电气"
    ],
    "液冷": [
        "液冷",
        "数据中心散热",
        "服务器液冷",
        "温控",
        "高澜股份",
        "申菱环境",
        "英维克"
    ],
    "PCB": [
        "PCB",
        "覆铜板",
        "高速PCB",
        "AI服务器PCB",
        "沪电股份",
        "胜宏科技",
        "深南电路"
    ],
    "光芯片": [
        "光芯片",
        "光模块",
        "800G",
        "1.6T",
        "中际旭创",
        "新易盛",
        "光迅科技"
    ],
    "半导体设备": [
        "半导体设备",
        "刻蚀机",
        "薄膜沉积",
        "国产替代",
        "北方华创",
        "中微公司",
        "长川科技"
    ]
}

# 执行分析
print("\n开始分析6大板块...")
print("-" * 80)

results = analyze_multiple_sectors(sectors)

# 汇总输出
print("\n" + "="*80)
print("📊 6大板块投资排序汇总")
print("="*80)

sector_summary = []
for sector_name, report in results.items():
    # 提取板块TOP1标的和得分
    # 这里简化处理，实际应该从report中解析
    sector_summary.append({
        'name': sector_name,
        'report': report
    })

# 打印每个板块的TOP1
for i, sector in enumerate(sector_summary, 1):
    print(f"\n【{i}】{sector['name']}")
    # 打印报告前500字符
    preview = sector['report'][:500].replace('\n', ' ')
    print(f"   预览: {preview}...")

print("\n" + "="*80)
print("✅ 分析完成！")
print("="*80)
print("\n详细报告已保存到 /root/.openclaw/workspace/reports/ 目录")
print("\n建议操作:")
print("1. 查看各板块的详细报告")
print("2. 比较综合评分，选择TOP3板块")
print("3. 根据买入区间和止损位制定交易计划")
