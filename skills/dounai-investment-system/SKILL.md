

---

# ⚠️ 运行环境要求

## 使用venv虚拟环境运行

本Skill依赖qteasy等库，建议在venv中运行：

```bash
# 1. 激活虚拟环境
source /root/.openclaw/workspace/venv_activate.sh

# 2. 运行Python脚本
python3 your_script.py
```

## 在Python代码中指定解释器

```python
#!/root/.openclaw/workspace/venv/bin/python3
import sys
sys.path.insert(0, '/root/.openclaw/workspace/skills/dounai-investment-system/scripts')

# 你的代码...
```

## 检查Python版本

```bash
# 确保使用venv中的Python
which python3
# 应该输出: /root/.openclaw/workspace/venv/bin/python3
```

---

# ⚠️ 前置检查清单（必须执行！）

## 分析前自检（防止出错）

### 1. 工具版本检查
- [ ] **必须使用** `multi_source_news_v2.py`（优化版）
- [ ] **禁止使用** `comprehensive_stock_analyzer.py`（旧版）
- [ ] **禁止使用** 旧版 `zsxq_fetcher.py`（非优化版）

### 2. 导入检查（复制使用）
```python
import sys
sys.path.insert(0, '/root/.openclaw/workspace/skills/dounai-investment-system/scripts')

# 必须使用优化版
from multi_source_news_v2 import MultiSourceNewsSearcher, ZsxqSearcher

# 初始化
zsxq = ZsxqSearcher()
searcher = MultiSourceNewsSearcher()
```

### 3. 数据源检查
- [ ] 知识星球v2.0（主数据源）- 必须调用
- [ ] **长桥API/Tushare - 必须获取真实股价**
- [ ] Exa全网搜索 - 必须调用  
- [ ] Tushare财务数据 - 必须调用
- [ ] 历史数据（30天）- 必须读取

### 4. 目标价计算规范（重要！）
**⚠️ 严禁瞎编股价！必须按以下步骤：**

```python
# 步骤1: 获取真实股价（必须！）
from longbridge_api import get_longbridge_api
lb = get_longbridge_api()
quote = lb.quote(symbols=["300548.SZ"])
current_price = quote.close  # 真实收盘价

# 步骤2: 获取总股本（必须！）
total_shares = quote.total_shares

# 步骤3: 计算目标价（基于真实数据）
target_price = target_market_cap / total_shares
upside = (target_price - current_price) / current_price * 100
```

**检查点**:
- [ ] 是否获取了真实股价？
- [ ] 是否获取了总股本？
- [ ] 目标价是否基于真实数据计算？
- [ ] 涨跌幅计算是否正确？

### 5. 10模块检查清单
生成报告前必须确认包含：
- [ ] 0️⃣ 投资摘要
- [ ] 1️⃣ 公司基本画像
- [ ] 2️⃣ 业务结构分析
- [ ] 3️⃣ 产业链定位与竞争格局
- [ ] 4️⃣ 订单与产能分析
- [ ] 5️⃣ 财务深度分析
- [ ] 6️⃣ 行业景气度验证
- [ ] 7️⃣ 客户与供应商分析
- [ ] 8️⃣ 业绩预测与估值
- [ ] 9️⃣ 风险提示
- [ ] 🔟 投资建议

### 5. 输出检查
- [ ] 保存为 `analysis_{stock_code}_report.md`
- [ ] 标注"使用知识星球优化版v2.0"
- [ ] 标注数据来源和时效性

---

## 📚 新闻检索标准流程（必须使用！）

### 全面搜索函数

个股分析时必须调用 `search_stock_comprehensive()`，自动执行6类关键词搜索：

```python
from multi_source_news_v2 import search_stock_comprehensive

# 全面搜索（自动执行6轮搜索）
results = search_stock_comprehensive(
    stock_code="300548.SZ",
    stock_name="长芯博创",
    industry="光模块"  # 可选，用于基础业务搜索
)

# 返回结构:
# results['基础'] - 行业/业务信息
# results['资本运作'] - 并购/收购/定增/重组
# results['风险'] - 减持/违规/监管/问询函
# results['业务驱动'] - 订单/合同/产能/技术
# results['业绩'] - 预增/下修/快报
# results['资本市场'] - 研报/评级/调研
```

### 6类关键词搜索清单

| 类别 | 关键词 | 重要性 | 用途 |
|:-----|:-------|:------:|:-----|
| **基础** | 行业关键词 | ⭐⭐⭐⭐⭐ | 业务基本面 |
| **资本运作** | 并购、收购、定增、重组、借壳 | ⭐⭐⭐⭐⭐ | 重大事件（如鸿辉光联） |
| **风险** | 减持、增持、违规、处罚、监管、问询函、关注函、警示函 | ⭐⭐⭐⭐⭐ | 风险排查 |
| **业务驱动** | 订单、合同、中标、产能扩张、技术突破、专利、产品认证、导入 | ⭐⭐⭐⭐⭐ | 业绩驱动 |
| **业绩** | 业绩预增、业绩快报、业绩下修、业绩变脸、扭亏、亏损 | ⭐⭐⭐⭐⭐ | 业绩验证 |
| **资本市场** | 研报、评级、目标价、机构调研、龙虎榜、大宗交易、北向资金 | ⭐⭐⭐⭐ | 市场情绪 |

### Exa搜索修正（重要！）

**已修复**：Exa搜索现在自动拼接"标的+关键词"
```python
# 修正前: Exa只搜"并购 收购"（遗漏鸿辉光联）
# 修正后: Exa搜"长芯博创 并购 收购"（找到鸿辉光联）

exa_keyword = f"{stock_name} {keyword}"  # "长芯博创 并购 收购"
```

---

## 8️⃣ 订单与营收预测模块

**调用**: `predict_revenue_growth(stock_code, current_revenue)`

**功能**:
- 自动抓取巨潮资讯网公告（重大合同/业绩预告等）
- 自动抓取深交所互动易投资者问答
- 从公告自动提取订单金额（亿元/万元）
- 三情景营收增速预测（保守/中性/乐观）
- 基于营收预测净利润（考虑毛利率/费用率）

**预测模型**:

### 营收增速预测
```
营收增速 = 订单增速 × 交付率 × 价格变化

三情景假设:
- 保守: 订单增速 × 0.5, 交付率 60%, 价格下降 5%
- 中性: 订单增速 × 1.0, 交付率 75%, 价格持平
- 乐观: 订单增速 × 1.3, 交付率 90%, 价格上涨 5%
```

### 净利润预测
```
净利润 = 营收 × 毛利率 - 费用 - 所得税
       = 营收 × (毛利率 - 费用率) × (1 - 税率)

默认假设:
- 毛利率: 35% (光模块行业)
- 费用率: 25%
- 所得税率: 15%
```

**数据源**:
| 来源 | 类型 | 覆盖内容 |
|:-----|:-----|:---------|
| 巨潮资讯网 | 官方公告 | 重大合同/业绩预告/增减持 |
| 互动易 | 投资者问答 | 订单细节/客户导入/产能 |
| 手动输入 | 补充数据 | 最新订单/非公告订单 |

**示例**:
```python
# 预测长芯博创营收和净利润
predictor = OrderRevenuePredictor()
result = predictor.analyze_stock(
    stock_code="300548.SZ",
    stock_name="长芯博创",
    current_revenue=35.0  # 当前营收35亿
)

# 输出:
# 📊 营收预测结果:
#   保守: 订单增速12.5% → 营收22.44亿
#   中性: 订单增速25.0% → 营收32.81亿
#   乐观: 订单增速32.5% → 营收43.82亿
#
# 📊 净利润预测（中性）:
#   营收: 32.81亿元
#   净利润: 2.79亿元
#   净利率: 8.5%
```

**集成场景**:
- 个股深度分析: 预测未来2-3年营收/净利润
- 投资决策: 基于预测估值（Forward PE）
- 建仓建议: 结合预测增速给出买卖建议

---

## 📚 知识星球数据集成（重要！）

### 多源新闻搜索 v2.0（优化版）

**文件**: `skills/dounai-investment-system/scripts/multi_source_news_v2.py`

**功能升级**:
1. ✅ **知识星球关键词搜索** - 支持API keyword参数
2. ✅ **频率控制** - 3秒间隔，限流自动退避
3. ✅ **多关键词组合** - 股票名称+行业关键词
4. ✅ **产业链搜索** - 上下游分别搜索

**使用方法**:

```python
# 方法1: 个股搜索（推荐）
from multi_source_news_v2 import search_multi_source_news

news = search_multi_source_news(
    keyword="光模块", 
    stock_code="300502.SZ", 
    stock_name="新易盛"
)

# 方法2: 产业链搜索
from multi_source_news_v2 import search_industry_chain_news

news = search_industry_chain_news(
    industry="半导体",
    upstream="硅片 光刻胶",
    downstream="芯片设计 封测"
)
```

### 历史数据调用（最近一个月）

**使用场景**: 个股分析、景气度分析需要历史数据支撑

```python
from pathlib import Path
import json
from datetime import datetime, timedelta

def get_recent_zsxq_data(days=30):
    '''获取最近N天知识星球数据'''
    raw_dir = Path('/root/.openclaw/workspace/data/zsxq/raw')
    all_data = []
    
    for i in range(days):
        date = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
        file_path = raw_dir / f"{date}.json"
        if file_path.exists():
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                all_data.extend(data)
    
    return all_data

# 搜索特定股票在知识星球中的提及
def search_stock_in_zsxq_history(stock_name, days=30):
    '''在历史数据中搜索股票'''
    data = get_recent_zsxq_data(days)
    results = []
    
    for topic in data:
        content = topic.get('content', '') + topic.get('title', '')
        if stock_name in content:
            results.append({
                'date': topic.get('date'),
                'title': topic.get('title'),
                'content': topic.get('content')[:200],
                'author': topic.get('author')
            })
    
    return results

# 示例：搜索"中际旭创"最近30天的研报
results = search_stock_in_zsxq_history("中际旭创", days=30)
print(f"最近30天提及 {len(results)} 次")
```

### 数据源优先级（更新）

| 优先级 | 数据源 | 用途 | 调用方式 |
|:---:|:---|:---|:---|
| P1 | Exa全网搜索 | 最新新闻、公告 | `multi_source_news_v2` |
| **P2** | **知识星球** | **产业调研、专家观点** | **`multi_source_news_v2`** |
| P3 | 新浪财经 | 财经新闻 | `multi_source_news_v2` |
| P4 | 长桥API | 行情数据 | 直接调用 |
| P5 | Tushare | 财务数据 | 直接调用 |

**重要**: 知识星球搜索必须使用优化版 `multi_source_news_v2.py`，旧版 `multi_source_news.py` 已废弃。

---

## 9️⃣ 投资建议框架

### 估值评估体系

| 估值指标 | 合理区间 | 评价标准 | 操作建议 |
|:---------|:---------|:---------|:---------|
| PE_TTM | 40-80倍 | <40:低估, 40-80:合理, >80:高估 | 低估买入, 高估观望 |
| PB | 3-8倍 | <3:低估, 3-8:合理, >8:高估 | 结合ROE判断 |
| Forward PE | 30-50倍 | <30:低估, 30-50:合理, >50:高估 | 预测未来1年利润 |
| PEG | <1 | <1:低估, 1-2:合理, >2:高估 | PE/盈利增速 |

### 综合评分体系

| 维度 | 权重 | 评分标准 |
|:-----|:-----|:---------|
| 行业景气度 | 20% | ⭐⭐⭐⭐⭐ 极高, ⭐⭐⭐⭐ 高, ⭐⭐⭐ 中, ⭐⭐ 低 |
| 盈利能力 | 25% | ROE>15%:⭐⭐⭐⭐⭐, 10-15%:⭐⭐⭐⭐, 5-10%:⭐⭐⭐ |
| 成长性 | 20% | 营收增速>50%:⭐⭐⭐⭐⭐, 30-50%:⭐⭐⭐⭐, 10-30%:⭐⭐⭐ |
| 估值水平 | 20% | PE<40:⭐⭐⭐⭐⭐, 40-80:⭐⭐⭐⭐, 80-150:⭐⭐⭐, >150:⭐⭐ |
| 财务健康 | 15% | 负债率低+现金充裕:⭐⭐⭐⭐⭐ |

**综合评分**: 4.0+ (强烈建议), 3.0-4.0 (建议), 2.0-3.0 (观望), <2.0 (回避)

### 操作建议矩阵

| 估值水平 | 盈利能力强 | 盈利一般 | 盈利弱 |
|:---------|:-----------|:---------|:-------|
| **低估(PE<40)** | 🟢🟢🟢 强烈买入 | 🟢🟢 买入 | 🟢 谨慎买入 |
| **合理(PE40-80)** | 🟢 买入 | 🟡 观望 | 🔴 回避 |
| **高估(PE80-150)** | 🟡 观望 | 🔴 回避 | 🔴🔴 强烈回避 |
| **极高(PE>150)** | 🔴 回避 | 🔴🔴 强烈回避 | 🔴🔴🔴 极度危险 |

### 关键跟踪指标

**必须跟踪**:
- 季度订单公告/重大合同
- 季度业绩快报/预告
- 月度产能利用率
- 核心客户导入进度

**建议跟踪**:
- 行业出货量数据
- 竞争对手动态
- 上游原材料价格
- 下游需求变化

---

## 🔟 数据验证与交叉检验

### 单一数据源不可靠

**必须多方验证**:
| 数据类型 | 主要来源 | 验证来源 | 交叉检验方法 |
|:---------|:---------|:---------|:-------------|
| 订单数据 | 公司公告 | 互动易问答+券商研报 | 公告金额vs调研细节 |
| 营收预测 | 券商模型 | 产业链数据+产能 | 券商预测vs产能上限 |
| 净利润 | 财报 | 杜邦分析+现金流 | 利润vs经营现金流 |
| 估值 | Tushare | 多数据源对比 | PE_TTM vs Forward PE |

### 异常数据识别

| 异常信号 | 可能原因 | 处理方法 |
|:---------|:---------|:---------|
| 净利润与经营现金流背离 | 应收账款增加/利润调节 | 重点关注现金流 |
| 订单增长但营收不增长 | 交付延迟/收入确认问题 | 检查交付进度 |
| PE异常高(>500) | 微利/亏损或数据错误 | 核实PE计算方式 |
| 毛利率突然变化 | 产品结构变化/成本波动 | 查看产品结构 |

---

## 更新日志

| 日期 | 更新内容 |
|:-----|:---------|
| 2026-03-01 | 新增订单与营收预测模块（order_revenue_predictor.py） |
| 2026-03-01 | 新增投资建议框架和估值评估体系 |
| 2026-03-01 | 新增数据验证与交叉检验方法论 |
| 2026-02-28 | 新增完整财务分析模块（financial_analyzer.py） |
| 2026-02-28 | 修复财务数据缺失同比环比的问题 |
| 2026-02-28 | 自动杜邦分析和风险警示生成 |
| 2026-02-28 | 新增`analyze_stock()`个股分析方法 |
| 2026-02-28 | 更新数据源优先级：Exa搜索 > 知识星球 > 长桥API |
| 2026-02-28 | 集成Agent Reach新闻搜索功能 |
| 2026-02-25 | 集成longport SDK，统一API调用 |
| 2026-02-25 | 添加知识星球自动获取 |
| 2026-02-25 | 完善产业链分析模块 |
