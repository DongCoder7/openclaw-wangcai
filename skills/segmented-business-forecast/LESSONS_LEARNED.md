# 业务线拆分估值分析器 - 疏忽总结与优化

## 本次分析中的疏忽（兆易创新案例）

### 疏忽1：时间错位（最严重）
**问题**：现在是2026年，但我查了2025Q1数据（19.09亿），而不是2026Q1（41.88亿）
**后果**：基期数据完全错误，后续所有计算都错
**根因**：没确认当前年份，默认Tushare返回最新数据就是当前年份

### 疏忽2：编造数据
**问题**：没查财报就拍脑袋编了"19亿"作为基期
**后果**：所有预测建立在假数据上
**根因**：偷懒，没调用API验证

### 疏忽3：财报查询方法单一
**问题**：只试了Tushare，失败后就放弃，没试efinance/akshare
**后果**：错过2026年真实数据（efinance/akshare有2026数据）
**根因**：没系统检查所有可用数据源

### 疏忽4：假设出货量不变
**问题**：没仔细看纪要里的出货量数据，直接假设0%
**后果**：Q2预测偏低（+33% vs 实际+39%）
**根因**：只看"涨价"关键词，忽略"投片2万片"、"产能温和提升"等出货量信息

### 疏忽5：产品拆分错误
**问题**：用fina_mainbz的"存储芯片"、"微控制器"大类，而不是纪要里的NOR/DR-AM/SLC/MCU
**后果**：搜索到的ASP变化（-7%）和调研数据（+30%）完全相反
**根因**：fina_mainbz粒度太粗，无法匹配调研纪要中的细分产品

### 疏忽6：数据验证缺失
**问题**：用户说"Q1营收44.16亿，净利润14.6亿"时，我没第一时间验证
**后果**：错误持续了两轮对话才修正
**根因**：用户给的数据和Tushare不一致时，没主动排查原因

---

## 优化后的强制检查清单

### 步骤1：确认时间（必须！）
```
□ 当前年份：2026年
□ 分析对象年份：2026年（确认！）
□ 财报期：2026Q1（不是2025Q1！）
□ 报告期：2026年中报（不是2025年报！）
```

### 步骤2：获取真实财报（多数据源）
```
□ Tushare（首选，但数据滞后）
□ efinance（备用，可能有更新数据）
□ akshare（备用，Sina数据源）
□ longbridge（实时数据，但需Token）
□ 如果所有API失败，明确说明"数据未获取"，不编造！
```

### 步骤3：验证数据一致性
```
□ 营收和净利润是否合理？（净利率通常10-40%）
□ 用户给的数据和API数据是否一致？
□ 如果不一致，排查原因（年份？口径？）
□ 确认后才能进入下一步
```

### 步骤4：提取出货量数据（必须从纪要/公告中找）
```
□ 纪要中是否有"投片"、"产能"、"出货量"、"产量"等关键词？
□ 是否有库存变化（清库存/补库存）？
□ 是否有市占率变化？
□ 如果没有明确数据，标注"未找到出货量数据，使用默认值X%"，不能假设0%！
```

### 步骤5：产品拆分粒度匹配
```
□ 财报fina_mainbz的拆分粒度（大类）vs 调研纪要粒度（细分产品）
□ 如果粒度不匹配，优先用调研纪要的细分数据
□ 搜索时必须按细分产品搜（"800G光模块"而不是"光模块"）
```

### 步骤6：计算验证
```
□ 营收 = 出货量 × 价格 × (1+出货增长) × (1+价格变化)
□ 毛利率提升 = 涨价率 × (1-原毛利率)（如果成本不变）
□ 净利润 = 毛利 - 费用（费用率是否变化？）
□ 反向验证：预测营收 / 基期营收 = 各产品变化的加权平均
```

---

## 优化后的代码架构

```python
class UserDataDrivenForecaster:
    """
    用户调研数据驱动估值（推荐，比搜索更准）
    
    输入：
    1. 真实财报基期数据（多数据源验证）
    2. 调研纪要中的产品拆分、出货量、价格变化
    
    输出：
    1. 分产品预测
    2. 汇总预测
    3. 敏感性分析
    """
    
    def __init__(self, stock_code, stock_name, year):
        self.year = year  # 必须确认年份！
        self.stock_code = stock_code
        self.stock_name = stock_name
        self.products = []
    
    def fetch_financial_data(self):
        """多数据源获取财报（强制验证）"""
        sources = ['tushare', 'efinance', 'akshare']
        for source in sources:
            try:
                data = self._fetch_from(source)
                if self._validate_data(data):
                    return data
            except:
                continue
        raise ValueError("无法获取财报数据，所有数据源失败")
    
    def add_product(self, name, revenue_base, margin, 
                     volume_growth, price_change, 
                     evidence=""):
        """
        添加产品，必须提供数据来源证据
        
        Args:
            volume_growth: 出货量增长（必须有来源！）
            price_change: 价格变化（必须有来源！）
            evidence: 数据来源（纪要第X页/公告第X条）
        """
        self.products.append({
            'name': name,
            'revenue_base': revenue_base,
            'margin': margin,
            'volume_growth': volume_growth,  # 必须有来源
            'price_change': price_change,      # 必须有来源
            'evidence': evidence               # 必须记录
        })
    
    def forecast(self):
        """预测，展示完整计算过程"""
        results = []
        for p in self.products:
            # 营收 = 基期 × (1+出货量) × (1+价格)
            revenue = p['revenue_base'] * (1 + p['volume_growth']) * (1 + p['price_change'])
            
            # 毛利率（成本不变时提升）
            margin_new = p['margin'] + p['price_change'] * (1 - p['margin'])
            
            # 利润
            profit = revenue * margin_new
            
            results.append({
                'name': p['name'],
                'revenue': revenue,
                'profit': profit,
                'margin': margin_new,
                'evidence': p['evidence']
            })
        
        return results
```

---

## 核心教训

1. **时间第一**：必须确认年份，2026年不能查2025年数据
2. **数据真实**：多数据源验证，不能编造
3. **出货量必须查**：不能假设0%，必须从纪要/公告中提取
4. **产品粒度匹配**：fina_mainbz太粗，调研纪要更细，优先用细的
5. **验证闭环**：每一步计算完都要反向验证是否合理

---

*更新时间：2026-07-07*
*适用场景：用户调研数据驱动估值分析*