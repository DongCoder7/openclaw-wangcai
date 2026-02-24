#!/usr/bin/env python3
"""
Heartbeat任务调度器 - 每10分钟强制汇报
不管有没有变化，每次都汇报当前状态
"""
import json
import os
import subprocess
import sqlite3
from datetime import datetime, timedelta
import sys

WORKSPACE = '/root/.openclaw/workspace'
DB_PATH = f'{WORKSPACE}/data/historical/historical.db'
USER_ID = 'ou_efbad805767f4572e8f93ebafa8d5402'
STATE_FILE = f'{WORKSPACE}/heartbeat_state.json'

def send_message(message):
    """发送消息到Feishu"""
    try:
        result = subprocess.run(
            ['openclaw', 'message', 'send', '--channel', 'feishu', '--target', USER_ID, '--message', message],
            capture_output=True, text=True, timeout=30
        )
        return result.returncode == 0
    except Exception as e:
        print(f"发送失败: {e}")
        return False

def get_current_status():
    """获取当前所有状态"""
    status = {}
    
    # 1. 数据库股票数量
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(DISTINCT ts_code) FROM stock_factors")
        status['stock_count'] = cursor.fetchone()[0]
        conn.close()
    except:
        status['stock_count'] = 0
    
    # 2. 检查优化器进程
    try:
        result = subprocess.run(
            ['pgrep', '-f', 'smart_optimizer'],
            capture_output=True, text=True
        )
        status['optimizer_running'] = len(result.stdout.strip().split('\n')) if result.stdout.strip() else 0
    except:
        status['optimizer_running'] = 0
    
    # 3. 检查数据采集进程
    try:
        result = subprocess.run(
            ['pgrep', '-f', 'fetch_all_stocks'],
            capture_output=True, text=True
        )
        status['data_fetch_running'] = len(result.stdout.strip().split('\n')) if result.stdout.strip() else 0
    except:
        status['data_fetch_running'] = 0
    
    # 4. 检查锁文件
    status['lock_exists'] = os.path.exists(f'{WORKSPACE}/quant/optimizer/optimizer.lock')
    
    # 5. 模拟盘状态
    try:
        with open(f'{WORKSPACE}/data/sim_portfolio.json', 'r') as f:
            portfolio = json.load(f)
        status['portfolio_positions'] = len(portfolio.get('positions', {}))
        status['portfolio_value'] = portfolio.get('total_value', 0)
    except:
        status['portfolio_positions'] = 0
        status['portfolio_value'] = 0
    
    return status

def generate_report(status):
    """生成状态报告"""
    now = datetime.now().strftime('%H:%M:%S')
    
    report = f"📊 **Heartbeat状态汇报** {now}\n\n"
    
    report += f"**数据库**: {status['stock_count']} 只股票\n"
    report += f"**优化器**: {'🟢运行中' if status['optimizer_running'] > 0 else '🔴未运行'} ({status['optimizer_running']}进程)\n"
    report += f"**数据采集**: {'🟢运行中' if status['data_fetch_running'] > 0 else '🔴未运行'}\n"
    report += f"**锁文件**: {'🔴存在' if status['lock_exists'] else '✅无'}\n"
    report += f"**模拟盘**: {status['portfolio_positions']}只持仓, ¥{status['portfolio_value']:,.0f}\n"
    
    # 问题提示
    issues = []
    if status['optimizer_running'] == 0:
        issues.append("优化器未运行")
    if status['data_fetch_running'] == 0:
        issues.append("数据采集未运行")
    if status['lock_exists'] and status['optimizer_running'] == 0:
        issues.append("僵尸锁文件")
    
    if issues:
        report += f"\n⚠️ **需要处理**: {', '.join(issues)}"
    else:
        report += "\n✅ 所有系统正常运行"
    
    return report

def fix_issues(status):
    """自动修复问题"""
    fixes = []
    
    # 清理僵尸锁
    if status['lock_exists'] and status['optimizer_running'] == 0:
        os.remove(f'{WORKSPACE}/quant/optimizer/optimizer.lock')
        fixes.append("清理僵尸锁")
    
    # 启动优化器
    if status['optimizer_running'] == 0:
        subprocess.Popen(
            ['python3', f'{WORKSPACE}/quant/optimizer/smart_optimizer_v23_async.py'],
            cwd=f'{WORKSPACE}/quant/optimizer',
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        fixes.append("启动优化器")
    
    # 启动数据采集
    if status['data_fetch_running'] == 0:
        subprocess.Popen(
            ['python3', f'{WORKSPACE}/tools/fetch_all_stocks_factors.py'],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        fixes.append("启动数据采集")
    
    return fixes

def git_sync():
    """同步git变更"""
    try:
        # 检查是否有变更
        result = subprocess.run(
            ['git', 'status', '--porcelain'],
            cwd=WORKSPACE,
            capture_output=True, text=True, timeout=10
        )
        
        if not result.stdout.strip():
            return None  # 无变更
        
        # 添加所有变更
        subprocess.run(['git', 'add', '.'], cwd=WORKSPACE, capture_output=True, timeout=10)
        
        # 提交
        commit_msg = f"heartbeat: auto sync {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        subprocess.run(
            ['git', 'commit', '-m', commit_msg],
            cwd=WORKSPACE,
            capture_output=True, timeout=10
        )
        
        # 推送 (后台执行)
        subprocess.Popen(
            ['git', 'push'],
            cwd=WORKSPACE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        
        return "已同步"
    except Exception as e:
        return f"失败: {e}"

def is_hour_start():
    """检查是否为整点（0分）"""
    return datetime.now().minute == 0

def main():
    now = datetime.now()
    print(f"🫘 Heartbeat检查 - {now.strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 判断是否为整点
    if not is_hour_start():
        print(f"⏱️ 非整点({now.minute}分)，跳过状态汇报")
        print("✅ Heartbeat完成")
        return
    
    print(f"🕐 整点汇报 - {now.hour}:00")
    
    # 获取状态
    status = get_current_status()
    
    # 生成报告
    report = generate_report(status)
    print(report)
    
    # 发送报告（整点才发送）
    send_message(report)
    
    # 自动修复问题
    fixes = fix_issues(status)
    if fixes:
        fix_msg = f"🔧 **自动修复**: {', '.join(fixes)}"
        print(fix_msg)
        send_message(fix_msg)
    
    # Git同步
    git_result = git_sync()
    if git_result:
        git_msg = f"🔄 **Git同步**: {git_result}"
        print(git_msg)
        send_message(git_msg)
    
    print("✅ Heartbeat完成")

if __name__ == "__main__":
    main()
