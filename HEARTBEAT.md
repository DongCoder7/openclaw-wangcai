# HEARTBEAT.md - 心跳机制任务调度

> **前置要求：阅读本md前，必须先读取 `SOUL.md` 确认身份和行为准则。**

---

> **检查要求：检查下方配置，并根据配置时间和脚本以及产出目录判断是否生成了报告，如果已经生成就马上发送，注意有不同的feishu user_id配置**

---

## 定时任务配置

| 时间 | 任务名称 | 执行脚本 | 超时时间 | 汇报方式 |
|:---:|:---|:---|:---:|:---|
| 08:00 | 知识星球日终抓取 | `读取并发送` | 10分钟 | 读取 最新的data/zswq/raw/YYYYMMDD_51111818455824和YYYYMMDD_88512145458842文件，并发给我，注意channel是feishu，user_id是：ou_efbad805767f4572e8f93ebafa8d5402
| 08:30 | 美股隔夜总结 | `skills/us-market-analysis/scripts/generate_report_longbridge.py` | 10分钟 | 即时发送结果 |
| 09:30 | A+H开盘前瞻 | `skills/ah-market-preopen/scripts/generate_report_longbridge.py` | 10分钟 | 即时发送结果 |
| 15:05 | 收盘深度报告生成 | `skills/daily-market-report/scripts/generate_report.py` | 10分钟 | Linux Cron执行 |
| 15:10 | 收盘报告发送 | Heartbeat读取并发送 | 5分钟 | 读取data/daily_report_YYYYMMDD.md发送 |
| 19:35 | 飞书多维表格URL提取 | `tools/daily_feishu_url_extractor.py` | 10分钟 | 提取表格所有记录中的URL，发送至feishu，user_id: ou_efbad805767f4572e8f93ebafa8d5402 |
| 22:30 | 知识星球日终抓取 | `读取并发送` | 10分钟 | 读取 最新的data/zswq/raw/YYYYMMDD_51111818455824和YYYYMMDD_88512145458842文件，并发给我，注意channel是feishu，user_id是：ou_efbad805767f4572e8f93ebafa8d5402 |


## Git同步要求

**每次Heartbeat执行后必须进行Git同步**:
1. 检查工作区变更 (`git status --porcelain`)
2. 添加所有变更 (`git add -A`)
3. 提交变更 (`git commit -m "HH:MM Heartbeat"`)
4. 推送到远程 (`git push`)

---


*版本: v3.1 - 增加飞书多维表格URL提取任务*
*更新: 2026-04-07*
