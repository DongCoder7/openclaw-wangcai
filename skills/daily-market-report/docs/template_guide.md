# 收盘报告Skill - 使用指南

## 快速开始

### 生成今日收盘报告

```bash
cd /root/.openclaw/workspace
./venv_runner.sh skills/daily-market-report/scripts/generate_report.py
```

### 查看生成的报告

```bash
cat data/daily_report_$(date +%Y%m%d).md
```

## 报告内容

报告包含8大模块：

1. **外围市场环境** - 美股、港股、地缘政治
2. **A股市场全景** - 涨跌分布、成交额
3. **板块表现** - 科创板/创业板/主板/北交所
4. **热点新闻** - Exa实时搜索
5. **龙虎榜数据** - 机构净买入/卖出TOP5
6. **涨幅榜 TOP10**
7. **跌幅榜 TOP10**
8. **明日展望与操作建议**

## 定时任务

已配置在 HEARTBEAT.md 中：
- **时间**: 每日15:05
- **脚本**: `skills/daily-market-report/scripts/generate_report.py`
- **输出**: `data/daily_report_YYYYMMDD.md`

## 数据源

| 数据 | 来源 | 备用 |
|:---|:---|:---|
| A股行情 | 长桥API | efinance |
| 美股/港股 | 腾讯API | - |
| 新闻 | Exa搜索 | 新浪财经 |
| 龙虎榜 | Akshare | - |

## 故障排除

### 长桥API失败
- 检查 `.longbridge.env` 是否存在
- 检查token是否过期

### Exa搜索失败
- 检查 mcporter 是否安装: `mcporter config list`
- 检查 exa 配置: `mcporter config list | grep exa`

### Akshare失败
- 更新akshare: `pip install akshare --upgrade`

## 自定义

修改 `scripts/generate_report.py` 中的参数：

```python
# 调整Exa搜索关键词
news_queries = [
    "A股今日行情",
    "美股最新走势", 
    # 添加自定义关键词...
]

# 调整龙虎榜统计数量
longhu_buy.head(10)  # 改为TOP10
```

## 输出示例

```
📊 A股收盘深度报告 (20260304)
数据来源: 长桥API + Exa搜索 + Akshare | 统计: 5190只

【一、外围市场环境】
🇺🇸 美股隔夜行情:
🟢 道琼斯: 48501.27 (-403.51, -0.83%)
🟢 纳斯达克: 22516.69 (-232.17, -1.02%)
🟢 标普500: 6816.63 (-64.99, -0.94%)
...
```

## 相关文件

- `SKILL.md` - Skill说明文档
- `scripts/generate_report.py` - 主脚本
- `docs/template_guide.md` - 本文件
- `../../data/daily_report_*.md` - 生成的报告

## 更新日志

### v6.0 (2026-03-04)
- 初始版本发布
- 8大模块完整实现
- Skill化封装
