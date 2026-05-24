# Multi-Source Search Methodology - Detailed Reference

## Table of Contents
1. [Historical Lessons](#historical-lessons)
2. [Search Strategy](#search-strategy)
3. [Keyword Engineering](#keyword-engineering)
4. [Cross-Verification Rules](#cross-verification-rules)
5. [Common Pitfalls](#common-pitfalls)
6. [Output Standards](#output-standards)

---

## Historical Lessons

### Lesson 1: Super Iron-Air Battery Analysis Failure (2026-02)

**Error:**
- Keyword extraction error: "energy storage battery" replaced "iron-air battery"
- Search strategy error: Did not search Form Energy, Google orders
- Stock screening error: Recommended CATL and other lithium battery stocks

**Root Cause:**
- Did not follow the Four-Step Search Protocol
- Did not distinguish between narrow concept and broad category
- Did not verify stock association

**Fix:**
- Mandatory multi-source search (P1-P4)
- Must search for news before finding stocks
- Every stock must have direct association evidence

### Lesson 2: Nitrogen Fertilizer Sector Analysis Omission (2026-03-07)

**Error:**
- **Completely skipped multi-source news search** (Exa, zsxq, Sina Finance)
- Did not identify Iran war's major impact on urea supply
- Did not quantify domestic-international price spread of 1100+ yuan
- Stock recommendations lacked geopolitical logic

**Root Cause:**
- Impatient when encountering API interface changes
- **Did not execute pre-checklist from industry-chain-analysis Skill**
- Violated Four-Step Search Protocol
- Pursued quick response over quality

**Impact:**
- First version report had severe quality defects
- User asked follow-up questions twice
- Had to re-output complete report

**Fix (Solidified):**
1. **Hard Rule**: Multi-source search (P1-P3) must be completed before report output
2. **Checklist Tool**: Use `./checklist_block_analysis.py` for mandatory checking
3. **Script Support**: Use `./analyze_block.sh` to auto-prompt search steps

### Lesson 3: Data Backfill False Completion Claim

**Error:**
- Claimed stock_fina backfill completed
- Actually only 3,772 records in 2026-03

**Root Cause:**
- Did not verify database true state
- Trusted script "completed" output blindly

**Fix:**
- Must verify after every task
- SQL query to confirm data ingestion
- Truthfully report actual progress

---

## Search Strategy

### For Concept Analysis (Narrow Concept)

Example: "iron-air battery", "CPO", "PEEK materials"

```
Step 1: Concept Definition
  └─ Exa: "iron-air battery technology principle energy density"
  └─ zsxq: "铁空气电池 技术原理"
  └─ Goal: Identify technical features (100h storage, $20/kWh)

Step 2: Catalyst Search
  └─ Exa: "iron-air battery Form Energy Google order 30GWh"
  └─ zsxq: "铁空气电池 订单 融资"
  └─ Goal: Find trigger events

Step 3: Stock Mapping
  └─ Exa: "iron-air battery A-share 概念股 上市公司"
  └─ Sina: Search for related stocks
  └─ Goal: Direct association evidence

Step 4: Industry Chain
  └─ Exa: "iron-air battery upstream iron material"
  └─ Exa: "iron-air battery downstream grid storage"
  └─ Goal: Verify chain completeness
```

### For Industry Chain Analysis (Broad Category)

Example: "semiconductor", "new energy", "PCB"

```
Step 1: Industry Overview
  └─ Exa: "semiconductor industry supply chain 2025 2026"
  └─ zsxq: "半导体 产业链 景气度"

Step 2: Price Cycle
  └─ Exa: "semiconductor price trend wafer 2025"
  └─ Sina: "半导体 涨价 库存"

Step 3: Competitive Landscape
  └─ Exa: "semiconductor domestic vs international market share"
  └─ zsxq: "半导体 国产替代 进度"

Step 4: Stock Screening
  └─ Exa: "semiconductor A-share leading companies"
  └─ Combined with v26 scoring
```

### For Individual Stock Analysis

Use `search_stock_comprehensive()` which auto-executes 6 categories:

| Category | Search Query | Importance |
|:---------|:-------------|:----------:|
| Basics | "stock_name industry business" | ⭐⭐⭐⭐⭐ |
| Capital Ops | "stock_name M&A acquisition restructuring" | ⭐⭐⭐⭐⭐ |
| Risk | "stock_name reduction violation regulatory inquiry" | ⭐⭐⭐⭐⭐ |
| Business Drivers | "stock_name orders contracts capacity expansion" | ⭐⭐⭐⭐⭐ |
| Earnings | "stock_name earnings pre-increase flash report" | ⭐⭐⭐⭐⭐ |
| Capital Market | "stock_name research report rating target price" | ⭐⭐⭐⭐ |

---

## Keyword Engineering

### Principles

1. **Specific > General**: "800G硅光模块渗透率" > "光模块"
2. **Chinese + English**: Search both languages for tech concepts
3. **Time-bound**: Add "2025 2026" to find latest data
4. **Entity + Keyword**: "中际旭创 订单" not just "订单"
5. **Quantifiable**: Look for numbers (%, 亿, 万只, GHz)

### Keyword Templates

| Analysis Type | Template | Example |
|:--------------|:---------|:--------|
| Concept | `"{concept} 技术原理 核心参数"` | `"硅光技术 CPO 功耗 pJ/bit"` |
| Catalyst | `"{concept} 订单 融资 政策 突破"` | `"硅光模块 Tower 扩产 13亿美元"` |
| Stock | `"{concept} A股 上市公司 概念股"` | `"硅光模块 概念股 中际旭创"` |
| Upstream | `"{concept} 上游 核心材料 供应"` | `"硅光 上游 磷化铟 衬底"` |
| Downstream | `"{concept} 下游 应用场景 需求"` | `"硅光 下游 数据中心 AI算力"` |
| Risk | `"{stock} 减持 违规 监管 问询函"` | `"中际旭创 减持 监管"` |

---

## Cross-Verification Rules

### Minimum Requirements

| Verification Type | Standard | Example |
|:------------------|:---------|:--------|
| **Fact verification** | ≥2 independent sources | "800G硅光占比50%" confirmed by both Exa(Sina纪要) and 36氪(野村证券) |
| **Data verification** | Numbers match across sources | "1.6T需求3000万只" same in 3 sources |
| **Event verification** | Same event, different angles | Tower扩产: Tower财报 + 21经济网 + 36氪 all confirm |
| **Opinion separation** | Label as opinion if only 1 source | "预计2031年突破500亿" = LightCounting prediction |

### Source Credibility Hierarchy

| Tier | Source Type | Weight | Notes |
|:----:|:------------|:------:|:------|
| 1 | Company official announcements | 100% | SEC filings, exchange announcements |
| 2 | Earnings calls / Investor Q&A | 90% | Direct from management |
| 3 | Research reports (top broker) | 80% | 中信/中金/高盛等 |
| 4 | Industry consulting (LightCounting) | 75% | Specialized research |
| 5 | Knowledge base expert notes | 70% | Industry insiders |
| 6 | Exa AI search aggregation | 65% | Multi-web synthesis |
| 7 | Financial media (Sina, 36氪) | 60% | Secondary reporting |
| 8 | Social media / Forums | 30% | Unverified rumors |

---

## Common Pitfalls

| Error Signal | Symptom | Fix |
|:-------------|:--------|:----|
| 🚨 Keyword Drift | Search terms don't match user query | Return to user query and re-extract |
| 🚨 Stock Generalization | Recommended industry leaders, not concept stocks | Add concept keywords and re-search |
| 🚨 Catalyst Missing | No recent orders/financing/policy found | Extend search time range |
| 🚨 Hollow Logic | "Benefits from industry development" | Find specific tech/order association |
| 🚨 Single Source | Only used Tushare or 1 source | Force multi_source_search |
| 🚨 Fake Data | Used np.random or faker | Must read real parquet/API data |
| 🚨 Skipped Search | Output report without searching | **FORBIDDEN** - checklist blocks this |

---

## Output Standards

### Search Result Format

```markdown
## Multi-Source News Synthesis

### Search Summary
| Method | Source | Key Findings |
|:---:|:---|:---|
| P1 Exa | AI semantic search | 国产替代率35%, orders +80% |
| P2 zsxq | Research notes | Expert views on supply chain |
| P3 Sina | Financial API | Sector dynamics |

### Core News (by importance)
**[国产替代进展]** (Exa + Sina 2026-01-07)
• 替代率25%→35%
• Verified: Multiple sources consistent

**[Company Orders]** (zsxq 2026-01-10)
• 北方华创 orders through 2027Q1
• Verified: Matches earnings data
```

### Pre-Report Checklist Output

```markdown
### [Sector Name] Analysis Checklist

#### Multi-Source Search (Mandatory)
- [x] **P1 Exa Search** — Executed ≥3 keyword groups
- [x] **P2 zsxq** — Called search function
- [x] **P3 Sina** — Called API
- [x] Cross-verification — ≥2 sources confirm same event

#### Data Quality
- [x] Key catalyst identified? Yes: Tower $1.3B order
- [x] Core metrics quantified? Yes: 800G硅光50%渗透率
- [x] Every target has logic support? Yes

#### Prohibitions
- [x] Did NOT skip search and output directly
- [x] Did NOT use fake data
```

**⚠️ If any mandatory item is unchecked, STOP and report to user.**

---

*Reference for multi-source-search Skill v1.0*
