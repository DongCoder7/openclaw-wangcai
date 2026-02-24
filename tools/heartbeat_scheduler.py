#!/usr/bin/env python3
"""
Heartbeat任务调度器
在心跳时检查并执行定时任务
"""
import json
import os
import subprocess
from datetime import datetime, timedelta

STATE_FILE = '/root/.openclaw/workspace/heartbeat_tasks.json'
USER_ID = 'ou_efbad805767f4572e8f93ebafa8d5402'

def load_state():
    """加载任务状态"""
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, 'r') as f:
            return json.load(f)
    return {}

def save_state(state):
    """保存任务状态"""
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f, indent=2)

def should_run_task(task_config, now):
    """检查任务是否应该执行"""
    schedule = task_config.get('schedule')
    last_run = task_config.get('last_run')
    
    if not schedule:
        return False
    
    # 解析schedule时间
    schedule_hour, schedule_minute = map(int, schedule.split(':'))
    schedule_time = now.replace(hour=schedule_hour, minute=schedule_minute, second=0, microsecond=0)
    
    # 如果当前时间已经过了schedule时间，但不在5分钟窗口内，也不执行
    time_diff = (now - schedule_time).total_seconds() / 60
    
    # 必须满足: 当前时间 >= schedule时间 且 time_diff <= 5分钟
    if time_diff < 0 or time_diff > 5:
        return False
    
    # 如果今天已经运行过，不再执行
    if last_run:
        last_run_time = datetime.fromisoformat(last_run)
        if last_run_time.date() == now.date():
            return False
    
    return True

def should_run_continuous_task(config, now):
    """检查连续运行任务是否应该执行"""
    if not config.get('enabled', False):
        return False
    
    # 检查是否在运行时间段内
    current_hour = now.hour
    current_minute = now.minute
    current_time = current_hour * 60 + current_minute
    
    # 解析配置的时间段
    start_str = config.get('schedule_start', '00:00')
    end_str = config.get('schedule_end', '23:59')
    
    start_hour, start_minute = map(int, start_str.split(':'))
    end_hour, end_minute = map(int, end_str.split(':'))
    
    start_time = start_hour * 60 + start_minute
    end_time = end_hour * 60 + end_minute
    
    # 判断是否在时间窗口内
    if start_time <= end_time:
        # 正常时间段 (如 09:00-15:00)
        in_window = start_time <= current_time <= end_time
    else:
        # 跨天时间 (如 22:00-09:00)
        in_window = (current_time >= start_time) or (current_time <= end_time)
    
    if not in_window:
        return False
    
    # 检查间隔
    last_run = config.get('last_run')
    interval = config.get('interval_minutes', 15)
    
    if last_run:
        last_run_time = datetime.fromisoformat(last_run)
        minutes_since_last = (now - last_run_time).total_seconds() / 60
        return minutes_since_last >= interval
    
    return True

def check_git_sync():
    """检查是否有未同步到远程git的更改"""
    git_changes = []
    workspace = '/root/.openclaw/workspace'
    
    try:
        # 检查是否有.git目录
        if not os.path.exists(os.path.join(workspace, '.git')):
            return git_changes
        
        # 获取未提交的更改
        result = subprocess.run(
            ['git', 'status', '--porcelain'],
            cwd=workspace,
            capture_output=True, text=True, timeout=10
        )
        
        if result.returncode == 0 and result.stdout.strip():
            lines = result.stdout.strip().split('\n')
            for line in lines:
                if line.strip():
                    status = line[:2]
                    file = line[3:].strip()
                    git_changes.append({'status': status, 'file': file})
        
        # 检查是否有未推送的提交
        result = subprocess.run(
            ['git', 'log', '@{u}..HEAD', '--oneline'],
            cwd=workspace,
            capture_output=True, text=True, timeout=10
        )
        
        unpushed = []
        if result.returncode == 0 and result.stdout.strip():
            unpushed = result.stdout.strip().split('\n')
        
        return {
            'uncommitted': git_changes,
            'unpushed': unpushed
        }
    except Exception as e:
        print(f"Git检查失败: {e}")
        return {'uncommitted': [], 'unpushed': []}

def should_sync_file(filepath):
    """判断文件是否应该被同步"""
    # 获取文件扩展名
    ext = os.path.splitext(filepath)[1].lower()
    
    # 应该同步的文件类型
    sync_extensions = ['.py', '.sh', '.json', '.yaml', '.yml', '.conf', '.md', '.txt']
    
    # 应该同步的目录
    sync_dirs = ['skills/', 'tools/', 'quant/', 'config/', 'scripts/', 'docs/', '.openclaw/']
    
    # 排除的报告/数据目录
    exclude_dirs = ['data/', 'reports/', 'logs/', 'output/', '__pycache__/', '.git/', 'node_modules/']
    exclude_patterns = ['report', 'log', 'output', 'cache', 'temp', 'daily_', 'market_preopen']
    
    # 检查是否在排除目录中
    for exclude in exclude_dirs:
        if exclude in filepath:
            return False
    
    # 检查是否匹配排除模式
    for pattern in exclude_patterns:
        if pattern in filepath.lower():
            return False
    
    # 检查是否在同步目录中
    in_sync_dir = any(sync_dir in filepath for sync_dir in sync_dirs)
    
    # 检查扩展名
    has_sync_ext = ext in sync_extensions
    
    # 如果是MD文件，必须是学习资料（在docs/, memory/, 或skills/中）
    if ext == '.md':
        is_learning = any(x in filepath for x in ['docs/', 'memory/', 'skills/', 'AGENTS.md', 'SOUL.md', 'USER.md', 'MEMORY.md', 'HEARTBEAT.md', 'BOOTSTRAP.md', 'IDENTITY.md'])
        return is_learning
    
    return in_sync_dir and has_sync_ext

def sync_git_to_remote():
    """同步更改到远程git"""
    workspace = '/root/.openclaw/workspace'
    
    try:
        print("🔄 检查Git同步状态...")
        
        # 检查远程仓库配置
        result = subprocess.run(
            ['git', 'remote', '-v'],
            cwd=workspace,
            capture_output=True, text=True, timeout=10
        )
        
        if result.returncode != 0 or not result.stdout.strip():
            print("⚠️ 未配置远程git仓库")
            return False
        
        # 获取未提交的更改
        result = subprocess.run(
            ['git', 'status', '--porcelain'],
            cwd=workspace,
            capture_output=True, text=True, timeout=10
        )
        
        if result.returncode != 0:
            print("❌ 获取Git状态失败")
            return False
        
        # 筛选需要同步的文件
        files_to_sync = []
        if result.stdout.strip():
            lines = result.stdout.strip().split('\n')
            for line in lines:
                if line.strip():
                    status = line[:2]
                    filepath = line[3:].strip()
                    if should_sync_file(filepath):
                        files_to_sync.append(filepath)
        
        if not files_to_sync:
            print("✅ 无需要同步的脚本/配置/学习资料")
            return True
        
        print(f"📦 发现 {len(files_to_sync)} 个需要同步的文件")
        for f in files_to_sync[:5]:  # 只显示前5个
            print(f"   • {f}")
        if len(files_to_sync) > 5:
            print(f"   ... 还有 {len(files_to_sync) - 5} 个文件")
        
        # 添加筛选后的文件
        for filepath in files_to_sync:
            try:
                subprocess.run(
                    ['git', 'add', filepath],
                    cwd=workspace,
                    timeout=5
                )
            except Exception as e:
                print(f"   ⚠️ 添加文件失败: {filepath} - {e}")
        
        # 检查是否有已暂存的更改
        result = subprocess.run(
            ['git', 'diff', '--cached', '--name-only'],
            cwd=workspace,
            capture_output=True, text=True, timeout=10
        )
        
        if not result.stdout.strip():
            print("✅ 无可提交的更改")
            return True
        
        # 提交
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        commit_msg = f"Auto-sync: {timestamp} - {len(files_to_sync)} files"
        subprocess.run(
            ['git', 'commit', '-m', commit_msg],
            cwd=workspace, capture_output=True, timeout=10
        )
        print(f"✅ 已提交: {commit_msg}")
        
        # 推送到远程
        result = subprocess.run(
            ['git', 'push'],
            cwd=workspace,
            capture_output=True, text=True, timeout=30
        )
        
        if result.returncode == 0:
            print("✅ 已推送到远程仓库")
            return True
        else:
            print(f"❌ 推送失败: {result.stderr}")
            return False
            
    except Exception as e:
        print(f"❌ Git同步失败: {e}")
        return False

def run_task(task_name, task_config):
    """执行任务"""
    script = task_config.get('script')
    description = task_config.get('description', task_name)
    
    print(f"🚀 执行任务: {description}")
    
    try:
        # 执行脚本
        if script.endswith('.py'):
            result = subprocess.run(
                ['python3', script],
                capture_output=True, text=True, timeout=300
            )
        else:
            result = subprocess.run(
                ['bash', script],
                capture_output=True, text=True, timeout=300
            )
        
        if result.returncode == 0:
            print(f"✅ {description} 执行成功")
            return True
        else:
            print(f"❌ {description} 执行失败: {result.stderr}")
            return False
    except Exception as e:
        print(f"❌ {description} 执行异常: {e}")
        return False

def check_and_run_tasks():
    """检查并执行所有任务"""
    state = load_state()
    now = datetime.now()
    executed = []
    
    print(f"\n{'='*60}")
    print(f"🫘 Heartbeat任务检查 - {now.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}")
    
    # 检查常规任务
    tasks = state.get('tasks', {})
    for task_name, task_config in tasks.items():
        if should_run_task(task_config, now):
            if run_task(task_name, task_config):
                task_config['last_run'] = now.isoformat()
                executed.append(task_config.get('description', task_name))
    
    # 检查策略优化器 (24小时运行)
    optimizer = state.get('optimizer', {})
    if should_run_continuous_task(optimizer, now):
        if run_task('optimizer', optimizer):
            optimizer['last_run'] = now.isoformat()
            executed.append(optimizer.get('description', '策略优化器'))
    
    # 检查数据采集任务 (24小时运行)
    data_collection = state.get('data_collection', {})
    if should_run_continuous_task(data_collection, now):
        print("\n📊 启动全市场因子数据采集...")
        print("   (在后台运行，不阻塞heartbeat)")
        # 后台运行数据采集
        try:
            subprocess.Popen(
                ['python3', '/root/.openclaw/workspace/tools/fetch_all_stocks_factors.py'],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            data_collection['last_run'] = now.isoformat()
            executed.append('全市场因子采集(后台)')
        except Exception as e:
            print(f"   ⚠️ 启动采集失败: {e}")
    
    # 模拟盘跟踪（每次heartbeat都执行）
    print("\n📈 执行模拟盘跟踪...")
    try:
        result = subprocess.run(
            ['python3', '/root/.openclaw/workspace/tools/sim_portfolio_tracker.py'],
            capture_output=True, text=True, timeout=120
        )
        if result.returncode == 0:
            print("✅ 模拟盘跟踪完成")
            executed.append('模拟盘跟踪')
        else:
            print(f"⚠️ 模拟盘跟踪异常: {result.stderr[:200]}")
    except Exception as e:
        print(f"❌ 模拟盘跟踪失败: {e}")
    
    # 检查Git同步
    print("\n🔄 检查Git同步...")
    sync_git_to_remote()
    
    # 保存状态
    save_state(state)
    
    # 获取模拟盘状态
    portfolio_status = get_portfolio_status()
    
    # 获取数据库股票数量
    db_stock_count = get_db_stock_count()
    
    # 检查优化器报告文件
    optimizer_report = check_optimizer_report(state)
    
    # 生成全量汇报
    report = generate_full_report(now, tasks, optimizer, data_collection, portfolio_status, db_stock_count, executed)
    
    # 合并优化器报告（如果有）
    if optimizer_report:
        report += f"\n\n📈 **策略优化器最新报告**:\n{optimizer_report}"
    
    # 发送汇报
    try:
        subprocess.run(
            ['openclaw', 'message', 'send', '--target', USER_ID, '--message', report],
            capture_output=True, text=True, timeout=30
        )
        print("✅ 汇报已发送")
    except Exception as e:
        print(f"发送汇报失败: {e}")
    
    return executed

def check_optimizer_report(state):
    """检查优化器是否有新报告"""
    optimizer = state.get('optimizer', {})
    report_file = optimizer.get('report_file', '/root/.openclaw/workspace/quant/optimizer/latest_report.txt')
    last_sent = optimizer.get('last_report_sent')
    
    if not os.path.exists(report_file):
        return None
    
    # 检查文件修改时间
    mtime = os.path.getmtime(report_file)
    mtime_dt = datetime.fromtimestamp(mtime)
    
    # 如果上次发送时间存在且文件未更新，则不发送
    if last_sent:
        last_sent_dt = datetime.fromisoformat(last_sent)
        if mtime_dt <= last_sent_dt:
            return None
    
    # 读取报告内容
    try:
        with open(report_file, 'r') as f:
            content = f.read().strip()
        
        # 更新已发送时间
        optimizer['last_report_sent'] = datetime.now().isoformat()
        save_state(state)
        
        return content
    except Exception as e:
        print(f"读取优化器报告失败: {e}")
        return None

def get_portfolio_status():
    """获取模拟盘状态"""
    try:
        import json
        portfolio_file = '/root/.openclaw/workspace/data/sim_portfolio.json'
        if os.path.exists(portfolio_file):
            with open(portfolio_file, 'r') as f:
                data = json.load(f)
            positions = data.get('positions', {})
            cash = data.get('cash', 0)
            total_value = data.get('total_value', 0)
            return {
                'positions_count': len(positions),
                'cash': cash,
                'total_value': total_value,
                'return_pct': (total_value - 1000000) / 1000000 * 100 if total_value else 0
            }
    except Exception as e:
        print(f"获取模拟盘状态失败: {e}")
    return {'positions_count': 0, 'cash': 1000000, 'total_value': 1000000, 'return_pct': 0}

def get_db_stock_count():
    """获取数据库股票数量"""
    try:
        import sqlite3
        conn = sqlite3.connect('/root/.openclaw/workspace/data/historical/historical.db')
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(DISTINCT ts_code) FROM stock_factors")
        count = cursor.fetchone()[0]
        conn.close()
        return count
    except Exception as e:
        print(f"获取数据库股票数量失败: {e}")
    return 0

def format_time_ago(iso_time_str):
    """格式化时间差"""
    if not iso_time_str:
        return "从未"
    try:
        from datetime import datetime
        dt = datetime.fromisoformat(iso_time_str)
        now = datetime.now()
        diff = now - dt
        if diff.days > 0:
            return f"{diff.days}天前"
        elif diff.seconds > 3600:
            return f"{diff.seconds // 3600}小时前"
        elif diff.seconds > 60:
            return f"{diff.seconds // 60}分钟前"
        else:
            return "刚刚"
    except:
        return "未知"

def get_next_run(schedule_time_str, last_run_str):
    """计算下次运行时间"""
    if not schedule_time_str:
        return "未设置"
    try:
        from datetime import datetime, timedelta
        now = datetime.now()
        hour, minute = map(int, schedule_time_str.split(':'))
        next_run = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        
        # 如果今天已过，显示明天
        if next_run < now:
            if last_run_str and last_run_str.startswith(now.strftime('%Y-%m-%d')):
                return "今日已完成"
            next_run = next_run + timedelta(days=1)
        
        return next_run.strftime('%H:%M')
    except:
        return "未知"

def generate_full_report(now, tasks, optimizer, data_collection, portfolio_status, db_stock_count, executed):
    """生成全量汇报"""
    
    # 定时任务状态
    us_config = tasks.get('us-market-summary', {})
    ah_config = tasks.get('ah-preopen', {})
    daily_config = tasks.get('daily-report', {})
    
    # 构建汇报
    report = f"""🫘 **Heartbeat全量汇报** {now.strftime('%Y-%m-%d %H:%M:%S')}

📋 **本次执行任务**:
"""
    if executed:
        for task in executed:
            report += f"✅ {task}\n"
    else:
        report += "• 无新任务执行\n"
    
    report += f"""
⏰ **定时任务状态**:
• 美股分析 (08:30): 上次{format_time_ago(us_config.get('last_run'))} | 下次{get_next_run('08:30', us_config.get('last_run'))}
• A+H开盘 (09:15): 上次{format_time_ago(ah_config.get('last_run'))} | 下次{get_next_run('09:15', ah_config.get('last_run'))}
• 每日汇报 (15:00): 上次{format_time_ago(daily_config.get('last_run'))} | 下次{get_next_run('15:00', daily_config.get('last_run'))}

🔄 **24小时连续任务**:
• 策略优化器: 上次{format_time_ago(optimizer.get('last_run'))} | 频率: 每15分钟
• 全市场采集: 上次{format_time_ago(data_collection.get('last_run'))} | 频率: 每6小时
• 模拟盘跟踪: 每次heartbeat执行

📊 **数据库状态**:
• 已采集股票: {db_stock_count} 只 (目标: 5000+)
• 采集进度: {db_stock_count/50:.1f}%

💼 **模拟盘状态**:
• 持仓数量: {portfolio_status['positions_count']} 只
• 当前总值: ¥{portfolio_status['total_value']:,.0f}
• 总收益: {portfolio_status['return_pct']:+.2f}%
• 可用现金: ¥{portfolio_status['cash']:,.0f}

⏱️ **系统状态**: 正常运行 | Heartbeat: 每10分钟
"""
    return report

if __name__ == "__main__":
    check_and_run_tasks()
