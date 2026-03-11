#!/root/.openclaw/workspace/venv/bin/python3
"""
Heartbeat调度器 v2.0 - 带错过任务补偿
确保定时任务即使被跳过也能自动补执行
"""
import os, sys, json, sqlite3
from datetime import datetime, timedelta
import time

WORKSPACE = '/root/.openclaw/workspace'
DB_PATH = f'{WORKSPACE}/data/historical/historical.db'
STATE_FILE = f'{WORKSPACE}/data/heartbeat_task_state.json'

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")
    sys.stdout.flush()

def load_task_state():
    """加载任务执行状态"""
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, 'r') as f:
            return json.load(f)
    return {}

def save_task_state(state):
    """保存任务执行状态"""
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f)

def get_today_tasks():
    """获取今日所有定时任务"""
    return [
        {'time': '08:30', 'name': '美股隔夜总结', 'script': 'skills/us-market-analysis/scripts/generate_report_longbridge.py', 'window': 60},
        {'time': '09:30', 'name': 'A+H开盘前瞻', 'script': 'skills/ah-market-preopen/scripts/generate_report_longbridge.py', 'window': 60},
        {'time': '15:00', 'name': '收盘深度报告', 'script': 'tools/daily_market_report.py', 'window': 30},
        {'time': '15:30', 'name': '模拟盘交易', 'script': 'skills/quant-data-system/scripts/sim_portfolio.py', 'window': 30},
        {'time': '16:00', 'name': '当日数据更新', 'script': 'data/supplement_daily.py', 'window': 120},
        {'time': '23:30', 'name': '知识星球日终', 'script': 'tools/zsxq_fetcher_prod.py', 'window': 60},
    ]

def check_missed_tasks():
    """检查并补偿错过的任务"""
    now = datetime.now()
    today_str = now.strftime('%Y-%m-%d')
    state = load_task_state()
    
    # 获取今天的任务状态
    today_state = state.get(today_str, {})
    
    missed_tasks = []
    for task in get_today_tasks():
        task_time = datetime.strptime(f"{today_str} {task['time']}", '%Y-%m-%d %H:%M')
        window = timedelta(minutes=task['window'])
        
        # 检查是否已执行
        task_key = f"{task['time']}_{task['name']}"
        if task_key in today_state:
            continue  # 已执行
        
        # 检查是否已过时间窗口
        if now > task_time + window:
            # 错过了，但还在当日，可以补偿
            if now.date() == task_time.date():
                missed_tasks.append(task)
                log(f"⚠️ 发现错过任务: {task['time']} {task['name']}")
    
    return missed_tasks

def run_task(task):
    """执行单个任务"""
    import subprocess
    log(f"🚀 执行任务: {task['name']}")
    
    try:
        script_path = f"{WORKSPACE}/{task['script']}"
        if not os.path.exists(script_path):
            log(f"❌ 脚本不存在: {script_path}")
            return False
        
        # 后台执行
        subprocess.Popen(
            ['python3', script_path],
            stdout=open(f"{WORKSPACE}/logs/task_{task['name']}_{datetime.now().strftime('%H%M')}.log", 'w'),
            stderr=subprocess.STDOUT,
            start_new_session=True
        )
        
        log(f"✅ {task['name']} 已启动")
        return True
        
    except Exception as e:
        log(f"❌ {task['name']} 执行失败: {e}")
        return False

def mark_task_executed(task):
    """标记任务已执行"""
    today_str = datetime.now().strftime('%Y-%m-%d')
    state = load_task_state()
    
    if today_str not in state:
        state[today_str] = {}
    
    task_key = f"{task['time']}_{task['name']}"
    state[today_str][task_key] = {
        'executed_at': datetime.now().isoformat(),
        'status': 'done'
    }
    
    save_task_state(state)

def get_current_task():
    """获取当前应该执行的任务"""
    now = datetime.now()
    current_time = now.strftime('%H:%M')
    current_hour = now.hour
    current_minute = now.minute
    
    for task in get_today_tasks():
        task_hour, task_minute = map(int, task['time'].split(':'))
        # 检查是否在任务时间窗口内（前后2分钟）
        task_datetime = now.replace(hour=task_hour, minute=task_minute, second=0, microsecond=0)
        time_diff = abs((now - task_datetime).total_seconds())
        
        if time_diff <= 120:  # 2分钟窗口
            return task
    
    return None

def main():
    log("="*60)
    log("Heartbeat调度器 v2.0 - 带错过任务补偿")
    log("="*60)
    
    now = datetime.now()
    log(f"当前时间: {now.strftime('%H:%M:%S')}")
    
    # 1. 检查错过的任务并补偿
    log("检查错过任务...")
    missed = check_missed_tasks()
    if missed:
        log(f"发现 {len(missed)} 个错过任务，开始补偿...")
        for task in missed:
            if run_task(task):
                mark_task_executed(task)
                time.sleep(2)  # 避免同时启动多个
    else:
        log("✅ 无错过任务")
    
    # 2. 检查当前是否应该执行任务
    current_task = get_current_task()
    if current_task:
        log(f"⏰ 当前任务: {current_task['time']} {current_task['name']}")
        if run_task(current_task):
            mark_task_executed(current_task)
    else:
        next_task = None
        for task in get_today_tasks():
            task_time = datetime.strptime(task['time'], '%H:%M')
            if task_time.hour > now.hour or (task_time.hour == now.hour and task_time.minute > now.minute):
                next_task = task
                break
        if next_task:
            log(f"下一任务: {next_task['time']} {next_task['name']}")
        else:
            log("今日任务全部完成")
    
    # 3. 数据回补进度汇报（整点）
    if now.minute <= 5:
        check_data_progress()
    
    log("="*60)
    log("完成")

def check_data_progress():
    """检查数据回补进度"""
    log("📊 数据回补进度检查...")
    
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        
        # 检查各年份数据
        c.execute('''
            SELECT substr(trade_date,1,4) as year, COUNT(DISTINCT trade_date) as days
            FROM daily_price GROUP BY year ORDER BY year
        ''')
        results = c.fetchall()
        conn.close()
        
        for year, days in results:
            if int(year) >= 2018:
                log(f"  {year}年: {days}天")
                
    except Exception as e:
        log(f"进度检查失败: {e}")

if __name__ == '__main__':
    main()
