#!/root/.openclaw/workspace/venv/bin/python3
"""
收盘报告发送脚本
读取生成的报告文件并发送给用户
"""
import os
import sys
from datetime import datetime

WORKSPACE = '/root/.openclaw/workspace'
USER_ID = 'ou_efbad805767f4572e8f93ebafa8d5402'

def log(msg):
    timestamp = datetime.now().strftime('%H:%M:%S')
    print(f"[{timestamp}] {msg}")
    sys.stdout.flush()

def send_report():
    today = datetime.now().strftime('%Y%m%d')
    report_path = f"{WORKSPACE}/data/daily_report_{today}.md"
    
    if not os.path.exists(report_path):
        log(f"❌ 报告文件不存在: {report_path}")
        return False
    
    try:
        with open(report_path, 'r', encoding='utf-8') as f:
            report_content = f.read()
        
        # 限制消息长度
        if len(report_content) > 8000:
            # 提取关键部分
            lines = report_content.split('\n')
            summary = []
            for line in lines[:100]:  # 前100行
                summary.append(line)
            report_content = '\n'.join(summary) + "\n\n... (报告已截断，完整内容请查看文件)"
        
        # 使用 openclaw message 发送
        import subprocess
        result = subprocess.run(
            ['openclaw', 'message', 'send', '--channel', 'feishu', '--target', USER_ID, '--message', report_content],
            capture_output=True, text=True, timeout=60
        )
        
        if result.returncode == 0:
            log(f"✅ 报告发送成功: {report_path}")
            return True
        else:
            log(f"❌ 发送失败: {result.stderr}")
            return False
            
    except Exception as e:
        log(f"❌ 发送异常: {e}")
        return False

if __name__ == '__main__':
    log("📤 开始发送收盘报告...")
    success = send_report()
    sys.exit(0 if success else 1)
