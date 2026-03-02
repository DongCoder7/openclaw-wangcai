# 板块投资分析通用方法论 v1.0

## 🎯 核心原则

**不硬编码任何标的**，所有标的通过**实时数据+动态筛选**自动发现。

---

## 一、板块分析流程（4步法）

```
Step 1: 板块热度扫描 → 发现板块内所有标的
Step 2: 标的筛选排序 → 按多维指标排序
Step 3: 深度验证分析 → 搜索新闻+订单+催化剂
Step 4: 生成投资报告 → 输出标的+逻辑+买卖点
```

---

## 二、Step 1: 板块热度扫描

### 2.1 自动发现板块标的

```python
def scan_sector_stocks(sector_name: str, keywords: List[str]) -> List[Dict]:
    """
    扫描板块内所有标的
    
    Args:
        sector_name: 板块名称（如"AI电源"）
        keywords: 板块关键词（如["AI电源","数据中心电源","服务器电源"]）
    
    Returns:
        板块内所有标的列表（自动发现，不硬编码）
    """
    all_stocks = []
    
    # P1: Exa全网搜索 - 发现板块内公司
    for kw in keywords:
        news = search_exa(f"{kw} 概念股 龙头 上市公司", count=20)
        for n in news:
            # 提取股票代码和名称
            stock_info = extract_stock_from_text(n['title'] + n.get('content', ''))
            if stock_info:
                all_stocks.append(stock_info)
    
    # P2: 知识星球搜索 - 发现热门标的
    for kw in keywords:
        topics = zsxq_search(kw, count=30)
        for t in topics:
            stock_info = extract_stock_from_text(t['title'] + t['content'])
            if stock_info:
                all_stocks.append(stock_info)
    
    # 去重并统计提及次数
    stock_counter = Counter([(s['code'], s['name']) for s in all_stocks])
    unique_stocks = []
    for (code, name), count in stock_counter.most_common(20):
        unique_stocks.append({
            'code': code,
            'name': name,
            'mention_count': count
        })
    
    return unique_stocks
```

### 2.2 获取实时行情数据

```python
def get_stocks_realtime_data(stocks: List[Dict]) -> List[Dict]:
    """获取标的实时行情"""
    for stock in stocks:
        # 腾讯财经API
        price_data = get_tencent_quote(stock['code'])
        stock.update(price_data)
        
        # Tushare基本面
        fundamental = get_tushare_fundamental(stock['code'])
        stock.update(fundamental)
    
    return stocks
```

---

## 三、Step 2: 标的筛选排序（5维评分法）

### 3.1 动态评分模型

```python
def score_stock(stock: Dict, sector_keywords: List[str]) -> Dict:
    """
    多维度动态评分
    """
    score = {
        'total': 0,
        'momentum': 0,      # 动量得分
        'fundamental': 0,   # 基本面得分
        'catalyst': 0,      # 催化剂得分
        'risk': 0,          # 风险得分
        'liquidity': 0      # 流动性得分
    }
    
    # 1. 动量评分（技术面）
    score['momentum'] = calculate_momentum(
        stock['pct_chg_1d'],    # 1日涨幅
        stock['pct_chg_5d'],    # 5日涨幅
        stock['pct_chg_20d'],   # 20日涨幅
        stock['vol_ratio']      # 量比
    )
    
    # 2. 基本面评分
    score['fundamental'] = calculate_fundamental(
        stock['pe_ttm'],        # PE
        stock['pb'],            # PB
        stock['revenue_growth'], # 营收增速
        stock['profit_growth']   # 利润增速
    )
    
    # 3. 催化剂评分（新闻搜索）
    catalyst_news = search_stock_comprehensive(
        stock_code=stock['code'],
        stock_name=stock['name'],
        industry=sector_keywords[0]
    )
    score['catalyst'] = calculate_catalyst_score(catalyst_news)
    
    # 4. 风险评分
    score['risk'] = calculate_risk_score(
        stock['volatility'],    # 波动率
        stock['max_drawdown'],  # 最大回撤
        catalyst_news['风险']    # 风险新闻
    )
    
    # 5. 流动性评分
    score['liquidity'] = calculate_liquidity(
        stock['market_cap'],    # 市值
        stock['turnover_rate'], # 换手率
        stock['volume']         # 成交量
    )
    
    # 加权总分
    weights = {
        'momentum': 0.25,
        'fundamental': 0.20,
        'catalyst': 0.30,
        'risk': 0.15,
        'liquidity': 0.10
    }
    
    score['total'] = sum(score[k] * weights[k] for k in weights)
    
    return score
```

### 3.2 动态筛选规则

```python
def filter_stocks(stocks: List[Dict], min_score: int = 70) -> List[Dict]:
    """动态筛选高评分标的"""
    
    # 基础过滤
    filtered = [s for s in stocks if 
        s['score']['total'] >= min_score and      # 总分达标
        s['market_cap'] > 50 and                  # 市值大于50亿
        s['pe_ttm'] > 0 and s['pe_ttm'] < 200 and # PE合理
        s['turnover_rate'] > 1.0                  # 有流动性
    ]
    
    # 按总分排序
    filtered.sort(key=lambda x: x['score']['total'], reverse=True)
    
    return filtered[:10]  # 取前10名
```

---

## 四、Step 3: 深度验证分析

### 4.1 自动搜索催化剂

```python
def analyze_catalysts(stock: Dict, sector: str) -> Dict:
    """
    自动分析标的催化剂
    """
    catalysts = {
        'policy': [],      # 政策催化剂
        'order': [],       # 订单催化剂
        'technology': [],  # 技术突破
        'earnings': [],    # 业绩催化
        'merger': []       # 并购重组
    }
    
    # 搜索各类催化剂
    searches = [
        (f"{stock['name']} 政策 补贴 扶持", 'policy'),
        (f"{stock['name']} 订单 合同 中标", 'order'),
        (f"{stock['name']} 技术突破 专利 新产品", 'technology'),
        (f"{stock['name']} 业绩预告 预增 快报", 'earnings'),
        (f"{stock['name']} 并购 收购 重组", 'merger')
    ]
    
    for query, cat_type in searches:
        news = search_exa(query, count=10)
        catalysts[cat_type].extend(news)
    
    return catalysts
```

### 4.2 自动计算买卖点

```python
def calculate_trade_points(stock: Dict) -> Dict:
    """
    基于技术面自动计算买卖点
    """
    price = stock['current_price']
    
    # 支撑位/阻力位（基于近期高低点）
    support = min(stock['low_5d'], stock['low_20d']) * 0.98
    resistance = max(stock['high_5d'], stock['high_20d']) * 1.02
    
    # 目标价（基于催化剂强度）
    catalyst_strength = stock['score']['catalyst'] / 100
    target = price * (1 + 0.10 + catalyst_strength * 0.10)  # 10-20%涨幅
    
    # 止损位
    stop_loss = support * 0.95
    
    return {
        'current': price,
        'buy_range': (support, price * 1.02),
        'target': target,
        'stop_loss': stop_loss,
        'upside': (target - price) / price * 100
    }
```

---

## 五、Step 4: 生成投资报告

### 5.1 通用报告模板

```python
def generate_sector_report(sector_name: str, keywords: List[str]) -> str:
    """
    自动生成板块投资报告（通用，不硬编码任何标的）
    """
    
    # Step 1: 扫描板块
    stocks = scan_sector_stocks(sector_name, keywords)
    
    # Step 2: 获取行情
    stocks = get_stocks_realtime_data(stocks)
    
    # Step 3: 评分排序
    for stock in stocks:
        stock['score'] = score_stock(stock, keywords)
    
    # Step 4: 筛选标的
    top_stocks = filter_stocks(stocks)
    
    # Step 5: 深度分析
    for stock in top_stocks:
        stock['catalysts'] = analyze_catalysts(stock, sector_name)
        stock['trade_points'] = calculate_trade_points(stock)
    
    # Step 6: 生成报告
    report = format_report(sector_name, top_stocks)
    
    return report
```

### 5.2 报告输出格式

```markdown
# 【板块名称】投资分析报告
> 生成时间: YYYY-MM-DD
> 分析标的: 动态发现 {N} 只，筛选出 {M} 只重点标的

---

## 📊 板块热度
| 指标 | 数值 | 说明 |
|:-----|:-----|:-----|
| 板块内标的数 | {N} | 自动发现 |
| 平均涨幅(5日) | {X}% | 实时计算 |
| 资金净流入 | {Y}亿 | 实时计算 |

---

## 🏆 投资排序（按综合评分）

### 第1名: {标的名称} ({代码})
| 指标 | 数值 |
|:-----|:-----|
| 当前价 | {price}元 |
| 综合评分 | {score}/100 |
| 预期收益 | {upside}% |
| 核心逻辑 | {自动提取的催化剂} |
| 买入区间 | {buy_range} |
| 目标价 | {target} |
| 止损价 | {stop_loss} |

### 第2-5名: ...

---

## 💰 投资组合建议

| 标的 | 仓位 | 逻辑 |
|:-----|:---:|:-----|
| {name1} | 30% | {catalyst1} |
| {name2} | 25% | {catalyst2} |
| ... | ... | ... |
```

---

## 六、使用方法

### 6.1 分析任意板块

```python
# 分析AI电源板块
report = generate_sector_report(
    sector_name="AI电源",
    keywords=["AI电源", "数据中心电源", "服务器电源", "UPS电源"]
)

# 分析液冷板块
report = generate_sector_report(
    sector_name="液冷",
    keywords=["液冷", "数据中心散热", "服务器液冷", "温控"]
)

# 分析任意新板块
report = generate_sector_report(
    sector_name="固态电池",
    keywords=["固态电池", "半固态电池", "电解质", "锂电"]
)
```

---

## 七、关键优势

| 优势 | 说明 |
|:-----|:-----|
| **不硬编码** | 标的自动发现，适应市场变化 |
| **多源数据** | Exa+知识星球+行情数据交叉验证 |
| **动态评分** | 5维评分模型，客观排序 |
| **催化剂自动发现** | 政策/订单/技术/业绩/并购全覆盖 |
| **买卖点自动计算** | 基于技术面和催化剂强度 |

---

## 八、待实现功能

- [ ] 实现 `scan_sector_stocks()` 函数
- [ ] 实现 `score_stock()` 评分模型
- [ ] 实现 `analyze_catalysts()` 催化剂分析
- [ ] 实现 `generate_sector_report()` 报告生成
- [ ] 接入更多数据源（龙虎榜、北向资金等）

---

*方法论版本: v1.0*  
*创建时间: 2026-03-02*  
*核心原则: 零硬编码，全自动发现*
