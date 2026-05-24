---
name: multi-source-search
description: |
  Multi-source information search and cross-verification methodology for investment analysis, industry research, concept validation, and news synthesis. Use when: (1) analyzing any investment concept, stock, or industry chain, (2) verifying information accuracy before producing a report, (3) searching for catalysts, orders, policies, or technology breakthroughs, (4) performing news synthesis across Exa AI search, knowledge base (zsxq), Sina Finance, and other sources. Triggers on: "分析XX概念", "搜索XX行业", "多源搜索", "news search", "cross-verify", "验证信息".
---

# Multi-Source Search Skill v1.0

## Overview

强制多源信息搜索与交叉验证方法论。任何分析任务在输出报告前，必须完成P1-P3搜索并交叉验证。

## Core Methodology: Three-Level Verification

```
┌─────────────────────────────────────────────────────────────┐
│ Level 1: Concept/Entity Verification                          │
│ • Extract core concept from user query                       │
│ • Determine if "broad category" or "narrow concept"        │
│ • Search precise definition and technical characteristics    │
├─────────────────────────────────────────────────────────────┤
│ Level 2: Industry Chain Mapping Verification                │
│ • Position in industry chain                                │
│ • Upstream/downstream critical links                        │
│ • Substitution relationships with existing tech/products    │
├─────────────────────────────────────────────────────────────┤
│ Level 3: Stock/Target Association Verification              │
│ • Directly related A-share targets                         │
│ • Indirectly related targets                                │
│ • Distinguish "pure plays" vs "concept蹭"                   │
└─────────────────────────────────────────────────────────────┘
```

## Four-Step Search Protocol (Mandatory)

**Rule: Do NOT proceed to stock screening without completing Steps 1-2.**

### Step 1: Concept Definition Search
- Search: `"concept_name technology principle core parameters"`
- Goal: Determine technical features and key metrics

### Step 2: Catalyst Search
- Search: `"concept_name orders financing policy breakthrough"`
- Goal: Identify trigger events for price movement

### Step 3: Stock Mapping Search
- Search: `"concept_name A-share listed company concept stocks"`
- Goal: Find directly related A-share targets

### Step 4: Industry Chain Verification
- Search: `"concept upstream core materials"`
- Search: `"concept downstream application scenarios"`
- Goal: Verify industry chain completeness

## Multi-Source Search Priority (P1-P4)

> ⚠️ **Iron Rule: Priority is search ORDER, not "use P1 only"! ALL sources must be used and synthesized.**
> ⚠️ **Reports are FORBIDDEN without completing P1-P3.**

| Priority | Source | Data Type | Method | Must Use |
|:---:|:---|:---|:---|:---:|
| **P1** | **Exa AI Search** | Web/news/semantic | `mcporter call exa.web_search_exa()` | ✅ Mandatory |
| **P2** | **Knowledge Base (zsxq)** | Research notes/expert views | `scripts/multi_source_search.py` or `search_industry_chain_news()` | ✅ Mandatory |
| **P3** | **Sina Finance API** | Financial news | `curl https://feed.mix.sina.com.cn/...` | ✅ Mandatory |
| P4 | **Wall Street见闻** | Deep analysis | API/web fetch | Optional |
| P5 | **Yicai/第一财经** | Policy analysis | API/web fetch | Optional |

## Six-Category Keyword Search Checklist

Every stock or industry analysis must execute all 6 categories:

| Category | Keywords | Importance | Purpose |
|:-----|:-------|:------:|:-----|
| **Basics** | Industry keywords | ⭐⭐⭐⭐⭐ | Business fundamentals |
| **Capital Ops** | M&A, acquisition, private placement, restructuring | ⭐⭐⭐⭐⭐ | Major events |
| **Risk** | Reduction, increase, violation, penalty, regulatory inquiry | ⭐⭐⭐⭐⭐ | Risk screening |
| **Business Drivers** | Orders, contracts, bids, capacity expansion, tech breakthrough | ⭐⭐⭐⭐⭐ | Performance drivers |
| **Earnings** | Pre-increase, flash report, downward revision, turnaround | ⭐⭐⭐⭐⭐ | Earnings validation |
| **Capital Market** | Research reports, ratings, target prices, institutional research | ⭐⭐⭐⭐ | Market sentiment |

## Cross-Verification Rules

1. **Must list ALL search sources used**
2. **Must label source and date for each news item**
3. **Must cross-validate**: Same event reported by ≥2 independent sources
4. **Must distinguish facts vs opinions**

## Pre-Report Checklist

Before outputting ANY report:

```markdown
### Multi-Source Search (Mandatory)
- [ ] **P1 Exa Search** — Executed ≥3 keyword groups
- [ ] **P2 Knowledge Base** — Called search function
- [ ] **P3 Sina Finance** — Called API
- [ ] Cross-verification — ≥2 sources confirm same event

### Data Quality
- [ ] Key catalyst event identified?
- [ ] Core metrics quantified (price/spread/supply-demand)?
- [ ] Every recommended target has logical support?

### Prohibitions
- [ ] Skipped search and output report directly ❌
- [ ] Used fake/simulated data ❌
```

**⚠️ Checklist incomplete = Report output FORBIDDEN.**

## Usage

### For Concept Analysis
```bash
# Step 1-2: Concept + Catalyst
mcporter call 'exa.web_search_exa({"query": "silicon photonics technology principle CPO", "numResults": 10})'
mcporter call 'exa.web_search_exa({"query": "silicon photonics orders policy 2025 2026", "numResults": 10})'

# Step 3-4: Stocks + Chain
mcporter call 'exa.web_search_exa({"query": "硅光模块 A股 上市公司 概念股", "numResults": 10})'
mcporter call 'exa.web_search_exa({"query": "硅光 上游 磷化铟 光芯片", "numResults": 10})'

# P2: Knowledge base
python3 scripts/multi_source_search.py --keyword "硅光" --days 30

# P3: Sina Finance
curl "https://feed.mix.sina.com.cn/api/roll/get?pageid=153&lid=2516&num=20"
```

### For Stock Comprehensive Search
```python
import sys
sys.path.insert(0, '/root/.openclaw/workspace/skills/multi-source-search/scripts')
from multi_source_search import search_stock_comprehensive

results = search_stock_comprehensive(
    stock_code="300308.SZ",
    stock_name="中际旭创",
    industry="光模块"
)
# Returns: basics, capital_ops, risk, business_drivers, earnings, capital_market
```

### For Industry Chain Search
```python
from multi_source_search import search_industry_chain_news

news = search_industry_chain_news(
    industry="半导体",
    upstream="硅片 光刻胶",
    downstream="芯片设计 封测"
)
```

## Resources

- **scripts/multi_source_search.py** — Unified search interface (Exa + zsxq + Sina)
- **scripts/cross_verify.py** — Cross-verification helper
- **references/methodology.md** — Detailed methodology and historical lessons

---

*Version: v1.0*  
*Updated: 2026-05-24*
