# 启动检查清单 - 每次会话开始时必须执行

## ✅ 必须读取的文件
- [ ] SOUL.md — 确认身份和行为准则
- [ ] MEMORY.md — 查看重要决策和规范
- [ ] HEARTBEAT.md — 如果有的话，了解当前任务

## 🐍 Python/venv 检查（极其重要！）
- [ ] **venv路径**: `/root/.openclaw/workspace/venv/bin/python3`
- [ ] **runner脚本**: `./venv_runner.sh`
- [ ] **环境变量**: `.longbridge.env` (长桥API需要)

### ⚠️ 运行Python代码前必须自问：
1. 我使用的是venv Python吗？
2. 脚本shebang正确吗？`#!/root/.openclaw/workspace/venv/bin/python3`
3. 需要长桥API吗？→ 使用 `./venv_runner.sh`

### 禁止事项
- ❌ `python3 script.py`
- ❌ `/usr/bin/python3 script.py`

### 正确示例
```bash
# 推荐：自动处理环境变量
./venv_runner.sh tools/script.py

# 直接指定venv Python
/root/.openclaw/workspace/venv/bin/python3 tools/script.py

# 激活后运行
source venv/bin/activate && python3 tools/script.py
```

## 📋 当前项目状态（2026-03-04）

### 数据回补
- 2026年价格数据: ✅ 191,261条
- 2026年估值数据: ✅ 185,787条
- 2026年因子数据: 🔄 计算中
- 2018-2025历史: 🔄 回补中

### 定时任务
- 08:30 美股报告
- 09:30 A+H开盘前瞻
- 15:00 收盘深度报告
- 15:30 模拟盘交易
- 16:00 数据更新
- 23:30 知识星球抓取

## 🔑 关键路径
- Workspace: `/root/.openclaw/workspace`
- Data: `/root/.openclaw/workspace/data`
- Tools: `/root/.openclaw/workspace/tools`
- Skills: `/root/.openclaw/workspace/skills`
- venv: `/root/.openclaw/workspace/venv`

## 📝 记忆原则
- **文本 > 大脑** — 重要信息写入文件
- **检查 > 假设** — 不确定就检查
- **venv > 系统Python** — 绝对使用venv
