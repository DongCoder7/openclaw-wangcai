---
name: dounai-investment-system
description: |
  豆奶投资策略系统 - 主控Skill
  
  系统核心功能：
  1. 🔍 产业链分析 - 存储芯片/PCB/半导体深度分析
  2. 📊 美股报告 - 隔夜美股市场总结
  3. 🌅 A+H开盘 - 开盘前瞻策略
  4. 📈 实时行情 - A股/港股/美股实时价格
  5. 📚 知识星球 - 调研纪要获取
  6. 🎯 投资组合 - 建仓建议/持仓诊断
  
  触发方式：
  - "分析存储芯片" → 产业链+知识星球+实时行情
  - "美股报告" → 隔夜美股分析
  - "开盘前瞻" → A+H开盘策略
  - "查002371价格" → 实时行情
  - "知识星球存储" → 调研信息
  
  自动任务：
  - 08:30 美股报告
  - 09:15 A+H开盘
  - 每2小时 知识星球
---

# 豆奶投资策略系统

## 快速入口

### 方式1: 自然语言调用 (推荐)

| 用户需求 | 系统响应 |
|:---------|:---------|
| "分析存储芯片产业链" | 自动调用产业链分析 + 知识星球 + 实时行情 |
| "生成美股报告" | 自动获取美股行情并生成报告 |
| "A+H开盘前瞻" | 自动生成开盘策略 |
| "查北方华创价格" | 返回实时行情 + 建仓建议 |
| "知识星球PCB" | 获取PCB相关调研纪要 |

### 方式2: 函数调用

```python
from skills.dounai_investment_system import DounaiSystem

system = DounaiSystem()

# 产业链分析
result = system.analyze_industry("存储芯片")

# 美股报告
report = system.generate_us_report()

# 实时行情
quotes = system.get_quotes(["002371.SZ", "688012.SH"])
```

---

## 功能模块

### 1️⃣ 产业链深度分析

**调用**: `analyze_industry(industry_name)`

**输入**: 行业名称 (存储芯片/PCB/半导体/新能源)

**输出**:
- 知识星球最新调研信息
- 产业链上下游分析
- 核心标的数据
- 实时行情 + v26因子
- 投资组合建议

**示例**:
```python
result = system.analyze_industry("存储芯片")

print(result['summary'])
# 输出: 
# 长鑫2300亿投资，设备占比65%
# 推荐标的: 北方华创(18%)、拓荆科技(12%)...
```

---

### 2️⃣ 美股市场报告

**调用**: `generate_us_report()`

**自动执行**: 每日08:30

**输出**:
- 道指/纳指/标普表现
- 科技股涨跌
- 中概股表现
- 对A股策略启示

---

### 3️⃣ A+H开盘前瞻

**调用**: `generate_ah_preopen()`

**自动执行**: 每日09:15

**输出**:
- 美股回顾
- A股板块分析
- 港股板块分析
- 开盘策略建议

---

### 4️⃣ 实时行情查询

**调用**: `get_quotes(symbols)`

**支持市场**:
- A股: 002371.SZ, 688012.SH
- 港股: 00700.HK, 09988.HK
- 美股: AAPL.US, NVDA.US

**输出**:
- 最新价格
- 涨跌幅
- 成交量/成交额
- 建仓建议

---

### 5️⃣ 知识星球获取

**调用**: `search_zsxq(keyword)`

**功能**:
- 按关键词搜索调研纪要
- 获取最新文章
- 行业信息聚合

---

### 6️⃣ 投资组合管理

**调用**: `analyze_portfolio(stocks)`

**功能**:
- 持仓诊断
- v26因子评分
- 建仓位置建议
- 调仓建议

---

## 自动化配置

### 定时任务 (Crontab)

```bash
# 08:30 美股报告
30 8 * * * cd ~/.openclaw/workspace && python3 -c "from skills.dounai_investment_system import DounaiSystem; DounaiSystem().generate_us_report()"

# 09:15 A+H开盘
15 9 * * * cd ~/.openclaw/workspace && python3 -c "from skills.dounai_investment_system import DounaiSystem; DounaiSystem().generate_ah_preopen()"

# 每2小时 知识星球
0 */2 * * * cd ~/.openclaw/workspace && python3 -c "from skills.dounai_investment_system import DounaiSystem; DounaiSystem().fetch_zsxq()"
```

### Heartbeat集成

在 `HEARTBEAT.md` 中配置自动任务调度。

---

## 数据流

```
用户请求
    ↓
自然语言理解
    ↓
技能路由
    ├─ 产业链分析 → 知识星球 + 长桥API + v26因子
    ├─ 美股报告 → 长桥API(美股)
    ├─ A+H开盘 → 长桥API(A股/港股)
    ├─ 实时行情 → 长桥API
    └─ 知识星球 → zsxq API
    ↓
结果整合
    ↓
输出报告/建议
```

---

## 依赖配置

### 必需
- 长桥API密钥 (`.longbridge.env`)
- 知识星球Token (已配置)

### 可选
- Tushare Token (`.tushare.env`)

---

## 示例场景

### 场景1: 存储芯片投资决策

**用户**: "分析存储芯片投资机会"

**系统自动执行**:
1. 🔍 搜索知识星球"存储芯片"相关内容
2. 📊 获取存储芯片产业链股票实时行情
3. 📈 计算v26因子评分
4. 🎯 生成投资组合建议
5. 📋 输出完整分析报告

**输出结果**:
```
📊 存储芯片产业链分析报告

【知识星球最新信息】
- 长鑫2300亿投资，设备占比65%
...

【实时行情】
- 北方华创: 496元 (+1.78%)
- 拓荆科技: 360元 (+9.98%) 🔴涨停
...

【推荐组合】
- 北方华创 18%: 订单确定，立即建仓
- 拓荆科技 12%: 等回调5%
...

【预期收益】+16.5%
```

### 场景2: 每日开盘准备

**自动执行时间**: 09:15

**系统自动执行**:
1. 📊 获取美股隔夜行情
2. 🌅 获取A+H盘前数据
3. 📚 获取知识星球最新信息
4. 📝 生成开盘策略简报
5. 📤 自动发送报告

---

## 故障处理

### API连接失败
- 自动重试3次
- 失败时返回缓存数据
- 记录错误日志

### 数据缺失
- 使用T-1日数据补充
- 标记数据时效性
- 提示用户注意

---

## 更新日志

| 日期 | 更新内容 |
|:-----|:---------|
| 2026-02-25 | 集成longport SDK，统一API调用 |
| 2026-02-25 | 添加知识星球自动获取 |
| 2026-02-25 | 完善产业链分析模块 |
