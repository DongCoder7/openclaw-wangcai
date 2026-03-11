# 个股盈利预测 Skill v5.0 - 收入-成本模型版

## 概述

基于**真实财务数据**的**收入-成本分解模型**，不使用PE估值，直接预测真实利润。

**核心原则**：
- ✅ 使用**当年数据**（如2025年Q1-Q3），不用旧数据
- ✅ 使用**真实财报**（Tushare Pro），不用估算
- ✅ **成本分解**（固定 vs 变动），不用PE倍数
- ✅ **完整计算过程展示**，不接受黑盒结果

---

## 数据流程（强制遵循）

### Step 1: 获取标杆企业当年累计财报数据

```python
import tushare as ts

pro = ts.pro_api()

# ✅ 正确：获取2025年数据（不是2024年！）
df = pro.income(
    ts_code='300394.SZ',  # 天孚通信
    start_date='20250101',
    end_date='20251231',
    fields='ts_code,end_date,total_revenue,operate_cost,n_income'
)

# 筛选当年数据
df = df[df['end_date'].str.startswith('2025')]
```

**⚠️ 常见错误**：
- ❌ 获取2024年数据（过时）
- ❌ 使用股价数据代替财报数据
- ❌ 编造财报数据

---

### Step 2: 从累计数据计算单季度数据

Tushare返回的是**累计数据**（Q1=累计，Q2=累计...），必须计算单季度：

```python
def calculate_quarterly(df):
    """从累计数据计算单季度数据"""
    df = df.sort_values('end_date').drop_duplicates('end_date')
    
    result = []
    prev_cumulative = None
    
    for _, row in df.iterrows():
        date = row['end_date']
        cum_rev = row['total_revenue'] / 1e8  # 转亿元
        cum_profit = row['n_income'] / 1e8
        
        if date.endswith('0331'):  # Q1
            result.append(('Q1', cum_rev, cum_profit))
            prev_cumulative = (cum_rev, cum_profit)
            
        elif date.endswith('0630') and prev_cumulative:  # Q2
            q_rev = cum_rev - prev_cumulative[0]
            q_profit = cum_profit - prev_cumulative[1]
            result.append(('Q2', q_rev, q_profit))
            prev_cumulative = (cum_rev, cum_profit)
            
        elif date.endswith('0930') and prev_cumulative:  # Q3
            q_rev = cum_rev - prev_cumulative[0]
            q_profit = cum_profit - prev_cumulative[1]
            result.append(('Q3', q_rev, q_profit))
            prev_cumulative = (cum_rev, cum_profit)
            
        elif date.endswith('1231') and prev_cumulative:  # Q4
            q_rev = cum_rev - prev_cumulative[0]
            q_profit = cum_profit - prev_cumulative[1]
            result.append(('Q4', q_rev, q_profit))
    
    return result

# 使用示例
quarterly_data = calculate_quarterly(df)
for period, rev, profit in quarterly_data:
    print(f"{period}: 营收{rev:.2f}亿, 净利{profit:.2f}亿")
```

**⚠️ 常见错误**：
- ❌ 把累计数据当单季度用
- ❌ 2023Q4当成2024Q4（跨年数据污染）
- ❌ 没有检查数据是否完整（缺少Q4）

---

### Step 3: 计算季度环比增长率

```python
growth_rates = []
for i in range(1, len(quarterly_data)):
    _, prev_rev, _ = quarterly_data[i-1]
    period, curr_rev, _ = quarterly_data[i]
    
    growth = (curr_rev - prev_rev) / prev_rev
    growth_rates.append(growth)
    
    print(f"{period}: {growth:+.1%}")  # 展示计算过程

# 行业平均
import statistics
avg_qoq = statistics.mean(growth_rates)  # 季度环比
annual_growth = (1 + avg_qoq) ** 4 - 1   # 年化增长
```

**示例输出**：
```
2025年天孚通信季度环比：
  Q1→Q2: +60.0%
  Q2→Q3: -3.2%
  
行业平均季度环比: +26.1%
年化增长率: +153.2%
```

---

## 计算流程

### 第一步：分析行业成本结构

从标杆企业Q3数据反推成本结构：

```python
# 天孚通信Q3数据示例
q3_revenue = 14.63      # 营收（亿元）
q3_profit = 5.66        # 净利润（亿元）
q3_margin = 0.387       # 净利率38.7%

# 假设变动成本率50%（需根据行业调整）
variable_cost_rate = 0.50

# 反推固定成本
fixed_cost = q3_revenue - q3_profit - (q3_revenue * variable_cost_rate)
# = 14.63 - 5.66 - 7.32 = 1.65亿

fixed_cost_ratio = fixed_cost / q3_revenue  # 11.3%
```

**行业平均成本结构**（2025年光通信）：
| 成本类型 | 占比 | 变化规律 |
|:---|:---:|:---|
| 变动成本 | 50% | 随营收线性变化 |
| 固定成本 | 13% | 不随营收变化 |
| **净利润** | **37%** | **行业平均净利率** |

---

### 第二步：应用到目标企业

**已知**：
- 光库科技2025年预估营收：15亿
- 光库科技2025年预估净利润：2.5亿

**成本分解**：
```python
base_revenue = 15.0     # 2025年营收（亿元）
base_profit = 2.5       # 2025年净利润（亿元）

# 使用行业成本结构
variable_rate = 0.50    # 变动成本率50%
fixed_ratio = 0.13      # 固定成本率13%

current_fixed = base_revenue * fixed_ratio  # 1.95亿
```

---

### 第三步：预测2026年业绩

**公式**：
```
2026营收 = 2025营收 × (1 + 行业年化增长率 × 调整系数)
2026固定成本 = 2025固定成本 × (1 + 3%)  # 产能扩张
2026变动成本 = 2026营收 × 变动成本率
2026净利润 = 2026营收 - 固定成本 - 变动成本
```

**示例计算**：
```python
# 行业年化增长
industry_annual = 1.53  # +153%（2025年高增长）
adjustment = 0.6        # 光库增速打6折（低于龙头）

growth_2026 = industry_annual * adjustment  # +92%
revenue_2026 = 15.0 * (1 + growth_2026)     # 28.8亿

fixed_2026 = 1.95 * 1.03                    # 2.01亿
variable_2026 = 28.8 * 0.50                 # 14.4亿
profit_2026 = 28.8 - 2.01 - 14.4            # 12.4亿

margin_2026 = profit_2026 / revenue_2026    # 43.0%
```

**输出**：
```
2026年预测：
  营收: 28.8亿 (+92%)
  固定成本: 2.01亿 (+3%)
  变动成本: 14.4亿 (+109%, 随营收线性)
  净利润: 12.4亿 (+396%)
  净利率: 43.0%（接近行业平均37%）
```

---

### 第四步：估值参考（仅作对比）

**核心原则**：收入-成本模型的核心是预测**真实利润**，不是PE估值。

如需估值参考：
```python
# PE估值仅作参考
for pe in [30, 40, 50]:
    market_cap = profit_2026 * pe
    print(f"PE {pe}x: {market_cap:.1f}亿元")

# 对比当前市值
current_cap = 406.3  # 当前市值
upside = (market_cap - current_cap) / current_cap * 100
```

---

## 真实性检查清单（强制！）

### 数据获取检查

- [ ] **年份正确**：使用的是**当年数据**（2025年），不是2024年
- [ ] **来源真实**：数据来自Tushare Pro/efinance API，不是编造
- [ ] **数据完整**：检查了Q1-Q3/Q4是否都有数据
- [ ] **累计转单季**：正确处理了累计数据→单季度数据

### 计算过程检查

- [ ] **环比计算**：展示了(Q2-Q1)/Q1的完整计算
- [ ] **年化公式**：使用了(1+环比)^4-1，不是简单×4
- [ ] **成本分解**：展示了固定成本和变动成本的推导
- [ ] **利润公式**：利润=营收-固定-变动，完整展示

### 常见造假识别

| 造假行为 | 识别方法 | 正确做法 |
|:---|:---|:---|
| **年份错误** | 使用2024年数据 | 必须使用当年（2025）数据 |
| **数据编造** | 整数营收/利润 | API查询，带2位小数 |
| **累计当单季** | Q2数据≈2×Q1 | 必须Q2-Q1计算单季 |
| **黑盒计算** | 直接给结果 | 展示每步计算公式 |
| **PE当估值** | 主要依据PE | 核心是利润预测，PE仅参考 |

### 报告必须包含

```markdown
## 数据真实性声明

| 检查项 | 状态 | 说明 |
|:---|:---:|:---|
| 数据年份 | ✅ | 2025年Q1-Q3 |
| 数据来源 | ✅ | Tushare Pro API |
| 单季度计算 | ✅ | 累计数据转单季度 |
| 环比计算 | ✅ | (Q2-Q1)/Q1 |
| 成本分解 | ✅ | 固定/变动成本推导 |
| 利润计算 | ✅ | 完整公式展示 |
```

---

## 完整代码示例

```python
#!/usr/bin/env python3
"""
收入-成本模型预测示例
"""

import tushare as ts
import statistics

# 初始化Tushare（需要token）
pro = ts.pro_api('your_token_here')

def get_quarterly_data(ts_code, year, name):
    """获取单季度数据"""
    print(f"\n获取{name}({ts_code}) {year}年数据...")
    
    # Step 1: 获取累计数据
    df = pro.income(
        ts_code=ts_code,
        start_date=f'{year}0101',
        end_date=f'{year}1231',
        fields='ts_code,end_date,total_revenue,n_income'
    )
    
    # Step 2: 筛选当年数据
    df = df[df['end_date'].str.startswith(str(year))]
    df = df.sort_values('end_date').drop_duplicates('end_date')
    
    # Step 3: 计算单季度
    result = []
    prev_cum = None
    
    for _, row in df.iterrows():
        date = row['end_date']
        cum_rev = row['total_revenue'] / 1e8
        cum_profit = row['n_income'] / 1e8
        
        if date.endswith('0331'):
            result.append(('Q1', cum_rev, cum_profit))
            prev_cum = (cum_rev, cum_profit)
        elif prev_cum and date.endswith(('0630', '0930', '1231')):
            q_rev = cum_rev - prev_cum[0]
            q_profit = cum_profit - prev_cum[1]
            period = 'Q2' if date.endswith('0630') else 'Q3' if date.endswith('0930') else 'Q4'
            result.append((period, q_rev, q_profit))
            prev_cum = (cum_rev, cum_profit)
    
    return result

# 获取标杆数据
benchmarks = [
    ('300394.SZ', '天孚通信'),
    ('300308.SZ', '中际旭创'),
    ('300502.SZ', '新易盛')
]

all_growth = []
for code, name in benchmarks:
    data = get_quarterly_data(code, 2025, name)
    
    # 计算环比
    for i in range(1, len(data)):
        _, prev_rev, _ = data[i-1]
        _, curr_rev, _ = data[i]
        growth = (curr_rev - prev_rev) / prev_rev
        all_growth.append(growth)
        print(f"  {data[i-1][0]}->{data[i][0]}: {growth:+.1%}")

# 行业平均
avg_qoq = statistics.mean(all_growth)
annual = (1 + avg_qoq) ** 4 - 1
print(f"\n行业平均季度环比: {avg_qoq:+.1%}")
print(f"年化增长率: {annual:+.1%}")

# 应用到目标企业...
```

---

## 版本历史

| 版本 | 时间 | 核心改进 |
|:---|:---|:---|
| v1.0 | 2026-03-06 | 标杆对比法 |
| v2.0 | 2026-03-07 | 经营杠杆模型 |
| v3.0 | 2026-03-07 | 机构预测校准（存储） |
| v4.0 | 2026-03-10 | 通用行业版（PE估值） |
| **v5.0** | **2026-03-10** | **收入-成本模型（真实财报，当年数据）** |

---

## 文件位置

```
skills/stock-earnings-forecast/
├── SKILL.md                              # 本文档
├── scripts/
│   ├── financial_data_fetcher.py         # 财务数据获取（Tushare/efinance）
│   ├── revenue_cost_forecaster.py        # v5.0 收入-成本预测器
│   └── examples/
│       └── guangku_2025_forecast.py      # 光库科技完整示例
```

---

*最后更新：2026-03-10*  
*核心: 当年真实财报数据 + 收入-成本分解 + 完整计算展示 + 真实性强制检查*