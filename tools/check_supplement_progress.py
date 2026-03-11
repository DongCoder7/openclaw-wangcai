#!/root/.openclaw/workspace/venv/bin/python3
"""
数据回补进度监控 - 用于Heartbeat汇报
"""
import json
import sqlite3
import os
from datetime import datetime

WORKSPACE = '/root/.openclaw/workspace'
REPORT_FILE = f'{WORKSPACE}/reports/supplement_progress.json'
STATE_FILE = f'{WORKSPACE}/data/supplement_state.json'
DB_PATH = f'{WORKSPACE}/data/historical/historical.db'

def check_daemon_status():
    """检查守护进程状态"""
    pid_file = f'{WORKSPACE}/logs/supplement_daemon.pid'
    if os.path.exists(pid_file):
        with open(pid_file) as f:
            pid = f.read().strip()
        # 检查进程是否存在
        result = os.popen(f'ps -p {pid} -o pid,cmd --no-headers 2>/dev/null').read()
        if result and 'supplement_daemon' in result:
            return 'running', pid
    return 'stopped', None

def get_progress_report():
    """获取进度报告"""
    if not os.path.exists(REPORT_FILE):
        return None
    with open(REPORT_FILE) as f:
        return json.load(f)

def get_db_stats():
    """获取数据库统计"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    stats = {}
    for year in [2018, 2019, 2020, 2021, 2022, 2023, 2024, 2025]:
        cursor.execute("""
            SELECT COUNT(*), COUNT(DISTINCT ts_code) 
            FROM fina_tushare 
            WHERE period LIKE ?
        """, (f'{year}%',))
        records, stocks = cursor.fetchone()
        stats[str(year)] = {'records': records, 'stocks': stocks}
    
    conn.close()
    return stats

def format_report():
    """格式化报告"""
    status, pid = check_daemon_status()
    progress = get_progress_report()
    db_stats = get_db_stats()
    
    lines = []
    lines.append("=" * 60)
    lines.append("📊 数据回补进度监控")
    lines.append("=" * 60)
    
    # 守护进程状态
    lines.append(f"\n【守护进程状态】")
    lines.append(f"  状态: {'🟢 运行中' if status == 'running' else '🔴 已停止'}")
    if pid:
        lines.append(f"  PID: {pid}")
    
    # 年度数据进度
    lines.append(f"\n【年度数据进度】")
    target_stocks = 5000
    for year in ['2018', '2019', '2020', '2021', '2022', '2023', '2024', '2025']:
        data = db_stats.get(year, {'records': 0, 'stocks': 0})
        records = data['records']
        stocks = data['stocks']
        percent = (stocks / target_stocks) * 100 if target_stocks > 0 else 0
        bar = '█' * int(percent / 10) + '░' * (10 - int(percent / 10))
        lines.append(f"  {year}: {bar} {stocks}/{target_stocks}只 ({percent:.1f}%) | {records}条")
    
    # 本批次进度
    if progress:
        lines.append(f"\n【最新进度】")
        lines.append(f"  更新时间: {progress.get('timestamp', 'N/A')}")
    
    # 启动建议
    if status == 'stopped':
        lines.append(f"\n⚠️ 守护进程已停止，建议重启:")
        lines.append(f"  cd /root/.openclaw/workspace && source venv_activate.sh && source .tushare.env && nohup python3 tools/supplement_daemon.py > logs/supplement_daemon.out 2>&1 &")
    
    lines.append("=" * 60)
    
    return '\n'.join(lines)

if __name__ == '__main__':
    print(format_report())
