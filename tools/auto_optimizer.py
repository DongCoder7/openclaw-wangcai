#!/usr/bin/env python3
"""
自动优化执行器 - 无需询问，直接执行，只汇报结果
"""
import subprocess
import os
import json
from datetime import datetime

OPT_DIR = '/root/.openclaw/workspace/quant/optimizer'

def should_run_optimization():
    """检查是否需要运行优化"""
    # 检查是否有待处理标记
    flag_file = f'{OPT_DIR}/result_pending.flag'
    if os.path.exists(flag_file):
        return True
    
    # 检查最新结果是否过期（超过4小时）
    try:
        latest = None
        for f in os.listdir(OPT_DIR):
            if f.startswith('v25_result_') and f.endswith('.json'):
                ts = f.replace('v25_result_', '').replace('.json', '')
                if latest is None or ts > latest:
                    latest = ts
        
        if latest:
            latest_time = datetime.strptime(latest, '%Y%m%d_%H%M%S')
            hours_passed = (datetime.now() - latest_time).total_seconds() / 3600
            return hours_passed > 4
    except:
        pass
    
    return True

def find_latest_optimizer():
    """自动发现最新版本的增强优化器"""
    # 查找所有增强优化器 (enhanced_optimizer_v*.py)
    enhanced = [f for f in os.listdir(OPT_DIR) 
                if f.startswith('enhanced_optimizer_v') and f.endswith('.py')]
    
    if enhanced:
        # 按版本号排序，取最新
        enhanced.sort(reverse=True)
        return f'{OPT_DIR}/{enhanced[0]}'
    
    # 查找所有smart_optimizer (旧版本)
    smart = [f for f in os.listdir(OPT_DIR) 
             if f.startswith('smart_optimizer_v') and f.endswith('.py')]
    
    if smart:
        smart.sort(reverse=True)
        return f'{OPT_DIR}/{smart[0]}'
    
    return None

def run_optimization():
    """直接执行优化，不询问"""
    print("🚀 启动自动优化...")
    
    # 自动发现最新优化器
    optimizer = find_latest_optimizer()
    
    if optimizer:
        version = os.path.basename(optimizer).replace('.py', '')
        print(f"📦 使用优化器: {version}")
        
        try:
            result = subprocess.run(
                ['python3', optimizer],
                capture_output=True,
                text=True,
                timeout=1800
            )
            if result.returncode == 0:
                print(f"✅ {version} 优化完成")
                return True
            else:
                print(f"❌ {version} 优化失败")
                if result.stderr:
                    print(f"   错误: {result.stderr[:200]}")
        except subprocess.TimeoutExpired:
            print("⏱️ 优化超时")
        except Exception as e:
            print(f"❌ 优化异常: {e}")
    else:
        print("❌ 未找到优化器脚本")
    
    return False

def main():
    """主函数"""
    print("="*60)
    print("🤖 自动优化执行器")
    print("="*60)
    
    if should_run_optimization():
        success = run_optimization()
        if success:
            # 生成新报告
            print("\n📝 生成策略报告...")
            subprocess.run(['python3', '/root/.openclaw/workspace/tools/generate_strategy_report.py'])
            
            # 清除待处理标记
            flag_file = f'{OPT_DIR}/result_pending.flag'
            if os.path.exists(flag_file):
                os.remove(flag_file)
        else:
            print("❌ 优化失败，保留上次结果")
    else:
        print("⏭️ 优化结果在有效期内，跳过执行")
        # 仅更新报告时间戳
        subprocess.run(['python3', '/root/.openclaw/workspace/tools/generate_strategy_report.py'])
    
    print("\n" + "="*60)

if __name__ == '__main__':
    main()
