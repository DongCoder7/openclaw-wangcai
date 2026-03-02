# 虚拟环境使用指南 (Venv Guide)

## 概述

本项目使用Python虚拟环境(venv)来管理依赖，确保不同Skill的库版本兼容。

## 快速开始

### 1. 激活虚拟环境

```bash
source /root/.openclaw/workspace/venv_activate.sh
```

或手动激活：

```bash
source /root/.openclaw/workspace/venv/bin/activate
```

### 2. 验证激活成功

```bash
which python3
# 输出: /root/.openclaw/workspace/venv/bin/python3

python3 --version
# 输出: Python 3.12.3
```

### 3. 运行Python脚本

```bash
# 方式1: 使用完整路径
/root/.openclaw/workspace/venv/bin/python3 your_script.py

# 方式2: 激活后运行
source /root/.openclaw/workspace/venv_activate.sh
python3 your_script.py
```

### 4. 退出虚拟环境

```bash
deactivate
```

## 在Shebang中指定解释器

所有Python脚本文件头部应添加：

```python
#!/root/.openclaw/workspace/venv/bin/python3
```

这样可以确保直接运行脚本时使用正确的Python版本：

```bash
./your_script.py  # 自动使用venv中的Python
```

## 在代码中动态添加路径

```python
#!/root/.openclaw/workspace/venv/bin/python3
import sys

# 添加Skill路径
sys.path.insert(0, '/root/.openclaw/workspace/skills/sector-analysis/scripts')
sys.path.insert(0, '/root/.openclaw/workspace/skills/quant-data-system/scripts')

# 导入模块
from sector_analyzer import analyze_sector
from qteasy_integration import QteasyIntegration
```

## 安装新依赖

```bash
source /root/.openclaw/workspace/venv_activate.sh
pip install 包名

# 更新requirements.txt
pip freeze > /root/.openclaw/workspace/requirements.txt
```

## 关键依赖版本

| 包 | 版本 | 用途 |
|:---|:---|:---|
| qteasy | 1.4.11 | 快速回测、组合优化 |
| pandas | 3.0.1 | 数据处理 |
| numpy | 2.4.2 | 数值计算 |
| tushare | 1.4.24 | 财经数据 |
| akshare | 1.18.30 | 财经数据 |
| requests | 2.32.5 | HTTP请求 |

## Skill特定的Python版本要求

| Skill | 是否依赖qteasy | 必须在venv中运行 |
|:---|:---:|:---:|
| sector-analysis | ✅ | 是 |
| quant-data-system | ✅ (部分功能) | 建议 |
| dounai-investment-system | ✅ (部分功能) | 建议 |
| industry-chain-analysis | ❌ | 否 |
| a-stock-analysis | ❌ | 否 |

## 故障排除

### 问题: ModuleNotFoundError: No module named 'qteasy'

**原因**: 使用了系统Python而非venv

**解决**:
```bash
# 确保激活venv
source /root/.openclaw/workspace/venv_activate.sh

# 或使用完整路径
/root/.openclaw/workspace/venv/bin/python3 your_script.py
```

### 问题: 脚本头部shebang不生效

**原因**: 文件缺少执行权限

**解决**:
```bash
chmod +x your_script.py
./your_script.py
```

### 问题: pip安装的包找不到

**原因**: 可能安装到了系统Python

**解决**:
```bash
# 确保使用venv的pip
which pip
# 应该输出: /root/.openclaw/workspace/venv/bin/pip

# 如果不正确，重新激活venv
source /root/.openclaw/workspace/venv_activate.sh
```

## 在Heartbeat/Cron中使用venv

```bash
#!/bin/bash
# 在定时任务脚本中激活venv

source /root/.openclaw/workspace/venv_activate.sh

# 运行你的脚本
python3 /root/.openclaw/workspace/skills/quant-data-system/scripts/your_script.py
```

## 参考文档

- [SKILL.md - sector-analysis](../skills/sector-analysis/SKILL.md)
- [SKILL.md - quant-data-system](../skills/quant-data-system/SKILL.md)
- [requirements.txt](../requirements.txt)

---

*更新日期: 2026-03-02*
