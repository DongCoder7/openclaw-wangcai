#!/root/.openclaw/workspace/venv/bin/python3
"""
板块分析强制检查清单工具
使用方式: ./checklist_block_analysis.py [板块名称]

功能:
1. 强制检查多源搜索是否完成
2. 记录搜索执行状态
3. 未完成检查禁止出报告

创建日期: 2026-03-07
更新原因: 氮肥板块分析事故 - 遗漏多源搜索
"""

import sys
import json
import os
from datetime import datetime
from pathlib import Path

CHECKLIST_FILE = Path("/root/.openclaw/workspace/quality/block_analysis_checklist.json")

def init_checklist(industry_name):
    """初始化检查清单"""
    checklist = {
        "industry": industry_name,
        "created_at": datetime.now().isoformat(),
        "status": "in_progress",
        "steps": {
            "p1_exa_search": {
                "name": "P1 Exa全网搜索",
                "status": "pending",
                "required": True,
                "keywords": [],
                "executed_at": None
            },
            "p2_zsxq_search": {
                "name": "P2 知识星球搜索",
                "status": "pending",
                "required": True,
                "keywords": [],
                "executed_at": None
            },
            "p3_sina_api": {
                "name": "P3 新浪财经API",
                "status": "pending",
                "required": True,
                "executed_at": None
            },
            "data_acquisition": {
                "name": "数据获取",
                "status": "pending",
                "required": True,
                "note": None,
                "executed_at": None
            },
            "cross_validation": {
                "name": "新闻交叉验证",
                "status": "pending",
                "required": True,
                "note": None,
                "executed_at": None
            }
        },
        "can_proceed": False,
        "blockers": []
    }
    return checklist

def save_checklist(checklist):
    """保存检查清单"""
    CHECKLIST_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(CHECKLIST_FILE, 'w', encoding='utf-8') as f:
        json.dump(checklist, f, ensure_ascii=False, indent=2)

def load_checklist():
    """加载检查清单"""
    if CHECKLIST_FILE.exists():
        with open(CHECKLIST_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return None

def mark_step_complete(step_name, note=None):
    """标记步骤完成"""
    checklist = load_checklist()
    if not checklist:
        print("❌ 错误：未找到检查清单，请先初始化")
        return False
    
    if step_name in checklist["steps"]:
        checklist["steps"][step_name]["status"] = "completed"
        checklist["steps"][step_name]["executed_at"] = datetime.now().isoformat()
        if note:
            checklist["steps"][step_name]["note"] = note
        save_checklist(checklist)
        print(f"✅ 已标记完成: {checklist['steps'][step_name]['name']}")
        return True
    else:
        print(f"❌ 错误：未知步骤 {step_name}")
        return False

def check_can_proceed():
    """检查是否可以继续输出报告"""
    checklist = load_checklist()
    if not checklist:
        print("❌ 错误：未找到检查清单")
        return False
    
    blockers = []
    for step_id, step in checklist["steps"].items():
        if step["required"] and step["status"] != "completed":
            blockers.append(step["name"])
    
    checklist["blockers"] = blockers
    checklist["can_proceed"] = len(blockers) == 0
    save_checklist(checklist)
    
    return checklist["can_proceed"], blockers

def print_checklist_status():
    """打印检查清单状态"""
    checklist = load_checklist()
    if not checklist:
        print("❌ 未找到检查清单")
        return
    
    print(f"\n{'='*60}")
    print(f"📋 板块分析检查清单 - {checklist['industry']}")
    print(f"{'='*60}")
    print(f"创建时间: {checklist['created_at']}")
    print(f"当前状态: {checklist['status']}")
    print(f"\n检查项目:")
    
    all_completed = True
    for step_id, step in checklist["steps"].items():
        status_icon = "✅" if step["status"] == "completed" else "⬜"
        required_icon = "🔴" if step["required"] else "⚪"
        print(f"  {status_icon} {required_icon} {step['name']}")
        if step["status"] != "completed":
            all_completed = False
    
    print(f"\n{'='*60}")
    can_proceed, blockers = check_can_proceed()
    
    if can_proceed:
        print("🟢 所有必填项已完成，可以输出报告！")
    else:
        print(f"🔴 存在 {len(blockers)} 个阻塞项，禁止输出报告！")
        print("\n阻塞项:")
        for blocker in blockers:
            print(f"  ❌ {blocker}")
    
    print(f"{'='*60}\n")

def print_usage():
    """打印使用说明"""
    print("""
╔══════════════════════════════════════════════════════════════╗
║     板块分析强制检查清单工具 v1.0                            ║
║     创建日期: 2026-03-07 (氮肥板块事故后)                    ║
╚══════════════════════════════════════════════════════════════╝

使用方法:
  1. 初始化检查清单:
     ./checklist_block_analysis.py init [板块名称]
     
  2. 标记步骤完成:
     ./checklist_block_analysis.py complete [步骤ID] [备注]
     
  3. 查看状态:
     ./checklist_block_analysis.py status
     
  4. 检查是否可以出报告:
     ./checklist_block_analysis.py check

步骤ID列表:
  - p1_exa_search      : P1 Exa全网搜索
  - p2_zsxq_search     : P2 知识星球搜索  
  - p3_sina_api        : P3 新浪财经API
  - data_acquisition   : 数据获取
  - cross_validation   : 新闻交叉验证

示例:
  ./checklist_block_analysis.py init 氮肥板块
  ./checklist_block_analysis.py complete p1_exa_search "搜索了伊朗战争影响"
  ./checklist_block_analysis.py complete p2_zsxq_search "近期无化肥专题"
  ./checklist_block_analysis.py status
  ./checklist_block_analysis.py check

⚠️  重要：未完成所有必填项，禁止输出报告！
""")

def main():
    if len(sys.argv) < 2:
        print_usage()
        return
    
    command = sys.argv[1]
    
    if command == "init":
        if len(sys.argv) < 3:
            print("❌ 错误：请提供板块名称")
            print("用法: ./checklist_block_analysis.py init [板块名称]")
            return
        industry = sys.argv[2]
        checklist = init_checklist(industry)
        save_checklist(checklist)
        print(f"✅ 已初始化检查清单: {industry}")
        print_checklist_status()
    
    elif command == "complete":
        if len(sys.argv) < 3:
            print("❌ 错误：请提供步骤ID")
            return
        step_name = sys.argv[2]
        note = sys.argv[3] if len(sys.argv) > 3 else None
        mark_step_complete(step_name, note)
        print_checklist_status()
    
    elif command == "status":
        print_checklist_status()
    
    elif command == "check":
        can_proceed, blockers = check_can_proceed()
        if can_proceed:
            print("✅ 检查通过，可以输出报告！")
            sys.exit(0)
        else:
            print(f"❌ 检查未通过，存在 {len(blockers)} 个阻塞项！")
            for blocker in blockers:
                print(f"   - {blocker}")
            sys.exit(1)
    
    else:
        print(f"❌ 未知命令: {command}")
        print_usage()

if __name__ == "__main__":
    main()
