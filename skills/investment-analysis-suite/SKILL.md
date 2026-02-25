---
name: investment-analysis-suite
description: |
  投资策略分析套件 - 统一调度入口
  
  整合所有分析功能，通过统一接口调用：
  1. 产业链深度分析 (industry-chain-analysis)
  2. 美股市场分析 (us-market-analysis)
  3. A+H开盘前瞻 (ah-market-preopen)
  4. 个股深度分析 (a-stock-analysis)
  5. 知识星球信息获取 (zsxq-fetcher)
  6. 实时行情查询 (longbridge-api)
  
  触发方式：
  - 用户说"分析存储芯片产业链" → 自动调用产业链分析
  - 用户说"生成美股报告" → 自动调用美股分析
  - 用户说"获取实时行情" → 自动调用长桥API
  - 用户说"知识星球存储" → 自动获取调研信息
---

# 投资策略分析套件

## 统一调用接口

### 1. 产业链分析

**触发词**: 分析产业链、存储芯片分析、PCB分析

**调用方式**:
```python
from skills.investment_analysis_suite import analyze_industry_chain

result = analyze_industry_chain(
    industry="存储芯片",
    include_zsxq=True,      # 包含知识星球信息
    include_factors=True,   # 包含v26因子分析
    generate_report=True    # 生成完整报告
)
```

**输出**: 完整产业链分析报告 + 投资组合建议

---

### 2. 美股市场分析

**触发词**: 美股报告、隔夜美股、US market summary

**调用方式**:
```python
from skills.investment_analysis_suite import generate_us_report

report = generate_us_report(
    send_message=True,      # 自动发送报告
    save_file=True          # 保存到文件
)
```

**定时任务**: 每日8:30自动执行

---

### 3. A+H开盘前瞻

**触发词**: 开盘报告、A+H分析、盘前策略

**调用方式**:
```python
from skills.investment_analysis_suite import generate_ah_preopen

report = generate_ah_preopen(
    include_us_review=True,  # 包含美股回顾
    send_message=True
)
```

**定时任务**: 每日9:15自动执行

---

### 4. 实时行情查询

**触发词**: 查股价、实时行情、股票涨跌

**调用方式**:
```python
from skills.investment_analysis_suite import get_quotes

quotes = get_quotes([
    "002371.SZ",  # 北方华创
    "688012.SH",  # 中微公司
    "AAPL.US",    # 苹果
])
```

---

### 5. 知识星球信息

**触发词**: 知识星球、调研纪要、行业调研

**调用方式**:
```python
from skills.investment_analysis_suite import search_zsxq

results = search_zsxq(
    keyword="存储芯片",
    count=10
)
```

---

### 6. 投资组合分析

**触发词**: 分析组合、建仓建议、持仓诊断

**调用方式**:
```python
from skills.investment_analysis_suite import analyze_portfolio

analysis = analyze_portfolio(
    stocks=["002371", "688012", "688525"],
    include_factors=True,
    suggest_positions=True
)
```

---

## 自动化任务配置

### Heartbeat集成

在 `HEARTBEAT.md` 中配置：

```python
# 心跳任务自动执行
from skills.investment_analysis_suite import run_scheduled_tasks

# 根据时间自动判断执行哪个任务
run_scheduled_tasks(
    current_time="08:30"  # 自动执行美股报告
)
```

### 定时任务映射

| 时间 | 自动调用 |
|:-----|:---------|
| 08:30 | `generate_us_report()` |
| 09:15 | `generate_ah_preopen()` |
| 每2小时 | `fetch_zsxq_latest()` |
| 每15分钟 | `run_optimizer()` |

---

## 使用示例

### 场景1: 存储芯片投资分析
```python
# 一键完成完整分析
from skills.investment_analysis_suite import full_analysis

result = full_analysis(
    industry="存储芯片",
    include_zsxq=True,
    include_quotes=True,
    generate_portfolio=True
)

# 输出：
# 1. 知识星球最新调研信息
# 2. 产业链上下游分析
# 3. 实时行情 + v26因子评分
# 4. 推荐组合 + 建仓建议
```

### 场景2: 每日开盘前准备
```python
from skills.investment_analysis_suite import morning_briefing

briefing = morning_briefing(
    include_us=True,        # 美股隔夜
    include_ah=True,        # A+H前瞻
    include_zsxq=True,      # 最新调研
    include_portfolio=True  # 持仓建议
)

# 自动发送综合简报
```

### 场景3: 实时监控
```python
from skills.investment_analysis_suite import monitor_stocks

# 监控持仓股票
monitor_stocks(
    stocks=["002371", "688012", "688525"],
    alert_conditions={
        "price_change": 5,      # 涨跌超5%告警
        "volume_spike": 2,      # 成交量放大2倍
    }
)
```

---

## 扩展接口

### 添加新的分析模块

```python
# 在 skills/investment_analysis_suite/__init__.py 中添加

def analyze_new_sector(sector_name: str):
    """新增板块分析"""
    # 1. 获取知识星球信息
    zsxq_data = search_zsxq(sector_name)
    
    # 2. 获取实时行情
    quotes = get_sector_quotes(sector_name)
    
    # 3. v26因子评分
    factors = calculate_factors(quotes)
    
    # 4. 生成报告
    return generate_report(zsxq_data, quotes, factors)
```

---

## 依赖配置

### 环境变量
```bash
# 已配置在 .longbridge.env
LONGPORT_APP_KEY=xxx
LONGPORT_APP_SECRET=xxx
LONGPORT_ACCESS_TOKEN=xxx

# 已配置在 .tushare.env (可选)
TUSHARE_TOKEN=xxx
```

### Python依赖
```bash
pip install longport  # 长桥API
pip install requests  # HTTP请求
pip install pandas    # 数据处理
```

---

## 故障处理

### API调用失败
```python
from skills.investment_analysis_suite import check_apis

status = check_apis()
# 检查长桥API、知识星球API连接状态
```

### 数据缓存
```python
from skills.investment_analysis_suite import cache

# 自动缓存最近1小时的数据
cache.get("quotes_002371", max_age=3600)
```
