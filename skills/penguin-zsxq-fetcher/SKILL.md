# 企鹅的知识星球抓取 Skill

## 概述

专门用于抓取**企鹅的两个知识星球Group**，合并输出到一个文件。

**目标Group**:
- 新Group (ID: 51111818455824)
- 新Group2 (ID: 88512145458842)

**特点**:
- 两个Group使用**相同token**
- 数据**合并到一个文件**
- 生成**统一汇总报告**
- 自动按作者分组统计

---

## 使用方法

### 直接运行

```bash
cd /root/.openclaw/workspace
./venv_runner.sh skills/penguin-zsxq-fetcher/scripts/fetcher.py
```

### 定时任务

```bash
# 每日23:00自动执行
openclaw cron create \
  --name "penguin-zsxq-fetcher" \
  --cron "0 23 * * *" \
  --tz "Asia/Shanghai" \
  --agent main \
  --session isolated \
  --message "cd /root/.openclaw/workspace && ./venv_runner.sh skills/penguin-zsxq-fetcher/scripts/fetcher.py" \
  --timeout-seconds 600 \
  --announce \
  --exact
```

---

## 输出文件

| 类型 | 路径 |
|:---|:---|
| **合并数据** | `data/zsxq/raw/YYYYMMDD_penguin_merged.json` |
| **汇总报告** | `data/zsxq/summary_YYYYMMDD_penguin.md` |

---

## 数据结构

### JSON格式

```json
[
  {
    "group_id": "51111818455824",
    "group_name": "新Group",
    "topics": [...],
    "fetch_time": "2026-03-10T22:00:00"
  },
  {
    "group_id": "88512145458842",
    "group_name": "新Group2",
    "topics": [...],
    "fetch_time": "2026-03-10T22:00:30"
  }
]
```

### 报告内容

- Group数据统计
- 作者发帖统计
- 热点关键词分析
- 市场情绪分析
- 明日关注方向

---

## 配置

**Token位置**: `.zsxq.env` 或环境变量 `ZSXQ_COOKIE`

**默认Token**: `AD5BC203-E94C-4B32-9BA2-6BFD0C435426_C1F959E538CA66E8`

---

## 版本历史

| 版本 | 时间 | 说明 |
|:---|:---|:---|
| v1.0 | 2026-03-10 | 初始版本，支持两个Group合并抓取 |

---

*Skill名称: 企鹅的知识星球抓取*  
*作者: Assistant*  
*最后更新: 2026-03-10*
