# Venv运行规范 - 固化文档

## 核心原则

**所有Python代码必须使用venv运行，禁止直接使用系统Python**

---

## 已实施的固化措施

### 1. 文档约束
- **AGENTS.md** - 添加了"Python运行强制规范"章节
- **SOUL.md** - 主身份文件（如需要）
- **SKILL.md** - 相关技能文件

### 2. 运行工具
- **venv_runner.sh** - 通用运行脚本，自动加载环境变量
- **venv_aliases.sh** - Bash别名快捷方式

### 3. 脚本规范
所有新创建的Python脚本必须包含：
```python
#!/root/.openclaw/workspace/venv/bin/python3
"""
脚本说明
"""
import sys
sys.path.insert(0, '/root/.openclaw/workspace/tools')
# ... 代码
```

---

## 使用方式

### 方式1: venv_runner.sh (最推荐)
```bash
./venv_runner.sh tools/daily_market_report.py
./venv_runner.sh skills/us-market-analysis/scripts/generate_report_longbridge.py
```

### 方式2: 快捷别名 (添加到 ~/.bashrc)
```bash
source /root/.openclaw/workspace/venv_aliases.sh
vrun tools/script.py
```

### 方式3: 直接指定路径
```bash
/root/.openclaw/workspace/venv/bin/python3 tools/script.py
```

### 方式4: 激活venv
```bash
source /root/.openclaw/workspace/venv/bin/activate
python3 tools/script.py
deactivate
```

---

## 环境变量加载

长桥API需要的环境变量：
```bash
export $(grep -v '^#' /root/.openclaw/workspace/.longbridge.env | xargs)
```

venv_runner.sh会自动加载此文件。

---

## venv包含的关键包

| 包名 | 用途 |
|-----|-----|
| longport | 长桥API SDK |
| efinance | A股实时行情 |
| tushare | 金融数据 |
| qteasy | 量化交易 |
| pandas | 数据处理 |
| numpy | 数值计算 |

---

## 检查清单

创建/修改Python脚本前：
- [ ] shebang是否指向venv python？
- [ ] 是否需要加载.longbridge.env？
- [ ] 是否使用了venv_runner.sh测试？

---

## 错误示例 ❌

```bash
# 错误！直接使用系统python
python3 tools/script.py

# 错误！未加载环境变量
/root/.openclaw/workspace/venv/bin/python3 tools/longbridge_script.py
```

## 正确示例 ✅

```bash
# 正确！使用venv_runner
./venv_runner.sh tools/script.py

# 正确！手动加载环境变量
export $(grep -v '^#' .longbridge.env | xargs)
./venv_runner.sh tools/longbridge_script.py
```

---

*创建于: 2026-03-04*
*更新: 固化venv运行规范*
