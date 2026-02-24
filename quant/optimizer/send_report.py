#!/usr/bin/env python3
"""发送优化报告到Feishu"""
import json
from datetime import datetime
import os

REPORT_FILE = '/root/.openclaw/workspace/quant/optimizer/latest_report.txt'
USER_ID = 'ou_efbad805767f4572e8f93ebafa8d5402'

def send_report():
    try:
        if not os.path.exists(REPORT_FILE):
            print(f"报告文件不存在: {REPORT_FILE}")
            return False
            
        with open(REPORT_FILE, 'r') as f:
            report = f.read()
        
        if not report.strip():
            print("报告内容为空")
            return False
        
        # 使用OpenClaw的消息工具发送
        import subprocess
        result = subprocess.run([
            'openclaw', 'message', 'send',
            '--to', USER_ID,
            '--message', report
        ], capture_output=True, text=True, timeout=30)
        
        if result.returncode == 0:
            print(f"✅ 汇报已发送 ({datetime.now().strftime('%H:%M:%S')})")
            return True
        else:
            print(f"发送失败: {result.stderr}")
            return False
            
    except Exception as e:
        print(f"错误: {e}")
        return False

if __name__ == "__main__":
    send_report()
