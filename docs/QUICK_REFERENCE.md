# 快速参考卡片

## 常用命令

### 环境加载
```bash
cd ~/.openclaw/workspace
source setup_env.sh
```

### 产业链分析
```python
from skills.dounai_investment_system import DounaiSystem
system = DounaiSystem()
result = system.analyze_industry("存储芯片")
```

### 个股分析
```python
from skills.dounai_investment_system import DounaiSystem
system = DounaiSystem()
result = system.analyze_stock("301421.SZ")
```

### 实时行情
```python
from tools.longbridge_api import get_longbridge_api
api = get_longbridge_api()
print(api.get_quote("002371.SZ"))
```

### 知识星球搜索
```python
from tools.zsxq_fetcher import search_industry_info
results = search_industry_info("存储芯片", count=10)
```

---

## 定时任务

| 时间 | 任务 | 输出 |
|:-----|:-----|:-----|
| 08:30 | 美股报告 | 飞书消息 |
| 09:15 | A+H开盘 | 飞书消息 |
| 15:00 | 收盘报告 | 飞书消息 |
| 每2小时 | 知识星球 | 本地日志 |
| 每15分钟 | 优化器 | 本地报告 |

---

## 文件位置

| 类型 | 路径 |
|:-----|:-----|
| 报告 | `data/*_YYYYMMDD.md` |
| 日志 | `logs/*.log` |
| 配置 | `.longbridge.env` |
| 主控 | `skills/dounai-investment-system/` |

---

## 故障排查

| 问题 | 解决 |
|:-----|:-----|
| 长桥API失败 | 检查 `.longbridge.env` |
| 知识星球14001 | 等待30秒重试 |
| 飞书推送失败 | 查看日志，手动发送 |

---

**保存到书签，随时查阅！** 📌
