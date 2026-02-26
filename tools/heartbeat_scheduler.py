#!/usr/bin/env python3
"""
Heartbeat任务调度器 - 整点策略效果汇报
使用新的汇报格式：策略组合 + 因子使用 + 后续优化点
"""
import json
import os
import subprocess
import sqlite3
from datetime import datetime
import sys

WORKSPACE = '/root/.openclaw/workspace'
DB_PATH = f'{WORKSPACE}/data/historical/historical.db'
OPT_PATH = f'{WORKSPACE}/quant/optimizer'
USER_ID = 'ou_efbad805767f4572e8f93ebafa8d5402'

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

def get_latest_strategy():
    """获取最新策略结果"""
    
    # 首先查找v26结果
    v26_files = [f for f in os.listdir(OPT_PATH) if f.startswith('v26_result_') and f.endswith('.json')]
    if v26_files:
        v26_files.sort(reverse=True)
        with open(f'{OPT_PATH}/{v26_files[0]}', 'r') as f:
            data = json.load(f)
        factor_count = data.get('factor_count', len(data.get('factors_used', [])))
        return {
            'version': 'v26',
            'params': data.get('params', {}),
            'yearly': data.get('yearly_returns', []),
            'avg_return': data.get('avg_return', 0),
            'top_factors': [{'factor': f} for f in data.get('factors_used', [])][:3],
            'factor_weights': {f: 1.0 for f in data.get('factors_used', [])},
            'factor_count': factor_count
        }
    
    # 查找增强优化器结果
    enhanced_files = []
    for f in os.listdir(OPT_PATH):
        if f.startswith('enhanced_optimizer_v') and f.endswith('.json'):
            enhanced_files.append(f)
    
    if enhanced_files:
        enhanced_files.sort(reverse=True)
        with open(f'{OPT_PATH}/{enhanced_files[0]}', 'r') as f:
            data = json.load(f)
        return {
            'version': enhanced_files[0].split('_')[2],
            'params': data.get('params', {}),
            'yearly': data.get('yearly_returns', []),
            'avg_return': data.get('avg_return', 0),
            'top_factors': data.get('top_factors', [])[:3],
            'factor_weights': data.get('factor_weights', {}),
        }
    
    # 查找v25结果
    v25_files = [f for f in os.listdir(OPT_PATH) if f.startswith('v25_result_') and f.endswith('.json')]
    if v25_files:
        v25_files.sort(reverse=True)
        with open(f'{OPT_PATH}/{v25_files[0]}', 'r') as f:
            data = json.load(f)
        return {
            'version': 'v25',
            'params': data.get('params', {}),
            'yearly': data.get('yearly_returns', []),
            'avg_return': data.get('avg_return', 0),
            'top_factors': data.get('top_factors', [])[:3],
            'factor_weights': data.get('factor_weights', {}),
        }
    
    return None

def get_factor_usage():
    """获取因子使用情况"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('SELECT COUNT(DISTINCT ts_code) FROM stock_factors WHERE trade_date >= "20250101"')
    sf = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(DISTINCT ts_code) FROM stock_defensive_factors WHERE trade_date >= "20250101"')
    sdf = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(DISTINCT ts_code) FROM stock_fina')
    fina = cursor.fetchone()[0]
    
    conn.close()
    
    return {'tech': sf, 'def': sdf, 'fina': fina, 'total': 26}

def generate_strategy_report():
    """生成策略效果报告（新格式）"""
    strategy = get_latest_strategy()
    factors = get_factor_usage()
    now = datetime.now().strftime('%H:%M')
    
    report_lines = [f"📊 **策略状态汇报** ({now})", ""]
    
    if not strategy:
        # 无策略数据的情况
        report_lines.append("【当前策略组合】")
        report_lines.append("- 状态: 暂无策略数据 ⚠️")
        report_lines.append("- 建议: 运行 auto_optimizer.py 生成首份策略")
        report_lines.append("")
        report_lines.append("【因子使用】")
        report_lines.append(f"- 已使用: 0/{factors['total']} 个因子 (0%)")
        report_lines.append(f"- 数据覆盖: 技术{factors['tech']}/防御{factors['def']}/财务{factors['fina']} ✅")
        report_lines.append("")
        report_lines.append("【后续优化点】")
        report_lines.append("- 立即执行: tools/auto_optimizer.py 生成策略")
        return "\n".join(report_lines)
    
    # 当前策略组合
    p = strategy['params']
    report_lines.append("【当前策略组合】")
    report_lines.append(f"- 仓位: {p.get('p', 0)*100:.0f}% | 止损: {p.get('s', 0)*100:.0f}% | 持仓: {p.get('n', 0)}只 | 调仓: {p.get('rebal', 10)}天")
    
    # 回测表现
    yearly_strs = []
    for y in strategy['yearly']:
        yearly_strs.append(f"{y['year']}:{y['return']*100:+.0f}%")
    report_lines.append(f"- 回测表现: {' | '.join(yearly_strs)}")
    report_lines.append(f"- 平均年化: {strategy['avg_return']:+.1f}% {'✅' if strategy['avg_return'] > 0 else '⚠️'}")
    
    # 因子使用情况
    used = strategy.get('factor_count', len(strategy['factor_weights']) if strategy['factor_weights'] else 6)
    unused = factors['total'] - used
    report_lines.append("")
    report_lines.append("【因子使用情况】")
    report_lines.append(f"- 已采用: {used}/{factors['total']} 个因子 ({used/factors['total']*100:.0f}%)")
    report_lines.append(f"- 未采用: {unused}/{factors['total']} 个因子 ({unused/factors['total']*100:.0f}%)")
    
    if strategy['top_factors']:
        top_names = [f['factor'] for f in strategy['top_factors']]
        report_lines.append(f"- Top 3: {' | '.join(top_names)}")
    
    report_lines.append(f"- 数据覆盖: 技术{factors['tech']}/防御{factors['def']}/财务{factors['fina']} ✅")
    
    # 后续优化点
    report_lines.append("")
    report_lines.append("【后续优化点】")
    
    suggestions = []
    if unused > 0:
        suggestions.append(f"有{unused}个因子未采用，建议逐步引入测试效果")
    
    if strategy['avg_return'] < 15:
        suggestions.append("当前收益有提升空间，建议调整止损参数或增加防御因子权重")
    
    # 检查是否需要持续优化
    suggestions.append("持续运行优化器，每15分钟迭代寻找更优组合")
    
    for s in suggestions:
        report_lines.append(f"- {s}")
    
    return "\n".join(report_lines)

def git_sync():
    """同步git变更 - 使用简单快速的方式"""
    try:
        # 快速检查
        result = subprocess.run(
            ['git', 'status', '--porcelain'],
            cwd=WORKSPACE,
            capture_output=True, text=True, timeout=5
        )
        
        if not result.stdout.strip():
            return None
        
        # 提交并推送
        subprocess.run(['git', 'add', '-A'], cwd=WORKSPACE, capture_output=True, timeout=5)
        commit_msg = f"🫘 {datetime.now().strftime('%H:%M')} Heartbeat"
        subprocess.run(
            ['git', 'commit', '-m', commit_msg],
            cwd=WORKSPACE, capture_output=True, timeout=5
        )
        
        # 异步推送
        subprocess.Popen(
            ['git', 'push'],
            cwd=WORKSPACE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        
        return "已同步"
    except Exception as e:
        return f"失败: {str(e)[:50]}"

def is_hour_start():
    """检查是否为整点"""
    return datetime.now().minute == 0


def run_us_market_report():
    """执行美股报告任务 - 08:30"""
    try:
        print("🌙 执行美股报告任务...")
        script = f'{WORKSPACE}/skills/us-market-analysis/scripts/generate_report_longbridge.py'
        result = subprocess.run(
            ['python3', script],
            cwd=WORKSPACE,
            capture_output=True, text=True, timeout=120
        )
        if result.returncode == 0:
            return "✅ 美股报告已生成并发送"
        else:
            return f"❌ 美股报告失败: {result.stderr[:100]}"
    except Exception as e:
        return f"❌ 美股报告异常: {str(e)[:100]}"


def run_ah_preopen_report():
    """执行A+H开盘前瞻任务 - 09:15"""
    try:
        print("🌅 执行A+H开盘前瞻任务...")
        script = f'{WORKSPACE}/skills/ah-market-preopen/scripts/generate_report_longbridge.py'
        result = subprocess.run(
            ['python3', script],
            cwd=WORKSPACE,
            capture_output=True, text=True, timeout=120
        )
        if result.returncode == 0:
            return "✅ A+H开盘前瞻已生成并发送"
        else:
            return f"❌ A+H开盘前瞻失败: {result.stderr[:100]}"
    except Exception as e:
        return f"❌ A+H开盘前瞻异常: {str(e)[:100]}"


def run_optimizer_if_needed():
    """检查并运行优化器 - 持续寻找最佳组合"""
    # 检查是否已有优化器在运行
    try:
        result = subprocess.run(
            ['pgrep', '-f', 'enhanced_optimizer|smart_optimizer'],
            capture_output=True, text=True, timeout=5
        )
        if result.stdout.strip():
            print("⏭️ 优化器已在运行，跳过")
            return "已在运行"
    except:
        pass
    
    # 检查最新结果时间
    try:
        latest_time = None
        for f in os.listdir(OPT_PATH):
            if f.endswith('.json') and ('result' in f or 'enhanced' in f):
                # 从文件名提取时间
                import re
                match = re.search(r'\d{8}_\d{6}', f)
                if match:
                    ts = match.group()
                    if latest_time is None or ts > latest_time:
                        latest_time = ts
        
        if latest_time:
            from datetime import datetime, timedelta
            last_dt = datetime.strptime(latest_time, '%Y%m%d_%H%M%S')
            hours_passed = (datetime.now() - last_dt).total_seconds() / 3600
            
            # 每4小时运行一次优化
            if hours_passed < 4:
                print(f"⏭️ 上次优化距今{hours_passed:.1f}小时，跳过")
                return f"{hours_passed:.1f}小时前已优化"
    except Exception as e:
        print(f"检查时间失败: {e}")
    
    # 启动优化器（后台运行）
    print("🚀 启动优化器...")
    try:
        # 自动发现最新优化器
        enhanced = [f for f in os.listdir(OPT_PATH) 
                   if f.startswith('enhanced_optimizer_v') and f.endswith('.py')]
        if enhanced:
            enhanced.sort(reverse=True)
            optimizer = f'{OPT_PATH}/{enhanced[0]}'
        else:
            # 回退到smart_optimizer
            smart = [f for f in os.listdir(OPT_PATH) 
                    if f.startswith('smart_optimizer_v') and f.endswith('.py')]
            smart.sort(reverse=True)
            optimizer = f'{OPT_PATH}/{smart[0]}' if smart else None
        
        if optimizer:
            subprocess.Popen(
                ['python3', optimizer],
                cwd=OPT_PATH,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            return f"已启动 {os.path.basename(optimizer)}"
    except Exception as e:
        return f"启动失败: {e}"
    
    return "未找到优化器"

def main():
    now = datetime.now()
    print(f"🫘 Heartbeat检查 - {now.strftime('%H:%M:%S')}")
    
    # 08:30 美股报告
    if now.hour == 8 and now.minute == 30:
        print("🌙 08:30 执行美股报告...")
        us_status = run_us_market_report()
        send_message(f"📊 **美股报告执行**: {us_status}")
    
    # 09:15 A+H开盘前瞻
    if now.hour == 9 and now.minute == 15:
        print("🌅 09:15 执行A+H开盘前瞻...")
        ah_status = run_ah_preopen_report()
        send_message(f"📊 **A+H开盘前瞻执行**: {ah_status}")
    
    # 每15分钟检查是否需要运行优化器
    if now.minute % 15 == 0:
        print("🔍 检查优化器状态...")
        opt_status = run_optimizer_if_needed()
        if opt_status and "已启动" in opt_status:
            send_message(f"🤖 **自动启动优化器**: {opt_status}")
    
    # 非整点跳过汇报
    if not is_hour_start():
        print(f"⏱️ 非整点({now.minute}分)，跳过汇报")
        return
    
    print(f"🕐 整点汇报 - {now.hour}:00")
    
    # 生成并发送策略报告（新格式）
    report = generate_strategy_report()
    print(report)
    send_message(report)
    
    # Git同步
    git_result = git_sync()
    if git_result:
        git_msg = f"🔄 **Git同步**: {git_result}"
        print(git_msg)
        send_message(git_msg)
    
    print("✅ Heartbeat完成")

if __name__ == "__main__":
    main()
