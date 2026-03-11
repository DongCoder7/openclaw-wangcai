# Venv运行快捷命令
# 添加到 ~/.bashrc 或 ~/.zshrc 中使用

# 快速使用venv运行python脚本
alias vrun='/root/.openclaw/workspace/venv_runner.sh'

# 激活venv
alias venv='source /root/.openclaw/workspace/venv/bin/activate'

# 直接调用venv python
alias vpy='/root/.openclaw/workspace/venv/bin/python3'

# 示例用法:
# vrun tools/daily_market_report.py
# vrun skills/us-market-analysis/scripts/generate_report_longbridge.py
# vpy -c "import longport; print('OK')"
