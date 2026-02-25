---
name: us-market-analysis
description: |
  美股市场深度分析，每日生成美股板块、个股行情报告。
  使用场景：
  1. 定时生成美股隔夜分析报告（每日8:30）
  2. 手动触发美股市场分析
  3. 获取美股板块强弱排序、亮点个股、拖累因素
  4. 为A股开盘提供策略启示
  
  分析内容包括：
  - 主要指数表现（道琼斯、纳斯达克、标普500）
  - 10大板块强弱排序（光通讯、半导体、AI算力、科技巨头等）
  - 亮点个股（涨幅前5）
  - 拖累因素（跌幅前5）
  - 对A股开盘策略启示
  
  触发关键词：美股分析、美股报告、US market、us-market-summary
---

# 美股市场深度分析

## 功能

生成完整的美股市场分析报告，包括：

1. **主要指数表现** - 道琼斯、纳斯达克、标普500
2. **板块强弱排序** - 10大板块按涨跌幅排名
3. **亮点个股** - 涨幅前5的股票
4. **拖累因素** - 跌幅前5的股票
5. **策略启示** - 对A股开盘的策略建议

## 使用方法

### 定时任务
```bash
# 每日8:30自动运行
30 8 * * * python3 ~/.openclaw/workspace/skills/us-market-analysis/scripts/generate_report.py
```

### 手动触发
```bash
python3 ~/.openclaw/workspace/skills/us-market-analysis/scripts/generate_report.py
```

### 用户指令
- "生成美股报告"
- "分析美股市场"
- "美股隔夜总结"
- "US market summary"

## 数据源

- 腾讯财经API（美股个股行情）
- 覆盖10大板块、50+只美股

## 输出格式

```
✅ 美股市场深度分析任务完成
报告生成时间: 2026-02-24 08:30:00
数据日期: 2026-02-23（前一交易日）

📊 核心摘要

主要指数:
• 🔻 道琼斯: -1.66%
• 📉 纳斯达克: -1.13%
...

板块强弱排序:
1. 🥇 📈 光通讯 +0.87% （应用光电 +4.41%领涨）
2. 🥈 📈 能源 +0.84%
...

🔥 关键发现

亮点个股:
• 🚀 礼来 (LLY): +4.86%
...

拖累因素:
• 🔻 诺和诺德 (NVO): -16.43%
...

💡 对A股开盘策略启示
• 🔴 美股科技股下跌，A股科技板块可能承压
...
```

## 板块列表

| 板块 | 代表个股 |
|------|----------|
| 光通讯 | ANET, LITE, CIEN |
| 半导体 | NVDA, AMD, TSM, ASML |
| AI算力 | NVDA, AVGO, MRVL |
| 科技巨头 | AAPL, MSFT, GOOGL, META |
| 生物医药 | LLY, NVO, JNJ |
| 存储/数据中心 | WDC, SNOW, NET |
| 能源 | XOM, CVX, COP |
| 金融 | V, MA, JPM |
| 消费 | WMT, COST, HD |
| 中概互联 | BABA, JD, PDD |

## 产出文件

- 报告保存：`~/.openclaw/workspace/data/us_market_daily_YYYYMMDD.md`
- 发送记录：`~/.openclaw/workspace/tools/us_market_send.log`
